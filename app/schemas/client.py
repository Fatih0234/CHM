"""Pydantic schemas for client API payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


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
