import asyncio

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai.gateway import AIGateway, PolicyViolation, ToolSuspended
from app.ai.providers import ChatResult, OpenAICompatibleProvider
from app.core.config import Settings
from app.db.base import Base
from app.db.models import AIRun, ToolSwitch, User


class MockProvider:
    zone = "cloud"

    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or ["synthetic response"])
        self.calls = 0
        self.request_options: list[dict[str, object]] = []

    async def chat(self, **options: object) -> ChatResult:
        self.request_options.append(options)
        self.calls += 1
        return ChatResult(self.responses.pop(0), "catalogue/model", 8, 3)

    async def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class FlakyProvider(MockProvider):
    def __init__(self):
        super().__init__()
        self.models: list[str] = []

    async def chat(self, *, model: str, **_: object) -> ChatResult:
        self.models.append(model)
        if len(self.models) == 1:
            raise RuntimeError("primary unavailable")
        return ChatResult("fallback response", model, 2, 1)


@pytest.fixture
def ai_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        person = User(name="Synthetic Reviewer", email="reviewer@ai.test", password_hash="x", role="cos", designation="Reviewer")
        db.add(person)
        db.flush()
        db.add(ToolSwitch(tool="jarvis", suspended=False))
        db.commit()
        yield db, person
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_gateway_success_persists_metadata_without_prompt_text(ai_db) -> None:
    db, person = ai_db
    provider = MockProvider()
    gateway = AIGateway(Settings(model_chat="catalogue/model"), provider=provider)
    response = asyncio.run(gateway.chat(db, tool="jarvis", role="chat", messages=[{"role": "user", "content": "private synthetic text"}], user_id=person.id, prompt_version="jarvis-v1", is_synthetic=True))
    run = db.scalar(select(AIRun))
    assert response == "synthetic response"
    assert run is not None and run.outcome == "success"
    assert run.model == "catalogue/model" and run.input_tokens == 8 and run.output_tokens == 3
    assert run.prompt_metadata == {"message_count": 1}
    assert "private synthetic text" not in str(run.prompt_metadata)


def test_confidential_cloud_call_fails_closed_and_is_logged(ai_db) -> None:
    db, person = ai_db
    provider = MockProvider()
    gateway = AIGateway(Settings(model_chat="catalogue/model", allow_cloud_for_synthetic_demo=False), provider=provider)
    with pytest.raises(PolicyViolation):
        asyncio.run(gateway.chat(db, tool="jarvis", role="chat", messages=[], classification="confidential", user_id=person.id))
    run = db.scalar(select(AIRun))
    assert provider.calls == 0
    assert run is not None and run.outcome == "blocked" and run.error_code == "policy_violation"


def test_suspended_tool_fails_closed_and_attempt_is_logged(ai_db) -> None:
    db, person = ai_db
    db.get(ToolSwitch, "jarvis").suspended = True
    db.commit()
    provider = MockProvider()
    gateway = AIGateway(Settings(model_chat="catalogue/model"), provider=provider)
    with pytest.raises(ToolSuspended):
        asyncio.run(gateway.chat(db, tool="jarvis", role="chat", messages=[], user_id=person.id))
    run = db.scalar(select(AIRun))
    assert provider.calls == 0
    assert run is not None and run.outcome == "blocked" and run.error_code == "tool_suspended"


def test_synthetic_confidential_cloud_exception_is_explicit(ai_db) -> None:
    db, person = ai_db
    provider = MockProvider()
    gateway = AIGateway(Settings(model_chat="catalogue/model", allow_cloud_for_synthetic_demo=True), provider=provider)
    response = asyncio.run(gateway.chat(db, tool="jarvis", role="chat", messages=[], classification="confidential", is_synthetic=True, user_id=person.id))
    run = db.scalar(select(AIRun))
    assert response == "synthetic response"
    assert provider.calls == 1
    assert run is not None and run.outcome == "success" and run.is_synthetic is True


def test_document_level_admin_permission_allows_confidential_extraction(ai_db) -> None:
    db, person = ai_db
    db.add(ToolSwitch(tool="document_extraction", suspended=False))
    db.commit()
    provider = MockProvider()
    gateway = AIGateway(Settings(model_extraction="catalogue/extract", allow_cloud_for_synthetic_demo=False), provider=provider)
    response = asyncio.run(gateway.chat(db, tool="document_extraction", role="extraction", messages=[], classification="confidential", user_id=person.id, allow_confidential_cloud=True))
    assert response == "synthetic response"
    run = db.scalar(select(AIRun).where(AIRun.tool == "document_extraction"))
    assert provider.calls == 1
    assert run is not None and run.outcome == "success" and run.classification == "confidential"


def test_zone_mode_selects_provider_without_code_changes() -> None:
    cloud = AIGateway(Settings(ai_zone_mode="cloud"))
    local = AIGateway(Settings(ai_zone_mode="cloud", ai_provider_chat="local"))
    assert cloud._provider("chat").zone == "cloud"
    assert local._provider("chat").zone == "local"


def test_configured_fallback_model_is_used_after_primary_failure(ai_db) -> None:
    db, person = ai_db
    provider = FlakyProvider()
    gateway = AIGateway(Settings(model_chat="primary/model", model_chat_fallback="fallback/model"), provider=provider)
    response = asyncio.run(gateway.chat(db, tool="jarvis", role="chat", messages=[], user_id=person.id))
    assert response == "fallback response"
    assert provider.models == ["primary/model", "fallback/model"]


class StructuredResult(BaseModel):
    label: str


def test_invalid_structured_response_is_repaired_once(ai_db) -> None:
    db, person = ai_db
    provider = MockProvider(["not-json", '{"label":"repaired"}'])
    gateway = AIGateway(Settings(model_extraction="catalogue/extract"), provider=provider)
    result = asyncio.run(gateway.chat(db, tool="jarvis", role="extraction", messages=[], response_schema=StructuredResult, user_id=person.id))
    run = db.scalar(select(AIRun))
    assert isinstance(result, StructuredResult) and result.label == "repaired"
    assert provider.calls == 2 and run is not None and run.outcome == "success"
    assert provider.request_options[0]["response_format"] == {"type": "json_schema", "json_schema": {"name": "StructuredResult", "strict": False, "schema": StructuredResult.model_json_schema()}}


def test_openai_compatible_provider_collects_streamed_text_and_tool_calls() -> None:
    import json

    import httpx

    chunks = [
        {"model": "catalogue/model", "choices": [{"delta": {"content": "I found "}}]},
        {"model": "catalogue/model", "choices": [{"delta": {"content": "the record."}}]},
        {"model": "catalogue/model", "choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "get_transaction", "arguments": "{\"code\":"}}]}}]},
        {"model": "catalogue/model", "choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "\"TX-A\"}"}}]}}]},
        {"model": "catalogue/model", "choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 4}},
    ]

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        body_json = json.loads(request.content)
        assert body_json["stream"] is True and body_json["temperature"] == 0
        body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)

    provider = OpenAICompatibleProvider(base_url="https://provider.test/v1", api_key="", zone="cloud", settings=Settings(), transport=httpx.MockTransport(respond))
    result = asyncio.run(provider.chat(model="catalogue/model", messages=[], tools=[{"type": "function"}], response_format={"type": "json_object"}, stream=True))

    assert result.content == "I found the record."
    assert result.model == "catalogue/model"
    assert result.input_tokens == 12 and result.output_tokens == 4
    assert result.tool_calls == [{"id": "call_1", "type": "function", "function": {"name": "get_transaction", "arguments": '{"code":"TX-A"}'}}]
