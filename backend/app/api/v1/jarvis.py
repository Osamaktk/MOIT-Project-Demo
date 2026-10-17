import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.gateway import AIGateway
from app.ai.stt import FasterWhisperProvider, STTProvider
from app.core.deps import get_current_user, get_db, require_roles
from app.db.models import AIRun, ChatMessage, ChatSession, ToolSwitch, User
from app.schemas.jarvis import ChatCreate, ChatMessageResponse, ChatSessionResponse
from app.services.audit import add_audit_event
from app.services.jarvis_graph import build_jarvis_graph

router = APIRouter(prefix="/jarvis", tags=["Jarvis assistant"])
READ_ROLES = ("minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin")


def get_stt_provider() -> STTProvider:
    return FasterWhisperProvider()


def _session_for_user(db: Session, session_id: str, user_id: str) -> ChatSession:
    session = db.scalar(select(ChatSession).options(selectinload(ChatSession.messages)).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session was not found")
    return session


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_sessions(db: Session = Depends(get_db), actor: User = Depends(require_roles(*READ_ROLES))) -> list[ChatSessionResponse]:
    rows = db.scalars(select(ChatSession).where(ChatSession.user_id == actor.id).order_by(ChatSession.updated_at.desc()).limit(20)).all()
    return [ChatSessionResponse.model_validate(row) for row in rows]


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
def create_session(db: Session = Depends(get_db), actor: User = Depends(require_roles(*READ_ROLES))) -> ChatSessionResponse:
    row = ChatSession(user_id=actor.id, title="New conversation")
    db.add(row)
    db.commit()
    db.refresh(row)
    return ChatSessionResponse.model_validate(row)


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(*READ_ROLES))) -> ChatSessionResponse:
    return ChatSessionResponse.model_validate(_session_for_user(db, session_id, actor.id))


@router.post("/chat")
def chat(payload: ChatCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles(*READ_ROLES))) -> StreamingResponse:
    session = _session_for_user(db, payload.session_id, actor.id) if payload.session_id else ChatSession(user_id=actor.id, title=payload.message[:80])
    if payload.session_id is None:
        db.add(session)
        db.flush()
    elif session.title == "New conversation":
        session.title = payload.message[:80]
    user_message = ChatMessage(session_id=session.id, role="user", content=payload.message.strip())
    db.add(user_message)
    switch = db.get(ToolSwitch, "jarvis")
    gateway = AIGateway()
    tool_name = "records_search"
    try:
        if switch is None or switch.suspended:
            blocked = gateway.record_blocked_attempt(db, tool="jarvis", role="chat", classification="internal", is_synthetic=False, user_id=actor.id, prompt_version="jarvis-rules-v1", error_code="tool_switch_missing" if switch is None else "tool_suspended")
            answer = "Jarvis is temporarily unavailable because its assurance control is active. Your message was not processed."
            citations: list[dict[str, Any]] = []
            proposal = None
            run = blocked
            tool_name = "blocked"
        else:
            result = build_jarvis_graph(db).invoke({"user_id": actor.id, "message": payload.message.strip(), "context": payload.context})
            answer = result["answer"]
            citations = result.get("citations", [])
            proposal = result.get("proposal")
            tool_name = result.get("tool", "records_search")
            run = AIRun(tool="jarvis", model_role="chat", model="deterministic-agent-v1", zone="local", classification="internal", is_synthetic=False, user_id=actor.id, outcome="success", prompt_version="jarvis-rules-v1", prompt_metadata={"message_count": 1, "tool": tool_name})
            db.add(run)
            db.flush()
            if proposal:
                from app.db.models import RegisterEntry

                entry = db.get(RegisterEntry, proposal["id"])
                if entry is not None:
                    entry.ai_assistance = {**(entry.ai_assistance or {}), "run_id": run.id}
                add_audit_event(db, actor, request, action="jarvis_proposal_created", entity_type="register_entry", entity_id=proposal["id"], after={"description": proposal["description"], "officer_id": proposal["officer_id"], "deadline": proposal["deadline"], "review_state": "proposed"})
        calls = [{"tool": tool_name}]
        assistant_message = ChatMessage(session_id=session.id, role="assistant", content=answer, tool_calls=calls, citations=citations, run_id=run.id)
        db.add(assistant_message)
        session.updated_at = datetime.now(timezone.utc)
        db.commit()
        session_id = session.id
        message_id = assistant_message.id
    except Exception:
        db.rollback()
        raise

    events: list[tuple[str, dict[str, Any]]] = [
        ("session", {"session_id": session_id, "message_id": message_id}),
        ("tool_start", {"tool": tool_name, "label": f"Checking {tool_name.replace('_', ' ')}"}),
        ("tool_result", {"tool": tool_name, "citation_count": len(citations)}),
    ]
    events.extend(("citation", citation) for citation in citations)
    if proposal:
        events.append(("proposal_card", proposal))
    for start in range(0, len(answer), 100):
        events.append(("token", {"text": answer[start:start + 100]}))
    events.append(("done", {"session_id": session_id, "message_id": message_id, "run_id": run.id}))

    def generate():
        for event, data in events:
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/stt")
async def speech_to_text(file: UploadFile = File(...), db: Session = Depends(get_db), actor: User = Depends(require_roles(*READ_ROLES)), stt: STTProvider = Depends(get_stt_provider)) -> dict[str, Any]:
    switch = db.get(ToolSwitch, "jarvis")
    if switch is None or switch.suspended:
        raise HTTPException(status_code=503, detail="Jarvis voice input is suspended by an AI assurance control")
    suffix = (file.filename or "audio.webm").rsplit(".", 1)[-1].lower()
    if suffix not in {"wav", "mp3", "m4a", "mp4", "webm", "ogg", "flac"}:
        raise HTTPException(status_code=415, detail="Unsupported audio format")
    content = await file.read(20 * 1024 * 1024 + 1)
    if not content or len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Voice recording must be between 1 byte and 20 MB")
    from pathlib import Path
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(suffix=f".{suffix}", delete=False) as temp:
        temp.write(content)
        audio_path = temp.name
    try:
        language, segments = stt.transcribe(audio_path, None)
    finally:
        Path(audio_path).unlink(missing_ok=True)
    return {"language": language, "text": " ".join(segment["text"] for segment in segments).strip(), "segments": segments}
