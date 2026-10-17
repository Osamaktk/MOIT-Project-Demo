from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, User


def add_audit_event(
    db: Session,
    actor: User,
    request: Request,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before,
        after_json=after,
        ip=request.client.host if request.client else None,
    )
    db.add(event)
    return event
