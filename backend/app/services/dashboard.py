from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.constants import TRANSACTION_STAGES
from app.db.models import Engagement, MinisterDecision, RegisterEntry, Transaction
from app.services.register import is_overdue


def week_ending_default(today: date | None = None) -> date:
    current = today or datetime.now(timezone.utc).date()
    days_until_friday = (4 - current.weekday()) % 7
    if days_until_friday == 0:
        days_until_friday = 7
    return current + timedelta(days=days_until_friday)


def week_window(week_ending: date | None) -> tuple[date, date]:
    end = week_ending or week_ending_default()
    return end - timedelta(days=6), end


def in_date_window(column: Any, start: date, end: date) -> Any:
    start_at = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_exclusive = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return (column >= start_at) & (column < end_exclusive)


def dashboard_summary(db: Session, week_ending: date | None) -> dict[str, Any]:
    start, end = week_window(week_ending)
    now = datetime.now(timezone.utc)
    transactions = db.scalars(select(Transaction).options(joinedload(Transaction.lead_user)).order_by(Transaction.next_milestone_date, Transaction.code)).all()
    decisions = db.scalars(select(MinisterDecision).options(joinedload(MinisterDecision.transaction)).where(
        MinisterDecision.due_date >= start,
        MinisterDecision.due_date <= end,
        MinisterDecision.status != "closed",
    ).order_by(MinisterDecision.due_date)).all()
    overdue = db.scalars(select(RegisterEntry).options(joinedload(RegisterEntry.officer)).where(
        RegisterEntry.review_state == "approved",
        RegisterEntry.deadline < now.date(),
        RegisterEntry.status.not_in(("closed", "closed_with_note")),
    ).order_by(RegisterEntry.deadline, RegisterEntry.officer_id)).all()
    engagements = db.scalars(select(Engagement).options(joinedload(Engagement.owner), joinedload(Engagement.transaction)).where(
        in_date_window(Engagement.starts_at, start, end),
    ).order_by(Engagement.starts_at)).all()
    stage_counts = {stage: 0 for stage, _ in TRANSACTION_STAGES}
    for transaction in transactions:
        stage_counts[transaction.stage] = stage_counts.get(transaction.stage, 0) + 1
    next_milestones = sorted(transactions, key=lambda item: (item.next_milestone_date, item.code))[:8]
    return {
        "week_starting": start,
        "week_ending": end,
        "kpis": {
            "transactions_in_process": db.scalar(select(func.count()).select_from(Transaction)) or 0,
            "decisions_due_this_week": len(decisions),
            "actions_overdue": len(overdue),
            "engagements_this_week": len(engagements),
        },
        "transactions_by_stage": [{"stage": code, "label": label, "count": stage_counts.get(code, 0)} for code, label in TRANSACTION_STAGES],
        "next_milestones": [transaction_summary(item) for item in next_milestones],
        "decisions_due": [decision_summary(item) for item in decisions],
        "overdue_actions": [register_summary(item) for item in overdue],
        "upcoming_engagements": [engagement_summary(item, now) for item in engagements],
        "last_refreshed": now,
        "source_note": "Transactions, minister decisions, engagements, and approved Register entries.",
    }


def transaction_summary(item: Transaction) -> dict[str, Any]:
    return {"id": item.id, "code": item.code, "name": item.name, "sector": item.sector, "stage": item.stage, "next_milestone": item.next_milestone, "next_milestone_date": item.next_milestone_date, "health": item.health}


def decision_summary(item: MinisterDecision) -> dict[str, Any]:
    return {"id": item.id, "title": item.title, "due_date": item.due_date, "status": item.status, "context_ref": item.context_ref, "transaction_id": item.transaction_id, "transaction_code": item.transaction.code if item.transaction else None}


def register_summary(item: RegisterEntry) -> dict[str, Any]:
    return {"id": item.id, "serial_no": item.serial_no, "fy": item.fy, "description": item.description, "officer_id": item.officer_id, "officer_name": item.officer.name, "deadline": item.deadline, "priority": item.priority, "status": item.status, "overdue": is_overdue(item)}


def engagement_summary(item: Engagement, now: datetime) -> dict[str, Any]:
    pack_due_at = item.pack_due_at
    if pack_due_at.tzinfo is None:
        pack_due_at = pack_due_at.replace(tzinfo=timezone.utc)
    return {"id": item.id, "title": item.title, "engagement_type": item.engagement_type, "starts_at": item.starts_at, "location": item.location, "pack_status": item.pack_status, "pack_due_at": item.pack_due_at, "pack_at_risk": item.pack_status != "ready" and pack_due_at < now, "owner_id": item.owner_id, "owner_name": item.owner.name, "transaction_id": item.transaction_id, "transaction_code": item.transaction.code if item.transaction else None}


def drill_down(db: Session, kpi: str, week_ending: date | None, stage: str | None) -> dict[str, Any]:
    start, end = week_window(week_ending)
    if kpi in {"transactions", "transactions_in_process"}:
        query = select(Transaction).order_by(Transaction.code)
        if stage:
            query = query.where(Transaction.stage == stage)
        rows = db.scalars(query).all()
        records = [{"record_type": "transaction", "id": item.id, "label": f"{item.code} · {item.name}", "code": item.code} for item in rows]
    elif kpi == "transactions_by_stage":
        if stage is None:
            raise HTTPException(status_code=422, detail="A transaction stage is required for this drill-down")
        rows = db.scalars(select(Transaction).where(Transaction.stage == stage).order_by(Transaction.code)).all()
        records = [{"record_type": "transaction", "id": item.id, "label": f"{item.code} · {item.name}", "code": item.code} for item in rows]
    elif kpi in {"decisions_due", "decisions_due_this_week"}:
        rows = db.scalars(select(MinisterDecision).where(MinisterDecision.due_date >= start, MinisterDecision.due_date <= end, MinisterDecision.status != "closed").order_by(MinisterDecision.due_date)).all()
        records = [{"record_type": "minister_decision", "id": item.id, "label": item.title, "due_date": item.due_date} for item in rows]
    elif kpi in {"actions_overdue", "overdue_actions"}:
        rows = db.scalars(select(RegisterEntry).options(joinedload(RegisterEntry.officer)).where(RegisterEntry.review_state == "approved", RegisterEntry.deadline < date.today(), RegisterEntry.status.not_in(("closed", "closed_with_note"))).order_by(RegisterEntry.deadline, RegisterEntry.serial_no)).all()
        records = [{"record_type": "register_entry", "id": item.id, "label": f"{item.fy}/{item.serial_no:03d} · {item.description}", "officer": item.officer.name, "deadline": item.deadline} for item in rows]
    elif kpi in {"engagements", "engagements_this_week"}:
        rows = db.scalars(select(Engagement).where(in_date_window(Engagement.starts_at, start, end)).order_by(Engagement.starts_at)).all()
        records = [{"record_type": "engagement", "id": item.id, "label": item.title, "starts_at": item.starts_at} for item in rows]
    else:
        raise HTTPException(status_code=404, detail="Dashboard drill-down was not found")
    return {"kpi": kpi, "week_starting": start, "week_ending": end, "total": len(records), "records": records}
