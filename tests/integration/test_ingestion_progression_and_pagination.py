"""Integration tests for ingestion status progression and pagination traversal."""

from __future__ import annotations

import copy
import importlib
import subprocess
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.base import DATABASE_URL
from app.db.models.alert_rule import AlertRule  # noqa: F401
from app.db.models.client import Client  # noqa: F401
from app.db.models.pipeline import PipelineTypeEnum
from app.db.models.pipeline import PlatformEnum
from app.db.models.run import Run
from app.db.repository.clients import create_client
from app.db.repository.pipelines import create_pipeline

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_BIN = ROOT / ".venv" / "bin" / "alembic"


def _apply_migrations() -> None:
    subprocess.run([str(ALEMBIC_BIN), "upgrade", "head"], cwd=ROOT, check=True)


@pytest.fixture(scope="session", autouse=True)
def migrated_schema() -> None:
    """Ensure schema is at latest revision before ingestion progression checks."""
    _apply_migrations()


@pytest.fixture(scope="session")
def engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


@pytest.fixture(autouse=True)
def clean_tables(engine) -> None:
    """Reset mutable tables for deterministic ingestion progression execution."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alert_rules"))
        conn.execute(text("DELETE FROM runs"))
        conn.execute(text("DELETE FROM pipelines"))
        conn.execute(text("DELETE FROM clients"))


class FakePaginatedPartnerClient:
    """Deterministic partner client that records cursor traversal calls."""

    def __init__(self, pages: dict[str, dict[str | None, dict[str, Any]]]) -> None:
        self._pages = pages
        self.calls: list[tuple[str, str | None]] = []

    def _get_page(self, pipeline_external_id: str, cursor: str | None = None) -> dict[str, Any]:
        self.calls.append((pipeline_external_id, cursor))
        page = self._pages.get(pipeline_external_id, {}).get(cursor)
        if page is None:
            return {"runs": [], "next_cursor": None}
        return copy.deepcopy(page)

    def fetch_runs(self, pipeline_external_id: str, cursor: str | None = None) -> dict[str, Any]:
        return self._get_page(pipeline_external_id, cursor)

    def list_runs(self, pipeline_external_id: str, cursor: str | None = None) -> dict[str, Any]:
        return self._get_page(pipeline_external_id, cursor)

    def fetch_pipeline_runs(
        self,
        pipeline_external_id: str,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return self._get_page(pipeline_external_id, cursor)



def _seed_external_pipeline(session: Session, *, external_id: str) -> tuple[UUID, str]:
    account = create_client(session, name="acme-ingestion-progression")
    pipeline = create_pipeline(
        session,
        client_id=account.id,
        name="partner-paginated-sync",
        platform=PlatformEnum.VENDOR_API,
        pipeline_type=PipelineTypeEnum.INGESTION,
        external_id=external_id,
        environment="prod",
    )
    session.commit()
    return pipeline.id, external_id



def _load_ingestion_job_callable():
    try:
        module = importlib.import_module("app.ingestion.job")
    except ModuleNotFoundError:
        pytest.fail(
            "Expected ingestion job module `app.ingestion.job` for US2 tests. "
            "Implement this in T026.",
            pytrace=False,
        )

    job_callable = getattr(module, "ingest_external_runs", None)
    if job_callable is None or not callable(job_callable):
        pytest.fail(
            "Expected callable `app.ingestion.job.ingest_external_runs(session, partner_client)` "
            "for US2 ingestion integration tests.",
            pytrace=False,
        )
    return job_callable



def _run_ingestion_job(session: Session, partner_client: FakePaginatedPartnerClient) -> None:
    job_callable = _load_ingestion_job_callable()
    try:
        job_callable(session=session, partner_client=partner_client)
    except TypeError:
        pytest.fail(
            "Expected ingestion job signature to accept `session` and `partner_client` "
            "keyword arguments.",
            pytrace=False,
        )



def _event(
    external_run_id: str,
    status: str,
    started_at: str,
    *,
    finished_at: str | None = None,
    duration_seconds: int | None = None,
) -> dict[str, Any]:
    return {
        "id": external_run_id,
        "external_run_id": external_run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "rows_processed": None,
        "error_message": None,
    }



def _utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)



def test_ingestion_job_progression_updates_running_to_success(engine) -> None:
    external_pipeline_id = "vendor-pipe-progression-001"

    first_replay_pages = {
        external_pipeline_id: {
            None: {
                "runs": [_event("run-100", "running", "2026-02-20T11:00:00Z")],
                "next_cursor": None,
            }
        }
    }

    second_replay_pages = {
        external_pipeline_id: {
            None: {
                "runs": [
                    _event(
                        "run-100",
                        "success",
                        "2026-02-20T11:00:00Z",
                        finished_at="2026-02-20T11:05:00Z",
                        duration_seconds=300,
                    )
                ],
                "next_cursor": None,
            }
        }
    }

    with Session(engine) as session:
        pipeline_id, _ = _seed_external_pipeline(session, external_id=external_pipeline_id)

        _run_ingestion_job(session, FakePaginatedPartnerClient(first_replay_pages))
        session.commit()

        _run_ingestion_job(session, FakePaginatedPartnerClient(second_replay_pages))
        session.commit()

        rows = list(
            session.scalars(
                select(Run)
                .where(
                    Run.pipeline_id == pipeline_id,
                    Run.external_run_id == "run-100",
                )
            )
        )

    assert len(rows) == 1
    assert rows[0].status.value == "success"
    assert rows[0].started_at == _utc("2026-02-20T11:00:00Z")
    assert rows[0].finished_at == _utc("2026-02-20T11:05:00Z")
    assert rows[0].duration_seconds == 300



def test_ingestion_job_consumes_paginated_results_until_cursor_exhausted(engine) -> None:
    external_pipeline_id = "vendor-pipe-pagination-001"

    pages = {
        external_pipeline_id: {
            None: {
                "runs": [_event("run-page-1", "success", "2026-02-20T09:00:00Z")],
                "next_cursor": "cursor-2",
            },
            "cursor-2": {
                "runs": [_event("run-page-2", "failed", "2026-02-20T09:05:00Z")],
                "next_cursor": "cursor-3",
            },
            "cursor-3": {
                "runs": [_event("run-page-3", "canceled", "2026-02-20T09:10:00Z")],
                "next_cursor": None,
            },
        }
    }

    fake_client = FakePaginatedPartnerClient(pages)

    with Session(engine) as session:
        pipeline_id, _ = _seed_external_pipeline(session, external_id=external_pipeline_id)

        _run_ingestion_job(session, fake_client)
        session.commit()

        rows = list(
            session.scalars(
                select(Run)
                .where(Run.pipeline_id == pipeline_id)
                .order_by(Run.external_run_id.asc())
            )
        )

    assert [row.external_run_id for row in rows] == [
        "run-page-1",
        "run-page-2",
        "run-page-3",
    ]
    assert fake_client.calls == [
        (external_pipeline_id, None),
        (external_pipeline_id, "cursor-2"),
        (external_pipeline_id, "cursor-3"),
    ]
