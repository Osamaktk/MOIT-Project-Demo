from collections.abc import Generator
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.permissions import CAPABILITIES, ROLE_PRESETS, AREAS, allowed_by_preset, has_permission
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models import Action, Commitment, Organisation, Project, User, UserPermission
from app.main import app
from app.services.project_rules import normalize_deadline, recompute_project_health


@pytest.fixture
def db_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.mark.parametrize(
    ("words", "meeting", "expected", "precision"),
    [
        ("Today", date(2026, 8, 21), date(2026, 8, 21), "day"),
        ("Immediate", date(2026, 8, 21), date(2026, 8, 25), "relative"),
        ("13 September 2026", date(2026, 8, 21), date(2026, 9, 13), "day"),
        ("First week of March 2027", date(2026, 8, 21), date(2027, 3, 7), "week"),
        ("March 2027", date(2026, 8, 21), date(2027, 3, 1), "month"),
        ("180 days from contractor mobilization", date(2026, 8, 21), date(2027, 3, 12), "relative"),
    ],
)
def test_deadline_normalisation(words: str, meeting: date, expected: date, precision: str) -> None:
    mobilization = date(2026, 9, 13) if "mobilization" in words else None
    result = normalize_deadline(words, meeting, mobilization_date=mobilization)
    assert result.resolved_date == expected
    assert result.precision == precision
    assert result.needs_input is False


def test_deadline_needs_input_for_unknown_next_meeting_and_unanchored_relative() -> None:
    assert normalize_deadline("Next Meeting", date(2026, 8, 21)).needs_input
    assert normalize_deadline("180 days from contractor mobilization", date(2026, 8, 21)).resolved_date is None
    next_date = normalize_deadline("Next Meeting", date(2026, 8, 21), next_meeting=date(2026, 9, 1))
    assert next_date.resolved_date == date(2026, 9, 1)


def _health_case(factory: sessionmaker[Session], *, action_days_late: int | None = None, priority: str = "B", commitment_days: int | None = None, progress: bool = False) -> tuple[str, str]:
    with factory() as db:
        org = Organisation(name="Ministry", short_name="MO", type="ministry", aliases=[])
        project = Project(code="PRJ-TEST", name="Test project", aliases=[], sector="Digital", stage="implementation", health="on_track", health_reason="Initial assessment.", summary="Synthetic test project.")
        db.add_all([org, project])
        db.flush()
        if action_days_late is not None:
            deadline = date(2026, 10, 18) - timedelta(days=action_days_late)
            db.add(Action(fy="2026-27", description="Synthetic follow-up action", owner_org_id=org.id, occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc), deadline=deadline, deadline_text=deadline.isoformat(), deadline_precision="day", priority=priority, status="in_progress" if progress else "open", review_state="approved", project_id=project.id))
        if commitment_days is not None:
            db.add(Commitment(project_id=project.id, statement="Synthetic project delivery commitment", due_date=date(2026, 10, 18) + timedelta(days=commitment_days), due_text="Synthetic date", precision="day", status="pending"))
        db.flush()
        health, reason = recompute_project_health(db, project, as_of=date(2026, 10, 18))
        assert project.health_reason == reason and reason
        return health, reason


def test_health_rules_delayed_at_risk_and_on_track(db_factory: sessionmaker[Session]) -> None:
    assert _health_case(db_factory, action_days_late=1)[0] == "at_risk"
    critical, critical_reason = _health_case(db_factory, action_days_late=15, priority="A")
    assert critical == "delayed" and "14 days" in critical_reason
    commitment, commitment_reason = _health_case(db_factory, commitment_days=-1)
    assert commitment == "delayed" and "commitment" in commitment_reason
    near, near_reason = _health_case(db_factory, commitment_days=10)
    assert near == "at_risk" and "no progress action" in near_reason
    progressing, _ = _health_case(db_factory, commitment_days=10, action_days_late=1, progress=True)
    assert progressing == "at_risk"  # the overdue action remains an independent risk
    progressing_before_deadline, _ = _health_case(db_factory, commitment_days=10, action_days_late=0, progress=True)
    assert progressing_before_deadline == "on_track"
    on_track, reason = _health_case(db_factory)
    assert on_track == "on_track" and "No overdue actions" in reason


