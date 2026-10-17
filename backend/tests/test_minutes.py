import json
from collections.abc import Generator
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.gateway import AIGateway
from app.ai.providers import ChatResult
from app.ai.stt import STTProvider
from app.api.v1.meetings import get_ai_gateway, get_stt_provider
from app.api.v1.jarvis import get_stt_provider as get_jarvis_stt_provider
from app.core.config import Settings, settings
from app.core.deps import get_db
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import AIRun, AuditEvent, ComplianceItem, Meeting, MeetingAction, MinutesDraft, RegisterEntry, RegisterSerialCounter, ToolSwitch, Transaction, Transcript, User
from app.main import app

TEST_PASSWORD = "Demo-Only-Change-Me-2026!"
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class SampleProvider:
    zone = "local"

    def __init__(self):
        self.calls = 0

    async def chat(self, **_: object) -> ChatResult:
        self.calls += 1
        result = {
            "body_markdown": "# Transaction review\n\nThe group reviewed TX-A and agreed on two follow-up actions. The review pack and milestone will be confirmed by the named officers.",
            "actions": [
                {"description": "Send the updated review pack to the Chief of Staff.", "officer_hint": "director_td", "deadline_hint": "October 21, 2026", "deadline_date": "2026-10-21", "priority_suggestion": "B", "transaction_hint": "TX-A", "quote": "The Director will send the updated review pack to the Chief of Staff by October twenty first, twenty twenty six.", "transcript_start": 5.18, "transcript_end": 12.81, "confidence": 0.96},
                {"description": "Confirm the next milestone for TX-A.", "officer_hint": "liaison", "deadline_hint": "October 23, 2026", "deadline_date": "2026-10-23", "priority_suggestion": "B", "transaction_hint": "TX-A", "quote": "The Chief of Staff asks the Liaison to confirm the next milestone for TX-A by October twenty third, twenty twenty six.", "transcript_start": 12.81, "transcript_end": 21.27, "confidence": 0.93},
            ],
        }
        return ChatResult(json.dumps(result), "synthetic/minutes-model", 180, 120)

    async def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


class SampleSTT:
    name = "synthetic-test-stt"

    def __init__(self):
        self.called = False

    def transcribe(self, audio_path: str, language_hint: str | None = None):
        self.called = True
        return "en", [
            {"start": 0.0, "end": 4.0, "text": "This is the transaction review meeting. We are discussing TX-A.", "lang": "en", "speaker": None},
            {"start": 4.0, "end": 12.0, "text": "The Director will send the updated review pack to the Chief of Staff by October twenty first, twenty twenty six.", "lang": "en", "speaker": None},
            {"start": 12.0, "end": 21.0, "text": "The Chief of Staff asks the Liaison to confirm the next milestone for TX-A by October twenty third, twenty twenty six.", "lang": "en", "speaker": None},
        ]


