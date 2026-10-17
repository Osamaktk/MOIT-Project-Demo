import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.db.models import Job, Meeting, User
from app.schemas.jobs import JobResponse

router = APIRouter(prefix="/jobs", tags=["background jobs"])
READ_ROLES = ("minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin")


def _visible_job(db: Session, job_id: str, actor: User) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job was not found")
    meeting = db.get(Meeting, job.resource_id) if job.resource_type == "meeting" else None
    if job.owner_id != actor.id and (meeting is None or (meeting.classification == "confidential" and actor.role not in {"minister", "cos"})):
        raise HTTPException(status_code=404, detail="Job was not found")
    return job


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(*READ_ROLES))) -> JobResponse:
    return JobResponse.model_validate(_visible_job(db, job_id, actor))


@router.get("/{job_id}/events")
def job_events(job_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(*READ_ROLES))) -> StreamingResponse:
    _visible_job(db, job_id, actor)

    def events() -> Iterator[str]:
        previous = ""
        while True:
            db.expire_all()
            job = _visible_job(db, job_id, actor)
            payload = JobResponse.model_validate(job).model_dump(mode="json")
            encoded = json.dumps(payload, separators=(",", ":"))
            if encoded != previous:
                yield f"event: job\ndata: {encoded}\n\n"
                previous = encoded
            if job.status in {"succeeded", "failed", "cancelled"}:
                return
            yield ": keep-alive\n\n"
            time.sleep(0.5)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
