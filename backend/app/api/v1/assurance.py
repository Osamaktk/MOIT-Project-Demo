import csv
import secrets
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_db, require_roles
from app.db.models import AIRun, AuditEvent, RegisterEntry, SpotCheck, ToolSwitch, User
from app.schemas.assurance import AIRunResponse, ToolSwitchResponse, ToolSwitchUpdate
from app.schemas.spotchecks import SpotCheckResponse, SpotCheckSampleRequest, SpotCheckUpdate
from app.services.audit import add_audit_event
from app.services.register import financial_year_for, next_serial_number

router = APIRouter(prefix="/assurance", tags=["AI assurance"])
READ_ROLES = ("minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin")
CONTROL_ROLES = ("cos", "director_td")
SPOT_READ_ROLES = ("minister", "cos", "director_td", "analyst", "admin")
SPOT_WRITE_ROLES = ("cos", "director_td", "analyst")


@router.get("/tools", response_model=list[ToolSwitchResponse])
def list_tools(db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> list[ToolSwitchResponse]:
    return [ToolSwitchResponse.model_validate(item) for item in db.scalars(select(ToolSwitch).order_by(ToolSwitch.tool)).all()]


@router.patch("/tools/{tool}", response_model=ToolSwitchResponse)
def update_tool(tool: str, payload: ToolSwitchUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*CONTROL_ROLES))) -> ToolSwitchResponse:
    item = db.get(ToolSwitch, tool)
    if item is None:
        raise HTTPException(status_code=404, detail="AI tool was not found")
    before = {"suspended": item.suspended, "reason": item.reason}
    item.suspended = payload.suspended
    item.changed_by = actor.id
    item.changed_at = datetime.now(timezone.utc)
    item.reason = payload.reason.strip()
    add_audit_event(db, actor, request, action="ai_tool_suspended" if item.suspended else "ai_tool_resumed", entity_type="tool_switch", entity_id=tool, before=before, after={"suspended": item.suspended, "reason": item.reason})
    if item.suspended and not before["suspended"]:
        now = datetime.now(timezone.utc)
        fy = financial_year_for(now.date())
        entry = RegisterEntry(
            fy=fy,
            serial_no=next_serial_number(db, fy),
            occurred_at=now,
            occasion_type="file",
            occasion_ref=f"AI assurance control: {tool}",
            description=f"AI tool '{tool}' was suspended by {actor.name}. Reason: {payload.reason.strip()}",
            minister_words=None,
            officer_id=actor.id,
            deadline=now.date(),
            priority="C",
            source_record=f"AI-CONTROL-{now.strftime('%Y%m%d')}-{tool}",
            status="closed",
            closed_at=now,
            closure_note="Administrative control change recorded in the AI assurance log.",
            origin="manual",
            review_state="approved",
        )
        db.add(entry)
        db.flush()
        add_audit_event(db, actor, request, action="ai_tool_suspension_register_log", entity_type="register_entry", entity_id=entry.id, after={"serial_no": entry.serial_no, "fy": entry.fy, "tool": tool})
    db.commit()
    db.refresh(item)
    return ToolSwitchResponse.model_validate(item)


