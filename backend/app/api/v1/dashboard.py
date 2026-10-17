from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.db.models import User
from app.services.dashboard import dashboard_summary, drill_down

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
READ_ROLES = ("minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin")


@router.get("")
def get_dashboard(week_ending: date | None = None, db: Session = Depends(get_db), _: User = Depends(require_roles(*READ_ROLES))) -> dict[str, Any]:
    return dashboard_summary(db, week_ending)


@router.get("/drill/{kpi}")
def get_dashboard_drill(
    kpi: str,
    week_ending: date | None = None,
    stage: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    return drill_down(db, kpi, week_ending, stage)
