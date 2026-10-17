from collections.abc import Generator
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import AIRun, Engagement, MinisterDecision, RegisterEntry, RegisterSerialCounter, ToolSwitch, Transaction, TransactionEvent, User
from app.services.register import financial_year_for
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
TEST_PASSWORD = "Demo-Only-Change-Me-2026!"
TEST_HASH = hash_password(TEST_PASSWORD)
STAGE_COUNTS = {"approval_inclusion": 2, "adviser_hiring": 3, "due_diligence": 3, "eoi_prequalification": 3, "bidding": 2, "approvals": 2, "closing": 2}


@pytest.fixture
def dashboard_client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        cos = User(name="Synthetic CoS", email="cos@demo.example", password_hash=TEST_HASH, role="cos", designation="Chief of Staff")
        director = User(name="Synthetic Director", email="director.td@demo.example", password_hash=TEST_HASH, role="director_td", designation="Director")
        liaison = User(name="Synthetic Liaison", email="liaison@demo.example", password_hash=TEST_HASH, role="liaison", designation="Liaison Lead")
        minister = User(name="Synthetic Minister", email="minister@demo.example", password_hash=TEST_HASH, role="minister", designation="Minister")
        db.add_all((cos, director, liaison, minister))
        db.flush()
        today = date.today()
        transactions: list[Transaction] = []
        index = 0
        for stage, count in STAGE_COUNTS.items():
            for _ in range(count):
                code = f"TX-{chr(65 + index)}"
                transaction = Transaction(code=code, name=f"Synthetic asset {code}", sector="Energy", stage=stage, next_milestone="Synthetic checkpoint", next_milestone_date=today + timedelta(days=index + 3), health="delayed" if index == 2 else "at_risk" if index == 12 else "on_track", lead_user_id=liaison.id, summary="Fictional dashboard fixture.", updated_by=cos.id)
                db.add(transaction)
                transactions.append(transaction)
                index += 1
        db.flush()
        db.add(TransactionEvent(transaction_id=transactions[0].id, occurred_at=datetime.now(timezone.utc), event_type="milestone", description="Synthetic milestone record."))
        for number in range(4):
            db.add(MinisterDecision(title=f"Synthetic decision {number + 1}", due_date=today + timedelta(days=number + 1), transaction_id=transactions[number].id, status="open", context_ref=f"SYN-DEC-{number + 1}"))
        for number in range(6):
            starts_at = datetime.combine(today + timedelta(days=number + 1), datetime.min.time(), tzinfo=timezone.utc)
            db.add(Engagement(title=f"Synthetic engagement {number + 1}", engagement_type="Review", starts_at=starts_at, location="Synthetic venue", pack_status="ready" if number == 0 else "not_started", pack_due_at=starts_at - timedelta(hours=48), owner_id=director.id, transaction_id=transactions[number].id))
        for number in range(6):
            db.add(RegisterEntry(fy="2026-27", serial_no=number + 1, occurred_at=datetime.now(timezone.utc) - timedelta(days=10), occasion_type="meeting", description=f"Synthetic overdue action {number + 1}", officer_id=liaison.id, deadline=today - timedelta(days=number + 1), priority="B", status="in_progress", transaction_id=transactions[number].id, origin="manual", review_state="approved"))
        db.add(RegisterSerialCounter(fy=financial_year_for(today), last_serial=6))
        db.commit()

    def override_db() -> Generator[Session, None, None]:
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, TestingSession
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def access_token(client: TestClient, email: str = "cos@demo.example") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_dashboard_counts_and_drilldowns_reconcile_to_source_records(dashboard_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = dashboard_client
    token = access_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    selected_end = date.today() + timedelta(days=7)
    summary = client.get(f"/api/v1/dashboard?week_ending={selected_end.isoformat()}", headers=headers)
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert data["kpis"] == {"transactions_in_process": 17, "decisions_due_this_week": 4, "actions_overdue": 6, "engagements_this_week": 6}
    assert {item["stage"]: item["count"] for item in data["transactions_by_stage"]} == STAGE_COUNTS
    assert sum(item["count"] for item in data["transactions_by_stage"]) == data["kpis"]["transactions_in_process"]
    for kpi, expected, query in (("transactions_in_process", 17, ""), ("decisions_due_this_week", 4, ""), ("actions_overdue", 6, ""), ("engagements_this_week", 6, ""), ("transactions_by_stage", 2, "&stage=bidding")):
        response = client.get(f"/api/v1/dashboard/drill/{kpi}?week_ending={data['week_ending']}{query}", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == expected
        assert len(response.json()["records"]) == expected


def test_transaction_detail_edits_events_and_register_links_are_audited(dashboard_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = dashboard_client
    token = access_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    detail = client.get("/api/v1/transactions/TX-A", headers=headers)
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["events"]) == 1
    assert len(detail.json()["register_entries"]) == 1
    changed = client.patch("/api/v1/transactions/TX-A", json={"health": "at_risk", "change_reason": "Synthetic review found an open dependency."}, headers=headers)
    assert changed.status_code == 200, changed.text
    event = client.post("/api/v1/transactions/TX-A/events", json={"occurred_at": datetime.now(timezone.utc).isoformat(), "event_type": "risk", "description": "Synthetic risk note recorded."}, headers=headers)
    assert event.status_code == 201, event.text
    assert event.json()["event_type"] == "risk"
    with session_factory() as db:
        history = db.scalars(select(TransactionEvent).where(TransactionEvent.transaction_id == detail.json()["id"])).all()
        assert len(history) == 2


def test_transaction_edits_are_denied_to_read_only_minister(dashboard_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = dashboard_client
    token = access_token(client, "minister@demo.example")
    response = client.patch("/api/v1/transactions/TX-A", json={"health": "delayed", "change_reason": "Read-only role check."}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_decisions_and_engagements_create_and_update(dashboard_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = dashboard_client
    token = access_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    with session_factory() as db:
        transaction_id = db.scalar(select(Transaction.id).where(Transaction.code == "TX-A"))
        owner_id = db.scalar(select(User.id).where(User.role == "director_td"))
    assert transaction_id and owner_id
    decision = client.post("/api/v1/decisions", json={"title": "Synthetic decision follow-up", "due_date": (date.today() + timedelta(days=2)).isoformat(), "transaction_id": transaction_id, "context_ref": "SYN-NEW-1"}, headers=headers)
    assert decision.status_code == 201, decision.text
    assert decision.json()["status"] == "open"
    updated_decision = client.patch(f"/api/v1/decisions/{decision.json()['id']}", json={"status": "in_progress"}, headers=headers)
    assert updated_decision.status_code == 200, updated_decision.text
    starts_at = datetime.now(timezone.utc) + timedelta(days=5)
    engagement = client.post("/api/v1/engagements", json={"title": "Synthetic portfolio review", "engagement_type": "Review", "starts_at": starts_at.isoformat(), "location": "Synthetic venue", "owner_id": owner_id, "transaction_id": transaction_id}, headers=headers)
    assert engagement.status_code == 201, engagement.text
    pack_due = datetime.fromisoformat(engagement.json()["pack_due_at"])
    assert pack_due == starts_at - timedelta(hours=48)
    updated_engagement = client.patch(f"/api/v1/engagements/{engagement.json()['id']}", json={"pack_status": "ready"}, headers=headers)
    assert updated_engagement.status_code == 200, updated_engagement.text
    assert updated_engagement.json()["pack_status"] == "ready"


def test_assurance_suspension_is_audited_and_written_to_register(dashboard_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = dashboard_client
    token = access_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    with session_factory() as db:
        db.add(ToolSwitch(tool="jarvis", suspended=False))
        db.commit()
    response = client.patch("/api/v1/assurance/tools/jarvis", json={"suspended": True, "reason": "Synthetic policy validation."}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["suspended"] is True
    with session_factory() as db:
        control_entry = db.scalar(select(RegisterEntry).where(RegisterEntry.source_record == f"AI-CONTROL-{date.today():%Y%m%d}-jarvis"))
        assert control_entry is not None and control_entry.review_state == "approved" and control_entry.status == "closed"
        assert db.scalar(select(ToolSwitch.suspended).where(ToolSwitch.tool == "jarvis")) is True


def test_register_proposal_review_updates_ai_run(dashboard_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = dashboard_client
    token = access_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    with session_factory() as db:
        actor = db.scalar(select(User).where(User.role == "cos"))
        assert actor is not None
        run = AIRun(tool="minutes_assistant", model_role="extraction", model="synthetic/model", zone="local", classification="internal", is_synthetic=True, user_id=actor.id, outcome="success", prompt_version="minutes-v1")
        db.add(run)
        db.flush()
        entry = RegisterEntry(fy="2026-27", serial_no=None, occurred_at=datetime.now(timezone.utc), occasion_type="meeting", description="Synthetic AI proposed action for review.", officer_id=actor.id, deadline=date.today() + timedelta(days=3), priority="B", status="open", origin="ai_proposed", review_state="proposed", ai_assistance={"run_id": run.id, "tool": "minutes_assistant"})
        db.add(entry)
        db.commit()
        run_id, entry_id, actor_id = run.id, entry.id, actor.id
    response = client.post(f"/api/v1/register/{entry_id}/approve", headers=headers)
    assert response.status_code == 200, response.text
    with session_factory() as db:
        run = db.get(AIRun, run_id)
        assert run is not None and run.approver_id == actor_id and run.approved_at is not None
