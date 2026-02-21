"""Pydantic schemas for client API payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict

from app.db.models.pipeline import PlatformEnum
from app.db.models.run import RunStatusEnum


class ClientCreate(BaseModel):
    """Payload to create a client."""

    name: str


class ClientUpdate(BaseModel):
    """Payload to update mutable client fields."""

    name: str | None = None
    is_active: bool | None = None


class Client(BaseModel):
    """Client response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClientListResponse(BaseModel):
    """List response envelope for clients."""

    items: list[Client]


class LatestPipelineStatus(BaseModel):
    """Latest run snapshot for one pipeline."""

    pipeline_id: UUID
    pipeline_name: str
    platform: PlatformEnum
    latest_status: RunStatusEnum
    latest_run_at: datetime | None = None


class ClientRunSummary(BaseModel):
    """Run summary payload for a client and time window."""

    client_id: UUID
    since: datetime
    until: datetime
    status_counts: dict[str, int]
    latest_by_pipeline: list[LatestPipelineStatus]
