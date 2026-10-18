from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import require_roles
from app.core.permissions import require_permission
from app.db.models import Action, Commitment, Document, IntakeReview, Meeting, Organisation, Project, ToolSwitch, User
from app.db.session import get_db
from app.schemas.intake import CloudPermission, IntakeEdit, IntakeExtraction, IntakeView
from app.services.audit import add_audit_event
from app.services.domain import approve_action
from app.services.intake import extract_document, extract_intake_pages
from app.services.intake import enrich_extraction
from app.services.project_rules import normalize_deadline, recompute_project_health
from app.services.records_search import index_intake_document

router = APIRouter(prefix="/api/v1/intake", tags=["document intake and review"])
EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
CLASSIFICATIONS = {"public", "internal", "confidential"}
COS_EMAIL = "ps@moitt.demo"


def _view(review: IntakeReview, duplicate: bool = False) -> IntakeView:
    return IntakeView(id=review.id, document_id=review.document_id, status=review.status, doc_kind=review.doc_kind, payload=review.payload, warnings=review.warnings, diff_summary=review.diff_summary, duplicate=duplicate)


@router.post("", response_model=IntakeView, status_code=201)
async def upload_for_review(
    request: Request,
    file: UploadFile = File(...),
    classification: str = Form("internal"),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("documents", "upload")),
) -> IntakeView:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in EXTENSIONS:
        raise HTTPException(status_code=415, detail="Upload a PDF, DOCX, TXT, MD, or image file")
    if classification not in CLASSIFICATIONS:
        raise HTTPException(status_code=422, detail="Select public, internal, or confidential classification")
    if classification == "confidential" and actor.role not in {"minister", "secretary", "cos", "admin"}:
        raise HTTPException(status_code=403, detail="Your account cannot upload confidential documents")
    content = await file.read(30 * 1024 * 1024 + 1)
    if not content or len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Document must be between 1 byte and 30 MB")
    digest = sha256(content).hexdigest()
    duplicate = db.scalar(select(Document).where(Document.sha256 == digest))
    if duplicate:
        review = db.scalar(select(IntakeReview).where(IntakeReview.document_id == duplicate.id))
        if review:
            return _view(review, duplicate=True)
        raise HTTPException(status_code=409, detail={"message": "This document is already in the library", "document_id": duplicate.id})

    storage = settings.resolved_data_dir / "documents"
    storage.mkdir(parents=True, exist_ok=True)
    path = storage / f"{uuid4()}{suffix}"
    path.write_bytes(content)
    doc_type = "minute" if suffix == ".pdf" else "other"
    document = Document(title=Path(file.filename or "Uploaded document").name[:255], doc_type=doc_type, classification=classification, file_path=str(path), text_extracted="", source_note="Intake awaiting human confirmation", is_synthetic=False, ingest_status="review", sha256=digest, uploaded_by=actor.id, cloud_ai_allowed=False)
    db.add(document)
    db.flush()
    switch = db.get(ToolSwitch, "document_extraction")
    if switch is None:
        db.add(ToolSwitch(tool="document_extraction", suspended=False))
        db.flush()
    provider_zone = (settings.ai_provider_extraction.strip() or settings.ai_zone_mode).lower()
    permission_pending = classification == "confidential" and provider_zone == "cloud"
    try:
        if permission_pending:
            pages = extract_intake_pages(path)
            document.text_extracted = "\n\n".join(body for _, body in pages)
            if not document.text_extracted.strip():
                raise ValueError("No readable text was found. Scanned PDFs require OCR support.")
            from app.schemas.intake import IntakeExtraction
            extraction, warnings, ai_run_id = IntakeExtraction(title=document.title), ["Confidential document is waiting for an administrator to allow cloud extraction."], None
        else:
            extraction, warnings, ai_run_id = await extract_document(db, document=document, user_id=actor.id)
    except Exception as exc:
        db.rollback()
        orphan = db.get(Document, document.id)
        if orphan is not None:
            db.delete(orphan)
            db.commit()
        path.unlink(missing_ok=True)
        message = str(exc)
        if "confidential data is blocked" in message.lower():
            raise HTTPException(status_code=403, detail="Confidential extraction is blocked until an administrator allows cloud AI for this document, or a local extraction provider is configured") from exc
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=message) from exc
        raise HTTPException(status_code=503, detail=f"Document extraction failed: {message}") from exc
    document.doc_type = "minute" if extraction.doc_kind == "minutes" else extraction.doc_kind
    if extraction.doc_kind == "minutes" and not extraction.meeting_date:
        warnings.append("Meeting date is missing and must be added before confirmation.")
    review = IntakeReview(document_id=document.id, owner_id=actor.id, status="awaiting_permission" if permission_pending else "review", doc_kind=extraction.doc_kind, payload=extraction.model_dump(mode="json"), warnings=sorted(set(warnings)), ai_run_id=ai_run_id)
    db.add(review)
    add_audit_event(db, actor, request, action="document_uploaded_for_review", entity_type="intake_review", entity_id=review.id, after={"sha256": digest, "doc_kind": review.doc_kind})
    db.commit()
    db.refresh(review)
    return _view(review)


