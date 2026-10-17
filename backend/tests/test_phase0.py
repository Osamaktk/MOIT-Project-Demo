from collections.abc import Generator

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.deps import require_roles
from app.core.middleware import RequestSecurityMiddleware, SlidingWindowLimiter
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import AuditEvent, User
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
DEMO_HASH = hash_password("Demo-Only-Change-Me-2026!")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        for role, email in (
            ("minister", "minister@demo.example"), ("cos", "cos@demo.example"),
            ("director_td", "director.td@demo.example"), ("liaison", "liaison@demo.example"),
            ("legal", "legal@demo.example"), ("analyst", "analyst@demo.example"),
            ("data_coordinator", "data.coordinator@demo.example"), ("admin", "admin@demo.example"),
        ):
            db.add(User(name=role, email=email, password_hash=DEMO_HASH, role=role, designation=role))
        db.commit()

    def override_db() -> Generator[Session, None, None]:
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_health_reports_database_ready(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    correlated = client.get("/health", headers={"X-Request-ID": "demo-check-01"})
    assert correlated.headers["x-request-id"] == "demo-check-01"


def test_sliding_window_rate_limit_expires_old_requests() -> None:
    limiter = SlidingWindowLimiter(window_seconds=10)
    assert limiter.allow("login:synthetic-client", 2, now=1.0)
    assert limiter.allow("login:synthetic-client", 2, now=2.0)
    assert not limiter.allow("login:synthetic-client", 2, now=3.0)
    assert limiter.allow("login:synthetic-client", 2, now=11.0)


def test_http_middleware_throttles_login_and_returns_request_id() -> None:
    limited_app = FastAPI()
    limited_app.add_middleware(RequestSecurityMiddleware, auth_limit=1, ai_limit=1)

    @limited_app.post("/api/v1/auth/login")
    def login() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(limited_app) as limited_client:
        first = limited_client.post("/api/v1/auth/login", json={})
        second = limited_client.post("/api/v1/auth/login", json={})
    assert first.status_code == 200 and first.headers.get("x-request-id")
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limited"


def test_ai_health_reports_readiness_without_exposing_credentials(client: TestClient) -> None:
    response = client.get("/health/ai")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "not_configured"}
    assert "stt_ready" in body and "vector_store_ready" in body
    assert "api_key" not in str(body).lower() and "secret" not in str(body).lower()


@pytest.mark.parametrize("email,role", [
    ("minister@demo.example", "minister"), ("cos@demo.example", "cos"),
    ("director.td@demo.example", "director_td"), ("liaison@demo.example", "liaison"),
    ("legal@demo.example", "legal"), ("analyst@demo.example", "analyst"),
    ("data.coordinator@demo.example", "data_coordinator"), ("admin@demo.example", "admin"),
])
def test_each_demo_role_can_login_and_read_own_profile(client: TestClient, email: str, role: str) -> None:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Demo-Only-Change-Me-2026!"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["role"] == role


def test_invalid_credentials_and_missing_token_are_rejected(client: TestClient) -> None:
    invalid_login = client.post("/api/v1/auth/login", json={"email": "minister@demo.example", "password": "wrong"})
    assert invalid_login.status_code == 401
    assert invalid_login.json()["error"]["code"] == "unauthorized"
    assert client.get("/api/v1/auth/me").status_code == 401


def test_request_validation_uses_the_shared_error_envelope(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "x"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_successful_login_creates_audit_event(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"email": "cos@demo.example", "password": "Demo-Only-Change-Me-2026!"})
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "login")) == 1


def test_role_dependency_allows_authorized_persona() -> None:
    user = User(name="Admin", email="admin@demo.example", password_hash=DEMO_HASH, role="admin", designation="Admin")
    assert require_roles("admin")(user=user) is user


def test_role_dependency_denies_unlisted_persona() -> None:
    user = User(name="Minister", email="minister@demo.example", password_hash=DEMO_HASH, role="minister", designation="Minister")
    with pytest.raises(HTTPException) as raised:
        require_roles("admin")(user=user)
    assert raised.value.status_code == 403
