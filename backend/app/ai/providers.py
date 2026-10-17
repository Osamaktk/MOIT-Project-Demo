from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class ChatResult:
    content: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    tool_calls: list[dict[str, Any]] | None = None


class AIProvider(Protocol):
    zone: str

    async def chat(self, *, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, response_format: dict[str, Any] | None = None, stream: bool = False) -> ChatResult: ...

    async def embed(self, *, model: str, texts: list[str]) -> list[list[float]]: ...


class OpenAICompatibleProvider:
    def __init__(self, *, base_url: str, api_key: str, zone: str, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.zone = zone
        self.settings = settings
        self.transport = transport

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last_error: Exception | None = None
        for attempt in range(self.settings.ai_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.ai_request_timeout_seconds, transport=self.transport) as client:
                    response = await client.post(f"{self.base_url}/{path.lstrip('/')}", headers=headers, json=payload)
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError("Provider returned a non-object response")
                return result
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code == 429 or exc.response.status_code >= 500
                if attempt >= self.settings.ai_max_retries or not retryable:
                    raise
                await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
        assert last_error is not None
        raise last_error

    async def chat(self, *, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, response_format: dict[str, Any] | None = None, stream: bool = False) -> ChatResult:
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
        if tools is not None:
            payload["tools"] = tools
        if response_format is not None:
            payload["response_format"] = response_format
            payload["temperature"] = 0
        if stream:
            return await self._stream_chat(payload, model)
        result = await self._post("chat/completions", payload)
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Provider response did not include a completion")
        message = choices[0].get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
        usage = result.get("usage") or {}
        return ChatResult(str(content), str(result.get("model") or model), usage.get("prompt_tokens"), usage.get("completion_tokens"), tool_calls if isinstance(tool_calls, list) else None)

    async def _stream_chat(self, payload: dict[str, Any], model: str) -> ChatResult:
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        content: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}
        input_tokens: int | None = None
        output_tokens: int | None = None
        response_model = model
        last_error: Exception | None = None
        for attempt in range(self.settings.ai_max_retries + 1):
            content.clear()
            tool_calls.clear()
            input_tokens = output_tokens = None
            try:
                async with httpx.AsyncClient(timeout=self.settings.ai_request_timeout_seconds, transport=self.transport) as client:
                    async with client.stream("POST", f"{self.base_url}/chat/completions", headers=headers, json=payload) as response:
                        if response.status_code == 429 or response.status_code >= 500:
                            await response.aread()
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                break
                            chunk = json.loads(data)
                            if not isinstance(chunk, dict):
                                continue
                            response_model = str(chunk.get("model") or response_model)
                            usage = chunk.get("usage")
                            if isinstance(usage, dict):
                                input_tokens = usage.get("prompt_tokens", input_tokens)
                                output_tokens = usage.get("completion_tokens", output_tokens)
                            choices = chunk.get("choices")
                            if not isinstance(choices, list) or not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            if not isinstance(delta, dict):
                                continue
                            text = delta.get("content")
                            if isinstance(text, str):
                                content.append(text)
                            deltas = delta.get("tool_calls")
                            if isinstance(deltas, list):
                                for item in deltas:
                                    if not isinstance(item, dict):
                                        continue
                                    index = item.get("index")
                                    if not isinstance(index, int):
                                        continue
                                    call = tool_calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                                    if item.get("id"):
                                        call["id"] = item["id"]
                                    if item.get("type"):
                                        call["type"] = item["type"]
                                    function = item.get("function")
                                    if isinstance(function, dict):
                                        if function.get("name"):
                                            call["function"]["name"] = function["name"]
                                        if isinstance(function.get("arguments"), str):
                                            call["function"]["arguments"] += function["arguments"]
                return ChatResult("".join(content), response_model, input_tokens, output_tokens, [tool_calls[key] for key in sorted(tool_calls)] or None)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code == 429 or exc.response.status_code >= 500
                if attempt >= self.settings.ai_max_retries or not retryable:
                    raise
                await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
        assert last_error is not None
        raise last_error

    async def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        result = await self._post("embeddings", {"model": model, "input": texts})
        data = result.get("data")
        if not isinstance(data, list):
            raise ValueError("Provider response did not include embeddings")
        return [item["embedding"] for item in data]


class OpenRouterProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings):
        super().__init__(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key.get_secret_value(), zone="cloud", settings=settings)


class LocalProvider(OpenAICompatibleProvider):
    """OpenAI-compatible local model endpoint; the URL and models come from config."""

    def __init__(self, settings: Settings):
        super().__init__(base_url=settings.local_llm_base_url, api_key="", zone="local", settings=settings)
