from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import Any, TypedDict
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.ai.gateway import AIGateway, PolicyViolation, ToolSuspended
from app.ai.stt import FasterWhisperProvider, STTProvider
from app.core.config import REPO_ROOT, settings
from app.db.models import AIRun, Meeting, MeetingAction, MinutesDraft, RegisterEntry, Transcript, Transaction, User
from app.schemas.minutes import ActionExtraction, MinutesExtraction
from app.services.register import financial_year_for


class MinutesState(TypedDict, total=False):
    meeting_id: str
    actor_id: str
    transcript: list[dict[str, Any]]
    language: str
    extraction: dict[str, Any]
    run_id: str
    minutes_id: str
    action_ids: list[str]


def resolve_officer(db: Session, hint: str | None) -> User | None:
    if not hint:
        return None
    needle = hint.strip().casefold()
    aliases = {"chief of staff": "cos", "cos": "cos", "director of transformation and delivery": "director_td", "director (transformation & delivery)": "director_td", "liaison lead": "liaison"}
    if needle in aliases:
        needle = aliases[needle]
    users = db.scalars(select(User).where(User.active.is_(True))).all()
    exact = [user for user in users if needle in {user.name.casefold(), user.designation.casefold(), user.role.casefold(), user.email.casefold()}]
    return exact[0] if len(exact) == 1 else None


def resolve_transaction(db: Session, hint: str | None) -> Transaction | None:
    if not hint:
        return None
    value = hint.strip().upper()
    return db.scalar(select(Transaction).where(Transaction.code == value))


