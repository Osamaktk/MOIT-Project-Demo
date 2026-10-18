from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import require_permission
from app.db.models import Action, Organisation, Project, User
from app.db.session import get_db
from app.schemas.domain import ActionCreate, ActionView, OrganisationView, ProjectCreate, ProjectView
from app.services.audit import add_audit_event
from app.services.domain import approve_action, create_action_proposal
from app.services.project_rules import recompute_project_health

router = APIRouter(tags=["MoITT projects, actions, and organisations"])


@router.get("/organisations", response_model=list[OrganisationView])
def list_organisations(db: Session = Depends(get_db), _: User = Depends(require_permission("projects", "view"))) -> list[Organisation]:
    return list(db.scalars(select(Organisation).order_by(Organisation.short_name)))


@router.get("/projects", response_model=list[ProjectView])
def list_projects(db: Session = Depends(get_db), _: User = Depends(require_permission("projects", "view"))) -> list[Project]:
    return list(db.scalars(select(Project).options(joinedload(Project.lead_org)).order_by(Project.name)))


@router.get("/projects/{code}", response_model=ProjectView)
def get_project(code: str, db: Session = Depends(get_db), _: User = Depends(require_permission("projects", "view"))) -> Project:
    project = db.scalar(select(Project).options(joinedload(Project.lead_org)).where(Project.code == code))
    if project is None:
        raise HTTPException(status_code=404, detail="Project was not found")
    return project


@router.post("/projects", response_model=ProjectView, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_permission("projects", "edit"))) -> Project:
    if db.scalar(select(Project.id).where(Project.code == payload.code)) is not None:
        raise HTTPException(status_code=409, detail="A project with that code already exists")
    if payload.lead_org_id and db.get(Organisation, payload.lead_org_id) is None:
        raise HTTPException(status_code=422, detail="Lead organisation was not found")
    project = Project(**payload.model_dump(), health="on_track", health_reason="No overdue actions or near-term unmet commitments.")
    db.add(project)
    db.flush()
    recompute_project_health(db, project)
    add_audit_event(db, actor, request, action="project_created", entity_type="project", entity_id=project.id, after={"code": project.code, "name": project.name, "stage": project.stage, "lead_org_id": project.lead_org_id})
    db.commit()
    return project


@router.get("/actions", response_model=list[ActionView])
def list_actions(db: Session = Depends(get_db), user: User = Depends(require_permission("actions", "view"))) -> list[Action]:
    query = select(Action).options(joinedload(Action.owner_org))
    if user.role == "external_org":
        if user.organisation_id is None:
            return []
        query = query.where(Action.owner_org_id == user.organisation_id)
    return list(db.scalars(query.order_by(Action.fy.desc(), Action.serial_no, Action.created_at.desc())))


@router.post("/actions", response_model=ActionView, status_code=status.HTTP_201_CREATED)
def propose_action(payload: ActionCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_permission("actions", "edit"))) -> Action:
    action = create_action_proposal(db, payload)
    add_audit_event(db, actor, request, action="action_proposed", entity_type="action", entity_id=action.id, after={"description": action.description, "owner_org_id": action.owner_org_id, "owner_person_name": action.owner_person_name, "project_id": action.project_id, "review_state": action.review_state})
    db.commit()
    return action


@router.post("/actions/{action_id}/confirm", response_model=ActionView)
def confirm_action(action_id: str, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_permission("actions", "approve"))) -> Action:
    action = db.get(Action, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action was not found")
    approve_action(db, action)
    add_audit_event(db, actor, request, action="action_confirmed", entity_type="action", entity_id=action.id, after={"fy": action.fy, "serial_no": action.serial_no, "review_state": action.review_state})
    db.commit()
    return action
