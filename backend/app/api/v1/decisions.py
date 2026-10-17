from datetime import date, datetime, time, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_db, require_roles
from app.db.models import MinisterDecision, Transaction, User
from app.schemas.transactions import MinisterDecisionCreate, MinisterDecisionResponse, MinisterDecisionUpdate
from app.services.audit import add_audit_event

router = APIRouter(prefix="/decisions", tags=["minister decisions"])
READ_ROLES = ("minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin")
WRITE_ROLES = ("cos", "director_td")


def validate_transaction(db: Session, transaction_id: str | None) -> None:
    if transaction_id and db.get(Transaction, transaction_id) is None:
        raise HTTPException(status_code=422, detail="Linked transaction was not found")


def snapshot(item: MinisterDecision) -> dict[str, Any]:
    return {"title": item.title, "due_date": item.due_date.isoformat(), "transaction_id": item.transaction_id, "status": item.status, "context_ref": item.context_ref}


def query_decision(db: Session, decision_id: str) -> MinisterDecision:
    item = db.scalar(select(MinisterDecision).options(joinedload(MinisterDecision.transaction).joinedload(Transaction.lead_user)).where(MinisterDecision.id == decision_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Minister decision was not found")
    return item


@router.get("", response_model=list[MinisterDecisionResponse])
def list_decisions(
    due_from: date | None = None,
    due_to: date | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*READ_ROLES)),
) -> list[MinisterDecisionResponse]:
    query = select(MinisterDecision).options(joinedload(MinisterDecision.transaction).joinedload(Transaction.lead_user))
    if due_from:
        query = query.where(MinisterDecision.due_date >= due_from)
    if due_to:
        query = query.where(MinisterDecision.due_date <= due_to)
    if status:
        query = query.where(MinisterDecision.status == status)
    rows = db.scalars(query.order_by(MinisterDecision.due_date, MinisterDecision.title)).unique().all()
    return [MinisterDecisionResponse.model_validate(row) for row in rows]


@router.post("", response_model=MinisterDecisionResponse, status_code=201)
def create_decision(payload: MinisterDecisionCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*WRITE_ROLES))) -> MinisterDecisionResponse:
    validate_transaction(db, payload.transaction_id)
    item = MinisterDecision(**payload.model_dump(), status="open")
    db.add(item)
    db.flush()
    add_audit_event(db, actor, request, action="minister_decision_created", entity_type="minister_decision", entity_id=item.id, after=snapshot(item))
    db.commit()
    return MinisterDecisionResponse.model_validate(query_decision(db, item.id))


@router.patch("/{decision_id}", response_model=MinisterDecisionResponse)
def update_decision(decision_id: str, payload: MinisterDecisionUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*WRITE_ROLES))) -> MinisterDecisionResponse:
    item = query_decision(db, decision_id)
    before = snapshot(item)
    changes = payload.model_dump(exclude_unset=True)
    validate_transaction(db, changes.get("transaction_id", item.transaction_id))
    for key, value in changes.items():
        setattr(item, key, value)
    add_audit_event(db, actor, request, action="minister_decision_updated", entity_type="minister_decision", entity_id=item.id, before=before, after=snapshot(item))
    db.commit()
    return MinisterDecisionResponse.model_validate(query_decision(db, item.id))
