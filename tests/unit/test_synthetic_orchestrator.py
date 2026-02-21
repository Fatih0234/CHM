"""Unit tests for synthetic data workflow orchestrator."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.synthetic.orchestrator import PIPELINE_TYPES
from app.synthetic.orchestrator import PLATFORMS
from app.synthetic.orchestrator import build_id_registry
from app.synthetic.orchestrator import execute_next_pending_step
from app.synthetic.orchestrator import generate_runs_batch
from app.synthetic.orchestrator import normalize_base_files


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _seed_base_files(root: Path) -> tuple[Path, Path]:
    clients_path = root / "clients.csv"
    pipelines_path = root / "pipelines.csv"

    _write_csv(
        clients_path,
        ["client_id", "company_name", "is_active", "created_at"],
        [
            ["c1", "Acme Co", "true", "2025-12-01"],
            ["c2", "Beta Co", "false", "2025-12-02"],
        ],
    )

    _write_csv(
        pipelines_path,
        [
            "pipeline_id",
            "client_id",
            "platform",
            "pipeline_type",
            "environment",
            "external_id",
            "is_active",
            "created_at",
        ],
        [
            [
                "p1",
                "c1",
                "Apache Airflow",
                "orchestration",
                "prod",
                "acme-airflow-prod-daily-load",
                "true",
                "2025-12-03",
            ],
            [
                "p2",
                "c2",
                "dbt Cloud",
                "transformation",
                "staging",
                "beta-dbt-staging-models",
                "true",
                "2025-12-04",
            ],
        ],
    )

    return clients_path, pipelines_path


def test_normalize_base_files_applies_contract_headers_and_enums(tmp_path: Path) -> None:
    clients_path, pipelines_path = _seed_base_files(tmp_path)

    normalize_base_files(clients_path, pipelines_path)

    with clients_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ["id", "name", "is_active", "created_at", "updated_at"]
        clients = list(reader)
        assert len(clients) == 2

    with pipelines_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "id",
            "client_id",
            "name",
            "platform",
            "external_id",
            "pipeline_type",
            "description",
            "environment",
            "is_active",
            "created_at",
            "updated_at",
        ]
        pipelines = list(reader)

    assert {row["platform"] for row in pipelines}.issubset(PLATFORMS)
    assert {row["pipeline_type"] for row in pipelines}.issubset(PIPELINE_TYPES)


def test_build_id_registry_includes_client_and_pipeline_relationships(tmp_path: Path) -> None:
    clients_path, pipelines_path = _seed_base_files(tmp_path)
    normalize_base_files(clients_path, pipelines_path)

    registry_path = tmp_path / "id_registry.csv"
    build_id_registry(clients_path, pipelines_path, registry_path)

    with registry_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    client_rows = [row for row in rows if row["entity_type"] == "client"]
    pipeline_rows = [row for row in rows if row["entity_type"] == "pipeline"]

    assert len(client_rows) == 2
    assert len(pipeline_rows) == 2

    client_ids = {row["entity_id"] for row in client_rows}
    assert all(row["parent_entity_id"] in client_ids for row in pipeline_rows)


def test_execute_next_pending_step_completes_a_and_sets_next_step(tmp_path: Path) -> None:
    clients_path, pipelines_path = _seed_base_files(tmp_path / "base")
    state_path = tmp_path / "session_state.json"

    state = {
        "workflow_id": "test",
        "dataset_version": "v1",
        "updated_at_utc": "2026-02-21T00:00:00Z",
        "steps": [
            {
                "id": "A",
                "status": "pending",
                "inputs": [str(clients_path), str(pipelines_path)],
                "outputs": [str(clients_path), str(pipelines_path)],
                "artifacts": {},
            },
            {
                "id": "B",
                "status": "pending",
                "inputs": [str(clients_path), str(pipelines_path)],
                "outputs": [str(tmp_path / "id_registry.csv")],
                "artifacts": {},
            },
        ],
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    result = execute_next_pending_step(state_path)

    assert result["step_executed"] == "A"
    assert result["pass"] is True
    assert result["next_step_id"] == "B"

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["steps"][0]["status"] == "completed"
    assert persisted["steps"][1]["status"] == "pending"


def test_generate_runs_batch_produces_valid_statuses_and_minimum_rows(tmp_path: Path) -> None:
    clients_path, pipelines_path = _seed_base_files(tmp_path / "base")
    normalize_base_files(clients_path, pipelines_path)

    registry_path = tmp_path / "id_registry.csv"
    build_id_registry(clients_path, pipelines_path, registry_path)

    runs_path = tmp_path / "runs.csv"
    output = generate_runs_batch(registry_path, runs_path)

    assert output["rows"] == 2500
    with runs_path.open(newline="", encoding="utf-8") as handle:
        runs = list(csv.DictReader(handle))

    assert len(runs) == 2500
    assert {row["status"] for row in runs}.issubset({"running", "success", "failed", "canceled", "skipped"})
