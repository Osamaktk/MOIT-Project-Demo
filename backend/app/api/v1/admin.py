from importlib.util import find_spec

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, require_roles
from app.core.security import hash_password
from app.db.models import AuditEvent, User
from app.schemas.admin import AdminUserCreate, AdminUserResponse, AdminUserUpdate

router = APIRouter(prefix="/admin", tags=["system administration"])


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))) -> list[AdminUserResponse]:
    return [AdminUserResponse.model_validate(user) for user in db.scalars(select(User).order_by(User.role, User.name)).all()]


@router.post("/users", response_model=AdminUserResponse, status_code=201)
def create_user(payload: AdminUserCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))) -> AdminUserResponse:
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(name=payload.name.strip(), email=email, designation=payload.designation.strip(), role=payload.role, active=True, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    db.add(AuditEvent(actor_id=actor.id, action="admin_user_created", entity_type="user", entity_id=user.id, after_json={"name": user.name, "email": user.email, "role": user.role, "designation": user.designation}, ip=request.client.host if request.client else None))
    db.commit()
    return AdminUserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(user_id: str, payload: AdminUserUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))) -> AdminUserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User was not found")
    changes = payload.model_dump(exclude_unset=True)
    if user.id == actor.id and changes.get("active") is False:
        raise HTTPException(status_code=422, detail="You cannot deactivate your own account")
    if user.role == "admin" and user.active and (changes.get("active") is False or (changes.get("role") and changes["role"] != "admin")):
        other_admins = db.scalar(select(User.id).where(User.role == "admin", User.active.is_(True), User.id != user.id).limit(1))
        if other_admins is None:
            raise HTTPException(status_code=409, detail="At least one active administrator must remain")
    before = {key: getattr(user, key) for key in changes}
    for key, value in changes.items():
        setattr(user, key, value.strip() if isinstance(value, str) else value)
    db.add(AuditEvent(actor_id=actor.id, action="admin_user_updated", entity_type="user", entity_id=user.id, before_json=before, after_json=changes, ip=request.client.host if request.client else None))
    db.commit()
    db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.get("/health")
def system_health(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    local_embedding_configured = bool(settings.embedding_model.strip())
    embedding_configured = (
        bool(settings.model_embedding.strip())
        if settings.embedding_provider == "openrouter"
        else not local_embedding_configured or find_spec("sentence_transformers") is not None
    )
    provider_configured = bool(settings.model_chat.strip()) and (bool(settings.openrouter_api_key.get_secret_value()) if settings.ai_zone_mode == "cloud" else bool(settings.local_llm_base_url))
    return {"database": "ok", "environment": settings.app_env, "ai_zone": settings.ai_zone_mode, "chat_provider_configured": provider_configured, "embedding_provider_configured": embedding_configured, "embedding_provider": settings.embedding_provider, "stt_package_installed": find_spec("faster_whisper") is not None, "chroma_directory_exists": (settings.resolved_data_dir / "chroma").exists(), "configured_models": {"chat": settings.model_chat or None, "embedding": settings.model_embedding or settings.embedding_model or "offline-hash-v1", "stt": settings.stt_model_size}}
