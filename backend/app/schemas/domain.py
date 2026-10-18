from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import PROJECT_STAGE_LABELS


class OrganisationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    short_name: str
    type: str
    aliases: list[str]


class ProjectView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    aliases: list[str]
    sector: str
    stage: str
    health: Literal["on_track", "at_risk", "delayed"]
    health_reason: str
    lead_org_id: str | None
    summary: str
    updated_at: datetime


class ActionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    serial_no: int | None
    fy: str
    description: str
    owner_org_id: str | None
    owner_person_name: str | None
    owner_user_id: str | None
    occurred_at: datetime
    deadline: date | None
    deadline_text: str
    deadline_precision: str
    priority: Literal["A", "B", "C"]
    status: str
    status_source: str
    review_state: str
    project_id: str | None
    source_document_id: str | None
    source_quote: str | None
    source_page: int | None


class ActionCreate(BaseModel):
    description: str = Field(min_length=3, max_length=4000)
    owner_org_id: str | None = None
    owner_person_name: str | None = Field(default=None, max_length=160)
    owner_user_id: str | None = None
    occurred_at: datetime
    deadline_text: str = Field(min_length=1, max_length=255)
    deadline: date | None = None
    deadline_precision: Literal["day", "week", "month", "relative"] = "day"
    priority: Literal["A", "B", "C"] = "B"
    status_source: Literal["open", "done_at_upload"] = "open"
    project_id: str | None = None
    source_document_id: str | None = None
    source_quote: str | None = Field(default=None, max_length=2000)
    source_page: int | None = Field(default=None, ge=1)


class ProjectCreate(BaseModel):
    code: str = Field(min_length=2, max_length=24, pattern="^[A-Z0-9][A-Z0-9-]+$")
    name: str = Field(min_length=3, max_length=180)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    sector: str = Field(min_length=2, max_length=80)
    stage: str
    lead_org_id: str | None = None
    summary: str = Field(min_length=3, max_length=2000)

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, value: str) -> str:
        if value not in PROJECT_STAGE_LABELS:
            raise ValueError("Unknown project stage")
        return value