@pytest.fixture
def minutes_client(tmp_path, monkeypatch) -> Generator[tuple[TestClient, sessionmaker[Session], SampleProvider, SampleSTT], None, None]:
    engine.dispose()
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "demo_mode_cache", False)
    with TestSessions() as db:
        cos = User(name="Synthetic CoS", email="cos@demo.example", password_hash=hash_password(TEST_PASSWORD), role="cos", designation="Chief of Staff")
        director = User(name="Synthetic Director", email="director@demo.example", password_hash=hash_password(TEST_PASSWORD), role="director_td", designation="Director, Transformation & Delivery")
        liaison = User(name="Synthetic Liaison", email="liaison@demo.example", password_hash=hash_password(TEST_PASSWORD), role="liaison", designation="Liaison Lead")
        db.add_all((cos, director, liaison))
        db.flush()
        tx = Transaction(code="TX-A", name="Synthetic Power Company A", sector="Energy", stage="approval_inclusion", next_milestone="Review pack", next_milestone_date=date(2026, 10, 25), health="on_track", lead_user_id=liaison.id, summary="Synthetic transaction summary.", updated_by=cos.id)
        db.add(tx)
        db.add_all((ToolSwitch(tool="minutes_assistant", suspended=False), ToolSwitch(tool="jarvis", suspended=False), RegisterSerialCounter(fy="2026-27", last_serial=0)))
        db.commit()
    def override_db() -> Generator[Session, None, None]:
        with TestSessions() as db:
            yield db
    provider = SampleProvider()
    stt = SampleSTT()
    gateway = AIGateway(Settings(ai_zone_mode="local", model_extraction="synthetic/extraction"), provider=provider)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_ai_gateway] = lambda: gateway
    app.dependency_overrides[get_stt_provider] = lambda: stt
    app.dependency_overrides[get_jarvis_stt_provider] = lambda: stt
    with TestClient(app) as client:
        yield client, TestSessions, provider, stt
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def token_for(client: TestClient) -> str:
    response = client.post("/api/v1/auth/login", json={"email": "cos@demo.example", "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def create_meeting(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/api/v1/meetings", json={"title": "Synthetic TX-A transaction review", "occurred_at": "2026-10-17T10:00:00Z", "location": "Synthetic conference room", "attendees": [{"name": "Synthetic Director", "role": "Director"}], "classification": "internal"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def process_meeting(client: TestClient, meeting_id: str, headers: dict[str, str]):
    queued = client.post(f"/api/v1/meetings/{meeting_id}/process", headers=headers)
    assert queued.status_code == 202, queued.text
    job = client.get(f"/api/v1/jobs/{queued.json()['id']}", headers=headers)
    assert job.status_code == 200 and job.json()["status"] == "succeeded", job.text
    return client.get(f"/api/v1/meetings/{meeting_id}", headers=headers)


def test_seeded_transcript_yields_minutes_evidence_actions_and_issued_docx(minutes_client, tmp_path) -> None:
    client, sessions, provider, _ = minutes_client
    headers = {"Authorization": f"Bearer {token_for(client)}"}
    meeting_id = create_meeting(client, headers)
    segments = json.loads((__import__("pathlib").Path(__file__).parents[1] / "samples" / "synthetic_minutes_review.json").read_text(encoding="utf-8"))
    with sessions() as db:
        meeting = db.get(Meeting, meeting_id)
        meeting.is_synthetic = True
        meeting.status = "transcribed"
        db.add(Transcript(meeting_id=meeting_id, language="en", segments=segments, stt_provider="synthetic-seed", stt_model="sample-v1"))
        db.commit()

    queued = client.post(f"/api/v1/meetings/{meeting_id}/process", headers=headers)
    assert queued.status_code == 202, queued.text
    job = client.get(f"/api/v1/jobs/{queued.json()['id']}", headers=headers)
    assert job.status_code == 200 and job.json()["status"] == "succeeded", job.text
    events = client.get(f"/api/v1/jobs/{queued.json()['id']}/events", headers=headers)
    assert events.status_code == 200 and "event: job" in events.text and '"progress":100' in events.text
    drafted = client.get(f"/api/v1/meetings/{meeting_id}", headers=headers)
    assert drafted.status_code == 200, drafted.text
    body = drafted.json()
    assert body["minutes"]["status"] == "draft"
    assert len(body["actions"]) == 2
    assert body["actions"][0]["quote"] in segments[1]["text"]
    assert body["actions"][0]["transcript_start"] == segments[1]["start"]
    assert body["actions"][1]["quote"] in segments[2]["text"]
    assert all(action["review_state"] == "pending" for action in body["actions"])
    edited = client.patch(f"/api/v1/meetings/{meeting_id}/actions/{body['actions'][0]['id']}", json={"deadline_date": "2026-10-22"}, headers=headers)
    assert edited.status_code == 200, edited.text
    with sessions() as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.action == "minutes_action_updated").order_by(AuditEvent.at.desc()))
        assert event is not None
        assert event.before_json["deadline_date"] == "2026-10-21"
        assert event.after_json["deadline_date"] == "2026-10-22"
    assert provider.calls == 1
    assert not (tmp_path / "demo_cache").exists()
    blocked = client.post(f"/api/v1/meetings/{meeting_id}/issue", headers=headers)
    assert blocked.status_code == 409
    with sessions() as db:
        proposals = db.scalars(select(RegisterEntry).where(RegisterEntry.review_state == "proposed")).all()
        assert len(proposals) == 2 and all(item.serial_no is None for item in proposals)
        run = db.scalar(select(AIRun).where(AIRun.tool == "minutes_assistant"))
        assert run is not None and run.outcome == "success"

    for action in body["actions"]:
        approved = client.post(f"/api/v1/meetings/{meeting_id}/actions/{action['id']}/review", json={"decision": "approve"}, headers=headers)
        assert approved.status_code == 200, approved.text
        assert approved.json()["review_state"] == "approved"
    issued = client.post(f"/api/v1/meetings/{meeting_id}/issue", headers=headers)
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == "issued"
    assert issued.json()["minutes"]["status"] == "issued"
    with sessions() as db:
        approved_entries = db.scalars(select(RegisterEntry).where(RegisterEntry.review_state == "approved", RegisterEntry.source_record == f"MIN-{meeting_id[:8]}")).all()
        assert len(approved_entries) == 2
        assert sorted(item.serial_no for item in approved_entries) == [1, 2]
        run = db.scalar(select(AIRun).where(AIRun.tool == "minutes_assistant"))
        assert run is not None and run.approver_id is not None and run.approved_at is not None
    export = client.get(f"/api/v1/meetings/{meeting_id}/minutes.docx", headers=headers)
    assert export.status_code == 200 and export.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")
    assert b"PK" == export.content[:2]


def test_demo_cache_reuses_only_a_matching_successful_synthetic_minutes_result(minutes_client, monkeypatch) -> None:
    client, sessions, provider, _ = minutes_client
    headers = {"Authorization": f"Bearer {token_for(client)}"}
    meeting_id = create_meeting(client, headers)
    segments = json.loads((__import__("pathlib").Path(__file__).parents[1] / "samples" / "synthetic_minutes_review.json").read_text(encoding="utf-8"))
    with sessions() as db:
        meeting = db.get(Meeting, meeting_id)
        meeting.is_synthetic = True
        meeting.status = "transcribed"
        db.add(Transcript(meeting_id=meeting_id, language="en", segments=segments, stt_provider="synthetic-seed", stt_model="sample-v1"))
        db.commit()
    monkeypatch.setattr(settings, "demo_mode_cache", True)
    assert process_meeting(client, meeting_id, headers).status_code == 200
    with sessions() as db:
        db.execute(delete(MeetingAction).where(MeetingAction.meeting_id == meeting_id))
        db.execute(delete(RegisterEntry).where(RegisterEntry.source_record == f"MIN-{meeting_id[:8]}"))
        db.execute(delete(MinutesDraft).where(MinutesDraft.meeting_id == meeting_id))
        db.get(Meeting, meeting_id).status = "transcribed"
        db.commit()

    async def provider_offline(**_: object) -> ChatResult:
        raise ConnectionError("synthetic provider outage")

    monkeypatch.setattr(provider, "chat", provider_offline)
    reused = process_meeting(client, meeting_id, headers)
    assert reused.status_code == 200, reused.text
    assert reused.json()["minutes"]["body_markdown"].startswith("# Transaction review")
    assert reused.json()["minutes"]["demo_cache_used"] is True
    with sessions() as db:
        run = db.scalar(select(AIRun).where(AIRun.error_code == "demo_cache_used"))
        assert run is not None and run.prompt_version == "minutes-cache-v1" and run.outcome == "success"


def test_uploaded_audio_uses_stt_provider_and_suspended_tool_fails_closed(minutes_client) -> None:
    client, sessions, _, stt = minutes_client
    headers = {"Authorization": f"Bearer {token_for(client)}"}
    meeting_id = create_meeting(client, headers)
    with sessions() as db:
        meeting = db.get(Meeting, meeting_id)
        meeting.audio_path = "audio/synthetic-upload.wav"
        db.commit()
    result = process_meeting(client, meeting_id, headers)
    assert result.status_code == 200, result.text
    assert stt.called is True

    meeting_id_2 = create_meeting(client, headers)
    suspended = client.patch("/api/v1/assurance/tools/minutes_assistant", json={"suspended": True, "reason": "Synthetic test suspension."}, headers=headers)
    assert suspended.status_code == 200
    blocked = client.post(f"/api/v1/meetings/{meeting_id_2}/process", headers=headers)
    assert blocked.status_code == 503
    with sessions() as db:
        run = db.scalar(select(AIRun).where(AIRun.error_code == "tool_suspended"))
        assert run is not None and run.outcome == "blocked"


def test_confidential_meetings_are_hidden_from_roles_without_clearance(minutes_client) -> None:
    client, _, _, _ = minutes_client
    cos_headers = {"Authorization": f"Bearer {token_for(client)}"}
    created = client.post("/api/v1/meetings", json={"title": "Synthetic confidential review", "occurred_at": "2026-10-17T10:00:00Z", "location": "Synthetic room", "classification": "confidential"}, headers=cos_headers)
    assert created.status_code == 201, created.text
    meeting_id = created.json()["id"]
    liaison_login = client.post("/api/v1/auth/login", json={"email": "liaison@demo.example", "password": TEST_PASSWORD})
    assert liaison_login.status_code == 200
    liaison_headers = {"Authorization": f"Bearer {liaison_login.json()['access_token']}"}
    listing = client.get("/api/v1/meetings", headers=liaison_headers)
    assert listing.status_code == 200 and all(item["id"] != meeting_id for item in listing.json())
    detail = client.get(f"/api/v1/meetings/{meeting_id}", headers=liaison_headers)
    assert detail.status_code == 404


def test_records_search_cites_source_and_filters_confidential_documents(minutes_client) -> None:
    client, _, _, _ = minutes_client
    cos_headers = {"Authorization": f"Bearer {token_for(client)}"}
    content = b"Synthetic Project Cedar board review is scheduled for 30 October 2026. The board will note the diligence timetable and confirm sequencing."
    uploaded = client.post("/api/v1/documents", data={"title": "Synthetic Project Cedar Board Paper", "doc_type": "board_paper", "classification": "confidential"}, files={"file": ("cedar.txt", content, "text/plain")}, headers=cos_headers)
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    assert uploaded.json()["chunk_count"] == 1
    assert uploaded.json()["is_synthetic"] is False

    cos_search = client.post("/api/v1/records/search", json={"query": "When is the Project Cedar board review scheduled?"}, headers=cos_headers)
    assert cos_search.status_code == 200, cos_search.text
    result = cos_search.json()
    assert result["declined"] is False
    assert result["citations"][0]["document_id"] == document_id
    assert "30 October 2026" in result["citations"][0]["snippet"]

    liaison_login = client.post("/api/v1/auth/login", json={"email": "liaison@demo.example", "password": TEST_PASSWORD})
    liaison_headers = {"Authorization": f"Bearer {liaison_login.json()['access_token']}"}
    denied_search = client.post("/api/v1/records/search", json={"query": "Project Cedar board review date"}, headers=liaison_headers)
    assert denied_search.status_code == 200 and denied_search.json()["declined"] is True
    assert denied_search.json()["citations"] == []
    denied_source = client.get(f"/api/v1/documents/{document_id}/source", headers=liaison_headers)
    assert denied_source.status_code == 404
    allowed_source = client.get(f"/api/v1/documents/{document_id}/source", headers=cos_headers)
    assert allowed_source.status_code == 200 and b"30 October 2026" in allowed_source.content

    no_evidence = client.post("/api/v1/records/search", json={"query": "unrelated badminton score result"}, headers=cos_headers)
    assert no_evidence.status_code == 200 and no_evidence.json()["declined"] is True


def test_jarvis_streams_grounded_answer_and_creates_only_a_proposal(minutes_client) -> None:
    client, sessions, _, _ = minutes_client
    headers = {"Authorization": f"Bearer {token_for(client)}"}
    answer = client.post("/api/v1/jarvis/chat", json={"message": "What is the next milestone for TX-A?"}, headers=headers)
    assert answer.status_code == 200 and "text/event-stream" in answer.headers["content-type"]
    assert "Stage: approval_inclusion" in answer.text and "event: citation" in answer.text and "TX-A" in answer.text
    assert "event: token" in answer.text and "event: done" in answer.text

    proposal = client.post("/api/v1/jarvis/chat", json={"message": "Create an action for the CoS to confirm the draft by 2099-12-01."}, headers=headers)
    assert proposal.status_code == 200 and "event: proposal_card" in proposal.text
    with sessions() as db:
        entry = db.scalar(select(RegisterEntry).where(RegisterEntry.description == "confirm the draft"))
        assert entry is not None and entry.review_state == "proposed" and entry.serial_no is None
        assert entry.ai_assistance["tool"] == "jarvis"
        assert entry.ai_assistance["run_id"] is not None

    session_event = next(line for line in answer.text.splitlines() if line.startswith("data: {") and "session_id" in line)
    session_id = json.loads(session_event.removeprefix("data: "))["session_id"]
    liaison_login = client.post("/api/v1/auth/login", json={"email": "liaison@demo.example", "password": TEST_PASSWORD})
    liaison_headers = {"Authorization": f"Bearer {liaison_login.json()['access_token']}"}
    assert client.get(f"/api/v1/jarvis/sessions/{session_id}", headers=liaison_headers).status_code == 404


def test_jarvis_suspended_returns_graceful_refusal_and_records_block(minutes_client) -> None:
    client, sessions, _, _ = minutes_client
    headers = {"Authorization": f"Bearer {token_for(client)}"}
    suspended = client.patch("/api/v1/assurance/tools/jarvis", json={"suspended": True, "reason": "Synthetic test suspension."}, headers=headers)
    assert suspended.status_code == 200
    response = client.post("/api/v1/jarvis/chat", json={"message": "What is overdue?"}, headers=headers)
    assert response.status_code == 200 and "temporarily unavailable" in response.text
    with sessions() as db:
        run = db.scalar(select(AIRun).where(AIRun.tool == "jarvis", AIRun.error_code == "tool_suspended"))
        assert run is not None and run.outcome == "blocked"


def test_jarvis_voice_endpoint_uses_configured_stt_provider(minutes_client) -> None:
    client, _, _, stt = minutes_client
    headers = {"Authorization": f"Bearer {token_for(client)}"}
    response = client.post("/api/v1/jarvis/stt", files={"file": ("voice.webm", b"synthetic voice bytes", "audio/webm")}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["language"] == "en" and "TX-A" in response.json()["text"]
    assert stt.called is True


def test_compliance_due_window_and_status_updates_are_audited(minutes_client) -> None:
    client, sessions, _, _ = minutes_client
    headers = {"Authorization": f"Bearer {token_for(client)}"}
    with sessions() as db:
        liaison = db.scalar(select(User).where(User.role == "liaison"))
        owner_id = liaison.id
    deadline = date.today() + timedelta(days=5)
    created = client.post("/api/v1/compliance", json={"category": "statutory", "title": "Synthetic statutory filing", "due_date": deadline.isoformat(), "owner_id": owner_id, "reference": "SYN-001"}, headers=headers)
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    due = client.get("/api/v1/compliance/due", headers=headers)
    assert any(item["id"] == item_id for item in due.json())
    completed = client.patch(f"/api/v1/compliance/{item_id}", json={"status": "complete"}, headers=headers)
    assert completed.status_code == 200 and completed.json()["status"] == "complete"
    due_after = client.get("/api/v1/compliance/due", headers=headers)
    assert all(item["id"] != item_id for item in due_after.json())
    with sessions() as db:
        actions = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == item_id)).all()
        assert len(actions) == 2


