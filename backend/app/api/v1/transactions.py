from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.constants import TRANSACTION_STAGE_LABELS
from app.core.deps import get_db, require_roles
from app.db.models import RegisterEntry, Transaction, TransactionEvent, User
from app.schemas.transactions import TransactionCreate, TransactionDetailResponse, TransactionEventCreate, TransactionEventResponse, TransactionResponse, TransactionUpdate
from app.services.audit import add_audit_event

router = APIRouter(prefix="/transactions", tags=["transactions"])
READ_ROLES = ("minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin")
EDIT_ROLES = ("cos", "liaison")


def transaction_snapshot(item: Transaction) -> dict[str, Any]:
    return {"code": item.code, "name": item.name, "sector": item.sector, "stage": item.stage, "next_milestone": item.next_milestone, "next_milestone_date": item.next_milestone_date.isoformat(), "health": item.health, "lead_user_id": item.lead_user_id, "summary": item.summary}


def active_user(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=422, detail="Lead must be an active individual user")
    return user


def get_transaction(db: Session, code: str) -> Transaction:
    item = db.scalar(select(Transaction).options(joinedload(Transaction.lead_user)).where(Transaction.code == code.upper()))
    if item is None:
        raise HTTPException(status_code=404, detail="Transaction was not found")
    return item


@router.get("/stages")
def list_transaction_stages(_: User = Depends(require_roles(*READ_ROLES))) -> list[dict[str, str]]:
    return [{"code": code, "label": label} for code, label in TRANSACTION_STAGE_LABELS.items()]


@router.get("", response_model=dict[str, Any])
def list_transactions(
    q: str | None = None,
    stage: str | None = None,
    health: str | None = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    query = select(Transaction).options(joinedload(Transaction.lead_user))
    if q:
        needle = f"%{q.strip()}%"
        query = query.where(or_(Transaction.code.ilike(needle), Transaction.name.ilike(needle), Transaction.sector.ilike(needle)))
    if stage:
        query = query.where(Transaction.stage == stage)
    if health:
        query = query.where(Transaction.health == health)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.scalars(query.order_by(Transaction.code).offset(offset).limit(limit)).unique().all()
    return {"items": [TransactionResponse.model_validate(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.post("", response_model=TransactionResponse, status_code=201)
def create_transaction(payload: TransactionCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*EDIT_ROLES))) -> TransactionResponse:
    lead = active_user(db, payload.lead_user_id)
    values = payload.model_dump()
    values["lead_user_id"] = lead.id
    item = Transaction(**values, updated_by=actor.id)
    db.add(item)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A transaction with that code already exists") from exc
    add_audit_event(db, actor, request, action="transaction_created", entity_type="transaction", entity_id=item.id, after=transaction_snapshot(item))
    db.commit()
    return TransactionResponse.model_validate(get_transaction(db, item.code))


@router.get("/{code}", response_model=TransactionDetailResponse)
def transaction_detail(code: str, db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> TransactionDetailResponse:
    item = db.scalar(select(Transaction).options(joinedload(Transaction.lead_user), selectinload(Transaction.events)).where(Transaction.code == code.upper()))
    if item is None:
        raise HTTPException(status_code=404, detail="Transaction was not found")
    register_entries = db.scalars(select(RegisterEntry).where(RegisterEntry.transaction_id == item.id, RegisterEntry.review_state == "approved").order_by(RegisterEntry.occurred_at.desc())).all()
    records = [{"id": row.id, "serial_no": row.serial_no, "fy": row.fy, "description": row.description, "deadline": row.deadline, "status": row.status, "officer_id": row.officer_id} for row in register_entries]
    return TransactionDetailResponse.model_validate({**TransactionResponse.model_validate(item).model_dump(), "events": item.events, "register_entries": records})


@router.patch("/{code}", response_model=TransactionResponse)
def update_transaction(code: str, payload: TransactionUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*EDIT_ROLES))) -> TransactionResponse:
    item = get_transaction(db, code)
    before = transaction_snapshot(item)
    changes = payload.model_dump(exclude_unset=True)
    reason = changes.pop("change_reason", None)
    if not reason:
        raise HTTPException(status_code=422, detail="A reason is required for transaction updates")
    if changes.get("lead_user_id"):
        active_user(db, changes["lead_user_id"])
    previous_stage = item.stage
    for field, value in changes.items():
        setattr(item, field, value)
    item.updated_by = actor.id
    after = transaction_snapshot(item)
    if item.stage != previous_stage:
        db.add(TransactionEvent(transaction_id=item.id, occurred_at=datetime.now(timezone.utc), event_type="stage_change", description=f"Stage changed from {TRANSACTION_STAGE_LABELS[previous_stage]} to {TRANSACTION_STAGE_LABELS[item.stage]}", source_ref=reason))
    add_audit_event(db, actor, request, action="transaction_updated", entity_type="transaction", entity_id=item.id, before=before, after=after | {"change_reason": reason})
    db.commit()
    return TransactionResponse.model_validate(get_transaction(db, item.code))


@router.post("/{code}/events", response_model=TransactionEventResponse, status_code=201)
def add_transaction_event(code: str, payload: TransactionEventCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*EDIT_ROLES))) -> TransactionEventResponse:
    item = get_transaction(db, code)
    event = TransactionEvent(transaction_id=item.id, **payload.model_dump())
    db.add(event)
    db.flush()
    add_audit_event(db, actor, request, action="transaction_event_added", entity_type="transaction", entity_id=item.id, after={"event_id": event.id, "event_type": event.event_type, "description": event.description, "source_ref": event.source_ref})
    db.commit()
    return TransactionEventResponse.model_validate(event)
