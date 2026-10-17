from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, joinedload

from app.db.models import AuditEvent, RegisterEntry, RegisterSerialCounter, User
from app.schemas.register import RegisterCreate, RegisterUpdate


def financial_year_for(day: date) -> str:
    start_year = day.year if day.month >= 7 else day.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def next_serial_number(db: Session, fy: str) -> int:
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        statement = sqlite_insert(RegisterSerialCounter).values(fy=fy, last_serial=0).on_conflict_do_nothing(index_elements=[RegisterSerialCounter.fy])
    elif dialect == "postgresql":
        statement = pg_insert(RegisterSerialCounter).values(fy=fy, last_serial=0).on_conflict_do_nothing(index_elements=[RegisterSerialCounter.fy])
    else:
        raise RuntimeError(f"Register serial allocation is not supported for database dialect: {dialect}")
    db.execute(statement)
    next_value = db.scalar(
        update(RegisterSerialCounter)
        .where(RegisterSerialCounter.fy == fy)
        .values(last_serial=RegisterSerialCounter.last_serial + 1)
        .returning(RegisterSerialCounter.last_serial)
    )
    if next_value is None:
        raise RuntimeError("Could not allocate a Register serial number")
    return next_value


def snapshot(entry: RegisterEntry) -> dict[str, Any]:
    return {
        "serial_no": entry.serial_no,
        "fy": entry.fy,
        "occurred_at": entry.occurred_at.isoformat(),
        "occasion_type": entry.occasion_type,
        "occasion_ref": entry.occasion_ref,
        "description": entry.description,
        "minister_words": entry.minister_words,
        "officer_id": entry.officer_id,
        "deadline": entry.deadline.isoformat(),
        "priority": entry.priority,
        "source_record": entry.source_record,
        "status": entry.status,
        "transaction_id": entry.transaction_id,
        "origin": entry.origin,
        "review_state": entry.review_state,
    }


def is_overdue(entry: RegisterEntry, *, as_of: date | None = None) -> bool:
    return entry.review_state == "approved" and entry.status not in {"closed", "closed_with_note"} and entry.deadline < (as_of or datetime.now(timezone.utc).date())


def get_entry(db: Session, entry_id: str) -> RegisterEntry:
    entry = db.scalar(select(RegisterEntry).options(joinedload(RegisterEntry.officer)).where(RegisterEntry.id == entry_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Register entry was not found")
    return entry


def validate_officer(db: Session, officer_id: str) -> User:
    officer = db.get(User, officer_id)
    if officer is None or not officer.active:
        raise HTTPException(status_code=422, detail="Officer must be an active individual user")
    return officer


def create_manual_entry(db: Session, payload: RegisterCreate) -> RegisterEntry:
    officer = validate_officer(db, payload.officer_id)
    if payload.deadline < payload.occurred_at.date():
        raise HTTPException(status_code=422, detail="Deadline cannot be earlier than the instruction date")
    fy = financial_year_for(payload.occurred_at.date())
    entry = RegisterEntry(
        serial_no=next_serial_number(db, fy),
        fy=fy,
        occurred_at=payload.occurred_at,
        occasion_type=payload.occasion_type,
        occasion_ref=payload.occasion_ref,
        description=payload.description.strip(),
        minister_words=payload.minister_words,
        officer_id=officer.id,
        deadline=payload.deadline,
        priority=payload.priority,
        source_record=payload.source_record,
        transaction_id=payload.transaction_id,
        origin="manual",
        review_state="approved",
        status="open",
    )
    db.add(entry)
    db.flush()
    return entry


def update_entry(db: Session, entry: RegisterEntry, payload: RegisterUpdate) -> tuple[RegisterEntry, dict[str, Any]]:
    before = snapshot(entry)
    changes = payload.model_dump(exclude_unset=True)
    reason = changes.pop("change_reason", None)
    new_officer = changes.get("officer_id")
    if new_officer is not None and new_officer != entry.officer_id:
        if not reason:
            raise HTTPException(status_code=422, detail="A reason is required when reassigning an officer")
        validate_officer(db, new_officer)
    if changes.get("deadline") and changes["deadline"] < entry.occurred_at.date():
        raise HTTPException(status_code=422, detail="Deadline cannot be earlier than the instruction date")
    new_status = changes.pop("status", None)
    if new_status is not None and new_status != entry.status:
        allowed = {"open": {"in_progress"}, "in_progress": {"closed", "closed_with_note"}, "closed": set(), "closed_with_note": set()}
        if new_status not in allowed[entry.status]:
            raise HTTPException(status_code=409, detail=f"Invalid status transition: {entry.status} to {new_status}")
        if new_status == "closed_with_note" and not changes.get("closure_note", entry.closure_note):
            raise HTTPException(status_code=422, detail="A closure note is required to close with a note")
        entry.status = new_status
        if new_status in {"closed", "closed_with_note"}:
            entry.closed_at = datetime.now(timezone.utc)
    if "closure_note" in changes:
        if entry.status != "closed_with_note" and changes["closure_note"]:
            raise HTTPException(status_code=422, detail="Closure notes are only used with closed_with_note status")
        entry.closure_note = changes["closure_note"]
    for field in ("description", "minister_words", "officer_id", "deadline", "priority", "source_record", "transaction_id"):
        if field in changes:
            setattr(entry, field, changes[field])
    db.flush()
    return entry, {"before": before, "after": snapshot(entry), "change_reason": reason}


def approve_proposal(db: Session, entry: RegisterEntry) -> tuple[RegisterEntry, dict[str, Any]]:
    if entry.review_state != "proposed":
        raise HTTPException(status_code=409, detail="Only proposed entries can be approved")
    validate_officer(db, entry.officer_id)
    if entry.serial_no is not None:
        raise HTTPException(status_code=409, detail="A proposed item already has a serial number")
    before = snapshot(entry)
    entry.serial_no = next_serial_number(db, entry.fy)
    entry.review_state = "approved"
    db.flush()
    return entry, {"before": before, "after": snapshot(entry)}


def reject_proposal(db: Session, entry: RegisterEntry, reason: str) -> tuple[RegisterEntry, dict[str, Any]]:
    if entry.review_state != "proposed":
        raise HTTPException(status_code=409, detail="Only proposed entries can be rejected")
    before = snapshot(entry)
    entry.review_state = "rejected"
    db.flush()
    return entry, {"before": before, "after": snapshot(entry), "reason": reason}


def audit_history(db: Session, entry_id: str) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).options(joinedload(AuditEvent.actor)).where(AuditEvent.entity_type == "register_entry", AuditEvent.entity_id == entry_id).order_by(AuditEvent.at.desc())))
