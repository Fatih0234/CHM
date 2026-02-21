"""Pydantic schemas for run API payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict

from app.db.models.run import RunStatusEnum

OrderDirection = Literal["desc", "asc"]


class RunCreate(BaseModel):
    """Payload to create a manual run event."""

    external_run_id: str | None = None
    status: RunStatusEnum
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    rows_processed: int | None = None
    error_message: str | None = None
    status_reason: str | None = None
    payload: dict[str, Any] | None = None


class Run(BaseModel):
    """Run response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pipeline_id: UUID
    external_run_id: str
    status: RunStatusEnum
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    rows_processed: int | None = None
    error_message: str | None = None
    status_reason: str | None = None
    payload: dict[str, Any] | None = None
    ingested_at: datetime
    created_at: datetime
    updated_at: datetime


class RunListResponse(BaseModel):
    """List response envelope for runs."""

    items: list[Run]
