"""Error envelope schemas shared across API handlers."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Single field-level validation or domain issue detail."""

    field: str
    issue: str


class ErrorObject(BaseModel):
    """Canonical error payload object."""

    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    """Top-level API error response envelope."""

    error: ErrorObject
