from __future__ import annotations

import json
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.ai.providers import AIProvider, LocalProvider, OpenRouterProvider
from app.core.config import Settings, settings
from app.db.models import AIRun, ToolSwitch

T = TypeVar("T", bound=BaseModel)


class PolicyViolation(RuntimeError):
    code = "policy_violation"


class ToolSuspended(RuntimeError):
    code = "tool_suspended"


class AIConfigurationError(RuntimeError):
    code = "ai_not_configured"


class AIGateway:
    def __init__(self, config: Settings = settings, provider: AIProvider | None = None, providers: dict[str, AIProvider] | None = None):
        self.config = config
        self.provider_override = provider
        self.providers = providers or {"cloud": OpenRouterProvider(config), "local": LocalProvider(config)}

    def _provider(self, role: str) -> AIProvider:
        if self.provider_override is not None:
            return self.provider_override
        configured = getattr(self.config, f"ai_provider_{role}", "").strip().lower()
        zone = configured or self.config.ai_zone_mode
        if zone not in self.providers:
            raise AIConfigurationError(f"Unknown provider zone '{zone}' for {role}.")
        return self.providers[zone]

    def _model(self, role: str, *, fallback: bool = False) -> str:
        if role not in {"chat", "reasoning", "extraction", "fast", "embedding"}:
            raise ValueError("Unknown AI model role")
        if fallback:
            configured = getattr(self.config, f"model_{role}_fallback", "")
            return configured or self.config.model_fallback
        configured = getattr(self.config, f"model_{role}", "")
        if role == "embedding" and not configured:
            configured = self.config.model_embedding
        return configured

    def _start_run(self, db: Session, *, tool: str, role: str, model: str, zone: str, classification: str, is_synthetic: bool, user_id: str | None, prompt_version: str, messages: list[dict[str, Any]]) -> AIRun:
        run = AIRun(tool=tool, model_role=role, model=model or "unconfigured", zone=zone, classification=classification, is_synthetic=is_synthetic, user_id=user_id, outcome="running", prompt_version=prompt_version, prompt_metadata={"message_count": len(messages)},)
        if self.config.log_prompts:
            run.prompt_metadata = {"messages": messages}
        db.add(run)
        db.commit()
        return run

    def record_blocked_attempt(self, db: Session, *, tool: str, role: str, classification: str, is_synthetic: bool, user_id: str, prompt_version: str, error_code: str) -> AIRun:
        provider = self._provider(role)
        run = self._start_run(db, tool=tool, role=role, model=self._model(role) or self._model(role, fallback=True), zone=provider.zone, classification=classification, is_synthetic=is_synthetic, user_id=user_id, prompt_version=prompt_version, messages=[])
        run.outcome = "blocked"
        run.error_code = error_code
        db.commit()
        return run

    async def chat(self, db: Session, *, tool: str, role: str, messages: list[dict[str, Any]], classification: str = "internal", is_synthetic: bool = False, user_id: str | None = None, prompt_version: str = "unversioned", tools: list[dict[str, Any]] | None = None, response_schema: type[T] | None = None, run_id_out: dict[str, str] | None = None, stream: bool = False) -> str | T:
        if classification not in {"public", "internal", "confidential"}:
            raise ValueError("Unknown data classification")
        provider = self._provider(role)
        model = self._model(role) or self._model(role, fallback=True)
        run = self._start_run(db, tool=tool, role=role, model=model, zone=provider.zone, classification=classification, is_synthetic=is_synthetic, user_id=user_id, prompt_version=prompt_version, messages=messages)
        if run_id_out is not None:
            run_id_out["run_id"] = run.id
        started = time.perf_counter()
        try:
            switch = db.get(ToolSwitch, tool)
            if switch is None or switch.suspended:
                raise ToolSuspended(f"{tool} is suspended. Contact an assurance administrator.")
            if provider.zone == "cloud" and classification == "confidential" and not (is_synthetic and self.config.allow_cloud_for_synthetic_demo):
                raise PolicyViolation("Confidential data is blocked from cloud AI providers.")
            if not model:
                raise AIConfigurationError(f"No model is configured for the {role} role.")
            structured = response_schema is not None
            schema_instruction = None
            if response_schema is not None:
                schema_json = json.dumps(response_schema.model_json_schema(), ensure_ascii=False)
                schema_instruction = f"Return one JSON object that strictly conforms to this JSON Schema. Do not add fields or prose:\n{schema_json}"
                request_messages = [{"role": "system", "content": schema_instruction}, *messages]
            else:
                request_messages = messages
            last_error: Exception | None = None
            attempt = 0
            used_fallback = model == self._model(role, fallback=True)
            while attempt < (2 if structured else 1):
                try:
                    response_format = {"type": "json_schema", "json_schema": {"name": response_schema.__name__, "strict": False, "schema": response_schema.model_json_schema()}} if response_schema is not None else None
                    result = await provider.chat(model=model, messages=request_messages, tools=tools, response_format=response_format, stream=stream)
                    run.model = result.model
                    run.input_tokens = (run.input_tokens or 0) + (result.input_tokens or 0)
                    run.output_tokens = (run.output_tokens or 0) + (result.output_tokens or 0)
                    if response_schema is None:
                        output: str | T = result.content
                    else:
                        try:
                            output = response_schema.model_validate_json(result.content)
                        except (ValidationError, ValueError) as exc:
                            if attempt:
                                raise ValueError("Provider returned invalid structured output after one repair attempt") from exc
                            request_messages = [{"role": "system", "content": schema_instruction or "Return one valid JSON object."}, *messages, {"role": "assistant", "content": result.content}, {"role": "user", "content": "Repair the previous response. Return only valid JSON that strictly conforms to the JSON Schema."}]
                            last_error = exc
                            attempt += 1
                            continue
                    run.outcome = "success"
                    return output
                except Exception as exc:
                    last_error = exc
                    fallback_model = self._model(role, fallback=True)
                    if not used_fallback and fallback_model and fallback_model != model:
                        model = fallback_model
                        run.model = model
                        used_fallback = True
                        continue
                    raise
            if last_error:
                raise last_error
            raise RuntimeError("AI provider failed without a result")
        except Exception as exc:
            run.outcome = "blocked" if isinstance(exc, (PolicyViolation, ToolSuspended)) else "error"
            run.error_code = getattr(exc, "code", "provider_error")
            raise
        finally:
            run.latency_ms = int((time.perf_counter() - started) * 1000)
            db.add(run)
            db.commit()

    async def embed(self, db: Session, *, tool: str, texts: list[str], classification: str = "internal", is_synthetic: bool = False, user_id: str | None = None, prompt_version: str = "embedding-v1") -> list[list[float]]:
        provider = self._provider("embedding")
        model = self._model("embedding")
        run = self._start_run(db, tool=tool, role="embedding", model=model, zone=provider.zone, classification=classification, is_synthetic=is_synthetic, user_id=user_id, prompt_version=prompt_version, messages=[])
        started = time.perf_counter()
        try:
            if classification not in {"public", "internal", "confidential"}:
                raise ValueError("Unknown data classification")
            switch = db.get(ToolSwitch, tool)
            if switch is None or switch.suspended:
                raise ToolSuspended(f"{tool} is suspended. Contact an assurance administrator.")
            if provider.zone == "cloud" and classification == "confidential" and not (is_synthetic and self.config.allow_cloud_for_synthetic_demo):
                raise PolicyViolation("Confidential data is blocked from cloud AI providers.")
            if not model:
                raise AIConfigurationError("No embedding model is configured.")
            vectors = await provider.embed(model=model, texts=texts)
            run.outcome = "success"
            return vectors
        except Exception as exc:
            run.outcome = "blocked" if isinstance(exc, (PolicyViolation, ToolSuspended)) else "error"
            run.error_code = getattr(exc, "code", "provider_error")
            raise
        finally:
            run.latency_ms = int((time.perf_counter() - started) * 1000)
            db.add(run)
            db.commit()
