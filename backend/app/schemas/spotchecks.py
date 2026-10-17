from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SpotCheckSampleRequest(BaseModel):
    sample_size: int = Field(default=5, ge=1, le=50)


class SpotCheckUpdate(BaseModel):
    findings: str = Field(min_length=5, max_length=4000)


class SpotCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    period: str
    sample: list[dict]
    reconciled_by: str | None
    reconciler_name: str | None
    findings: str | None
    status: str
    creator_id: str
    creator_name: str
    created_at: datetime
    updated_at: datetime
