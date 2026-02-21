"""Unit tests for dashboard query repository and service adapter."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

import pytest

from app.core.errors import APIError
import app.db.repository.dashboard as dashboard_repo
from app.services import dashboard_queries


class _RowStub:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping


class _ResultStub:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = [_RowStub(row) for row in rows]

    def __iter__(self):
        return iter(self._rows)


class _SessionStub:
    def __init__(self, responses: list[list[dict[str, object]]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def execute(self, statement, params=None):
        self.calls.append({"sql": str(statement), "params": params})
        rows = self._responses.pop(0) if self._responses else []
        return _ResultStub(rows)


def test_dashboard_repository_queries_bind_params_and_map_rows() -> None:
    since = datetime(2026, 2, 1, tzinfo=timezone.utc)
    until = datetime(2026, 2, 2, tzinfo=timezone.utc)
    as_of = datetime(2026, 2, 3, tzinfo=timezone.utc)

    session = _SessionStub(
        responses=[
            [{"ts_bucket": since, "failed_runs": 2}],
            [{"client_name": "acme", "pipeline_name": "pipe-a", "latest_status": "failed"}],
            [{"client_id": "c1", "failed_24h": 1, "failed_7d": 3}],
            [{"pipeline_name": "pipe-a", "failure_count": 2, "total_runs": 3, "failure_rate": 0.6667}],
            [{"platform": "airflow", "failures": 2, "total_runs": 5, "failure_rate": 0.4}],
            [{"duration_bucket": 3, "run_count": 8}],
        ]
    )

    failures = dashboard_repo.query_failures_over_time(
        session, since=since, until=until, bucket="day"
    )
    latest = dashboard_repo.query_latest_status_by_pipeline(session)
    counts = dashboard_repo.query_failure_counts_by_client(session, as_of=as_of)
    flaky = dashboard_repo.query_top_flaky_pipelines(session, since=since, limit=10)
    rates = dashboard_repo.query_failure_rate_by_platform(session, since=since, until=until)
    durations = dashboard_repo.query_run_duration_distribution(
        session,
        since=since,
        until=until,
        max_duration_seconds=7200,
        bucket_count=12,
    )

    assert failures[0]["failed_runs"] == 2
    assert latest[0]["pipeline_name"] == "pipe-a"
    assert counts[0]["failed_7d"] == 3
    assert flaky[0]["failure_rate"] == 0.6667
    assert rates[0]["platform"] == "airflow"
    assert durations[0]["duration_bucket"] == 3

    assert session.calls[0]["params"] == {"since": since, "until": until, "bucket": "day"}
    assert session.calls[1]["params"] is None
    assert session.calls[2]["params"] == {"as_of": as_of}
    assert session.calls[3]["params"] == {"since": since, "limit": 10}
    assert session.calls[4]["params"] == {"since": since, "until": until}
    assert session.calls[5]["params"] == {
        "since": since,
        "until": until,
        "max_duration_seconds": 7200,
        "bucket_count": 12,
    }


def test_dashboard_repository_rejects_invalid_time_bucket() -> None:
    session = _SessionStub(responses=[[]])
    with pytest.raises(ValueError):
        dashboard_repo.query_failures_over_time(
            session,
            since=datetime(2026, 2, 1, tzinfo=timezone.utc),
            until=datetime(2026, 2, 2, tzinfo=timezone.utc),
            bucket="month",
        )


def test_dashboard_service_normalizes_window_and_uses_repository() -> None:
    since = datetime(2026, 2, 1, tzinfo=timezone.utc)
    until = datetime(2026, 2, 2, tzinfo=timezone.utc)
    session = _SessionStub(
        responses=[
            [{"ts_bucket": since, "failed_runs": 4}],
            [{"platform": "dbt", "failures": 3, "total_runs": 10, "failure_rate": 0.3}],
        ]
    )

    failures = dashboard_queries.get_failures_over_time(
        session,
        since=since,
        until=until,
        bucket="hour",
    )
    rates = dashboard_queries.get_failure_rate_by_platform(
        session,
        since=since,
        until=until,
    )

    assert failures[0]["failed_runs"] == 4
    assert rates[0]["platform"] == "dbt"
    assert session.calls[0]["params"] == {"since": since, "until": until, "bucket": "hour"}
    assert session.calls[1]["params"] == {"since": since, "until": until}


def test_dashboard_service_rejects_invalid_window() -> None:
    now = datetime(2026, 2, 2, tzinfo=timezone.utc)
    with pytest.raises(APIError):
        dashboard_queries.get_failure_rate_by_platform(
            _SessionStub(responses=[[]]),
            since=now,
            until=now,
        )


def test_dashboard_service_rejects_non_positive_limit() -> None:
    with pytest.raises(APIError):
        dashboard_queries.get_top_flaky_pipelines(
            _SessionStub(responses=[[]]),
            limit=0,
        )


def test_dashboard_service_rejects_invalid_distribution_args() -> None:
    with pytest.raises(APIError):
        dashboard_queries.get_run_duration_distribution(
            _SessionStub(responses=[[]]),
            since=datetime(2026, 2, 1, tzinfo=timezone.utc),
            until=datetime(2026, 2, 2, tzinfo=timezone.utc),
            max_duration_seconds=0,
            bucket_count=10,
        )
    with pytest.raises(APIError):
        dashboard_queries.get_run_duration_distribution(
            _SessionStub(responses=[[]]),
            since=datetime(2026, 2, 1, tzinfo=timezone.utc),
            until=datetime(2026, 2, 2, tzinfo=timezone.utc),
            max_duration_seconds=3600,
            bucket_count=0,
        )
