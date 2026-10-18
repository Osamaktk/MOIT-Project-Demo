from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Action, Organisation, Project, RegisterSerialCounter, User
from app.schemas.domain import ActionCreate
from app.services.project_rules import normalize_deadline
from app.services.register import financial_year_for, next_serial_number


def create_action_proposal(db: Session, payload: ActionCreate) -> Action:
    if not payload.owner_org_id and not (payload.owner_person_name or "").strip():
        raise HTTPException(status_code=422, detail="An owner organisation or named person is required")
    if payload.owner_org_id and db.get(Organisation, payload.owner_org_id) is None:
        raise HTTPException(status_code=422, detail="Owner organisation was not found")
    if payload.owner_user_id and db.get(User, payload.owner_user_id) is None:
        raise HTTPException(status_code=422, detail="Owner user was not found")
    if payload.project_id and db.get(Project, payload.project_id) is None:
        raise HTTPException(status_code=422, detail="Project was not found")

    deadline = payload.deadline
    precision = payload.deadline_precision
    if deadline is None:
        resolution = normalize_deadline(payload.deadline_text, payload.occurred_at.date())
        deadline, precision = resolution.resolved_date, resolution.precision

    action = Action(
        fy=financial_year_for(payload.occurred_at.date()),
        serial_no=None,
        description=payload.description.strip(),
        owner_org_id=payload.owner_org_id,
        owner_person_name=(payload.owner_person_name or "").strip() or None,
        owner_user_id=payload.owner_user_id,
        occurred_at=payload.occurred_at,
        deadline=deadline,
        deadline_text=payload.deadline_text.strip(),
        deadline_precision=precision,
        priority=payload.priority,
        status="closed" if payload.status_source == "done_at_upload" else "open",
        status_source=payload.status_source,
        review_state="proposed",
        origin="manual",
        project_id=payload.project_id,
        source_document_id=payload.source_document_id,
        source_quote=payload.source_quote,
        source_page=payload.source_page,
    )
    db.add(action)
    db.flush()
    return action


def approve_action(db: Session, action: Action) -> Action:
    if action.review_state != "proposed":
        raise HTTPException(status_code=409, detail="Only proposed actions can be confirmed")
    if not action.owner_org_id and not (action.owner_person_name or "").strip():
        raise HTTPException(status_code=422, detail="An owner organisation or named person is required")
    if action.deadline is None:
        raise HTTPException(status_code=422, detail="Resolve the deadline before confirming this action")
    action.serial_no = next_serial_number(db, action.fy)
    action.review_state = "approved"
    action.updated_at = datetime.now(timezone.utc)
    db.flush()
    return action
