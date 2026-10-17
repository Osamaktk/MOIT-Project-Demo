import csv
from datetime import date, datetime, timezone
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, get_db, require_roles
from app.db.models import AIRun, RegisterEntry, User
from app.schemas.register import AuditResponse, PaginatedRegisterResponse, RegisterCreate, RegisterReject, RegisterResponse, RegisterUpdate
from app.services.audit import add_audit_event
from app.services.register import audit_history, approve_proposal, create_manual_entry, get_entry, is_overdue, reject_proposal, update_entry

router = APIRouter(prefix="/register", tags=["register"])
READ_ROLES = ("minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin")
WRITE_ROLES = ("cos", "director_td")


def serialize_entry(entry: RegisterEntry) -> RegisterResponse:
    data = {column.key: getattr(entry, column.key) for column in RegisterEntry.__table__.columns}
    data.update(officer=entry.officer, overdue=is_overdue(entry))
    return RegisterResponse.model_validate(data)


def safe_csv(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> Response:
    rows = db.scalars(select(RegisterEntry).options(joinedload(RegisterEntry.officer)).where(RegisterEntry.review_state == "approved").order_by(RegisterEntry.fy, RegisterEntry.serial_no)).all()
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("FY", "Serial", "Occurred at", "Occasion", "Description", "Officer", "Deadline", "Priority", "Status", "Overdue", "Source record", "Transaction"))
    for entry in rows:
        writer.writerow(tuple(safe_csv(value) for value in (
            entry.fy, entry.serial_no, entry.occurred_at.isoformat(), entry.occasion_type,
            entry.description, entry.officer.name, entry.deadline.isoformat(), entry.priority,
            entry.status, "Yes" if is_overdue(entry) else "No", entry.source_record, entry.transaction_id,
        )))
    return Response(content="\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=decision-action-register.csv"})


@router.get("/overdue")
def list_overdue(db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> dict[str, object]:
    rows = db.scalars(select(RegisterEntry).options(joinedload(RegisterEntry.officer)).where(
        RegisterEntry.review_state == "approved",
        RegisterEntry.deadline < datetime.now(timezone.utc).date(),
        RegisterEntry.status.not_in(("closed", "closed_with_note")),
    ).order_by(RegisterEntry.officer_id, RegisterEntry.deadline)).all()
    grouped: dict[str, dict[str, object]] = {}
    for entry in rows:
        key = entry.officer_id
        if key not in grouped:
            grouped[key] = {"officer": {"id": entry.officer.id, "name": entry.officer.name, "designation": entry.officer.designation}, "entries": []}
        grouped[key]["entries"].append(serialize_entry(entry))  # type: ignore[union-attr]
    return {"groups": list(grouped.values()), "total": len(rows)}


@router.get("/officers")
def list_officers(db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> list[dict[str, str]]:
    users = db.scalars(select(User).where(User.active.is_(True)).order_by(User.name)).all()
    return [{"id": user.id, "name": user.name, "designation": user.designation, "role": user.role} for user in users]


@router.get("", response_model=PaginatedRegisterResponse)
def list_register(
    q: str | None = None,
    status: str | None = None,
    priority: str | None = Query(default=None, pattern="^[ABC]$"),
    officer_id: str | None = None,
    transaction_id: str | None = None,
    origin: str | None = Query(default=None, pattern="^(manual|ai_proposed)$"),
    overdue: bool | None = None,
    review_state: str = Query(default="approved", pattern="^(approved|proposed|rejected|all)$"),
    occurred_from: date | None = None,
    occurred_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
) -> PaginatedRegisterResponse:
    if review_state in {"proposed", "rejected", "all"} and user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Only Register reviewers can view unapproved proposals")
    query = select(RegisterEntry).options(joinedload(RegisterEntry.officer))
    if review_state != "all":
        query = query.where(RegisterEntry.review_state == review_state)
    if q:
        needle = f"%{q.strip()}%"
        query = query.join(RegisterEntry.officer).where(or_(RegisterEntry.description.ilike(needle), RegisterEntry.minister_words.ilike(needle), RegisterEntry.source_record.ilike(needle), User.name.ilike(needle)))
    if status:
        query = query.where(RegisterEntry.status == status)
    if priority:
        query = query.where(RegisterEntry.priority == priority)
    if officer_id:
        query = query.where(RegisterEntry.officer_id == officer_id)
    if transaction_id:
        query = query.where(RegisterEntry.transaction_id == transaction_id)
    if origin:
        query = query.where(RegisterEntry.origin == origin)
    if occurred_from:
        query = query.where(RegisterEntry.occurred_at >= datetime.combine(occurred_from, datetime.min.time(), tzinfo=timezone.utc))
    if occurred_to:
        query = query.where(RegisterEntry.occurred_at < datetime.combine(occurred_to, datetime.max.time(), tzinfo=timezone.utc))
    if overdue is True:
        query = query.where(RegisterEntry.deadline < date.today(), RegisterEntry.status.not_in(("closed", "closed_with_note")))
    elif overdue is False:
        query = query.where(or_(RegisterEntry.deadline >= date.today(), RegisterEntry.status.in_(("closed", "closed_with_note"))))
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    entries = db.scalars(query.order_by(RegisterEntry.occurred_at.desc(), RegisterEntry.serial_no.desc()).offset(offset).limit(limit)).unique().all()
    return PaginatedRegisterResponse(items=[serialize_entry(entry) for entry in entries], total=total, limit=limit, offset=offset)


@router.post("", response_model=RegisterResponse, status_code=201)
def create_register_entry(
    payload: RegisterCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*WRITE_ROLES)),
) -> RegisterResponse:
    entry = create_manual_entry(db, payload)
    add_audit_event(db, actor, request, action="register_created", entity_type="register_entry", entity_id=entry.id, after={"record": {"serial_no": entry.serial_no, "fy": entry.fy, "description": entry.description, "status": entry.status}})
    db.commit()
    return serialize_entry(get_entry(db, entry.id))


