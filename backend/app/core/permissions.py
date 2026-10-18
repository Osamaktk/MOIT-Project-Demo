from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.db.models import RolePreset, User, UserPermission

AREAS = (
    "dashboard", "projects", "actions", "meetings", "documents", "review",
    "jarvis", "jarvis_voice", "compliance", "ai_oversight", "admin",
)
CAPABILITIES = {"view", "edit", "approve", "upload"}


def _grant(*permissions: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for permission in permissions:
        area, capability = permission.split(".", 1)
        result.setdefault(area, []).append(capability)
    return result


ROLE_PRESETS: dict[str, dict[str, list[str]]] = {
    "minister": _grant("dashboard.view", "projects.view", "actions.view", "actions.approve", "meetings.view", "documents.view", "documents.upload", "documents.approve", "jarvis.view", "jarvis_voice.view"),
    "secretary": _grant("dashboard.view", "projects.view", "projects.edit", "actions.view", "actions.edit", "actions.approve", "meetings.view", "documents.view", "documents.upload", "documents.approve", "review.view", "jarvis.view", "jarvis_voice.view"),
    "cos": _grant("dashboard.view", "dashboard.edit", "projects.view", "projects.edit", "actions.view", "actions.edit", "actions.approve", "meetings.view", "meetings.edit", "documents.view", "documents.edit", "documents.upload", "documents.approve", "review.view", "review.edit", "review.approve", "jarvis.view", "jarvis_voice.view", "compliance.view", "compliance.edit", "ai_oversight.view", "ai_oversight.edit"),
    "project_lead": _grant("dashboard.view", "projects.view", "projects.edit", "actions.view", "actions.edit", "meetings.view", "documents.view", "documents.upload", "review.view", "review.edit", "jarvis.view", "jarvis_voice.view"),
    "legal": _grant("dashboard.view", "actions.view", "meetings.view", "documents.view", "documents.edit", "documents.approve", "compliance.view", "compliance.edit", "jarvis.view"),
    "analyst": _grant("dashboard.view", "projects.view", "actions.view", "meetings.view", "ai_oversight.view"),
    "data_coordinator": _grant("dashboard.view", "documents.view", "documents.edit", "documents.upload", "jarvis.view"),
    "external_org": _grant("actions.view", "actions.edit"),
    "admin": _grant("admin.view", "admin.edit"),
}

LEGACY_ROLE_ALIASES = {
    "director_td": "project_lead",
    "liaison": "external_org",
}


def allowed_by_preset(role: str, area: str, capability: str) -> bool:
    preset = ROLE_PRESETS.get(LEGACY_ROLE_ALIASES.get(role, role), {})
    return capability in preset.get(area, [])


def has_permission(db: Session, user: User, area: str, capability: str) -> bool:
    if area not in AREAS or capability not in CAPABILITIES:
        return False
    key = f"{area}.{capability}"
    override = db.scalar(select(UserPermission).where(UserPermission.user_id == user.id, UserPermission.permission_key == key))
    if override is not None:
        return override.allowed
    preset = db.scalar(select(RolePreset).where(RolePreset.key == user.role))
    permissions = preset.permissions if preset is not None else ROLE_PRESETS.get(LEGACY_ROLE_ALIASES.get(user.role, user.role), {})
    return capability in permissions.get(area, [])


def require_permission(area: str, capability: str) -> Callable[..., User]:
    if area not in AREAS or capability not in CAPABILITIES:
        raise ValueError(f"Unknown permission: {area}.{capability}")

    def permission_dependency(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not has_permission(db, user, area, capability):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account does not have this permission")
        return user

    return permission_dependency
