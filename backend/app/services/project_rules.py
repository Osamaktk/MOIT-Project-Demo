from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Action, Commitment, Project

MONTHS = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): index for index, name in enumerate(calendar.month_abbr) if name})


@dataclass(frozen=True)
class DeadlineResolution:
    resolved_date: date | None
    precision: str
    needs_input: bool = False


def _add_workdays(start: date, count: int) -> date:
    current = start
    added = 0
    while added < count:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def normalize_deadline(
    text: str,
    meeting_date: date,
    *,
    next_meeting: date | None = None,
    mobilization_date: date | None = None,
) -> DeadlineResolution:
    original = " ".join(text.strip().lower().replace(",", " ").split())
    if not original:
        return DeadlineResolution(None, "relative", True)
    if original == "today":
        return DeadlineResolution(meeting_date, "day")
    if original == "immediate":
        return DeadlineResolution(_add_workdays(meeting_date, 2), "relative")
    if original in {"next meeting", "by the next meeting"}:
        return DeadlineResolution(next_meeting, "relative", next_meeting is None)

    week = re.search(r"first week of ([a-z]+)\s+(\d{4})", original)
    if week and week.group(1) in MONTHS:
        month = MONTHS[week.group(1)]
        return DeadlineResolution(date(int(week.group(2)), month, min(7, calendar.monthrange(int(week.group(2)), month)[1])), "week")

    relative = re.search(r"(?:within\s+)?(\d+)\s+days?(?:\s+from\s+(?:contractor\s+)?mobilization)?", original)
    if relative:
        anchor = mobilization_date if "mobilization" in original else meeting_date
        if "mobilization" in original and anchor is None:
            return DeadlineResolution(None, "relative", True)
        return DeadlineResolution(anchor + timedelta(days=int(relative.group(1))), "relative")

    iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", original)
    if iso:
        try:
            return DeadlineResolution(date(*(int(part) for part in iso.groups())), "day")
        except ValueError:
            return DeadlineResolution(None, "day", True)

    explicit = re.fullmatch(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", original)
    if explicit and explicit.group(2) in MONTHS:
        try:
            return DeadlineResolution(date(int(explicit.group(3)), MONTHS[explicit.group(2)], int(explicit.group(1))), "day")
        except ValueError:
            return DeadlineResolution(None, "day", True)

    month = re.fullmatch(r"([a-z]+)\s+(\d{4})", original)
    if month and month.group(1) in MONTHS:
        return DeadlineResolution(date(int(month.group(2)), MONTHS[month.group(1)], 1), "month")
    return DeadlineResolution(None, "relative", True)


def recompute_project_health(db: Session, project: Project, *, as_of: date | None = None) -> tuple[str, str]:
    today = as_of or date.today()
    actions = list(db.scalars(select(Action).where(Action.project_id == project.id, Action.review_state == "approved")))
    commitments = list(db.scalars(select(Commitment).where(Commitment.project_id == project.id)))
    overdue_actions = [action for action in actions if action.status not in {"closed", "closed_with_note"} and action.deadline < today]
    delayed_commitments = [item for item in commitments if item.status == "pending" and item.due_date is not None and item.due_date < today]
    critical_actions_late = [action for action in overdue_actions if action.priority == "A" and (today - action.deadline).days > 14]
    near_commitments = [item for item in commitments if item.status == "pending" and item.due_date is not None and 0 <= (item.due_date - today).days <= 30]
    has_progress = any(action.status in {"in_progress", "closed", "closed_with_note"} for action in actions)

    if delayed_commitments or critical_actions_late:
        health = "delayed"
    elif overdue_actions or (near_commitments and not has_progress):
        health = "at_risk"
    else:
        health = "on_track"

    reasons: list[str] = []
    if delayed_commitments:
        reasons.append(f"{len(delayed_commitments)} commitment(s) overdue")
    if critical_actions_late:
        reasons.append(f"{len(critical_actions_late)} critical action(s) more than 14 days overdue")
    if overdue_actions and not critical_actions_late:
        reasons.append(f"{len(overdue_actions)} action(s) overdue")
    if near_commitments and not has_progress:
        reasons.append(f"{len(near_commitments)} commitment(s) due within 30 days with no progress action")
    reason = "; ".join(reasons) if reasons else "No overdue actions or near-term unmet commitments."
    project.health, project.health_reason = health, reason
    return health, reason
