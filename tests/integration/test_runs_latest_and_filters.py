"""Integration tests for run filtering and latest selection semantics."""

from __future__ import annotations

import subprocess
import uuid
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.base import DATABASE_URL
from app.db.models.alert_rule import AlertRule  # noqa: F401
from app.db.models.client import Client  # noqa: F401
from app.db.models.pipeline import Pipeline  # noqa: F401
from app.db.models.run import Run
from app.db.models.run import RunStatusEnum
from app.db.repository.clients import create_client
from app.db.repository.pipelines import create_pipeline
from app.db.repository.runs import create_run
from app.db.repository.runs import get_latest_run_for_pipeline
from app.db.repository.runs import list_runs
from app.db.models.pipeline import PipelineTypeEnum
from app.db.models.pipeline import PlatformEnum

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_BIN = ROOT / ".venv" / "bin" / "alembic"


def _apply_migrations() -> None:
    subprocess.run([str(ALEMBIC_BIN), "upgrade", "head"], cwd=ROOT, check=True)


@pytest.fixture(scope="session", autouse=True)
def migrated_schema() -> None:
    """Ensure schema is at latest revision before run-query checks."""
    _apply_migrations()


@pytest.fixture(scope="session")
def engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


@pytest.fixture(autouse=True)
def clean_tables(engine) -> None:
    """Reset mutable tables for deterministic test execution."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alert_rules"))
        conn.execute(text("DELETE FROM runs"))
        conn.execute(text("DELETE FROM pipelines"))
        conn.execute(text("DELETE FROM clients"))


def _utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)


def _seed_pipeline(session: Session) -> uuid.UUID:
    client = create_client(session, name="acme-runs")
    pipeline = create_pipeline(
        session,
        client_id=client.id,
        name="daily-pipeline",
        platform=PlatformEnum.AIRFLOW,
        pipeline_type=PipelineTypeEnum.INGESTION,
        environment="prod",
    )
    session.commit()
    return pipeline.id


def test_list_runs_applies_status_and_time_window_filters(engine) -> None:
    with Session(engine) as session:
        pipeline_id = _seed_pipeline(session)
        create_run(
            session,
            pipeline_id=pipeline_id,
            external_run_id="before-window",
            status=RunStatusEnum.FAILED,
            started_at=_utc("2026-02-20T09:59:00"),
        )
        create_run(
            session,
            pipeline_id=pipeline_id,
            external_run_id="window-failed",
            status=RunStatusEnum.FAILED,
            started_at=_utc("2026-02-20T10:00:00"),
        )
        create_run(
            session,
            pipeline_id=pipeline_id,
            external_run_id="window-success",
            status=RunStatusEnum.SUCCESS,
            started_at=_utc("2026-02-20T10:30:00"),
        )
        create_run(
            session,
            pipeline_id=pipeline_id,
            external_run_id="at-until-boundary",
            status=RunStatusEnum.FAILED,
            started_at=_utc("2026-02-20T11:00:00"),
        )
        session.commit()

    with Session(engine) as session:
        filtered = list_runs(
            session,
            pipeline_id=pipeline_id,
            status=RunStatusEnum.FAILED,
            since=_utc("2026-02-20T10:00:00"),
            until=_utc("2026-02-20T11:00:00"),
            limit=100,
            order="desc",
        )

    assert [run.external_run_id for run in filtered] == ["window-failed"]


def test_list_runs_respects_order_and_limit(engine) -> None:
    with Session(engine) as session:
        pipeline_id = _seed_pipeline(session)
        create_run(
            session,
            pipeline_id=pipeline_id,
            external_run_id="t10",
            status=RunStatusEnum.SUCCESS,
            started_at=_utc("2026-02-20T10:00:00"),
            finished_at=_utc("2026-02-20T10:10:00"),
        )
        create_run(
            session,
            pipeline_id=pipeline_id,
            external_run_id="t11-finish-20",
            status=RunStatusEnum.SUCCESS,
            started_at=_utc("2026-02-20T11:00:00"),
            finished_at=_utc("2026-02-20T11:20:00"),
        )
        create_run(
            session,
            pipeline_id=pipeline_id,
            external_run_id="t11-finish-10",
            status=RunStatusEnum.SUCCESS,
            started_at=_utc("2026-02-20T11:00:00"),
            finished_at=_utc("2026-02-20T11:10:00"),
        )
        create_run(
            session,
            pipeline_id=pipeline_id,
            external_run_id="null-started-at",
            status=RunStatusEnum.RUNNING,
            started_at=None,
            finished_at=None,
        )
        session.commit()

    with Session(engine) as session:
        desc_limited = list_runs(
            session,
            pipeline_id=pipeline_id,
            limit=2,
            order="desc",
        )
        asc_all = list_runs(
            session,
            pipeline_id=pipeline_id,
            limit=100,
            order="asc",
        )

    assert [run.external_run_id for run in desc_limited] == [
        "t11-finish-20",
        "t11-finish-10",
    ]
    assert [run.external_run_id for run in asc_all] == [
        "t10",
        "t11-finish-10",
        "t11-finish-20",
        "null-started-at",
    ]


def test_latest_run_uses_tie_breaker_on_id_desc(engine) -> None:
    low_uuid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    high_uuid = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    with Session(engine) as session:
        pipeline_id = _seed_pipeline(session)
        session.add(
            Run(
                id=low_uuid,
                pipeline_id=pipeline_id,
                external_run_id="same-time-low-id",
                status=RunStatusEnum.SUCCESS,
                started_at=_utc("2026-02-20T12:00:00"),
                finished_at=_utc("2026-02-20T12:05:00"),
            )
        )
        session.add(
            Run(
                id=high_uuid,
                pipeline_id=pipeline_id,
                external_run_id="same-time-high-id",
                status=RunStatusEnum.SUCCESS,
                started_at=_utc("2026-02-20T12:00:00"),
                finished_at=_utc("2026-02-20T12:05:00"),
            )
        )
        session.add(
            Run(
                pipeline_id=pipeline_id,
                external_run_id="null-timestamps",
                status=RunStatusEnum.RUNNING,
                started_at=None,
                finished_at=None,
            )
        )
        session.commit()

    with Session(engine) as session:
        latest = get_latest_run_for_pipeline(session, pipeline_id=pipeline_id)

    assert latest is not None
    assert latest.id == high_uuid
    assert latest.external_run_id == "same-time-high-id"


def test_client_summary_endpoint_returns_deterministic_payload(
    client: TestClient,
    engine,
) -> None:
    with Session(engine) as session:
        account = create_client(session, name="acme-summary")
        alpha = create_pipeline(
            session,
            client_id=account.id,
            name="alpha-pipeline",
            platform=PlatformEnum.AIRFLOW,
            pipeline_type=PipelineTypeEnum.INGESTION,
            environment="prod",
        )
        beta = create_pipeline(
            session,
            client_id=account.id,
            name="beta-pipeline",
            platform=PlatformEnum.DBT,
            pipeline_type=PipelineTypeEnum.TRANSFORM,
            environment="prod",
        )

        create_run(
            session,
            pipeline_id=alpha.id,
            external_run_id="alpha-before-window",
            status=RunStatusEnum.FAILED,
            started_at=_utc("2026-02-20T09:50:00"),
        )
        create_run(
            session,
            pipeline_id=alpha.id,
            external_run_id="alpha-running",
            status=RunStatusEnum.RUNNING,
            started_at=_utc("2026-02-20T10:15:00"),
        )
        create_run(
            session,
            pipeline_id=alpha.id,
            external_run_id="alpha-success",
            status=RunStatusEnum.SUCCESS,
            started_at=_utc("2026-02-20T11:30:00"),
        )
        create_run(
            session,
            pipeline_id=beta.id,
            external_run_id="beta-failed",
            status=RunStatusEnum.FAILED,
            started_at=_utc("2026-02-20T10:45:00"),
        )
        account_id = account.id
        alpha_id = alpha.id
        beta_id = beta.id
        session.commit()

    response = client.get(
        f"/api/v1/clients/{account_id}/runs/summary",
        params={
            "since": "2026-02-20T10:00:00Z",
            "until": "2026-02-20T12:00:00Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["client_id"] == str(account_id)
    assert payload["status_counts"]["running"] == 1
    assert payload["status_counts"]["success"] == 1
    assert payload["status_counts"]["failed"] == 1

    latest_items = payload["latest_by_pipeline"]
    assert len(latest_items) == 2
    assert [item["pipeline_name"] for item in latest_items] == [
        "alpha-pipeline",
        "beta-pipeline",
    ]

    by_pipeline = {item["pipeline_id"]: item for item in latest_items}
    assert by_pipeline[str(alpha_id)]["latest_status"] == "success"
    assert by_pipeline[str(alpha_id)]["latest_run_at"].startswith("2026-02-20T11:30:00")
    assert by_pipeline[str(beta_id)]["latest_status"] == "failed"
