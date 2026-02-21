"""Service helpers for run API operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.core.errors import NotFoundError
from app.db.repository.pipelines import get_pipeline
from app.db.repository.runs import create_run
from app.db.repository.runs import get_latest_run_for_pipeline
from app.db.repository.runs import list_runs
from app.schemas.error import ErrorDetail
from app.schemas.run import OrderDirection
from app.schemas.run import RunCreate
from app.db.models.run import RunStatusEnum


def _raise_validation_error(message: str, *, field: str = "request") -> None:
    raise APIError(
        status_code=400,
        code="validation_error",
        message=message,
        details=[ErrorDetail(field=field, issue=message)],
    )


def _ensure_pipeline_exists(session: Session, pipeline_id: UUID) -> None:
    if get_pipeline(session, pipeline_id) is None:
        raise NotFoundError(message="Pipeline not found")


def create_run_service(session: Session, pipeline_id: UUID, payload: RunCreate):
    """Create and persist a run for a pipeline."""
    _ensure_pipeline_exists(session, pipeline_id)
    external_run_id = payload.external_run_id or f"manual-{uuid4()}"
    try:
        run = create_run(
            session,
            pipeline_id=pipeline_id,
            external_run_id=external_run_id,
            status=payload.status,
            started_at=payload.started_at,
            finished_at=payload.finished_at,
            duration_seconds=payload.duration_seconds,
            rows_processed=payload.rows_processed,
            error_message=payload.error_message,
            status_reason=payload.status_reason,
            payload=payload.payload,
        )
        session.commit()
        return run
    except IntegrityError:
        session.rollback()
        _raise_validation_error("Run payload violates schema constraints")


def list_runs_service(
    session: Session,
    *,
    pipeline_id: UUID,
    status: RunStatusEnum | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    order: OrderDirection = "desc",
):
    """List runs for a pipeline with filter options."""
    _ensure_pipeline_exists(session, pipeline_id)
    return list_runs(
        session,
        pipeline_id=pipeline_id,
        status=status,
        since=since,
        until=until,
        limit=limit,
        order=order,
    )


def get_latest_run_service(session: Session, pipeline_id: UUID):
    """Get latest run for a pipeline with deterministic ordering."""
    _ensure_pipeline_exists(session, pipeline_id)
    run = get_latest_run_for_pipeline(session, pipeline_id=pipeline_id)
    if run is None:
        raise NotFoundError(message="Run not found")
    return run
