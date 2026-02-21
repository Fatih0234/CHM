"""Service helpers for alert-rule API operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.core.errors import NotFoundError
from app.db.models.alert_rule import RuleTypeEnum
from app.db.repository.alert_rules import UNSET
from app.db.repository.alert_rules import create_alert_rule
from app.db.repository.alert_rules import delete_alert_rule
from app.db.repository.alert_rules import get_alert_rule
from app.db.repository.alert_rules import list_alert_rules
from app.db.repository.alert_rules import update_alert_rule
from app.schemas.alert_rule import AlertRuleCreate
from app.schemas.alert_rule import AlertRuleUpdate
from app.schemas.error import ErrorDetail


def _raise_validation_error(message: str, *, field: str = "request") -> None:
    raise APIError(
        status_code=400,
        code="validation_error",
        message=message,
        details=[ErrorDetail(field=field, issue=message)],
    )


def _validate_scope(client_id: UUID | None, pipeline_id: UUID | None) -> None:
    if client_id is None and pipeline_id is None:
        _raise_validation_error(
            "At least one scope must be set (client_id or pipeline_id)",
            field="client_id",
        )


def _validate_rule_params(
    *,
    rule_type: RuleTypeEnum,
    threshold: int | None,
    window_minutes: int | None,
) -> None:
    if threshold is not None and threshold <= 0:
        _raise_validation_error("threshold must be greater than 0", field="threshold")
    if window_minutes is not None and window_minutes <= 0:
        _raise_validation_error("window_minutes must be greater than 0", field="window_minutes")
    if rule_type == RuleTypeEnum.FAILURES_IN_WINDOW and (
        threshold is None or window_minutes is None
    ):
        _raise_validation_error(
            "failures_in_window requires threshold and window_minutes",
            field="rule_type",
        )


def create_alert_rule_service(session: Session, payload: AlertRuleCreate):
    """Create and persist a new alert rule."""
    _validate_scope(payload.client_id, payload.pipeline_id)
    _validate_rule_params(
        rule_type=payload.rule_type,
        threshold=payload.threshold,
        window_minutes=payload.window_minutes,
    )
    try:
        alert_rule = create_alert_rule(
            session,
            client_id=payload.client_id,
            pipeline_id=payload.pipeline_id,
            rule_type=payload.rule_type,
            threshold=payload.threshold,
            window_minutes=payload.window_minutes,
            channel=payload.channel,
            destination=payload.destination,
            is_enabled=payload.is_enabled,
        )
        session.commit()
        return alert_rule
    except IntegrityError:
        session.rollback()
        _raise_validation_error("Alert rule payload violates schema constraints")


def list_alert_rules_service(
    session: Session,
    *,
    client_id: UUID | None = None,
    pipeline_id: UUID | None = None,
    is_enabled: bool | None = None,
):
    """List alert rules with optional scope and enabled filters."""
    return list_alert_rules(
        session,
        client_id=client_id,
        pipeline_id=pipeline_id,
        is_enabled=is_enabled,
    )


def get_alert_rule_service(session: Session, rule_id: UUID):
    """Fetch an alert rule or raise not found."""
    alert_rule = get_alert_rule(session, rule_id)
    if alert_rule is None:
        raise NotFoundError(message="Alert rule not found")
    return alert_rule


def update_alert_rule_service(session: Session, rule_id: UUID, payload: AlertRuleUpdate):
    """Update mutable alert-rule fields."""
    alert_rule = get_alert_rule_service(session, rule_id)

    next_client_id = payload.client_id if "client_id" in payload.model_fields_set else alert_rule.client_id
    next_pipeline_id = (
        payload.pipeline_id if "pipeline_id" in payload.model_fields_set else alert_rule.pipeline_id
    )
    next_rule_type = payload.rule_type if payload.rule_type is not None else alert_rule.rule_type
    next_threshold = payload.threshold if "threshold" in payload.model_fields_set else alert_rule.threshold
    next_window_minutes = (
        payload.window_minutes
        if "window_minutes" in payload.model_fields_set
        else alert_rule.window_minutes
    )

    _validate_scope(next_client_id, next_pipeline_id)
    _validate_rule_params(
        rule_type=next_rule_type,
        threshold=next_threshold,
        window_minutes=next_window_minutes,
    )

    try:
        alert_rule = update_alert_rule(
            session,
            alert_rule,
            client_id=payload.client_id if "client_id" in payload.model_fields_set else UNSET,
            pipeline_id=payload.pipeline_id if "pipeline_id" in payload.model_fields_set else UNSET,
            rule_type=payload.rule_type if "rule_type" in payload.model_fields_set else UNSET,
            threshold=next_threshold if "threshold" in payload.model_fields_set else UNSET,
            window_minutes=next_window_minutes if "window_minutes" in payload.model_fields_set else UNSET,
            channel=payload.channel if "channel" in payload.model_fields_set else UNSET,
            destination=payload.destination if "destination" in payload.model_fields_set else UNSET,
            is_enabled=payload.is_enabled if "is_enabled" in payload.model_fields_set else UNSET,
        )
        session.commit()
        return alert_rule
    except IntegrityError:
        session.rollback()
        _raise_validation_error("Alert rule payload violates schema constraints")


def delete_alert_rule_service(session: Session, rule_id: UUID) -> None:
    """Delete an alert rule by id."""
    alert_rule = get_alert_rule_service(session, rule_id)
    delete_alert_rule(session, alert_rule)
    session.commit()