@router.get("", response_model=list[IntakeView])
def list_intake(db: Session = Depends(get_db), actor: User = Depends(require_permission("documents", "view"))) -> list[IntakeView]:
    query = select(IntakeReview).where(IntakeReview.status.in_(("review", "awaiting_permission")))
    if actor.role not in {"cos", "admin"}:
        query = query.where((IntakeReview.owner_id == actor.id) | (IntakeReview.assigned_to == actor.id))
    return [_view(row) for row in db.scalars(query.order_by(IntakeReview.created_at.desc()))]


@router.get("/{review_id}", response_model=IntakeView)
def get_intake(review_id: str, db: Session = Depends(get_db), actor: User = Depends(require_permission("documents", "view"))) -> IntakeView:
    review = db.get(IntakeReview, review_id)
    if review is None or (actor.role not in {"cos", "admin"} and review.owner_id != actor.id and review.assigned_to != actor.id):
        raise HTTPException(status_code=404, detail="Intake review was not found")
    return _view(review)


@router.patch("/{review_id}", response_model=IntakeView)
def update_intake(review_id: str, payload: IntakeEdit, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_permission("review", "edit"))) -> IntakeView:
    review = db.get(IntakeReview, review_id)
    if review is None or review.status != "review":
        raise HTTPException(status_code=404, detail="Editable intake review was not found")
    document = db.get(Document, review.document_id)
    if actor.role not in {"cos", "admin"} and review.owner_id != actor.id and review.assigned_to != actor.id:
        raise HTTPException(status_code=403, detail="This review belongs to another user")
    data = payload.payload
    pages = [(None, document.text_extracted)]
    actions = data.actions
    commitments = data.commitments
    created_organisations: list[str] = []
    created_projects: list[str] = []
    known_orgs = list(db.scalars(select(Organisation)))
    for name in payload.create_organisations:
        clean = name.strip()
        if not clean or any(item.name.casefold() == clean.casefold() for item in known_orgs):
            continue
        short = "".join(part[0] for part in re.findall(r"[A-Za-z0-9]+", clean)).upper()[:36] or "ORG"
        base, suffix = short, 1
        while db.scalar(select(Organisation.id).where(Organisation.short_name == short)):
            suffix += 1
            short = f"{base[:34]}{suffix}"
        organisation = Organisation(name=clean, short_name=short, type="agency", aliases=[])
        db.add(organisation)
        db.flush()
        known_orgs.append(organisation)
        created_organisations.append(organisation.id)
    known_projects = list(db.scalars(select(Project)))
    for name in payload.create_projects:
        clean = name.strip()
        if not clean or any(item.name.casefold() == clean.casefold() for item in known_projects):
            continue
        code = f"NEW-{sha256(clean.casefold().encode('utf-8')).hexdigest()[:8].upper()}"
        project = Project(code=code, name=clean, aliases=[], sector="MoITT", stage="planning", health="on_track", health_reason="No overdue actions or near-term unmet commitments.", summary=f"Project added during document review: {clean}")
        db.add(project)
        db.flush()
        known_projects.append(project)
        created_projects.append(project.id)
    # Recheck quotes on reviewer edits; the UI cannot mark invented evidence as verified.
    from app.services.intake import enrich_extraction
    data, warnings = enrich_extraction(db, data, pages, anchor_date=document.created_at.date())
    document_project_name = data.project_hint or next((item.project for item in data.actions if item.project), None) or next((item.project for item in data.commitments if item.project), None)
    project = next((item for item in known_projects if document_project_name and (item.name == document_project_name or item.code == document_project_name)), None)
    document.project_id = project.id if project else None
    review.payload, review.warnings = data.model_dump(mode="json"), warnings
    review.was_edited = True
    add_audit_event(db, actor, request, action="intake_review_edited", entity_type="intake_review", entity_id=review.id, after={"action_count": len(actions), "commitment_count": len(commitments), "created_organisation_ids": created_organisations, "created_project_ids": created_projects, "warnings": warnings})
    db.commit()
    return _view(review)


