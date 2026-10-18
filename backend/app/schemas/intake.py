from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IntakeAction(BaseModel):
    description: str = Field(min_length=3, max_length=4000)
    owner_org: str | None = None
    owner_person: str | None = None
    deadline_text: str = ""
    resolved_deadline: date | None = None
    deadline_precision: Literal["day", "week", "month", "relative"] = "relative"
    priority: Literal["A", "B", "C"] = "B"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status_source: Literal["open", "done_at_upload"] = "open"
    project: str | None = None
    source_quote: str = Field(min_length=3, max_length=2000)
    source_page: int | None = Field(default=None, ge=1)
    quote_verified: bool = False
    needs_input: bool = False


class IntakeCommitment(BaseModel):
    statement: str = Field(min_length=3, max_length=2000)
    committed_by_org: str | None = None
    committed_by_text: str | None = None
    due_text: str = ""
    resolved_due_date: date | None = None
    deadline_precision: Literal["day", "week", "month", "relative"] = "relative"
    project: str | None = None
    source_quote: str = Field(min_length=3, max_length=2000)
    source_page: int | None = Field(default=None, ge=1)
    quote_verified: bool = False
    needs_input: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class IntakeDecision(BaseModel):
    text: str = Field(min_length=2, max_length=2000)
    source_quote: str = Field(min_length=3, max_length=2000)
    source_page: int | None = Field(default=None, ge=1)
    quote_verified: bool = False


class IntakeParticipant(BaseModel):
    text: str = Field(min_length=1, max_length=255)
    org_hint: str | None = None


class IntakeExtraction(BaseModel):
    doc_kind: Literal["minutes", "letter", "brief", "note", "other"] = "other"
    title: str = Field(default="Uploaded document", max_length=255)
    meeting_date: date | None = None
    meeting_time: str | None = Field(default=None, max_length=32)
    chair: str | None = None
    venue: str | None = None
    participants: list[IntakeParticipant] = Field(default_factory=list)
    project_hint: str | None = None
    summary: str = ""
    actions: list[IntakeAction] = Field(default_factory=list)
    commitments: list[IntakeCommitment] = Field(default_factory=list)
    decisions: list[IntakeDecision] = Field(default_factory=list)


class IntakeEdit(BaseModel):
    payload: IntakeExtraction
    create_organisations: list[str] = Field(default_factory=list, max_length=20)
    create_projects: list[str] = Field(default_factory=list, max_length=20)


class CloudPermission(BaseModel):
    allowed: bool


class IntakeView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    status: str
    doc_kind: str
    payload: dict
    warnings: list[str]
    diff_summary: str | None = None
    duplicate: bool = False
