"""Integration validation for dashboard SQL query contract outputs."""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
import subprocess

import pytest
from sqlalchemy import create_engine
from sqlalchemy import text

from app.db.base import DATABASE_URL

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_BIN = ROOT / ".venv" / "bin" / "alembic"
DASHBOARD_CONTRACT = (
    ROOT / "specs" / "001-chm-api-ingestion" / "contracts" / "dashboard-queries.sql"
)
SEED_FIXTURE = ROOT / "tests" / "fixtures" / "dashboard_seed.sql"


def _apply_migrations() -> None:
    subprocess.run([str(ALEMBIC_BIN), "upgrade", "head"], cwd=ROOT, check=True)


def _split_sql_statements(sql_text: str) -> list[str]:
    chunks = [chunk.strip() for chunk in sql_text.split(";")]
    return [f"{chunk};" for chunk in chunks if chunk]


def _strip_sql_comments(statement: str) -> str:
    return "\n".join(
        line for line in statement.splitlines() if not line.lstrip().startswith("--")
    ).strip()


def _load_dashboard_queries() -> list[str]:
    statements = _split_sql_statements(DASHBOARD_CONTRACT.read_text(encoding="utf-8"))
    queries = []
    for statement in statements:
        if "SELECT" not in statement.upper():
            continue
        stripped = _strip_sql_comments(statement)
        if stripped:
            queries.append(stripped)
    assert len(queries) == 6, "Expected six dashboard SQL query shapes in contract"
    return queries


def _seed_dashboard_dataset(engine) -> None:
    with engine.begin() as conn:
        for statement in _split_sql_statements(SEED_FIXTURE.read_text(encoding="utf-8")):
            conn.execute(text(statement))


@pytest.fixture(scope="session", autouse=True)
def migrated_schema() -> None:
    """Ensure schema is at latest revision before dashboard-query validation."""
    _apply_migrations()


@pytest.fixture(scope="session")
def engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


@pytest.fixture(autouse=True)
def seeded_data(engine) -> None:
    """Seed representative data before each dashboard-query test."""
    _seed_dashboard_dataset(engine)


def _rows_as_dicts(result) -> list[dict]:
    return [dict(row._mapping) for row in result]


def test_dashboard_queries_contract_outputs_match_seeded_expectations(engine) -> None:
    now = datetime.now(timezone.utc)
    query_1, query_2, query_3, query_4, query_5, query_6 = _load_dashboard_queries()

    with engine.connect() as conn:
        failures_over_time = _rows_as_dicts(
            conn.execute(
                text(query_1),
                {
                    "bucket": "hour",
                    "since": now - timedelta(hours=6),
                    "until": now + timedelta(minutes=1),
                },
            )
        )
        latest_status = _rows_as_dicts(conn.execute(text(query_2)))
        failure_counts = _rows_as_dicts(conn.execute(text(query_3)))
        flaky = _rows_as_dicts(conn.execute(text(query_4)))
        failure_rate = _rows_as_dicts(
            conn.execute(
                text(query_5),
                {
                    "since": now - timedelta(days=10),
                    "until": now + timedelta(minutes=1),
                },
            )
        )
        duration_distribution = _rows_as_dicts(
            conn.execute(
                text(query_6),
                {
                    "since": now - timedelta(days=10),
                    "until": now + timedelta(minutes=1),
                    "max_duration_seconds": 4000,
                    "bucket_count": 4,
                },
            )
        )

    assert sum(row["failed_runs"] for row in failures_over_time) == 2

    latest_by_pipeline = {row["pipeline_name"]: row["latest_status"] for row in latest_status}
    assert latest_by_pipeline == {
        "ingest-a": "failed",
        "transform-a": "success",
        "vendor-b": "success",
    }

    by_client = {row["client_name"]: row for row in failure_counts}
    assert by_client["acme"]["failed_24h"] == 1
    assert by_client["acme"]["failed_7d"] == 3
    assert by_client["beta"]["failed_24h"] == 1
    assert by_client["beta"]["failed_7d"] == 1

    assert flaky[0]["pipeline_name"] == "ingest-a"
    assert flaky[0]["failure_count"] == 2
    assert flaky[0]["total_runs"] == 3

    failure_rate_by_platform = {row["platform"]: row for row in failure_rate}
    assert failure_rate_by_platform["airflow"]["failures"] == 3
    assert failure_rate_by_platform["airflow"]["total_runs"] == 4
    assert failure_rate_by_platform["dbt"]["failures"] == 1
    assert failure_rate_by_platform["vendor_api"]["failures"] == 1

    assert sum(row["run_count"] for row in duration_distribution) == 8
