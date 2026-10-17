from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    context: dict[str, Any] | None = None


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None
    citations: list[dict[str, Any]] | None
    created_at: datetime


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse] = []


class ProposalEdit(BaseModel):
    description: str = Field(min_length=3, max_length=4000)
    officer_id: str
    deadline: date
    priority: str = Field(pattern="^[ABC]$")
