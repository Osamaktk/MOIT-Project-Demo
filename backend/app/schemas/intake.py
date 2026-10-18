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


class IntakeExtraction(BaseModel):
    doc_kind: Literal["minutes", "letter", "brief", "note", "other"] = "other"
    title: str = Field(default="Uploaded document", max_length=255)
    meeting_date: date | None = None
    chair: str | None = None
    venue: str | None = None
    participants: list[str] = Field(default_factory=list)
    project_hint: str | None = None
    summary: str = ""
    actions: list[IntakeAction] = Field(default_factory=list)
    commitments: list[IntakeCommitment] = Field(default_factory=list)


class IntakeEdit(BaseModel):
    payload: IntakeExtraction


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
