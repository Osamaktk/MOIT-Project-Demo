from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.stt import STTProvider
from app.db.models import AuditEvent, Job, Meeting
from app.services.minutes_graph import build_minutes_graph


def _set_progress(db: Session, job_id: str, *, progress: int, message: str) -> None:
    job = db.get(Job, job_id)
    if job is None:
        return
    job.progress = progress
    job.message = message
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def process_minutes_job(db: Session, job_id: str, gateway: AIGateway, stt: STTProvider) -> None:
    job = db.get(Job, job_id)
    if job is None:
        return
    job.status = "running"
    job.progress = 5
    job.message = "Preparing meeting transcript"
    job.started_at = datetime.now(timezone.utc)
    db.commit()
    try:
        graph = build_minutes_graph(db, gateway, stt)
        result: dict[str, Any] = {}
        stages = {
            "transcribe": (35, "Transcribing recording"),
            "draft": (78, "Drafting minutes and proposed actions"),
            "persist": (94, "Saving minutes and actions for review"),
        }
        for update in graph.stream({"meeting_id": job.resource_id, "actor_id": job.owner_id}, stream_mode="updates"):
            for stage, values in update.items():
                result.update(values)
                progress, message = stages.get(stage, (85, "Processing meeting"))
                _set_progress(db, job_id, progress=progress, message=message)
        meeting = db.get(Meeting, job.resource_id)
        if meeting is None or not result.get("minutes_id"):
            raise RuntimeError("Minutes draft was not saved")
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = "succeeded"
        job.progress = 100
        job.message = "Minutes are ready for review"
        job.finished_at = datetime.now(timezone.utc)
        db.add(AuditEvent(actor_id=job.owner_id, action="minutes_drafted", entity_type="meeting", entity_id=meeting.id, after_json={"minutes_id": result["minutes_id"], "action_count": len(result.get("action_ids", []))}, ip=None))
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(Job, job_id)
        meeting = db.get(Meeting, job.resource_id) if job else None
        if meeting is not None and meeting.status == "transcribing":
            meeting.status = "uploaded" if meeting.audio_path else "transcribed"
        if job is not None:
            job.status = "failed"
            job.progress = 100
            # Provider exceptions may contain request data; only surface safe validation messages.
            job.error_message = str(exc)[:1000] if isinstance(exc, (ValueError,)) else "Meeting processing failed. Check provider readiness and retry."
            job.message = "Meeting processing failed"
            job.finished_at = datetime.now(timezone.utc)
        db.commit()
