"""Repository primitives for pipeline run entities."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from uuid import UUID

from sqlalchemy import Select
from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models.run import Run
from app.db.models.run import RunStatusEnum


def create_run(
    session: Session,
    *,
    pipeline_id: UUID,
    external_run_id: str,
    status: RunStatusEnum,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    duration_seconds: int | None = None,
    rows_processed: int | None = None,
    error_message: str | None = None,
    status_reason: str | None = None,
    payload: dict | None = None,
) -> Run:
    """Create and return a run row."""
    status_value = status.value if isinstance(status, RunStatusEnum) else status

    run = Run(
        pipeline_id=pipeline_id,
        external_run_id=external_run_id,
        status=status_value,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
        rows_processed=rows_processed,
        error_message=error_message,
        status_reason=status_reason,
        payload=payload,
    )
    session.add(run)
    session.flush()
    session.refresh(run)
    return run


def get_run(session: Session, run_id: UUID) -> Run | None:
    """Fetch a run by id."""
    return session.get(Run, run_id)


def list_runs(
    session: Session,
    *,
    pipeline_id: UUID,
    status: RunStatusEnum | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    order: str = "desc",
) -> list[Run]:
    """List runs for a pipeline with optional filters."""
    stmt: Select[tuple[Run]] = select(Run).where(Run.pipeline_id == pipeline_id)
    if status is not None:
        status_value = status.value if isinstance(status, RunStatusEnum) else status
        stmt = stmt.where(Run.status == status_value)
    if since is not None:
        stmt = stmt.where(Run.started_at >= since)
    if until is not None:
        stmt = stmt.where(Run.started_at < until)

    if order == "asc":
        stmt = stmt.order_by(
            Run.started_at.asc().nulls_last(),
            Run.finished_at.asc().nulls_last(),
            Run.id.asc(),
        )
    else:
        stmt = stmt.order_by(
            Run.started_at.desc().nulls_last(),
            Run.finished_at.desc().nulls_last(),
            Run.id.desc(),
        )

    stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def get_latest_run_for_pipeline(session: Session, *, pipeline_id: UUID) -> Run | None:
    """Return the latest run for a pipeline using CHM ordering rules."""
    stmt = (
        select(Run)
        .where(Run.pipeline_id == pipeline_id)
        .order_by(
            Run.started_at.desc().nulls_last(),
            Run.finished_at.desc().nulls_last(),
            desc(Run.id),
        )
        .limit(1)
    )
    return session.scalars(stmt).first()


def update_run(
    session: Session,
    run: Run,
    *,
    status: RunStatusEnum | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    duration_seconds: int | None = None,
    rows_processed: int | None = None,
    error_message: str | None = None,
    status_reason: str | None = None,
    payload: dict | None = None,
) -> Run:
    """Update mutable run fields."""
    if status is not None:
        run.status = status.value if isinstance(status, RunStatusEnum) else status
    if started_at is not None:
        run.started_at = started_at
    if finished_at is not None:
        run.finished_at = finished_at
    if duration_seconds is not None:
        run.duration_seconds = duration_seconds
    if rows_processed is not None:
        run.rows_processed = rows_processed
    if error_message is not None:
        run.error_message = error_message
    if status_reason is not None:
        run.status_reason = status_reason
    if payload is not None:
        run.payload = payload

    session.flush()
    session.refresh(run)
    return run


def upsert_run(
    session: Session,
    *,
    pipeline_id: UUID,
    external_run_id: str,
    status: RunStatusEnum,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    duration_seconds: int | None = None,
    rows_processed: int | None = None,
    error_message: str | None = None,
    status_reason: str | None = None,
    payload: dict | None = None,
    ingested_at: datetime | None = None,
) -> Run:
    """Insert or update a run keyed by `(pipeline_id, external_run_id)`."""
    status_value = status.value if isinstance(status, RunStatusEnum) else status
    now = ingested_at or datetime.now(timezone.utc)

    insert_stmt = insert(Run).values(
        pipeline_id=pipeline_id,
        external_run_id=external_run_id,
        status=status_value,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
        rows_processed=rows_processed,
        error_message=error_message,
        status_reason=status_reason,
        payload=payload,
        ingested_at=now,
        updated_at=now,
    )

    upsert_stmt = insert_stmt.on_conflict_do_update(
        constraint="uq_runs_pipeline_id_external_run_id",
        set_={
            "status": status_value,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_seconds,
            "rows_processed": rows_processed,
            "error_message": error_message,
            "status_reason": status_reason,
            "payload": payload,
            "ingested_at": now,
            "updated_at": now,
        },
    ).returning(Run.id)

    run_id = session.execute(upsert_stmt).scalar_one()
    run = session.get(Run, run_id)
    if run is None:
        raise RuntimeError("Upsert did not return a persisted run")
    return run
