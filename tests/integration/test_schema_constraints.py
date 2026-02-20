"""Schema hard-gate tests for CHM migration constraints and indexes."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import DATABASE_URL
from app.db.models.alert_rule import AlertRule
from app.db.models.alert_rule import ChannelEnum
from app.db.models.alert_rule import RuleTypeEnum
from app.db.models.client import Client
from app.db.models.pipeline import Pipeline
from app.db.models.pipeline import PipelineTypeEnum
from app.db.models.pipeline import PlatformEnum
from app.db.models.run import Run
from app.db.models.run import RunStatusEnum

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_BIN = ROOT / ".venv" / "bin" / "alembic"


def _apply_migrations() -> None:
    subprocess.run([str(ALEMBIC_BIN), "upgrade", "head"], cwd=ROOT, check=True)


@pytest.fixture(scope="session", autouse=True)
def migrated_schema() -> None:
    """Ensure schema is at latest revision before constraint checks."""
    _apply_migrations()


@pytest.fixture(scope="session")
def engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


@pytest.fixture(autouse=True)
def clean_tables(engine) -> None:
    """Reset mutable tables so each test runs in isolation."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alert_rules"))
        conn.execute(text("DELETE FROM runs"))
        conn.execute(text("DELETE FROM pipelines"))
        conn.execute(text("DELETE FROM clients"))


def _new_client(name: str) -> Client:
    return Client(name=name)


def _new_pipeline(client_id: uuid.UUID, name: str) -> Pipeline:
    return Pipeline(
        client_id=client_id,
        name=name,
        platform=PlatformEnum.AIRFLOW,
        pipeline_type=PipelineTypeEnum.INGESTION,
        environment="prod",
    )


def test_clients_pipelines_uniqueness_and_fk_clients_pipelines(engine) -> None:
    with Session(engine) as session:
        client = _new_client("client-a")
        session.add(client)
        session.flush()

        pipeline = _new_pipeline(client.id, "pipeline-a")
        session.add(pipeline)
        session.commit()

    with Session(engine) as session:
        session.add(_new_client("client-a"))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

        existing = session.execute(text("SELECT id FROM clients LIMIT 1")).scalar_one()
        session.add(_new_pipeline(existing, "pipeline-a"))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

        session.add(_new_pipeline(uuid.uuid4(), "pipeline-orphan"))
        with pytest.raises(IntegrityError):
            session.flush()


def test_runs_idempotency_and_alert_rule_checks_runs_alert_rules(engine) -> None:
    with Session(engine) as session:
        client = _new_client("client-b")
        session.add(client)
        session.flush()

        pipeline = _new_pipeline(client.id, "pipeline-b")
        session.add(pipeline)
        session.flush()

        session.add(
            Run(
                pipeline_id=pipeline.id,
                external_run_id="run-1",
                status=RunStatusEnum.RUNNING,
            )
        )
        session.flush()
        session.commit()

    with Session(engine) as session:
        pipeline_id = session.execute(text("SELECT id FROM pipelines LIMIT 1")).scalar_one()
        client_id = session.execute(text("SELECT id FROM clients LIMIT 1")).scalar_one()

        session.add(
            Run(
                pipeline_id=pipeline_id,
                external_run_id="run-1",
                status=RunStatusEnum.SUCCESS,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

        session.add(
            Run(
                pipeline_id=pipeline_id,
                external_run_id="run-2",
                status=RunStatusEnum.RUNNING,
                duration_seconds=-1,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

        session.add(
            AlertRule(
                rule_type=RuleTypeEnum.ON_FAILURE,
                channel=ChannelEnum.SLACK,
                destination="#alerts",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

        session.add(
            AlertRule(
                client_id=client_id,
                rule_type=RuleTypeEnum.FAILURES_IN_WINDOW,
                channel=ChannelEnum.SLACK,
                destination="#alerts",
                window_minutes=30,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

        session.add(
            AlertRule(
                client_id=client_id,
                rule_type=RuleTypeEnum.FAILURES_IN_WINDOW,
                channel=ChannelEnum.SLACK,
                destination="#alerts",
                threshold=0,
                window_minutes=30,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_run_and_join_indexes_exist_indexes(engine) -> None:
    with engine.connect() as conn:
        run_index_names = {
            row[0]
            for row in conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename='runs'")
            )
        }
        pipeline_index_names = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename='pipelines'"
                )
            )
        }
        alert_rule_index_names = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename='alert_rules'"
                )
            )
        }

    assert "ix_runs_pipeline_latest_order" in run_index_names
    assert "ix_runs_pipeline_status_started_at" in run_index_names
    assert "ix_runs_status_event_time" in run_index_names
    assert "ix_runs_event_time" in run_index_names
    assert "ix_pipelines_client_id" in pipeline_index_names
    assert "ix_alert_rules_client_id" in alert_rule_index_names
    assert "ix_alert_rules_pipeline_id" in alert_rule_index_names
