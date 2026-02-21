"""Repository queries for dashboard-ready analytical outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

_FAILURES_OVER_TIME_SQL = text(
    """
    SELECT
      date_trunc(:bucket, COALESCE(r.finished_at, r.started_at, r.created_at)) AS ts_bucket,
      COUNT(*) AS failed_runs
    FROM runs r
    WHERE r.status = 'failed'
      AND COALESCE(r.finished_at, r.started_at, r.created_at) >= :since
      AND COALESCE(r.finished_at, r.started_at, r.created_at) < :until
    GROUP BY 1
    ORDER BY 1
    """
)

_LATEST_STATUS_BY_PIPELINE_SQL = text(
    """
    WITH latest_run AS (
      SELECT
        r.*,
        ROW_NUMBER() OVER (
          PARTITION BY r.pipeline_id
          ORDER BY r.started_at DESC NULLS LAST, r.finished_at DESC NULLS LAST, r.id DESC
        ) AS rn
      FROM runs r
    )
    SELECT
      c.name AS client_name,
      p.name AS pipeline_name,
      p.platform,
      lr.status AS latest_status,
      COALESCE(lr.started_at, lr.finished_at, lr.created_at) AS last_run_time
    FROM pipelines p
    JOIN clients c ON c.id = p.client_id
    LEFT JOIN latest_run lr ON lr.pipeline_id = p.id AND lr.rn = 1
    WHERE p.is_active = TRUE
      AND c.is_active = TRUE
    ORDER BY c.name, p.name
    """
)

_FAILURE_COUNTS_BY_CLIENT_SQL = text(
    """
    SELECT
      c.id AS client_id,
      c.name AS client_name,
      SUM(CASE WHEN r.status = 'failed'
                AND COALESCE(r.finished_at, r.started_at, r.created_at) >= :as_of - interval '24 hours'
               THEN 1 ELSE 0 END) AS failed_24h,
      SUM(CASE WHEN r.status = 'failed'
                AND COALESCE(r.finished_at, r.started_at, r.created_at) >= :as_of - interval '7 days'
               THEN 1 ELSE 0 END) AS failed_7d
    FROM clients c
    LEFT JOIN pipelines p ON p.client_id = c.id
    LEFT JOIN runs r ON r.pipeline_id = p.id
    GROUP BY c.id, c.name
    ORDER BY failed_24h DESC, failed_7d DESC
    """
)

_TOP_FLAKY_PIPELINES_SQL = text(
    """
    SELECT
      c.name AS client_name,
      p.name AS pipeline_name,
      p.platform,
      COUNT(*) FILTER (WHERE r.status = 'failed') AS failure_count,
      COUNT(*) AS total_runs,
      CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE ROUND((COUNT(*) FILTER (WHERE r.status = 'failed'))::numeric / COUNT(*), 4)
      END AS failure_rate
    FROM pipelines p
    JOIN clients c ON c.id = p.client_id
    LEFT JOIN runs r ON r.pipeline_id = p.id
      AND COALESCE(r.finished_at, r.started_at, r.created_at) >= :since
    GROUP BY c.name, p.name, p.platform
    ORDER BY failure_count DESC, failure_rate DESC, total_runs DESC
    LIMIT :limit
    """
)

_FAILURE_RATE_BY_PLATFORM_SQL = text(
    """
    SELECT
      p.platform,
      COUNT(*) FILTER (WHERE r.status = 'failed') AS failures,
      COUNT(*) AS total_runs,
      CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE ROUND((COUNT(*) FILTER (WHERE r.status = 'failed'))::numeric / COUNT(*), 4)
      END AS failure_rate
    FROM pipelines p
    LEFT JOIN runs r ON r.pipeline_id = p.id
    WHERE COALESCE(r.finished_at, r.started_at, r.created_at) >= :since
      AND COALESCE(r.finished_at, r.started_at, r.created_at) < :until
    GROUP BY p.platform
    ORDER BY failure_rate DESC
    """
)

_RUN_DURATION_DISTRIBUTION_SQL = text(
    """
    SELECT
      width_bucket(r.duration_seconds, 0, :max_duration_seconds, :bucket_count) AS duration_bucket,
      COUNT(*) AS run_count
    FROM runs r
    WHERE r.duration_seconds IS NOT NULL
      AND COALESCE(r.finished_at, r.started_at, r.created_at) >= :since
      AND COALESCE(r.finished_at, r.started_at, r.created_at) < :until
    GROUP BY duration_bucket
    ORDER BY duration_bucket
    """
)

_ALLOWED_BUCKETS = {"minute", "hour", "day", "week"}


def _rows_as_dicts(result: Any) -> list[dict[str, Any]]:
    return [dict(row._mapping) for row in result]


def query_failures_over_time(
    session: Session,
    *,
    since: datetime,
    until: datetime,
    bucket: str = "day",
) -> list[dict[str, Any]]:
    """Return failed-run counts grouped by time bucket."""
    if bucket not in _ALLOWED_BUCKETS:
        raise ValueError(f"Unsupported bucket `{bucket}`")
    result = session.execute(_FAILURES_OVER_TIME_SQL, {"since": since, "until": until, "bucket": bucket})
    return _rows_as_dicts(result)


def query_latest_status_by_pipeline(session: Session) -> list[dict[str, Any]]:
    """Return latest run status snapshot for each active pipeline."""
    result = session.execute(_LATEST_STATUS_BY_PIPELINE_SQL)
    return _rows_as_dicts(result)


def query_failure_counts_by_client(
    session: Session,
    *,
    as_of: datetime,
) -> list[dict[str, Any]]:
    """Return failed-run counts by client for rolling windows."""
    result = session.execute(_FAILURE_COUNTS_BY_CLIENT_SQL, {"as_of": as_of})
    return _rows_as_dicts(result)


def query_top_flaky_pipelines(
    session: Session,
    *,
    since: datetime,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return top pipelines by failure frequency and failure rate."""
    result = session.execute(_TOP_FLAKY_PIPELINES_SQL, {"since": since, "limit": limit})
    return _rows_as_dicts(result)


def query_failure_rate_by_platform(
    session: Session,
    *,
    since: datetime,
    until: datetime,
) -> list[dict[str, Any]]:
    """Return failures and failure rate grouped by platform."""
    result = session.execute(_FAILURE_RATE_BY_PLATFORM_SQL, {"since": since, "until": until})
    return _rows_as_dicts(result)


def query_run_duration_distribution(
    session: Session,
    *,
    since: datetime,
    until: datetime,
    max_duration_seconds: int,
    bucket_count: int,
) -> list[dict[str, Any]]:
    """Return duration distribution buckets for runs with duration values."""
    result = session.execute(
        _RUN_DURATION_DISTRIBUTION_SQL,
        {
            "since": since,
            "until": until,
            "max_duration_seconds": max_duration_seconds,
            "bucket_count": bucket_count,
        },
    )
    return _rows_as_dicts(result)
