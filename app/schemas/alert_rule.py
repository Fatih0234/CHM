"""Pydantic schemas for alert-rule API payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict

from app.db.models.alert_rule import ChannelEnum
from app.db.models.alert_rule import RuleTypeEnum


class AlertRuleCreate(BaseModel):
    """Payload to create an alert rule."""

    client_id: UUID | None = None
    pipeline_id: UUID | None = None
    rule_type: RuleTypeEnum
    threshold: int | None = None
    window_minutes: int | None = None
    channel: ChannelEnum
    destination: str
    is_enabled: bool = True


class AlertRuleUpdate(BaseModel):
    """Payload to update mutable alert rule fields."""

    client_id: UUID | None = None
    pipeline_id: UUID | None = None
    rule_type: RuleTypeEnum | None = None
    threshold: int | None = None
    window_minutes: int | None = None
    channel: ChannelEnum | None = None
    destination: str | None = None
    is_enabled: bool | None = None


class AlertRule(BaseModel):
    """Alert-rule response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID | None = None
    pipeline_id: UUID | None = None
    rule_type: RuleTypeEnum
    threshold: int | None = None
    window_minutes: int | None = None
    channel: ChannelEnum
    destination: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class AlertRuleListResponse(BaseModel):
    """List response envelope for alert rules."""

    items: list[AlertRule]
