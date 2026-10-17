from datetime import date, datetime, time, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DocType = Literal["board_paper", "cabinet_paper", "ccop", "wing_paper", "minute", "brief", "register", "other"]
Classification = Literal["public", "internal", "confidential"]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    doc_type: str
    classification: str
    transaction_id: str | None
    source_note: str | None
    is_synthetic: bool
    ingest_status: str
    created_at: datetime
    chunk_count: int = 0


class SearchFilters(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    transaction_id: str | None = None
    doc_type: DocType | None = None
    date_from: date | None = None
    date_to: date | None = None
    top_k: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("End date must be on or after start date")
        return self


class Citation(BaseModel):
    number: int
    document_id: str
    title: str
    doc_type: str
    page: int | None
    section: str | None
    snippet: str
    chunk_id: str


class SearchResponse(BaseModel):
    query: str
    answer: str
    declined: bool
    citations: list[Citation]


class DocumentList(BaseModel):
    items: list[DocumentResponse]
