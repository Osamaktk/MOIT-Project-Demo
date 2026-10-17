from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OccasionType = Literal["meeting", "engagement", "file", "on_the_move"]
Priority = Literal["A", "B", "C"]
RegisterStatus = Literal["open", "in_progress", "closed", "closed_with_note"]
ReviewState = Literal["approved", "proposed", "rejected"]


class RegisterCreate(BaseModel):
    occurred_at: datetime
    occasion_type: OccasionType
    occasion_ref: str | None = Field(default=None, max_length=255)
    description: str = Field(min_length=3, max_length=4000)
    minister_words: str | None = Field(default=None, max_length=2000)
    officer_id: str
    deadline: date
    priority: Priority
    source_record: str | None = Field(default=None, max_length=255)
    transaction_id: str | None = None


class RegisterUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=3, max_length=4000)
    minister_words: str | None = Field(default=None, max_length=2000)
    officer_id: str | None = None
    deadline: date | None = None
    priority: Priority | None = None
    source_record: str | None = Field(default=None, max_length=255)
    transaction_id: str | None = None
    status: RegisterStatus | None = None
    closure_note: str | None = Field(default=None, max_length=2000)
    change_reason: str | None = Field(default=None, max_length=500)

    @field_validator("change_reason")
    @classmethod
    def nonblank_reason(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class RegisterReject(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class OfficerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    designation: str


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    serial_no: int | None
    fy: str
    occurred_at: datetime
    occasion_type: str
    occasion_ref: str | None
    description: str
    minister_words: str | None
    officer_id: str
    officer: OfficerSummary
    deadline: date
    priority: str
    source_record: str | None
    status: str
    closed_at: datetime | None
    closure_note: str | None
    transaction_id: str | None
    origin: str
    review_state: str
    ai_assistance: dict[str, object] | None
    evidence: dict[str, object] | None
    created_at: datetime
    updated_at: datetime
    overdue: bool


class AuditResponse(BaseModel):
    id: str
    actor_id: str | None
    actor_name: str | None
    action: str
    before: dict[str, object] | None
    after: dict[str, object] | None
    ip: str | None
    at: datetime


class PaginatedRegisterResponse(BaseModel):
    items: list[RegisterResponse]
    total: int
    limit: int
    offset: int
