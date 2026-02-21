"""Repository primitives for pipeline entities."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.pipeline import Pipeline
from app.db.models.pipeline import PipelineTypeEnum
from app.db.models.pipeline import PlatformEnum


def create_pipeline(
    session: Session,
    *,
    client_id: UUID,
    name: str,
    platform: PlatformEnum,
    pipeline_type: PipelineTypeEnum,
    external_id: str | None = None,
    description: str | None = None,
    environment: str = "prod",
    is_active: bool = True,
) -> Pipeline:
    """Create and return a pipeline row."""
    platform_value = platform.value if isinstance(platform, PlatformEnum) else platform
    pipeline_type_value = (
        pipeline_type.value if isinstance(pipeline_type, PipelineTypeEnum) else pipeline_type
    )

    pipeline = Pipeline(
        client_id=client_id,
        name=name,
        platform=platform_value,
        pipeline_type=pipeline_type_value,
        external_id=external_id,
        description=description,
        environment=environment,
        is_active=is_active,
    )
    session.add(pipeline)
    session.flush()
    session.refresh(pipeline)
    return pipeline


def get_pipeline(session: Session, pipeline_id: UUID) -> Pipeline | None:
    """Fetch a pipeline by id."""
    return session.get(Pipeline, pipeline_id)


def list_pipelines(
    session: Session,
    *,
    client_id: UUID | None = None,
    is_active: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Pipeline]:
    """List pipelines with optional client/active filters."""
    stmt = select(Pipeline)
    if client_id is not None:
        stmt = stmt.where(Pipeline.client_id == client_id)
    if is_active is not None:
        stmt = stmt.where(Pipeline.is_active == is_active)
    stmt = stmt.order_by(Pipeline.created_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt))


def list_ingestion_pipelines_with_external_id(
    session: Session,
    *,
    only_active: bool = True,
) -> list[Pipeline]:
    """List pipelines eligible for external ingestion sync."""
    stmt = select(Pipeline).where(Pipeline.external_id.is_not(None))
    stmt = stmt.where(Pipeline.pipeline_type == PipelineTypeEnum.INGESTION)
    if only_active:
        stmt = stmt.where(Pipeline.is_active.is_(True))
    stmt = stmt.order_by(Pipeline.created_at.asc())
    return list(session.scalars(stmt))


def update_pipeline(
    session: Session,
    pipeline: Pipeline,
    *,
    name: str | None = None,
    platform: PlatformEnum | None = None,
    pipeline_type: PipelineTypeEnum | None = None,
    external_id: str | None = None,
    description: str | None = None,
    environment: str | None = None,
    is_active: bool | None = None,
) -> Pipeline:
    """Update mutable pipeline fields."""
    if name is not None:
        pipeline.name = name
    if platform is not None:
        pipeline.platform = platform.value if isinstance(platform, PlatformEnum) else platform
    if pipeline_type is not None:
        pipeline.pipeline_type = (
            pipeline_type.value
            if isinstance(pipeline_type, PipelineTypeEnum)
            else pipeline_type
        )
    if description is not None:
        pipeline.description = description
    if environment is not None:
        pipeline.environment = environment
    if is_active is not None:
        pipeline.is_active = is_active

    if external_id is not None:
        pipeline.external_id = external_id

    session.flush()
    session.refresh(pipeline)
    return pipeline


def disable_pipeline(session: Session, pipeline: Pipeline) -> Pipeline:
    """Soft-disable a pipeline."""
    pipeline.is_active = False
    session.flush()
    session.refresh(pipeline)
    return pipeline