def build_minutes_graph(db: Session, gateway: AIGateway, stt: STTProvider | None = None):
    transcription = stt or FasterWhisperProvider()

    def transcribe_node(state: MinutesState) -> dict[str, Any]:
        meeting = db.get(Meeting, state["meeting_id"])
        if meeting is None:
            raise ValueError("Meeting was not found")
        transcript = db.scalar(select(Transcript).where(Transcript.meeting_id == meeting.id))
        if transcript is not None:
            return {"transcript": transcript.segments, "language": transcript.language}
        if not meeting.audio_path:
            raise ValueError("Attach a recording or add a transcript before drafting minutes")
        meeting.status = "transcribing"
        db.commit()
        audio_path = str((settings.resolved_data_dir / meeting.audio_path).resolve())
        language, segments = transcription.transcribe(audio_path, meeting.language_hint)
        if not segments:
            meeting.status = "uploaded"
            db.commit()
            raise ValueError("Speech-to-text did not return any transcript segments")
        transcript = Transcript(meeting_id=meeting.id, language=language, segments=segments, stt_provider=transcription.name, stt_model=settings.stt_model_size)
        meeting.status = "transcribed"
        db.add(transcript)
        db.commit()
        return {"transcript": segments, "language": language}

    def draft_node(state: MinutesState) -> dict[str, Any]:
        meeting = db.get(Meeting, state["meeting_id"])
        if meeting is None:
            raise ValueError("Meeting was not found")
        transcript_text = "\n".join(f"[{float(segment['start']):.2f}-{float(segment['end']):.2f}] {segment.get('speaker') or 'Speaker'}: {segment['text']}" for segment in state["transcript"])
        attendees = ", ".join(attendee.get("name", "") for attendee in meeting.attendees)
        system_prompt = (REPO_ROOT / "backend" / "app" / "ai" / "prompts" / "minutes_v1.md").read_text(encoding="utf-8")
        prompt = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Return JSON for the requested schema. Meeting: {meeting.title}. Date: {meeting.occurred_at.isoformat()}. Place: {meeting.location}. Attendees: {attendees}. Transcript:\n{transcript_text}"},
        ]
        run_id: dict[str, str] = {}
        transcript_digest = hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()
        cache_path = settings.resolved_data_dir / "demo_cache" / f"minutes-{meeting.id}.json"
        try:
            extracted = asyncio.run(gateway.chat(db, tool="minutes_assistant", role="extraction", messages=prompt, classification=meeting.classification, is_synthetic=meeting.is_synthetic, user_id=state["actor_id"], prompt_version="minutes-v1", response_schema=MinutesExtraction, run_id_out=run_id))
            if settings.demo_mode_cache and meeting.is_synthetic:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path = cache_path.with_suffix(".tmp")
                temporary_path.write_text(json.dumps({"transcript_sha256": transcript_digest, "extraction": extracted.model_dump(mode="json")}, ensure_ascii=False), encoding="utf-8")
                os.replace(temporary_path, cache_path)
        except (PolicyViolation, ToolSuspended):
            raise
        except Exception:
            if not (settings.demo_mode_cache and meeting.is_synthetic and cache_path.is_file()):
                raise
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("transcript_sha256") != transcript_digest:
                raise RuntimeError("The saved demo result does not match this transcript; retry with AI available")
            extracted = MinutesExtraction.model_validate(cached["extraction"])
            run = AIRun(tool="minutes_assistant", model_role="extraction", model="cached-demo-result", zone="local", classification=meeting.classification, is_synthetic=True, user_id=state["actor_id"], outcome="success", prompt_version="minutes-cache-v1", error_code="demo_cache_used", prompt_metadata={"cache": "last_successful_seeded_sample", "transcript_sha256": transcript_digest})
            db.add(run)
            db.commit()
            run_id["run_id"] = run.id
        if not isinstance(extracted, MinutesExtraction):
            raise RuntimeError("Minutes gateway returned an invalid response type")
        return {"extraction": extracted.model_dump(mode="json"), "run_id": run_id["run_id"]}

    def persist_node(state: MinutesState) -> dict[str, Any]:
        meeting = db.get(Meeting, state["meeting_id"])
        actor = db.get(User, state["actor_id"])
        if meeting is None or actor is None:
            raise ValueError("Meeting or reviewer was not found")
        extracted = MinutesExtraction.model_validate(state["extraction"])
        prior_version = db.scalar(select(MinutesDraft.version).where(MinutesDraft.meeting_id == meeting.id).order_by(MinutesDraft.version.desc()).limit(1)) or 0
        draft = MinutesDraft(meeting_id=meeting.id, version=prior_version + 1, body_markdown=extracted.body_markdown, status="draft", drafted_by_run_id=state["run_id"])
        db.add(draft)
        db.flush()
        transcript = db.scalar(select(Transcript).where(Transcript.meeting_id == meeting.id))
        if transcript is None:
            raise ValueError("Transcript was not saved")
        action_ids: list[str] = []
        run = db.get(AIRun, state["run_id"])
        for action in extracted.actions:
            officer = resolve_officer(db, action.officer_hint)
            deadline = action.deadline_date
            if deadline is not None and deadline < meeting.occurred_at.date():
                deadline = None
            transaction = resolve_transaction(db, action.transaction_hint)
            issues = []
            if officer is None:
                issues.append("Confirm the responsible officer")
            if deadline is None:
                issues.append("Set a valid deadline")
            record = MeetingAction(meeting_id=meeting.id, ai_run_id=run.id if run else None, description=action.description, officer_hint=action.officer_hint, officer_id=officer.id if officer else None, deadline_hint=action.deadline_hint, deadline_date=deadline, priority_suggestion=action.priority_suggestion, transaction_hint=action.transaction_hint, transaction_id=transaction.id if transaction else None, quote=action.quote, transcript_start=action.transcript_start, transcript_end=action.transcript_end, confidence=action.confidence, review_state="pending", review_reason="; ".join(issues) or None)
            db.add(record)
            db.flush()
            action_ids.append(record.id)
            if officer is not None and deadline is not None:
                entry = RegisterEntry(fy=financial_year_for(meeting.occurred_at.date()), serial_no=None, occurred_at=meeting.occurred_at, occasion_type=meeting.occasion_type, occasion_ref=meeting.title, description=action.description, officer_id=officer.id, deadline=deadline, priority=action.priority_suggestion, source_record=f"MIN-{meeting.id[:8]}", status="open", transaction_id=transaction.id if transaction else None, origin="ai_proposed", review_state="proposed", ai_assistance={"tool": "minutes_assistant", "model": run.model if run else "unavailable", "run_id": run.id if run else None}, evidence={"quote": action.quote, "transcript_start": action.transcript_start, "transcript_end": action.transcript_end, "confidence": action.confidence})
                db.add(entry)
                db.flush()
                record.register_entry_id = entry.id
        meeting.status = "draft_ready"
        db.add(draft)
        db.commit()
        return {"minutes_id": draft.id, "action_ids": action_ids}

    graph = StateGraph(MinutesState)
    graph.add_node("transcribe", transcribe_node)
    graph.add_node("draft", draft_node)
    graph.add_node("persist", persist_node)
    graph.add_edge(START, "transcribe")
    graph.add_edge("transcribe", "draft")
    graph.add_edge("draft", "persist")
    graph.add_edge("persist", END)
    return graph.compile()


def resolve_meeting(db: Session, meeting_id: str) -> Meeting | None:
    return db.scalar(select(Meeting).options(joinedload(Meeting.transcript), selectinload(Meeting.minutes), selectinload(Meeting.actions).joinedload(MeetingAction.officer)).where(Meeting.id == meeting_id))