def test_spot_check_samples_successful_runs_and_records_reconciliation(minutes_client) -> None:
    client, sessions, _, _ = minutes_client
    headers = {"Authorization": f"Bearer {token_for(client)}"}
    with sessions() as db:
        db.add_all([AIRun(tool="jarvis", model_role="chat", model="synthetic-model", zone="local", classification="internal", is_synthetic=True, outcome="success", prompt_version="test", user_id=None) for _ in range(3)])
        db.commit()
    created = client.post("/api/v1/assurance/spot-checks?period=2026-10", json={"sample_size": 2}, headers=headers)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["status"] == "pending" and len(row["sample"]) == 2
    saved = client.patch(f"/api/v1/assurance/spot-checks/{row['id']}", json={"findings": "Source comparison confirmed both sampled records."}, headers=headers)
    assert saved.status_code == 200 and saved.json()["status"] == "reviewed" and saved.json()["reconciled_by"] is not None
    duplicate = client.post("/api/v1/assurance/spot-checks?period=2026-10", json={"sample_size": 2}, headers=headers)
    assert duplicate.status_code == 409


def test_admin_user_lifecycle_and_system_health_are_role_restricted(minutes_client) -> None:
    client, sessions, _, _ = minutes_client
    with sessions() as db:
        admin = User(name="Synthetic Admin", email="admin@demo.example", password_hash=hash_password(TEST_PASSWORD), role="admin", designation="Administrator")
        db.add(admin)
        db.commit()
    login = client.post("/api/v1/auth/login", json={"email": "admin@demo.example", "password": TEST_PASSWORD})
    admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    health = client.get("/api/v1/admin/health", headers=admin_headers)
    assert health.status_code == 200 and health.json()["database"] == "ok"
    created = client.post("/api/v1/admin/users", json={"name": "Synthetic Analyst", "email": "new.analyst@demo.example", "designation": "Analyst", "role": "analyst", "password": "Synthetic-Strong-Password-2026"}, headers=admin_headers)
    assert created.status_code == 201, created.text
    disabled = client.patch(f"/api/v1/admin/users/{created.json()['id']}", json={"active": False}, headers=admin_headers)
    assert disabled.status_code == 200 and disabled.json()["active"] is False
    assert client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token_for(client)}"}).status_code == 403