@router.post("/{review_id}/handoff", response_model=IntakeView)
def handoff_to_cos(review_id: str, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_permission("documents", "upload"))) -> IntakeView:
    review = db.get(IntakeReview, review_id)
    if review is None or review.owner_id != actor.id or review.status not in {"review", "awaiting_permission"}:
        raise HTTPException(status_code=404, detail="Your open review was not found")
    cos = db.scalar(select(User).where(User.email == COS_EMAIL, User.active.is_(True)))
    if cos is None:
        cos = db.scalar(select(User).where(User.role == "cos", User.active.is_(True)))
    if cos is None:
        raise HTTPException(status_code=409, detail="A Chief of Staff account is not configured")
    review.assigned_to = cos.id
    add_audit_event(db, actor, request, action="intake_handed_to_cos", entity_type="intake_review", entity_id=review.id, after={"assigned_to": cos.id})
    db.commit()
    return _view(review)


@router.patch("/{review_id}/cloud-permission", response_model=IntakeView)
def set_cloud_permission(review_id: str, payload: CloudPermission, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))) -> IntakeView:
    review = db.get(IntakeReview, review_id)
    if review is None or review.status != "awaiting_permission":
        raise HTTPException(status_code=404, detail="Intake awaiting cloud permission was not found")
    document = db.get(Document, review.document_id)
    document.cloud_ai_allowed = payload.allowed
    add_audit_event(db, actor, request, action="document_cloud_ai_permission_changed", entity_type="document", entity_id=document.id, after={"allowed": payload.allowed})
    db.commit()
    return _view(review)


