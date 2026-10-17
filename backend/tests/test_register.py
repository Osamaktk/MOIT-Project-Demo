from collections.abc import Generator
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import AuditEvent, RegisterEntry, RegisterSerialCounter, User
from app.main import app
from app.api.v1.register import safe_csv
from app.services.register import financial_year_for, is_overdue, next_serial_number

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
TEST_PASSWORD = "Demo-Only-Change-Me-2026!"
TEST_HASH = hash_password(TEST_PASSWORD)


@pytest.fixture
def register_client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        db.add_all((
            User(name="Synthetic CoS", email="cos@demo.example", password_hash=TEST_HASH, role="cos", designation="Chief of Staff"),
            User(name="Synthetic Liaison", email="liaison@demo.example", password_hash=TEST_HASH, role="liaison", designation="Liaison Lead"),
            User(name="Synthetic Minister", email="minister@demo.example", password_hash=TEST_HASH, role="minister", designation="Minister"),
        ))
        db.commit()

    def override_db() -> Generator[Session, None, None]:
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, TestingSession
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def get_token(client: TestClient, email: str = "cos@demo.example") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def payload(officer_id: str, *, deadline: date | None = None) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    return {
        "occurred_at": now.isoformat(),
        "occasion_type": "meeting",
        "occasion_ref": "Synthetic delivery meeting",
        "description": "Confirm the next milestone and record the source.",
        "officer_id": officer_id,
        "deadline": (deadline or now.date() + timedelta(days=2)).isoformat(),
        "priority": "B",
        "source_record": "SYN-TEST-001",
    }


def test_financial_year_changes_on_july_first() -> None:
    assert financial_year_for(date(2026, 6, 30)) == "2025-26"
    assert financial_year_for(date(2026, 7, 1)) == "2026-27"


def test_serial_counter_increments_and_is_scoped_to_financial_year(register_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    _, session_factory = register_client
    with session_factory() as db:
        assert next_serial_number(db, "2026-27") == 1
        assert next_serial_number(db, "2026-27") == 2
        assert next_serial_number(db, "2027-28") == 1
        db.rollback()


def test_register_creation_validation_and_audit_trail(register_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = register_client
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    with session_factory() as db:
        officer_id = db.scalar(select(User.id).where(User.role == "liaison"))
    assert officer_id is not None
    response = client.post("/api/v1/register", json=payload(officer_id), headers=headers)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["serial_no"] == 1
    assert record["review_state"] == "approved"
    assert record["officer"]["name"] == "Synthetic Liaison"
    assert len(client.get(f"/api/v1/register/{record['id']}/audit", headers=headers).json()) == 1
    invalid = client.post("/api/v1/register", json=payload(officer_id) | {"deadline": "urgent"}, headers=headers)
    assert invalid.status_code == 422


def test_deadline_cannot_precede_instruction_date(register_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = register_client
    token = get_token(client)
    with session_factory() as db:
        officer_id = db.scalar(select(User.id).where(User.role == "liaison"))
    assert officer_id is not None
    body = payload(officer_id) | {"occurred_at": datetime.now(timezone.utc).isoformat(), "deadline": (date.today() - timedelta(days=1)).isoformat()}
    response = client.post("/api/v1/register", json=body, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 422


def test_only_approved_rows_appear_in_default_register_list(register_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = register_client
    with session_factory() as db:
        officer = db.scalar(select(User).where(User.role == "liaison"))
        assert officer is not None
        db.add_all((
            RegisterEntry(fy="2026-27", serial_no=1, occurred_at=datetime.now(timezone.utc), occasion_type="meeting", description="Approved synthetic item", officer_id=officer.id, deadline=date.today() + timedelta(days=1), priority="B", status="open", origin="manual", review_state="approved"),
            RegisterEntry(fy="2026-27", serial_no=None, occurred_at=datetime.now(timezone.utc), occasion_type="meeting", description="Unapproved synthetic proposal", officer_id=officer.id, deadline=date.today() + timedelta(days=1), priority="B", status="open", origin="ai_proposed", review_state="proposed"),
            RegisterSerialCounter(fy="2026-27", last_serial=1),
        ))
        db.commit()
    token = get_token(client)
    response = client.get("/api/v1/register", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["total"] == 1
    all_rows = client.get("/api/v1/register?review_state=all", headers={"Authorization": f"Bearer {token}"})
    assert all_rows.status_code == 200
    assert all_rows.json()["total"] == 2
    proposal_id = next(row["id"] for row in all_rows.json()["items"] if row["review_state"] == "proposed")
    approved = client.post(f"/api/v1/register/{proposal_id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert approved.status_code == 200
    assert approved.json()["serial_no"] == 2
    assert approved.json()["review_state"] == "approved"


def test_write_roles_are_required_for_creating_official_register_entries(register_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = register_client
    token = get_token(client, "minister@demo.example")
    with session_factory() as db:
        officer_id = db.scalar(select(User.id).where(User.role == "liaison"))
    assert officer_id is not None
    response = client.post("/api/v1/register", json=payload(officer_id), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_csv_export_neutralizes_spreadsheet_formulas() -> None:
    assert safe_csv("=HYPERLINK(\"https://example.invalid\")").startswith("'=")
    assert safe_csv("Ordinary office record") == "Ordinary office record"


def test_status_transitions_and_reassignment_reason_are_enforced(register_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = register_client
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    with session_factory() as db:
        officer_id = db.scalar(select(User.id).where(User.role == "liaison"))
    assert officer_id is not None
    created = client.post("/api/v1/register", json=payload(officer_id), headers=headers).json()
    invalid_close = client.patch(f"/api/v1/register/{created['id']}", json={"status": "closed"}, headers=headers)
    assert invalid_close.status_code == 409
    reassignment_without_reason = client.patch(f"/api/v1/register/{created['id']}", json={"officer_id": "not-a-user"}, headers=headers)
    assert reassignment_without_reason.status_code == 422
    started = client.patch(f"/api/v1/register/{created['id']}", json={"status": "in_progress"}, headers=headers)
    assert started.status_code == 200
    closed = client.patch(f"/api/v1/register/{created['id']}", json={"status": "closed_with_note", "closure_note": "Verified against the synthetic source."}, headers=headers)
    assert closed.status_code == 200
    assert closed.json()["closed_at"]
    assert closed.json()["overdue"] is False


def test_overdue_logic_excludes_closed_and_unapproved_entries(register_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    _, session_factory = register_client
    with session_factory() as db:
        user = db.scalar(select(User).where(User.role == "liaison"))
        assert user is not None
        base = dict(fy="2026-27", occurred_at=datetime.now(timezone.utc) - timedelta(days=3), occasion_type="meeting", description="Synthetic overdue validation record", officer_id=user.id, deadline=date.today() - timedelta(days=1), priority="B", origin="manual")
        active = RegisterEntry(**base, serial_no=1, status="in_progress", review_state="approved")
        closed = RegisterEntry(**base, serial_no=2, status="closed", review_state="approved")
        proposed = RegisterEntry(**(base | {"origin": "ai_proposed"}), serial_no=None, status="open", review_state="proposed")
        assert is_overdue(active)
        assert not is_overdue(closed)
        assert not is_overdue(proposed)
        db.add_all((active, closed, proposed))
        db.commit()
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 0
