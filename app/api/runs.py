"""Run API routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from app.db.base import get_db_session
from app.db.models.run import RunStatusEnum
from app.schemas.run import OrderDirection
from app.schemas.run import Run
from app.schemas.run import RunCreate
from app.schemas.run import RunListResponse
from app.services.runs import create_run_service
from app.services.runs import get_latest_run_service
from app.services.runs import list_runs_service

router = APIRouter(prefix="/api/v1", tags=["runs"])


@router.post("/pipelines/{pipeline_id}/runs", response_model=Run, status_code=201)
def create_run_endpoint(
    pipeline_id: UUID,
    payload: RunCreate,
    session: Session = Depends(get_db_session),
) -> Run:
    """Create a run for a pipeline."""
    return create_run_service(session, pipeline_id, payload)


@router.get("/pipelines/{pipeline_id}/runs", response_model=RunListResponse)
def list_runs_endpoint(
    pipeline_id: UUID,
    status: RunStatusEnum | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    order: OrderDirection = "desc",
    session: Session = Depends(get_db_session),
) -> RunListResponse:
    """List runs for a pipeline."""
    runs = list_runs_service(
        session,
        pipeline_id=pipeline_id,
        status=status,
        since=since,
        until=until,
        limit=limit,
        order=order,
    )
    return RunListResponse(items=runs)


@router.get("/pipelines/{pipeline_id}/runs/latest", response_model=Run)
def get_latest_run_endpoint(
    pipeline_id: UUID,
    session: Session = Depends(get_db_session),
) -> Run:
    """Get the latest run for a pipeline."""
    return get_latest_run_service(session, pipeline_id)
