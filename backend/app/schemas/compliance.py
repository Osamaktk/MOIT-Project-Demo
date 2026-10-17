from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["statutory", "cabinet_ccop", "board", "audit", "courts", "transaction_milestone", "integrity", "rti"]


class ComplianceCreate(BaseModel):
    category: Category
    title: str = Field(min_length=3, max_length=255)
    due_date: date
    owner_id: str
    status: Literal["open", "in_progress", "complete"] = "open"
    reference: str | None = Field(default=None, max_length=255)


class ComplianceUpdate(BaseModel):
    category: Category | None = None
    title: str | None = Field(default=None, min_length=3, max_length=255)
    due_date: date | None = None
    owner_id: str | None = None
    status: Literal["open", "in_progress", "complete"] | None = None
    reference: str | None = Field(default=None, max_length=255)


class ComplianceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    category: str
    title: str
    due_date: date
    owner_id: str
    owner_name: str
    status: str
    reference: str | None
    created_at: datetime
    updated_at: datetime
