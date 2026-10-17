from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_db, require_roles
from app.db.models import ComplianceItem, User
from app.schemas.compliance import ComplianceCreate, ComplianceResponse, ComplianceUpdate
from app.services.audit import add_audit_event

router = APIRouter(prefix="/compliance", tags=["compliance calendar"])
READ_ROLES = ("minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin")
WRITE_ROLES = ("cos", "legal")


def response(item: ComplianceItem) -> ComplianceResponse:
    return ComplianceResponse.model_validate({**{column.name: getattr(item, column.name) for column in ComplianceItem.__table__.columns}, "owner_name": item.owner.name})


@router.get("", response_model=list[ComplianceResponse])
def list_items(status: str | None = None, category: str | None = None, due_within_days: int | None = Query(default=None, ge=1, le=365), db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> list[ComplianceResponse]:
    query = select(ComplianceItem).options(joinedload(ComplianceItem.owner)).order_by(ComplianceItem.due_date, ComplianceItem.title)
    if status:
        query = query.where(ComplianceItem.status == status)
    if category:
        query = query.where(ComplianceItem.category == category)
    if due_within_days:
        query = query.where(ComplianceItem.due_date >= date.today(), ComplianceItem.due_date <= date.today() + timedelta(days=due_within_days), ComplianceItem.status != "complete")
    return [response(item) for item in db.scalars(query).all()]


@router.get("/due", response_model=list[ComplianceResponse])
def due_fortnight(db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> list[ComplianceResponse]:
    end = date.today() + timedelta(days=14)
    query = select(ComplianceItem).options(joinedload(ComplianceItem.owner)).where(ComplianceItem.due_date >= date.today(), ComplianceItem.due_date <= end, ComplianceItem.status != "complete").order_by(ComplianceItem.due_date)
    return [response(item) for item in db.scalars(query).all()]


@router.post("", response_model=ComplianceResponse, status_code=201)
def create_item(payload: ComplianceCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*WRITE_ROLES))) -> ComplianceResponse:
    owner = db.get(User, payload.owner_id)
    if owner is None or not owner.active:
        raise HTTPException(status_code=422, detail="Select an active owner")
    item = ComplianceItem(**payload.model_dump())
    db.add(item)
    db.flush()
    add_audit_event(db, actor, request, action="compliance_item_created", entity_type="compliance_item", entity_id=item.id, after=payload.model_dump(mode="json"))
    db.commit()
    return response(db.scalar(select(ComplianceItem).options(joinedload(ComplianceItem.owner)).where(ComplianceItem.id == item.id)))


@router.patch("/{item_id}", response_model=ComplianceResponse)
def update_item(item_id: str, payload: ComplianceUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*WRITE_ROLES))) -> ComplianceResponse:
    item = db.scalar(select(ComplianceItem).options(joinedload(ComplianceItem.owner)).where(ComplianceItem.id == item_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Compliance item was not found")
    before = {key: getattr(item, key) for key in payload.model_fields_set}
    changes = payload.model_dump(exclude_unset=True)
    if "owner_id" in changes:
        owner = db.get(User, changes["owner_id"]) if changes["owner_id"] else None
        if owner is None or not owner.active:
            raise HTTPException(status_code=422, detail="Select an active owner")
    for key, value in changes.items():
        setattr(item, key, value)
    add_audit_event(db, actor, request, action="compliance_item_updated", entity_type="compliance_item", entity_id=item.id, before=before, after=changes)
    db.commit()
    return response(db.scalar(select(ComplianceItem).options(joinedload(ComplianceItem.owner)).where(ComplianceItem.id == item.id)))
