"""Dashboard query adapter service helpers."""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.repository.dashboard import query_failure_counts_by_client
from app.db.repository.dashboard import query_failure_rate_by_platform
from app.db.repository.dashboard import query_failures_over_time
from app.db.repository.dashboard import query_latest_status_by_pipeline
from app.db.repository.dashboard import query_run_duration_distribution
from app.db.repository.dashboard import query_top_flaky_pipelines
from app.schemas.error import ErrorDetail

_DEFAULT_SINCE = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _raise_validation_error(message: str, *, field: str = "request") -> None:
    raise APIError(
        status_code=400,
        code="validation_error",
        message=message,
        details=[ErrorDetail(field=field, issue=message)],
    )


def _normalize_window(
    *,
    since: datetime | None,
    until: datetime | None,
) -> tuple[datetime, datetime]:
    normalized_since = since or _DEFAULT_SINCE
    normalized_until = until or datetime.now(timezone.utc)

    if normalized_since >= normalized_until:
        _raise_validation_error("since must be before until", field="since")
    return normalized_since, normalized_until


def get_failures_over_time(
    session: Session,
    *,
    since: datetime | None,
    until: datetime | None,
    bucket: str = "day",
):
    """Return failures over time for dashboard time-series views."""
    normalized_since, normalized_until = _normalize_window(since=since, until=until)
    try:
        return query_failures_over_time(
            session,
            since=normalized_since,
            until=normalized_until,
            bucket=bucket,
        )
    except ValueError as exc:
        _raise_validation_error(str(exc), field="bucket")


def get_latest_status_by_pipeline(session: Session):
    """Return latest status snapshot per active pipeline."""
    return query_latest_status_by_pipeline(session)


def get_failure_counts_by_client(
    session: Session,
    *,
    as_of: datetime | None = None,
):
    """Return failed-run counts by client for rolling 24h and 7d windows."""
    return query_failure_counts_by_client(
        session,
        as_of=as_of or datetime.now(timezone.utc),
    )


def get_top_flaky_pipelines(
    session: Session,
    *,
    as_of: datetime | None = None,
    limit: int = 20,
):
    """Return top flaky pipelines for the prior 30 days."""
    if limit <= 0:
        _raise_validation_error("limit must be greater than 0", field="limit")
    window_end = as_of or datetime.now(timezone.utc)
    return query_top_flaky_pipelines(
        session,
        since=window_end - timedelta(days=30),
        limit=limit,
    )


def get_failure_rate_by_platform(
    session: Session,
    *,
    since: datetime | None,
    until: datetime | None,
):
    """Return failure-rate output grouped by platform."""
    normalized_since, normalized_until = _normalize_window(since=since, until=until)
    return query_failure_rate_by_platform(
        session,
        since=normalized_since,
        until=normalized_until,
    )


def get_run_duration_distribution(
    session: Session,
    *,
    since: datetime | None,
    until: datetime | None,
    max_duration_seconds: int = 3600,
    bucket_count: int = 10,
):
    """Return run-duration histogram buckets for dashboards."""
    if max_duration_seconds <= 0:
        _raise_validation_error(
            "max_duration_seconds must be greater than 0",
            field="max_duration_seconds",
        )
    if bucket_count <= 0:
        _raise_validation_error("bucket_count must be greater than 0", field="bucket_count")

    normalized_since, normalized_until = _normalize_window(since=since, until=until)
    return query_run_duration_distribution(
        session,
        since=normalized_since,
        until=normalized_until,
        max_duration_seconds=max_duration_seconds,
        bucket_count=bucket_count,
    )