@router.post("/{review_id}/extract", response_model=IntakeView)
async def extract_after_admin_permission(review_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))) -> IntakeView:
    review = db.get(IntakeReview, review_id)
    if review is None or review.status != "awaiting_permission":
        raise HTTPException(status_code=404, detail="Intake awaiting extraction was not found")
    document = db.get(Document, review.document_id)
    if not document.cloud_ai_allowed:
        raise HTTPException(status_code=403, detail="An administrator must explicitly allow cloud AI for this document first")
    try:
        extraction, warnings, run_id = await extract_document(db, document=document, user_id=actor.id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Document extraction failed: {exc}") from exc
    review.doc_kind = extraction.doc_kind
    review.payload = extraction.model_dump(mode="json")
    review.warnings = warnings
    review.ai_run_id = run_id
    review.status = "review"
    db.commit()
    return _view(review)


@router.post("/{review_id}/confirm", response_model=IntakeView)
def confirm_intake(review_id: str, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_permission("documents", "approve"))) -> IntakeView:
    review = db.get(IntakeReview, review_id)
    if review is None or review.status != "review":
        raise HTTPException(status_code=404, detail="Open intake review was not found")
    if actor.role not in {"cos", "admin"} and review.owner_id != actor.id and review.assigned_to != actor.id:
        raise HTTPException(status_code=403, detail="Only the uploader or assigned reviewer can confirm this upload")
    document = db.get(Document, review.document_id)
    data = IntakeExtraction.model_validate(review.payload)
    anchor_date = data.meeting_date or document.created_at.date()
    data, verified_warnings = enrich_extraction(db, data, [(None, document.text_extracted)], anchor_date=document.created_at.date())
    review.payload = data.model_dump(mode="json")
    review.warnings = verified_warnings
    created_actions: list[Action] = []
    meeting = None
    if review.doc_kind == "minutes":
        if data.meeting_date is None:
            raise HTTPException(status_code=422, detail="Add the meeting date before confirming")
        meeting_time = time(9)
        if data.meeting_time:
            try:
                meeting_time = time.fromisoformat(data.meeting_time)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Enter meeting time in 24-hour HH:MM format") from exc
        moment = datetime.combine(data.meeting_date, meeting_time, tzinfo=timezone.utc)
        participant_rows = [{"name": item.text, "organisation": item.org_hint} for item in data.participants]
        meeting_decisions = [item.model_dump(mode="json") for item in data.decisions if item.quote_verified]
        meeting = Meeting(title=data.title, occurred_at=moment, occasion_type="meeting", location=data.venue or "Not recorded", attendees=participant_rows, chair=data.chair, venue=data.venue, participants=participant_rows, decisions=meeting_decisions, summary=data.summary, source_document_id=document.id, classification=document.classification, is_synthetic=False, status="reviewed", draft_due_at=moment + timedelta(days=1), issue_due_at=moment + timedelta(days=2), created_by=review.owner_id)
        db.add(meeting)
        db.flush()
    moment = datetime.combine(anchor_date, meeting_time if review.doc_kind == "minutes" else time(9), tzinfo=timezone.utc)
    known_orgs = list(db.scalars(select(Organisation)))
    known_projects = list(db.scalars(select(Project)))
    document_project_name = data.project_hint or next((item.project for item in data.actions if item.project), None) or next((item.project for item in data.commitments if item.project), None)
    project_for_hint = next((row for row in known_projects if document_project_name and (row.name == document_project_name or row.code == document_project_name)), None)
    if document.project_id is None and project_for_hint:
        document.project_id = project_for_hint.id
    if review.doc_kind != "minutes" and document.project_id is None:
        raise HTTPException(status_code=422, detail="Link this document to a project before confirming")
    for item in data.actions:
        if not item.quote_verified or item.needs_input:
            raise HTTPException(status_code=422, detail="Resolve every flagged action and verify its source quote before confirming")
        owner = next((row for row in known_orgs if item.owner_org and (row.name == item.owner_org or row.short_name == item.owner_org or item.owner_org in (row.aliases or []))), None)
        project = next((row for row in known_projects if item.project and (row.name == item.project or row.code == item.project)), None)
        if (not owner and not item.owner_person) or not project:
            raise HTTPException(status_code=422, detail="Select or create a known owner and project for every action")
        if item.resolved_deadline is None:
            raise HTTPException(status_code=422, detail=f"Resolve deadline '{item.deadline_text}' before confirming")
        action_fy = f"{anchor_date.year}-{(anchor_date.year + 1) % 100:02d}" if anchor_date.month >= 7 else f"{anchor_date.year - 1}-{anchor_date.year % 100:02d}"
        action = Action(fy=action_fy, serial_no=None, description=item.description, owner_org_id=owner.id if owner else None, owner_person_name=item.owner_person, occurred_at=moment, deadline=item.resolved_deadline, deadline_text=item.deadline_text, deadline_precision=item.deadline_precision, priority=item.priority, status="closed" if item.status_source == "done_at_upload" else "open", status_source=item.status_source, review_state="proposed", origin="document_intake", project_id=project.id, source_document_id=document.id, source_quote=item.source_quote, source_page=item.source_page)
        db.add(action)
        db.flush()
        approve_action(db, action)
        created_actions.append(action)
    for item in data.commitments:
        if not item.quote_verified or item.needs_input:
            raise HTTPException(status_code=422, detail="Resolve every flagged commitment and verify its source quote before confirming")
        project = next((row for row in known_projects if item.project and (row.name == item.project or row.code == item.project)), None)
        if project is None:
            raise HTTPException(status_code=422, detail="Select or create a known project for every commitment")
        if item.resolved_due_date is None:
            raise HTTPException(status_code=422, detail=f"Resolve commitment date '{item.due_text}' before confirming")
        organisation = next((row for row in known_orgs if item.committed_by_org and (row.name == item.committed_by_org or row.short_name == item.committed_by_org or item.committed_by_org in (row.aliases or []))), None)
        db.add(Commitment(project_id=project.id, statement=item.statement, committed_by_org_id=organisation.id if organisation else None, committed_by_text=item.committed_by_text, due_date=item.resolved_due_date, due_text=item.due_text, precision=item.deadline_precision, status="pending", source_document_id=document.id, source_quote=item.source_quote))
    for item in data.decisions:
        if not item.quote_verified:
            raise HTTPException(status_code=422, detail="Verify every extracted decision quote before confirming")
    db.flush()
    touched = {action.project_id for action in created_actions if action.project_id}
    touched.update(item.project_id for item in db.scalars(select(Commitment).where(Commitment.source_document_id == document.id)))
    for project_id in touched:
        project = db.get(Project, project_id)
        if project:
            recompute_project_health(db, project)
    review.status = "confirmed"
    review.diff_summary = f"Added {len(created_actions)} action(s), {len(data.commitments)} commitment(s), and {len(data.decisions)} decision(s); linked to {project_for_hint.name if project_for_hint else 'no project'}; indexed '{document.title}'."
    document.ingest_status = "ready"
    index_intake_document(db, document)
    add_audit_event(db, actor, request, action="intake_confirmed", entity_type="intake_review", entity_id=review.id, after={"document_id": document.id, "action_ids": [item.id for item in created_actions], "commitments": len(data.commitments), "summary": review.diff_summary})
    if review.ai_run_id:
        from app.db.models import AIRun
        run = db.get(AIRun, review.ai_run_id)
        if run:
            run.outcome = "edited" if review.was_edited else "approved"
            run.approver_id = actor.id
            run.approved_at = datetime.now(timezone.utc)
            run.diff_summary = review.diff_summary
    db.commit()
    db.refresh(review)
    return _view(review)


@router.delete("/{review_id}", status_code=204)
def discard_intake(review_id: str, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_permission("documents", "approve"))) -> None:
    review = db.get(IntakeReview, review_id)
    if review is None or review.status not in {"review", "awaiting_permission"} or (actor.role not in {"cos", "admin"} and review.owner_id != actor.id):
        raise HTTPException(status_code=404, detail="Discardable intake review was not found")
    document = db.get(Document, review.document_id)
    add_audit_event(db, actor, request, action="intake_discarded", entity_type="intake_review", entity_id=review.id, after={"document_id": document.id})
    db.delete(review)
    db.delete(document)
    db.commit()
    Path(document.file_path).unlink(missing_ok=True)
