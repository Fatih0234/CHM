"""Service helpers for pipeline API operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.core.errors import NotFoundError
from app.db.repository.clients import get_client
from app.db.repository.pipelines import create_pipeline
from app.db.repository.pipelines import get_pipeline
from app.db.repository.pipelines import list_pipelines
from app.db.repository.pipelines import update_pipeline
from app.schemas.error import ErrorDetail
from app.schemas.pipeline import PipelineCreate
from app.schemas.pipeline import PipelineUpdate


def _raise_validation_error(message: str, *, field: str = "request") -> None:
    raise APIError(
        status_code=400,
        code="validation_error",
        message=message,
        details=[ErrorDetail(field=field, issue=message)],
    )


def _ensure_client_exists(session: Session, client_id: UUID) -> None:
    if get_client(session, client_id) is None:
        raise NotFoundError(message="Client not found")


def create_pipeline_service(session: Session, client_id: UUID, payload: PipelineCreate):
    """Create and persist a pipeline for a client."""
    _ensure_client_exists(session, client_id)
    try:
        pipeline = create_pipeline(
            session,
            client_id=client_id,
            name=payload.name,
            platform=payload.platform,
            pipeline_type=payload.pipeline_type,
            external_id=payload.external_id,
            description=payload.description,
            environment=payload.environment,
            is_active=payload.is_active,
        )
        session.commit()
        return pipeline
    except IntegrityError:
        session.rollback()
        _raise_validation_error("Pipeline payload violates schema constraints")


def list_client_pipelines_service(
    session: Session,
    *,
    client_id: UUID,
    is_active: bool | None = None,
):
    """List pipelines scoped to a client."""
    _ensure_client_exists(session, client_id)
    return list_pipelines(session, client_id=client_id, is_active=is_active)


def get_pipeline_service(session: Session, pipeline_id: UUID):
    """Fetch a pipeline or raise not found."""
    pipeline = get_pipeline(session, pipeline_id)
    if pipeline is None:
        raise NotFoundError(message="Pipeline not found")
    return pipeline


def update_pipeline_service(session: Session, pipeline_id: UUID, payload: PipelineUpdate):
    """Update mutable pipeline fields for an existing pipeline."""
    pipeline = get_pipeline_service(session, pipeline_id)
    try:
        pipeline = update_pipeline(
            session,
            pipeline,
            name=payload.name,
            platform=payload.platform,
            pipeline_type=payload.pipeline_type,
            external_id=payload.external_id,
            description=payload.description,
            environment=payload.environment,
            is_active=payload.is_active,
        )
        session.commit()
        return pipeline
    except IntegrityError:
        session.rollback()
        _raise_validation_error("Pipeline payload violates schema constraints")