@router.get("/ai-runs", response_model=list[AIRunResponse])
def list_ai_runs(
    tool: str | None = None,
    outcome: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*READ_ROLES)),
) -> list[AIRunResponse]:
    query = select(AIRun).options(joinedload(AIRun.user), joinedload(AIRun.approver))
    if tool:
        query = query.where(AIRun.tool == tool)
    if outcome:
        query = query.where(AIRun.outcome == outcome)
    if created_from:
        query = query.where(AIRun.created_at >= datetime.combine(created_from, time.min, tzinfo=timezone.utc))
    if created_to:
        query = query.where(AIRun.created_at < datetime.combine(created_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    rows = db.scalars(query.order_by(AIRun.created_at.desc()).limit(limit)).all()
    return [AIRunResponse.model_validate({**{column.name: getattr(item, column.name) for column in AIRun.__table__.columns}, "user_name": item.user.name if item.user else None, "approver_name": item.approver.name if item.approver else None}) for item in rows]


@router.get("/ai-runs/export.csv")
def export_ai_runs(db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> Response:
    rows = db.scalars(select(AIRun).order_by(AIRun.created_at.desc())).all()
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("Created at", "Tool", "Model role", "Model", "Zone", "Classification", "Outcome", "Input tokens", "Output tokens", "Latency ms", "Reviewer", "Review time", "Diff summary"))
    for item in rows:
        values = (item.created_at.isoformat(), item.tool, item.model_role, item.model, item.zone, item.classification, item.outcome, item.input_tokens, item.output_tokens, item.latency_ms, item.approver.name if item.approver else None, item.approved_at.isoformat() if item.approved_at else None, item.diff_summary)
        writer.writerow(tuple(_safe_csv(value) for value in values))
    return Response(content="\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=ai-decision-log.csv"})


def _safe_csv(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def spot_check_response(row: SpotCheck) -> SpotCheckResponse:
    return SpotCheckResponse.model_validate({**{column.name: getattr(row, column.name) for column in SpotCheck.__table__.columns}, "reconciler_name": row.reconciler.name if row.reconciler else None, "creator_name": row.creator.name if row.creator else ""})


@router.get("/spot-checks", response_model=list[SpotCheckResponse])
def list_spot_checks(db: Session = Depends(get_db), _: User = Depends(require_roles(*SPOT_READ_ROLES))) -> list[SpotCheckResponse]:
    rows = db.scalars(select(SpotCheck).options(joinedload(SpotCheck.creator), joinedload(SpotCheck.reconciler)).order_by(SpotCheck.period.desc(), SpotCheck.created_at.desc())).all()
    return [spot_check_response(row) for row in rows]


@router.post("/spot-checks", response_model=SpotCheckResponse, status_code=201)
def create_spot_check(payload: SpotCheckSampleRequest, request: Request, period: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), db: Session = Depends(get_db), actor: User = Depends(require_roles(*SPOT_WRITE_ROLES))) -> SpotCheckResponse:
    month = period or datetime.now(timezone.utc).strftime("%Y-%m")
    if db.scalar(select(SpotCheck.id).where(SpotCheck.period == month)):
        raise HTTPException(status_code=409, detail="A spot-check has already been created for this period")
    candidates = db.scalars(select(AIRun).where(AIRun.outcome == "success").order_by(AIRun.created_at.desc())).all()
    sample = secrets.SystemRandom().sample(candidates, min(payload.sample_size, len(candidates))) if candidates else []
    records = [{"run_id": row.id, "tool": row.tool, "model": row.model, "zone": row.zone, "classification": row.classification, "created_at": row.created_at.isoformat(), "reviewed": row.approver_id is not None} for row in sample]
    item = SpotCheck(period=month, sample=records, status="pending", creator_id=actor.id)
    db.add(item)
    db.flush()
    db.add(AuditEvent(actor_id=actor.id, action="spot_check_created", entity_type="spot_check", entity_id=item.id, after_json={"period": month, "sample_size": len(records)}, ip=request.client.host if request.client else None))
    db.commit()
    row = db.scalar(select(SpotCheck).options(joinedload(SpotCheck.creator), joinedload(SpotCheck.reconciler)).where(SpotCheck.id == item.id))
    return spot_check_response(row)


@router.patch("/spot-checks/{item_id}", response_model=SpotCheckResponse)
def reconcile_spot_check(item_id: str, payload: SpotCheckUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*SPOT_WRITE_ROLES))) -> SpotCheckResponse:
    item = db.scalar(select(SpotCheck).options(joinedload(SpotCheck.creator), joinedload(SpotCheck.reconciler)).where(SpotCheck.id == item_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Spot-check was not found")
    before = {"findings": item.findings, "status": item.status, "reconciled_by": item.reconciled_by}
    item.findings = payload.findings.strip()
    item.status = "reviewed"
    item.reconciled_by = actor.id
    db.add(AuditEvent(actor_id=actor.id, action="spot_check_reconciled", entity_type="spot_check", entity_id=item.id, before_json=before, after_json={"findings": item.findings, "status": item.status, "sample_size": len(item.sample)}, ip=request.client.host if request.client else None))
    db.commit()
    row = db.scalar(select(SpotCheck).options(joinedload(SpotCheck.creator), joinedload(SpotCheck.reconciler)).where(SpotCheck.id == item.id))
    return spot_check_response(row)