def test_role_permission_matrix_and_user_override(db_factory: sessionmaker[Session]) -> None:
    with db_factory() as db:
        for role, grants in ROLE_PRESETS.items():
            user = User(name=role, email=f"{role}@test.invalid", role=role, designation=role, password_hash="x")
            db.add(user)
            db.flush()
            for area in AREAS:
                for capability in CAPABILITIES:
                    assert has_permission(db, user, area, capability) == (capability in grants.get(area, [])), (role, area, capability)
        admin = db.scalar(select(User).where(User.role == "admin"))
        assert admin is not None
        db.add(UserPermission(user_id=admin.id, permission_key="projects.view", allowed=True))
        db.flush()
        assert has_permission(db, admin, "projects", "view")
        assert allowed_by_preset("director_td", "projects", "edit")
        assert not allowed_by_preset("unrecognised", "projects", "view")


def test_domain_api_permissions_and_action_confirmation(db_factory: sessionmaker[Session]) -> None:
    with db_factory() as db:
        ministry = Organisation(name="Ministry of IT and Telecommunication", short_name="MoITT", type="ministry", aliases=[])
        minister = User(name="Minister", email="minister@test.invalid", role="minister", designation="Minister", password_hash="x")
        cos = User(name="Chief of Staff", email="cos@test.invalid", role="cos", designation="Chief of Staff", password_hash="x")
        admin = User(name="Admin", email="admin@test.invalid", role="admin", designation="Admin", password_hash="x")
        db.add_all([ministry, minister, cos, admin])
        db.flush()
        project = Project(code="ITP-TEST", name="IT Park Islamabad", aliases=["IT Park"], sector="Digital infrastructure", stage="implementation", health="on_track", health_reason="No overdue actions or near-term unmet commitments.", lead_org_id=ministry.id, summary="Synthetic project for API coverage.")
        db.add(project)
        db.commit()
        tokens = {user.role: create_access_token(user.id) for user in (minister, cos, admin)}
        organisation_id, project_id = ministry.id, project.id

    def override_db() -> Generator[Session, None, None]:
        with db_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            minister_headers = {"Authorization": f"Bearer {tokens['minister']}"}
            cos_headers = {"Authorization": f"Bearer {tokens['cos']}"}
            admin_headers = {"Authorization": f"Bearer {tokens['admin']}"}
            assert client.get("/api/v1/projects", headers=minister_headers).status_code == 200
            assert client.get("/api/v1/projects", headers=admin_headers).status_code == 403
            payload = {
                "description": "Confirm the next IT Park checkpoint.",
                "owner_org_id": organisation_id,
                "occurred_at": "2026-08-21T10:00:00Z",
                "deadline_text": "Immediate",
                "priority": "A",
                "project_id": project_id,
            }
            proposal = client.post("/api/v1/actions", json=payload, headers=cos_headers)
            assert proposal.status_code == 201
            assert proposal.json()["review_state"] == "proposed"
            assert proposal.json()["serial_no"] is None
            assert proposal.json()["deadline"] == "2026-08-25"
            action_id = proposal.json()["id"]
            confirmed = client.post(f"/api/v1/actions/{action_id}/confirm", headers=minister_headers)
            assert confirmed.status_code == 200
            assert confirmed.json()["review_state"] == "approved"
            assert confirmed.json()["serial_no"] == 1
            missing_owner = client.post("/api/v1/actions", json={**payload, "owner_org_id": None}, headers=cos_headers)
            assert missing_owner.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_external_organisation_action_scope(db_factory: sessionmaker[Session]) -> None:
    with db_factory() as db:
        pseb = Organisation(name="Pakistan Software Export Board", short_name="PSEB", type="attached_dept", aliases=[])
        cda = Organisation(name="Capital Development Authority", short_name="CDA", type="authority", aliases=[])
        user = User(name="PSEB Liaison", email="pseb@test.invalid", role="external_org", designation="Liaison", password_hash="x")
        db.add_all([pseb, cda, user])
        db.flush()
        user.organisation_id = pseb.id
        for org, code in ((pseb, "SCOPE-PSEB"), (cda, "SCOPE-CDA")):
            db.add(Action(fy="2026-27", description=f"Synthetic action for {code}", owner_org_id=org.id, occurred_at=datetime(2026, 10, 18, tzinfo=timezone.utc), deadline=date(2026, 11, 1), deadline_text="1 November 2026", deadline_precision="day", status="open", review_state="approved"))
        db.flush()
        token = create_access_token(user.id)
        expected_org = pseb.id
        db.commit()

    def override_db() -> Generator[Session, None, None]:
        with db_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/actions", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["owner_org_id"] == expected_org
    finally:
        app.dependency_overrides.clear()
