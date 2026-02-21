"""Repository primitives for alert-rule entities."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.alert_rule import AlertRule
from app.db.models.alert_rule import ChannelEnum
from app.db.models.alert_rule import RuleTypeEnum

UNSET = object()


def create_alert_rule(
    session: Session,
    *,
    rule_type: RuleTypeEnum,
    channel: ChannelEnum,
    destination: str,
    client_id: UUID | None = None,
    pipeline_id: UUID | None = None,
    threshold: int | None = None,
    window_minutes: int | None = None,
    is_enabled: bool = True,
) -> AlertRule:
    """Create and return an alert rule row."""
    rule_type_value = rule_type.value if isinstance(rule_type, RuleTypeEnum) else rule_type
    channel_value = channel.value if isinstance(channel, ChannelEnum) else channel

    alert_rule = AlertRule(
        client_id=client_id,
        pipeline_id=pipeline_id,
        rule_type=rule_type_value,
        threshold=threshold,
        window_minutes=window_minutes,
        channel=channel_value,
        destination=destination,
        is_enabled=is_enabled,
    )
    session.add(alert_rule)
    session.flush()
    session.refresh(alert_rule)
    return alert_rule


def get_alert_rule(session: Session, rule_id: UUID) -> AlertRule | None:
    """Fetch an alert rule by id."""
    return session.get(AlertRule, rule_id)


def list_alert_rules(
    session: Session,
    *,
    client_id: UUID | None = None,
    pipeline_id: UUID | None = None,
    is_enabled: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AlertRule]:
    """List alert rules with optional scope/enablement filters."""
    stmt = select(AlertRule)
    if pipeline_id is not None:
        stmt = stmt.where(AlertRule.pipeline_id == pipeline_id)
    elif client_id is not None:
        # Pipeline-scoped rules take precedence and should not be returned
        # in a client-only scoped list.
        stmt = stmt.where(AlertRule.client_id == client_id).where(AlertRule.pipeline_id.is_(None))
    if is_enabled is not None:
        stmt = stmt.where(AlertRule.is_enabled == is_enabled)
    stmt = stmt.order_by(AlertRule.created_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt))


def update_alert_rule(
    session: Session,
    alert_rule: AlertRule,
    *,
    rule_type: RuleTypeEnum | None | object = UNSET,
    channel: ChannelEnum | None | object = UNSET,
    destination: str | None | object = UNSET,
    client_id: UUID | None | object = UNSET,
    pipeline_id: UUID | None | object = UNSET,
    threshold: int | None | object = UNSET,
    window_minutes: int | None | object = UNSET,
    is_enabled: bool | None | object = UNSET,
) -> AlertRule:
    """Update mutable alert-rule fields."""
    if rule_type is not UNSET:
        alert_rule.rule_type = (
            rule_type.value if isinstance(rule_type, RuleTypeEnum) else rule_type
        )
    if channel is not UNSET:
        alert_rule.channel = channel.value if isinstance(channel, ChannelEnum) else channel
    if destination is not UNSET:
        alert_rule.destination = destination
    if client_id is not UNSET:
        alert_rule.client_id = client_id
    if pipeline_id is not UNSET:
        alert_rule.pipeline_id = pipeline_id
    if threshold is not UNSET:
        alert_rule.threshold = threshold
    if window_minutes is not UNSET:
        alert_rule.window_minutes = window_minutes
    if is_enabled is not UNSET:
        alert_rule.is_enabled = is_enabled

    session.flush()
    session.refresh(alert_rule)
    return alert_rule


def delete_alert_rule(session: Session, alert_rule: AlertRule) -> None:
    """Delete an alert-rule row."""
    session.delete(alert_rule)
    session.flush()
