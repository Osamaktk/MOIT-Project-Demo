from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    resource_type: str
    resource_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    message: str
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime
