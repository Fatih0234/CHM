"""Pydantic schemas for pipeline API payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict

from app.db.models.pipeline import PipelineTypeEnum
from app.db.models.pipeline import PlatformEnum

Environment = Literal["dev", "staging", "prod"]


class PipelineCreate(BaseModel):
    """Payload to create a pipeline under a client."""

    name: str
    platform: PlatformEnum
    pipeline_type: PipelineTypeEnum
    external_id: str | None = None
    description: str | None = None
    environment: Environment = "prod"
    is_active: bool = True


class PipelineUpdate(BaseModel):
    """Payload to update mutable pipeline fields."""

    name: str | None = None
    platform: PlatformEnum | None = None
    pipeline_type: PipelineTypeEnum | None = None
    external_id: str | None = None
    description: str | None = None
    environment: Environment | None = None
    is_active: bool | None = None


class Pipeline(BaseModel):
    """Pipeline response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    name: str
    platform: PlatformEnum
    external_id: str | None = None
    pipeline_type: PipelineTypeEnum
    description: str | None = None
    environment: Environment
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PipelineListResponse(BaseModel):
    """List response envelope for pipelines."""

    items: list[Pipeline]
