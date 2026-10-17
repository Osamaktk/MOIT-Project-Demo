from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIRunResponse(BaseModel):
    id: str
    tool: str
    model_role: str
    model: str
    zone: str
    classification: str
    is_synthetic: bool
    user_id: str | None
    user_name: str | None = None
    outcome: str
    prompt_version: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    error_code: str | None
    approver_id: str | None
    approver_name: str | None = None
    approved_at: datetime | None
    diff_summary: str | None
    created_at: datetime


class ToolSwitchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tool: str
    suspended: bool
    changed_by: str | None
    changed_at: datetime
    reason: str | None


class ToolSwitchUpdate(BaseModel):
    suspended: bool
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def require_nonblank_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("A meaningful reason is required")
        return cleaned


class SpotCheckCreate(BaseModel):
    ai_run_id: str
    finding: str = Field(min_length=3, max_length=2000)
    outcome: str = Field(pattern="^(accurate|partially_accurate|inaccurate|unable_to_verify)$")