@router.get("/{entry_id}", response_model=RegisterResponse)
def get_register_entry(entry_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> RegisterResponse:
    return serialize_entry(get_entry(db, entry_id))


@router.patch("/{entry_id}", response_model=RegisterResponse)
def patch_register_entry(entry_id: str, payload: RegisterUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*WRITE_ROLES))) -> RegisterResponse:
    entry = get_entry(db, entry_id)
    updated, change = update_entry(db, entry, payload)
    add_audit_event(db, actor, request, action="register_updated", entity_type="register_entry", entity_id=entry.id, before=change["before"], after=change["after"] | ({"change_reason": change["change_reason"]} if change.get("change_reason") else {}))
    db.commit()
    return serialize_entry(get_entry(db, updated.id))


@router.post("/{entry_id}/approve", response_model=RegisterResponse)
def approve_register_proposal(entry_id: str, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*WRITE_ROLES))) -> RegisterResponse:
    entry = get_entry(db, entry_id)
    entry, change = approve_proposal(db, entry)
    run_id = (entry.ai_assistance or {}).get("run_id")
    run = db.get(AIRun, run_id) if run_id else None
    if run is not None:
        run.approver_id = actor.id
        run.approved_at = datetime.now(timezone.utc)
        run.diff_summary = "AI proposal approved without edits."
    add_audit_event(db, actor, request, action="register_proposal_approved", entity_type="register_entry", entity_id=entry.id, before=change["before"], after=change["after"])
    db.commit()
    return serialize_entry(get_entry(db, entry.id))


@router.post("/{entry_id}/reject", response_model=RegisterResponse)
def reject_register_proposal(entry_id: str, payload: RegisterReject, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*WRITE_ROLES))) -> RegisterResponse:
    entry = get_entry(db, entry_id)
    entry, change = reject_proposal(db, entry, payload.reason)
    run_id = (entry.ai_assistance or {}).get("run_id")
    run = db.get(AIRun, run_id) if run_id else None
    if run is not None:
        run.approver_id = actor.id
        run.approved_at = datetime.now(timezone.utc)
        run.diff_summary = f"AI proposal rejected. Reason: {payload.reason.strip()}"
    add_audit_event(db, actor, request, action="register_proposal_rejected", entity_type="register_entry", entity_id=entry.id, before=change["before"], after=change["after"] | {"reason": change["reason"]})
    db.commit()
    return serialize_entry(get_entry(db, entry.id))


@router.get("/{entry_id}/audit", response_model=list[AuditResponse])
def get_register_audit(entry_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> list[AuditResponse]:
    get_entry(db, entry_id)
    return [AuditResponse(id=event.id, actor_id=event.actor_id, actor_name=event.actor.name if event.actor else None, action=event.action, before=event.before_json, after=event.after_json, ip=event.ip, at=event.at) for event in audit_history(db, entry_id)]
