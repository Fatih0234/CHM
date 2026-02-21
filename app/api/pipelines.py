"""Pipeline API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.base import get_db_session
from app.schemas.pipeline import Pipeline
from app.schemas.pipeline import PipelineCreate
from app.schemas.pipeline import PipelineListResponse
from app.schemas.pipeline import PipelineUpdate
from app.services.pipelines import create_pipeline_service
from app.services.pipelines import get_pipeline_service
from app.services.pipelines import list_client_pipelines_service
from app.services.pipelines import update_pipeline_service

router = APIRouter(prefix="/api/v1", tags=["pipelines"])


@router.post("/clients/{client_id}/pipelines", response_model=Pipeline, status_code=201)
def create_pipeline_endpoint(
    client_id: UUID,
    payload: PipelineCreate,
    session: Session = Depends(get_db_session),
) -> Pipeline:
    """Create a pipeline under a client."""
    return create_pipeline_service(session, client_id, payload)


@router.get("/clients/{client_id}/pipelines", response_model=PipelineListResponse)
def list_client_pipelines_endpoint(
    client_id: UUID,
    is_active: bool | None = None,
    session: Session = Depends(get_db_session),
) -> PipelineListResponse:
    """List pipelines for a client."""
    pipelines = list_client_pipelines_service(session, client_id=client_id, is_active=is_active)
    return PipelineListResponse(items=pipelines)


@router.get("/pipelines/{pipeline_id}", response_model=Pipeline)
def get_pipeline_endpoint(
    pipeline_id: UUID,
    session: Session = Depends(get_db_session),
) -> Pipeline:
    """Get a single pipeline by id."""
    return get_pipeline_service(session, pipeline_id)


@router.patch("/pipelines/{pipeline_id}", response_model=Pipeline)
def update_pipeline_endpoint(
    pipeline_id: UUID,
    payload: PipelineUpdate,
    session: Session = Depends(get_db_session),
) -> Pipeline:
    """Update a pipeline."""
    return update_pipeline_service(session, pipeline_id, payload)
