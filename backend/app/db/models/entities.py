from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    designation: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="actor")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    actor: Mapped[User | None] = relationship(back_populates="audit_events")


class RegisterEntry(TimestampMixin, Base):
    __tablename__ = "register_entries"
    __table_args__ = (UniqueConstraint("fy", "serial_no", name="uq_register_fy_serial"),)

    serial_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fy: Mapped[str] = mapped_column(String(7), index=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occasion_type: Mapped[str] = mapped_column(String(20), nullable=False)
    occasion_ref: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(4000), nullable=False)
    minister_words: Mapped[str | None] = mapped_column(String(2000))
    officer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    deadline: Mapped[date] = mapped_column(Date, nullable=False)
    priority: Mapped[str] = mapped_column(String(1), nullable=False, index=True)
    source_record: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="open", index=True, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closure_note: Mapped[str | None] = mapped_column(String(2000))
    transaction_id: Mapped[str | None] = mapped_column(String(36), index=True)
    origin: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    review_state: Mapped[str] = mapped_column(String(20), default="approved", index=True, nullable=False)
    ai_assistance: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    officer: Mapped[User] = relationship()


class RegisterSerialCounter(Base):
    __tablename__ = "register_serial_counters"

    fy: Mapped[str] = mapped_column(String(7), primary_key=True)
    last_serial: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sector: Mapped[str] = mapped_column(String(80), nullable=False)
    stage: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    next_milestone: Mapped[str] = mapped_column(String(255), nullable=False)
    next_milestone_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    health: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    lead_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    lead_user: Mapped[User] = relationship(foreign_keys=[lead_user_id])
    events: Mapped[list["TransactionEvent"]] = relationship(back_populates="transaction", order_by="TransactionEvent.occurred_at.desc()")


class TransactionEvent(TimestampMixin, Base):
    __tablename__ = "transaction_events"

    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255))
    transaction: Mapped[Transaction] = relationship(back_populates="events")


class MinisterDecision(TimestampMixin, Base):
    __tablename__ = "minister_decisions"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True, default="open", nullable=False)
    context_ref: Mapped[str | None] = mapped_column(String(255))
    transaction: Mapped[Transaction | None] = relationship()


class Engagement(TimestampMixin, Base):
    __tablename__ = "engagements"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    engagement_type: Mapped[str] = mapped_column(String(80), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    pack_status: Mapped[str] = mapped_column(String(20), index=True, default="not_started", nullable=False)
    pack_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    owner: Mapped[User] = relationship()
    transaction: Mapped[Transaction | None] = relationship()


class ToolSwitch(Base):
    __tablename__ = "tool_switches"

    tool: Mapped[str] = mapped_column(String(80), primary_key=True)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    changer: Mapped[User | None] = relationship()


class AIRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tool: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    model_role: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    zone: Mapped[str] = mapped_column(String(12), nullable=False)
    classification: Mapped[str] = mapped_column(String(24), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    prompt_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    approver_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    diff_summary: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    user: Mapped[User | None] = relationship(foreign_keys=[user_id])
    approver: Mapped[User | None] = relationship(foreign_keys=[approver_id])


class Meeting(TimestampMixin, Base):
    __tablename__ = "meetings"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    occasion_type: Mapped[str] = mapped_column(String(24), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    attendees: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    audio_path: Mapped[str | None] = mapped_column(String(500))
    language_hint: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    classification: Mapped[str] = mapped_column(String(24), default="confidential", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="uploaded", index=True, nullable=False)
    draft_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issue_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    transcript: Mapped["Transcript | None"] = relationship(back_populates="meeting", uselist=False)
    minutes: Mapped[list["MinutesDraft"]] = relationship(back_populates="meeting", order_by="MinutesDraft.version.desc()")
    actions: Mapped[list["MeetingAction"]] = relationship(back_populates="meeting")


class Transcript(TimestampMixin, Base):
    __tablename__ = "transcripts"
    __table_args__ = (UniqueConstraint("meeting_id", name="uq_transcripts_meeting"),)

    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    segments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    stt_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    stt_model: Mapped[str] = mapped_column(String(120), nullable=False)
    meeting: Mapped[Meeting] = relationship(back_populates="transcript")


class MinutesDraft(TimestampMixin, Base):
    __tablename__ = "minutes"
    __table_args__ = (UniqueConstraint("meeting_id", "version", name="uq_minutes_meeting_version"),)

    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body_markdown: Mapped[str] = mapped_column(String(30000), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True, nullable=False)
    drafted_by_run_id: Mapped[str | None] = mapped_column(ForeignKey("ai_runs.id"))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    export_path: Mapped[str | None] = mapped_column(String(500))
    meeting: Mapped[Meeting] = relationship(back_populates="minutes")


class MeetingAction(TimestampMixin, Base):
    __tablename__ = "meeting_actions"

    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), nullable=False, index=True)
    ai_run_id: Mapped[str | None] = mapped_column(ForeignKey("ai_runs.id"), index=True)
    register_entry_id: Mapped[str | None] = mapped_column(String(36), index=True)
    description: Mapped[str] = mapped_column(String(4000), nullable=False)
    officer_hint: Mapped[str | None] = mapped_column(String(255))
    officer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    deadline_hint: Mapped[str | None] = mapped_column(String(255))
    deadline_date: Mapped[date | None] = mapped_column(Date)
    priority_suggestion: Mapped[str] = mapped_column(String(1), default="B", nullable=False)
    transaction_hint: Mapped[str | None] = mapped_column(String(255))
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"))
    quote: Mapped[str] = mapped_column(String(2000), nullable=False)
    transcript_start: Mapped[float] = mapped_column(Float, nullable=False)
    transcript_end: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_state: Mapped[str] = mapped_column(String(24), default="pending", index=True, nullable=False)
    review_reason: Mapped[str | None] = mapped_column(String(1000))
    meeting: Mapped[Meeting] = relationship(back_populates="actions")
    officer: Mapped[User | None] = relationship()
    transaction: Mapped[Transaction | None] = relationship()


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    classification: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    text_extracted: Mapped[str] = mapped_column(String, nullable=False)
    source_note: Mapped[str | None] = mapped_column(String(1000))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ingest_status: Mapped[str] = mapped_column(String(24), default="ready", index=True, nullable=False)
    transaction: Mapped[Transaction | None] = relationship()
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),)

    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(255))
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    document: Mapped[Document] = relationship(back_populates="chunks")


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(String(12000), nullable=False)
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("ai_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    session: Mapped[ChatSession] = relationship(back_populates="messages")


class ComplianceItem(TimestampMixin, Base):
    __tablename__ = "compliance_items"

    category: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255))
    owner: Mapped[User] = relationship()


class SpotCheck(TimestampMixin, Base):
    __tablename__ = "spot_checks"

    period: Mapped[str] = mapped_column(String(7), index=True, nullable=False)
    sample: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    reconciled_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    findings: Mapped[str | None] = mapped_column(String(4000))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True, nullable=False)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    reconciler: Mapped[User | None] = relationship(foreign_keys=[reconciled_by])
    creator: Mapped[User] = relationship(foreign_keys=[creator_id])


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), index=True, default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    owner: Mapped[User] = relationship()
