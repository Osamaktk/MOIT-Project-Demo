from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.register import OfficerSummary

TransactionStage = Literal["approval_inclusion", "adviser_hiring", "due_diligence", "eoi_prequalification", "bidding", "approvals", "closing"]
TransactionHealth = Literal["on_track", "at_risk", "delayed"]


class TransactionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=12, pattern="^TX-[A-Z]{1,3}$")
    name: str = Field(min_length=3, max_length=160)
    sector: str = Field(min_length=2, max_length=80)
    stage: TransactionStage
    next_milestone: str = Field(min_length=3, max_length=255)
    next_milestone_date: date
    health: TransactionHealth = "on_track"
    lead_user_id: str
    summary: str = Field(min_length=3, max_length=2000)


class TransactionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=160)
    sector: str | None = Field(default=None, min_length=2, max_length=80)
    stage: TransactionStage | None = None
    next_milestone: str | None = Field(default=None, min_length=3, max_length=255)
    next_milestone_date: date | None = None
    health: TransactionHealth | None = None
    lead_user_id: str | None = None
    summary: str | None = Field(default=None, min_length=3, max_length=2000)
    change_reason: str | None = Field(default=None, max_length=500)


class TransactionEventCreate(BaseModel):
    occurred_at: datetime
    event_type: Literal["stage_change", "milestone", "note", "risk"]
    description: str = Field(min_length=3, max_length=2000)
    source_ref: str | None = Field(default=None, max_length=255)


class TransactionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transaction_id: str
    occurred_at: datetime
    event_type: str
    description: str
    source_ref: str | None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    sector: str
    stage: str
    next_milestone: str
    next_milestone_date: date
    health: str
    lead_user_id: str
    lead_user: OfficerSummary
    summary: str
    updated_by: str
    updated_at: datetime


class TransactionDetailResponse(TransactionResponse):
    events: list[TransactionEventResponse]
    register_entries: list[dict[str, object]]


class MinisterDecisionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    due_date: date
    transaction_id: str | None = None
    context_ref: str | None = Field(default=None, max_length=255)


class MinisterDecisionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    due_date: date | None = None
    transaction_id: str | None = None
    status: Literal["open", "in_progress", "closed"] | None = None
    context_ref: str | None = Field(default=None, max_length=255)


class MinisterDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    due_date: date
    transaction_id: str | None
    status: str
    context_ref: str | None
    transaction: TransactionResponse | None


class EngagementCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    engagement_type: str = Field(min_length=2, max_length=80)
    starts_at: datetime
    location: str = Field(min_length=2, max_length=255)
    pack_status: Literal["not_started", "in_progress", "ready"] = "not_started"
    owner_id: str
    transaction_id: str | None = None


class EngagementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    engagement_type: str | None = Field(default=None, min_length=2, max_length=80)
    starts_at: datetime | None = None
    location: str | None = Field(default=None, min_length=2, max_length=255)
    pack_status: Literal["not_started", "in_progress", "ready"] | None = None
    owner_id: str | None = None
    transaction_id: str | None = None


class EngagementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    engagement_type: str
    starts_at: datetime
    location: str
    pack_status: str
    pack_due_at: datetime
    owner_id: str
    owner: OfficerSummary
    transaction_id: str | None
    transaction: TransactionResponse | None