@pytest.mark.parametrize("rehearsal", [1, 2, 3])
def test_demo_backend_path_rehearses_end_to_end(rehearsal: int, minutes_client) -> None:
    client, sessions, _, _ = minutes_client
    cos_headers = {"Authorization": f"Bearer {token_for(client)}"}

    dashboard = client.get("/api/v1/dashboard", headers=cos_headers)
    assert dashboard.status_code == 200 and dashboard.json()["kpis"]["transactions_in_process"] == 1

    meeting_id = create_meeting(client, cos_headers)
    segments = json.loads((__import__("pathlib").Path(__file__).parents[1] / "samples" / "synthetic_minutes_review.json").read_text(encoding="utf-8"))
    with sessions() as db:
        meeting = db.get(Meeting, meeting_id)
        meeting.is_synthetic = True
        meeting.status = "transcribed"
        db.add(Transcript(meeting_id=meeting_id, language="en", segments=segments, stt_provider="synthetic-seed", stt_model="sample-v1"))
        liaison = db.scalar(select(User).where(User.role == "liaison"))
        db.add(ComplianceItem(category="statutory", title=f"Synthetic rehearsal {rehearsal}", due_date=date.today() + timedelta(days=3), owner_id=liaison.id, status="open", reference=f"SYN-REHEARSAL-{rehearsal}"))
        db.commit()
    drafted = process_meeting(client, meeting_id, cos_headers)
    assert drafted.status_code == 200 and len(drafted.json()["actions"]) == 2
    for action in drafted.json()["actions"]:
        assert client.post(f"/api/v1/meetings/{meeting_id}/actions/{action['id']}/review", json={"decision": "approve"}, headers=cos_headers).status_code == 200
    assert client.post(f"/api/v1/meetings/{meeting_id}/issue", headers=cos_headers).status_code == 200
    assert client.get(f"/api/v1/meetings/{meeting_id}/minutes.docx", headers=cos_headers).content[:2] == b"PK"

    uploaded = client.post("/api/v1/documents", data={"title": f"Synthetic rehearsal note {rehearsal}", "doc_type": "brief", "classification": "internal"}, files={"file": ("rehearsal.txt", b"Synthetic TX-A diligence milestone review is due 25 October 2026.", "text/plain")}, headers=cos_headers)
    assert uploaded.status_code == 201, uploaded.text
    search = client.post("/api/v1/records/search", json={"query": "When is the TX-A diligence milestone review due?"}, headers=cos_headers)
    assert search.status_code == 200 and search.json()["citations"]

    jarvis = client.post("/api/v1/jarvis/chat", json={"message": "What is the status of TX-A?"}, headers=cos_headers)
    assert jarvis.status_code == 200 and "TX-A" in jarvis.text and "event: citation" in jarvis.text
    proposal = client.post("/api/v1/jarvis/chat", json={"message": "Create an action for the CoS to confirm the rehearsal draft by 2099-12-01."}, headers=cos_headers)
    assert proposal.status_code == 200 and "event: proposal_card" in proposal.text
    proposal_event = next(line.removeprefix("data: ") for line in proposal.text.splitlines() if line.startswith("data: {") and '"review_state": "proposed"' in line)
    proposal_data = json.loads(proposal_event)
    approved_proposal = client.post(f"/api/v1/register/{proposal_data['id']}/approve", headers=cos_headers)
    assert approved_proposal.status_code == 200 and approved_proposal.json()["serial_no"] is not None

    compliance = client.get("/api/v1/compliance/due", headers=cos_headers)
    assert any(item["reference"] == f"SYN-REHEARSAL-{rehearsal}" for item in compliance.json())
    period = f"2099-0{rehearsal}"
    sampled = client.post(f"/api/v1/assurance/spot-checks?period={period}", json={"sample_size": 2}, headers=cos_headers)
    assert sampled.status_code == 201 and sampled.json()["sample"]
    reconciled = client.patch(f"/api/v1/assurance/spot-checks/{sampled.json()['id']}", json={"findings": "Synthetic rehearsal source check completed."}, headers=cos_headers)
    assert reconciled.status_code == 200 and reconciled.json()["status"] == "reviewed"

    with sessions() as db:
        db.add(User(name=f"Synthetic admin {rehearsal}", email=f"admin{rehearsal}@demo.example", password_hash=hash_password(TEST_PASSWORD), role="admin", designation="Administrator"))
        db.commit()
    admin_login = client.post("/api/v1/auth/login", json={"email": f"admin{rehearsal}@demo.example", "password": TEST_PASSWORD})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    assert client.get("/api/v1/admin/health", headers=admin_headers).json()["database"] == "ok"
    assert client.get("/api/v1/admin/users", headers=admin_headers).status_code == 200
