from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_db, require_roles
from app.db.models import Engagement, Transaction, User
from app.schemas.transactions import EngagementCreate, EngagementResponse, EngagementUpdate
from app.services.audit import add_audit_event

router = APIRouter(prefix="/engagements", tags=["engagements"])
READ_ROLES = ("minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin")
WRITE_ROLES = ("cos", "director_td")


def validate_links(db: Session, owner_id: str, transaction_id: str | None) -> User:
    owner = db.get(User, owner_id)
    if owner is None or not owner.active:
        raise HTTPException(status_code=422, detail="Engagement owner must be an active user")
    if transaction_id and db.get(Transaction, transaction_id) is None:
        raise HTTPException(status_code=422, detail="Linked transaction was not found")
    return owner


def snapshot(item: Engagement) -> dict[str, Any]:
    return {"title": item.title, "engagement_type": item.engagement_type, "starts_at": item.starts_at.isoformat(), "location": item.location, "pack_status": item.pack_status, "pack_due_at": item.pack_due_at.isoformat(), "owner_id": item.owner_id, "transaction_id": item.transaction_id}


def query_engagement(db: Session, engagement_id: str) -> Engagement:
    item = db.scalar(select(Engagement).options(joinedload(Engagement.owner), joinedload(Engagement.transaction).joinedload(Transaction.lead_user)).where(Engagement.id == engagement_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Engagement was not found")
    return item


@router.get("", response_model=list[EngagementResponse])
def list_engagements(
    starts_from: date | None = None,
    starts_to: date | None = None,
    pack_status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*READ_ROLES)),
) -> list[EngagementResponse]:
    query = select(Engagement).options(joinedload(Engagement.owner), joinedload(Engagement.transaction).joinedload(Transaction.lead_user))
    if starts_from:
        query = query.where(Engagement.starts_at >= datetime.combine(starts_from, time.min, tzinfo=timezone.utc))
    if starts_to:
        query = query.where(Engagement.starts_at < datetime.combine(starts_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    if pack_status:
        query = query.where(Engagement.pack_status == pack_status)
    rows = db.scalars(query.order_by(Engagement.starts_at)).unique().all()
    return [EngagementResponse.model_validate(row) for row in rows]


@router.post("", response_model=EngagementResponse, status_code=201)
def create_engagement(payload: EngagementCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*WRITE_ROLES))) -> EngagementResponse:
    owner = validate_links(db, payload.owner_id, payload.transaction_id)
    starts_at = payload.starts_at
    item = Engagement(**payload.model_dump(exclude={"owner_id"}), owner_id=owner.id, pack_due_at=starts_at - timedelta(hours=48))
    db.add(item)
    db.flush()
    add_audit_event(db, actor, request, action="engagement_created", entity_type="engagement", entity_id=item.id, after=snapshot(item))
    db.commit()
    return EngagementResponse.model_validate(query_engagement(db, item.id))


@router.patch("/{engagement_id}", response_model=EngagementResponse)
def update_engagement(engagement_id: str, payload: EngagementUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*WRITE_ROLES))) -> EngagementResponse:
    item = query_engagement(db, engagement_id)
    before = snapshot(item)
    changes = payload.model_dump(exclude_unset=True)
    owner_id = changes.get("owner_id", item.owner_id)
    transaction_id = changes.get("transaction_id", item.transaction_id)
    validate_links(db, owner_id, transaction_id)
    for key, value in changes.items():
        setattr(item, key, value)
    if "starts_at" in changes:
        item.pack_due_at = item.starts_at - timedelta(hours=48)
    add_audit_event(db, actor, request, action="engagement_updated", entity_type="engagement", entity_id=item.id, before=before, after=snapshot(item))
    db.commit()
    return EngagementResponse.model_validate(query_engagement(db, item.id))
