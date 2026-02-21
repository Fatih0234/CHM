"""Client run summary service helpers."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from uuid import UUID

from sqlalchemy import Select
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.core.errors import NotFoundError
from app.db.models.pipeline import Pipeline
from app.db.models.run import Run
from app.db.models.run import RunStatusEnum
from app.db.repository.clients import get_client
from app.schemas.client import ClientRunSummary
from app.schemas.client import LatestPipelineStatus
from app.schemas.error import ErrorDetail

_DEFAULT_SINCE = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _normalize_window(
    *,
    since: datetime | None,
    until: datetime | None,
) -> tuple[datetime, datetime]:
    normalized_since = since or _DEFAULT_SINCE
    normalized_until = until or datetime.now(timezone.utc)

    if normalized_since >= normalized_until:
        raise APIError(
            status_code=400,
            code="validation_error",
            message="Invalid time window",
            details=[ErrorDetail(field="since", issue="must be before until")],
        )
    return normalized_since, normalized_until


def get_client_run_summary_service(
    session: Session,
    *,
    client_id: UUID,
    since: datetime | None,
    until: datetime | None,
) -> ClientRunSummary:
    """Return status counts and latest pipeline status for a client."""
    if get_client(session, client_id) is None:
        raise NotFoundError(message="Client not found")

    normalized_since, normalized_until = _normalize_window(since=since, until=until)

    status_counts = {status.value: 0 for status in RunStatusEnum}
    counts_stmt: Select[tuple[RunStatusEnum, int]] = (
        select(Run.status, func.count(Run.id))
        .join(Pipeline, Pipeline.id == Run.pipeline_id)
        .where(Pipeline.client_id == client_id)
        .where(Run.started_at >= normalized_since)
        .where(Run.started_at < normalized_until)
        .group_by(Run.status)
    )
    for status, count in session.execute(counts_stmt):
        key = status.value if isinstance(status, RunStatusEnum) else str(status)
        status_counts[key] = int(count)

    latest_stmt: Select[tuple[Run, str, object]] = (
        select(Run, Pipeline.name, Pipeline.platform)
        .join(Pipeline, Pipeline.id == Run.pipeline_id)
        .where(Pipeline.client_id == client_id)
        .where(Run.started_at >= normalized_since)
        .where(Run.started_at < normalized_until)
        .order_by(
            Pipeline.name.asc(),
            Pipeline.id.asc(),
            Run.started_at.desc().nulls_last(),
            Run.finished_at.desc().nulls_last(),
            Run.id.desc(),
        )
    )

    latest_by_pipeline: list[LatestPipelineStatus] = []
    seen_pipeline_ids: set[UUID] = set()
    for run, pipeline_name, platform in session.execute(latest_stmt):
        if run.pipeline_id in seen_pipeline_ids:
            continue
        seen_pipeline_ids.add(run.pipeline_id)
        latest_by_pipeline.append(
            LatestPipelineStatus(
                pipeline_id=run.pipeline_id,
                pipeline_name=pipeline_name,
                platform=platform,
                latest_status=run.status,
                latest_run_at=run.started_at,
            )
        )

    latest_by_pipeline.sort(key=lambda item: (item.pipeline_name, str(item.pipeline_id)))
    return ClientRunSummary(
        client_id=client_id,
        since=normalized_since,
        until=normalized_until,
        status_counts=status_counts,
        latest_by_pipeline=latest_by_pipeline,
    )
