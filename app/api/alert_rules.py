"""Alert-rule API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Response
from sqlalchemy.orm import Session

from app.db.base import get_db_session
from app.schemas.alert_rule import AlertRule
from app.schemas.alert_rule import AlertRuleCreate
from app.schemas.alert_rule import AlertRuleListResponse
from app.schemas.alert_rule import AlertRuleUpdate
from app.services.alert_rules import create_alert_rule_service
from app.services.alert_rules import delete_alert_rule_service
from app.services.alert_rules import get_alert_rule_service
from app.services.alert_rules import list_alert_rules_service
from app.services.alert_rules import update_alert_rule_service

router = APIRouter(prefix="/api/v1", tags=["alert_rules"])


@router.post("/alert_rules", response_model=AlertRule, status_code=201)
def create_alert_rule_endpoint(
    payload: AlertRuleCreate,
    session: Session = Depends(get_db_session),
) -> AlertRule:
    """Create an alert rule."""
    return create_alert_rule_service(session, payload)


@router.get("/alert_rules", response_model=AlertRuleListResponse)
def list_alert_rules_endpoint(
    client_id: UUID | None = None,
    pipeline_id: UUID | None = None,
    is_enabled: bool | None = None,
    session: Session = Depends(get_db_session),
) -> AlertRuleListResponse:
    """List alert rules with optional filters."""
    items = list_alert_rules_service(
        session,
        client_id=client_id,
        pipeline_id=pipeline_id,
        is_enabled=is_enabled,
    )
    return AlertRuleListResponse(items=items)


@router.get("/alert_rules/{rule_id}", response_model=AlertRule)
def get_alert_rule_endpoint(
    rule_id: UUID,
    session: Session = Depends(get_db_session),
) -> AlertRule:
    """Get an alert rule by id."""
    return get_alert_rule_service(session, rule_id)


@router.patch("/alert_rules/{rule_id}", response_model=AlertRule)
def update_alert_rule_endpoint(
    rule_id: UUID,
    payload: AlertRuleUpdate,
    session: Session = Depends(get_db_session),
) -> AlertRule:
    """Update an alert rule."""
    return update_alert_rule_service(session, rule_id, payload)


@router.delete("/alert_rules/{rule_id}", status_code=204)
def delete_alert_rule_endpoint(
    rule_id: UUID,
    session: Session = Depends(get_db_session),
) -> Response:
    """Delete an alert rule by id."""
    delete_alert_rule_service(session, rule_id)
    return Response(status_code=204)
