from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Attendee(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=120)


class MeetingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    occurred_at: datetime
    occasion_type: Literal["meeting", "engagement", "file", "on_the_move"] = "meeting"
    location: str = Field(min_length=2, max_length=255)
    attendees: list[Attendee] = Field(default_factory=list, max_length=50)
    language_hint: str = Field(default="en", min_length=2, max_length=20)
    classification: Literal["public", "internal", "confidential"] = "confidential"


class TranscriptSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=4000)
    lang: str = "en"
    speaker: str | None = None


class TranscriptOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    meeting_id: str
    language: str
    segments: list[TranscriptSegment]
    stt_provider: str
    stt_model: str


class ActionExtraction(BaseModel):
    description: str = Field(min_length=3, max_length=4000)
    officer_hint: str | None = None
    deadline_hint: str | None = None
    deadline_date: date | None = None
    priority_suggestion: Literal["A", "B", "C"] = "B"
    transaction_hint: str | None = None
    quote: str = Field(min_length=1, max_length=2000)
    transcript_start: float = Field(ge=0)
    transcript_end: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)


class MinutesExtraction(BaseModel):
    body_markdown: str = Field(min_length=40, max_length=30000)
    actions: list[ActionExtraction] = Field(max_length=50)


class MeetingActionUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=3, max_length=4000)
    officer_id: str | None = None
    deadline_date: date | None = None
    priority_suggestion: Literal["A", "B", "C"] | None = None
    transaction_id: str | None = None


class MeetingActionReview(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, min_length=3, max_length=1000)


class MinutesUpdate(BaseModel):
    body_markdown: str = Field(min_length=40, max_length=30000)


class MeetingActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    meeting_id: str
    ai_run_id: str | None
    register_entry_id: str | None
    description: str
    officer_hint: str | None
    officer_id: str | None
    officer_name: str | None = None
    deadline_hint: str | None
    deadline_date: date | None
    priority_suggestion: str
    transaction_hint: str | None
    transaction_id: str | None
    quote: str
    transcript_start: float
    transcript_end: float
    confidence: float
    review_state: str
    review_reason: str | None


class MinutesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    meeting_id: str
    version: int
    body_markdown: str
    status: str
    drafted_by_run_id: str | None
    reviewed_by: str | None
    issued_at: datetime | None
    export_path: str | None
    demo_cache_used: bool = False


class MeetingResponse(BaseModel):
    id: str
    title: str
    occurred_at: datetime
    occasion_type: str
    location: str
    attendees: list[dict[str, object]]
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    source_document_id: str | None = None
    intake_actions: list[dict[str, Any]] = Field(default_factory=list)
    audio_url: str | None = None
    language_hint: str
    classification: str
    is_synthetic: bool
    status: str
    draft_due_at: datetime
    issue_due_at: datetime
    transcript: TranscriptOutput | None = None
    minutes: MinutesResponse | None = None
    actions: list[MeetingActionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
