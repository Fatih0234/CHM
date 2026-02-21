"""State-driven synthetic data workflow orchestrator for CHM datasets."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import json
from pathlib import Path
import random
from typing import Any
import uuid

UTC = timezone.utc
DEFAULT_STATE_FILE = Path("/Volumes/T7/CHM/data/synthetic/v1/context/session_state.json")
NAMESPACE_UUID = uuid.UUID("2f4f6c12-23aa-4db2-bd2f-8f4f84d84f22")

PLATFORMS = {"airflow", "dbt", "cron", "vendor_api", "custom"}
PIPELINE_TYPES = {"ingestion", "transform", "quality", "export", "healthcheck"}
RUN_STATUSES = {"running", "success", "failed", "canceled", "skipped"}
RULE_TYPES = {"on_failure", "failures_in_window"}
CHANNELS = {"slack", "email", "webhook"}

CLIENT_HEADERS = ["id", "name", "is_active", "created_at", "updated_at"]
PIPELINE_HEADERS = [
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
RUN_HEADERS = [
    "id",
    "pipeline_id",
    "external_run_id",
    "status",
    "started_at",
    "finished_at",
    "duration_seconds",
    "rows_processed",
    "error_message",
    "status_reason",
    "payload",
    "ingested_at",
    "created_at",
    "updated_at",
]
ALERT_RULE_HEADERS = [
    "id",
    "client_id",
    "pipeline_id",
    "rule_type",
    "threshold",
    "window_minutes",
    "channel",
    "destination",
    "is_enabled",
    "created_at",
    "updated_at",
]
ID_REGISTRY_HEADERS = [
    "entity_type",
    "entity_id",
    "entity_name",
    "parent_entity_id",
    "parent_entity_name",
    "platform",
    "pipeline_type",
    "environment",
    "is_active",
    "created_at",
]


class StepExecutionError(RuntimeError):
    """Raised when a workflow step cannot be completed."""


@dataclass(frozen=True)
class PipelineContext:
    """Pipeline metadata required for synthetic row generation."""

    pipeline_id: str
    client_id: str
    name: str
    platform: str
    pipeline_type: str
    environment: str


def _now_utc_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_datetime_utc(raw: str | None) -> datetime:
    if raw in (None, ""):
        raise ValueError("timestamp value is required")

    text = str(raw).strip()
    if len(text) == 10:
        parsed = datetime.strptime(text, "%Y-%m-%d")
        return parsed.replace(tzinfo=UTC)

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _to_iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []

        rows: list[dict[str, str]] = []
        for row in reader:
            if row is None:
                continue
            normalized = {key: (value or "").strip() for key, value in row.items() if key is not None}
            if not any(normalized.values()):
                continue
            rows.append(normalized)

        return rows


def _read_headers(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in headers})


def _stable_offset_days(seed: str, min_days: int, max_days: int) -> int:
    if min_days > max_days:
        raise ValueError("min_days must be <= max_days")

    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    span = max_days - min_days + 1
    return min_days + (int.from_bytes(digest[:4], "big") % span)


def _normalize_bool(raw: str | bool | None) -> str:
    if isinstance(raw, bool):
        return "true" if raw else "false"
    if raw is None:
        return "false"
    return "true" if str(raw).strip().lower() in {"1", "true", "t", "yes", "y"} else "false"


def _normalize_environment(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    mapping = {
        "prod": "prod",
        "production": "prod",
        "staging": "staging",
        "stage": "staging",
        "dev": "dev",
        "development": "dev",
    }
    return mapping.get(value, "dev")


def _map_platform(raw_platform: str | None) -> str:
    value = (raw_platform or "").strip().lower()
    if "airflow" in value:
        return "airflow"
    if "dbt" in value:
        return "dbt"
    if "cron" in value:
        return "cron"
    vendor_hints = {
        "fivetran",
        "matillion",
        "hightouch",
        "stitch",
        "airbyte",
        "kafka",
        "glue",
        "data factory",
        "api",
        "connect",
        "dataflow",
    }
    if any(hint in value for hint in vendor_hints):
        return "vendor_api"
    return "custom"


def _map_pipeline_type(raw_type: str | None, external_id: str | None) -> str:
    source = f"{raw_type or ''} {external_id or ''}".lower()

    quality_hints = {"quality", "dq", "test", "validation", "checks"}
    export_hints = {"export", "reverse_etl", "reverse", "reporting", "dashboard", "publish", "serving"}
    ingestion_hints = {"ingest", "ingestion", "landing", "extract", "stream", "sync"}
    transform_hints = {"transform", "transformation", "model", "marts", "feature", "ml_training"}
    healthcheck_hints = {"orchestration", "scheduling", "schedule", "health", "heartbeat", "orchestrate"}

    if any(token in source for token in quality_hints):
        return "quality"
    if any(token in source for token in export_hints):
        return "export"
    if any(token in source for token in ingestion_hints):
        return "ingestion"
    if any(token in source for token in transform_hints):
        return "transform"
    if any(token in source for token in healthcheck_hints):
        return "healthcheck"

    return "healthcheck"


def _pipeline_name_from_external_id(external_id: str, pipeline_type: str) -> str:
    tokens = [token for token in external_id.replace("_", "-").split("-") if token]
    ignored = {
        "prod",
        "staging",
        "dev",
        "airflow",
        "dbt",
        "glue",
        "adf",
        "dataflow",
        "prefect",
        "databricks",
        "gx",
        "kafka",
        "fivetran",
        "matillion",
        "hightouch",
        "looker",
        "cloud",
        "core",
    }

    if len(tokens) > 1:
        tokens = tokens[1:]

    filtered = [token for token in tokens if token.lower() not in ignored]
    selected = filtered[:4] if filtered else tokens[-3:]

    words = [segment.upper() if len(segment) <= 3 else segment.capitalize() for segment in selected]
    name = " ".join(words).strip()
    if name:
        return name

    fallback = pipeline_type.replace("_", " ").title()
    return f"{fallback} Pipeline"


def normalize_base_files(clients_path: Path, pipelines_path: Path) -> dict[str, Any]:
    """Normalize base CSV files into CHM schema-compatible rows."""
    client_rows_raw = _read_csv(clients_path)
    pipeline_rows_raw = _read_csv(pipelines_path)

    if not client_rows_raw:
        raise StepExecutionError(f"No client rows found in {clients_path}")
    if not pipeline_rows_raw:
        raise StepExecutionError(f"No pipeline rows found in {pipelines_path}")

    normalized_clients: list[dict[str, str]] = []
    seen_clients: set[tuple[str, ...]] = set()
    client_ids: set[str] = set()

    for row in client_rows_raw:
        client_id = row.get("id") or row.get("client_id")
        name = row.get("name") or row.get("company_name")
        if not client_id or not name:
            raise StepExecutionError("clients.csv contains row missing id/name")

        created_at = _parse_datetime_utc(row.get("created_at"))
        updated_at = created_at + timedelta(days=_stable_offset_days(client_id, 1, 14))

        normalized = {
            "id": client_id,
            "name": name,
            "is_active": _normalize_bool(row.get("is_active")),
            "created_at": _to_iso_utc(created_at),
            "updated_at": _to_iso_utc(updated_at),
        }

        identity = tuple(normalized[column] for column in CLIENT_HEADERS)
        if identity in seen_clients:
            continue
        seen_clients.add(identity)
        client_ids.add(client_id)
        normalized_clients.append(normalized)

    normalized_clients.sort(key=lambda item: item["name"].lower())

    normalized_pipelines: list[dict[str, str]] = []
    seen_pipelines: set[tuple[str, ...]] = set()

    for row in pipeline_rows_raw:
        pipeline_id = row.get("id") or row.get("pipeline_id")
        client_id = row.get("client_id", "")
        external_id = row.get("external_id", "")

        if not pipeline_id or not client_id or not external_id:
            raise StepExecutionError("pipelines.csv contains row missing id/client_id/external_id")
        if client_id not in client_ids:
            raise StepExecutionError(f"pipeline {pipeline_id} references unknown client_id {client_id}")

        pipeline_type = _map_pipeline_type(row.get("pipeline_type"), external_id)
        created_at = _parse_datetime_utc(row.get("created_at"))
        updated_at = created_at + timedelta(days=_stable_offset_days(pipeline_id, 1, 30))

        normalized = {
            "id": pipeline_id,
            "client_id": client_id,
            "name": _pipeline_name_from_external_id(external_id, pipeline_type),
            "platform": _map_platform(row.get("platform")),
            "external_id": external_id,
            "pipeline_type": pipeline_type,
            "description": (
                f"{pipeline_type.title()} pipeline for {row.get('environment', 'dev')} "
                "workloads and monitoring needs."
            ),
            "environment": _normalize_environment(row.get("environment")),
            "is_active": _normalize_bool(row.get("is_active")),
            "created_at": _to_iso_utc(created_at),
            "updated_at": _to_iso_utc(updated_at),
        }

        identity = tuple(normalized[column] for column in PIPELINE_HEADERS)
        if identity in seen_pipelines:
            continue
        seen_pipelines.add(identity)
        normalized_pipelines.append(normalized)

    normalized_pipelines.sort(key=lambda item: (item["client_id"], item["name"].lower(), item["id"]))

    _write_csv(clients_path, CLIENT_HEADERS, normalized_clients)
    _write_csv(pipelines_path, PIPELINE_HEADERS, normalized_pipelines)

    return {
        "files_written": [str(clients_path), str(pipelines_path)],
        "clients_count": len(normalized_clients),
        "pipelines_count": len(normalized_pipelines),
        "summary": "normalized clients/pipelines to CHM contract",
    }


def build_id_registry(clients_path: Path, pipelines_path: Path, registry_path: Path) -> dict[str, Any]:
    """Build id_registry.csv from normalized client/pipeline entities."""
    clients = _read_csv(clients_path)
    pipelines = _read_csv(pipelines_path)

    clients_by_id = {row["id"]: row for row in clients}
    if len(clients_by_id) != len(clients):
        raise StepExecutionError("clients.csv contains duplicate client ids")

    registry_rows: list[dict[str, str]] = []

    for client in sorted(clients, key=lambda item: item["name"].lower()):
        registry_rows.append(
            {
                "entity_type": "client",
                "entity_id": client["id"],
                "entity_name": client["name"],
                "parent_entity_id": "",
                "parent_entity_name": "",
                "platform": "",
                "pipeline_type": "",
                "environment": "",
                "is_active": client["is_active"],
                "created_at": client["created_at"],
            }
        )

    pipeline_rows: list[dict[str, str]] = []
    for pipeline in pipelines:
        client = clients_by_id.get(pipeline["client_id"])
        if client is None:
            raise StepExecutionError(
                f"pipeline {pipeline['id']} in pipelines.csv references unknown client {pipeline['client_id']}"
            )

        pipeline_rows.append(
            {
                "entity_type": "pipeline",
                "entity_id": pipeline["id"],
                "entity_name": pipeline["name"],
                "parent_entity_id": pipeline["client_id"],
                "parent_entity_name": client["name"],
                "platform": pipeline["platform"],
                "pipeline_type": pipeline["pipeline_type"],
                "environment": pipeline["environment"],
                "is_active": pipeline["is_active"],
                "created_at": pipeline["created_at"],
            }
        )

    pipeline_rows.sort(key=lambda item: (item["parent_entity_name"].lower(), item["entity_name"].lower()))
    registry_rows.extend(pipeline_rows)

    _write_csv(registry_path, ID_REGISTRY_HEADERS, registry_rows)

    return {
        "files_written": [str(registry_path)],
        "client_rows": len(clients),
        "pipeline_rows": len(pipeline_rows),
        "summary": "built deterministic id registry for clients/pipelines",
    }


def _slugify(text: str) -> str:
    filtered = [ch.lower() if ch.isalnum() else "-" for ch in text]
    compact = "".join(filtered)
    while "--" in compact:
        compact = compact.replace("--", "-")
    return compact.strip("-") or "pipeline"


def _build_pipeline_contexts(registry_path: Path) -> tuple[list[dict[str, str]], list[PipelineContext]]:
    rows = _read_csv(registry_path)
    clients = [row for row in rows if row.get("entity_type") == "client"]
    pipelines = [
        PipelineContext(
            pipeline_id=row["entity_id"],
            client_id=row["parent_entity_id"],
            name=row["entity_name"],
            platform=row["platform"],
            pipeline_type=row["pipeline_type"],
            environment=row["environment"],
        )
        for row in rows
        if row.get("entity_type") == "pipeline"
    ]
    if not pipelines:
        raise StepExecutionError("id_registry.csv has no pipeline rows")
    return clients, pipelines


def _status_for_generic_run(rng: random.Random) -> str:
    roll = rng.random()
    if roll < 0.865:
        return "success"
    if roll < 0.94:
        return "failed"
    if roll < 0.97:
        return "canceled"
    if roll < 0.99:
        return "skipped"
    return "running"


def _rows_processed(rng: random.Random, pipeline_type: str) -> int:
    ranges = {
        "ingestion": (50_000, 5_000_000),
        "transform": (20_000, 2_000_000),
        "quality": (5_000, 500_000),
        "export": (10_000, 1_000_000),
        "healthcheck": (100, 10_000),
    }
    low, high = ranges.get(pipeline_type, (1_000, 100_000))
    return rng.randint(low, high)


def _duration_seconds(rng: random.Random, pipeline_type: str) -> int:
    ranges = {
        "ingestion": (180, 7200),
        "transform": (300, 10800),
        "quality": (60, 2400),
        "export": (120, 3600),
        "healthcheck": (30, 1200),
    }
    low, high = ranges.get(pipeline_type, (60, 1800))
    return rng.randint(low, high)


def _error_pair(rng: random.Random) -> tuple[str, str]:
    candidates = [
        ("API rate limit exceeded", "upstream_throttle"),
        ("Warehouse timeout during query execution", "warehouse_timeout"),
        ("Schema mismatch detected in source payload", "schema_drift"),
        ("Dependency task failed in upstream DAG", "upstream_failure"),
        ("Checkpoint commit failed", "checkpoint_failure"),
    ]
    return candidates[rng.randrange(len(candidates))]


def _create_run_row(
    rng: random.Random,
    pipeline: PipelineContext,
    start_at: datetime,
    sequence_by_key: dict[tuple[str, str], int],
    status_override: str | None = None,
    duration_multiplier: float = 1.0,
    incident_tag: str | None = None,
) -> dict[str, str]:
    status = status_override or _status_for_generic_run(rng)

    day_key = start_at.strftime("%Y%m%d")
    seq_key = (pipeline.pipeline_id, day_key)
    next_seq = sequence_by_key.get(seq_key, 0) + 1
    sequence_by_key[seq_key] = next_seq

    run_slug = _slugify(pipeline.name)
    external_run_id = f"{run_slug}-{day_key}-{next_seq:04d}"
    run_id = str(uuid.uuid5(NAMESPACE_UUID, f"{pipeline.pipeline_id}:{external_run_id}"))

    finished_at = ""
    duration_seconds = ""
    error_message = ""
    status_reason = ""

    if status != "running":
        duration = max(1, int(_duration_seconds(rng, pipeline.pipeline_type) * duration_multiplier))
        finish_dt = start_at + timedelta(seconds=duration)
        finished_at = _to_iso_utc(finish_dt)
        duration_seconds = str(duration)

    if status == "failed":
        error_message, status_reason = _error_pair(rng)

    payload = {
        "source": "synthetic-orchestrator-v1",
        "platform": pipeline.platform,
        "pipeline_type": pipeline.pipeline_type,
        "environment": pipeline.environment,
        "attempt": rng.randint(1, 3),
    }
    if incident_tag is not None:
        payload["incident_tag"] = incident_tag

    ingested_at_dt = start_at + timedelta(minutes=rng.randint(1, 25))
    ingested_at = _to_iso_utc(ingested_at_dt)

    return {
        "id": run_id,
        "pipeline_id": pipeline.pipeline_id,
        "external_run_id": external_run_id,
        "status": status,
        "started_at": _to_iso_utc(start_at),
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "rows_processed": str(_rows_processed(rng, pipeline.pipeline_type)),
        "error_message": error_message,
        "status_reason": status_reason,
        "payload": json.dumps(payload, separators=(",", ":"), sort_keys=True),
        "ingested_at": ingested_at,
        "created_at": ingested_at,
        "updated_at": ingested_at,
    }


def generate_runs_batch(registry_path: Path, runs_path: Path, row_count: int = 2500) -> dict[str, Any]:
    """Generate a synthetic runs batch using id_registry pipeline IDs."""
    _, pipelines = _build_pipeline_contexts(registry_path)

    start_window = datetime(2025, 11, 1, 0, 0, 0, tzinfo=UTC)
    end_window = datetime(2026, 2, 21, 23, 59, 59, tzinfo=UTC)

    incident_start = datetime(2026, 1, 29, 14, 0, 0, tzinfo=UTC)
    incident_end = incident_start + timedelta(minutes=110)

    latency_start = datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)
    latency_end = latency_start + timedelta(days=10)

    vendor_incident_candidates = [
        item
        for item in pipelines
        if item.platform == "vendor_api" and item.pipeline_type == "ingestion" and item.environment == "prod"
    ]
    latency_candidates = [
        item for item in pipelines if item.platform == "dbt" and item.pipeline_type == "transform"
    ]

    if not vendor_incident_candidates:
        vendor_incident_candidates = [item for item in pipelines if item.platform == "vendor_api"]
    if not vendor_incident_candidates:
        vendor_incident_candidates = list(pipelines)
    if not latency_candidates:
        latency_candidates = [item for item in pipelines if item.pipeline_type == "transform"]
    if not latency_candidates:
        latency_candidates = list(pipelines)

    rng = random.Random(20260221)
    run_rows: list[dict[str, str]] = []
    sequence_by_key: dict[tuple[str, str], int] = {}

    days: list[datetime] = []
    weights: list[float] = []
    cursor = start_window
    while cursor.date() <= end_window.date():
        days.append(cursor)
        weekend = cursor.weekday() >= 5
        weights.append(0.45 if weekend else 1.0)
        cursor += timedelta(days=1)

    incident_count = 220
    latency_count = 130
    running_tail_count = 5
    generic_count = row_count - incident_count - latency_count - running_tail_count

    if generic_count <= 0:
        raise StepExecutionError("configured run counts are invalid")

    for _ in range(generic_count):
        pipeline = pipelines[rng.randrange(len(pipelines))]
        day_anchor = rng.choices(days, weights=weights, k=1)[0]
        random_seconds = rng.randint(0, 86_399)
        start_at = day_anchor + timedelta(seconds=random_seconds)
        if start_at > end_window:
            start_at = end_window - timedelta(minutes=rng.randint(5, 180))

        run_rows.append(_create_run_row(rng, pipeline, start_at, sequence_by_key))

    for _ in range(incident_count):
        pipeline = vendor_incident_candidates[rng.randrange(len(vendor_incident_candidates))]
        offset_seconds = rng.randint(0, int((incident_end - incident_start).total_seconds()))
        start_at = incident_start + timedelta(seconds=offset_seconds)

        roll = rng.random()
        if roll < 0.76:
            status = "failed"
        elif roll < 0.92:
            status = "success"
        elif roll < 0.97:
            status = "canceled"
        else:
            status = "skipped"

        run_rows.append(
            _create_run_row(
                rng,
                pipeline,
                start_at,
                sequence_by_key,
                status_override=status,
                duration_multiplier=1.2,
                incident_tag="vendor_api_failure_spike",
            )
        )

    latency_span_seconds = int((latency_end - latency_start).total_seconds())
    for _ in range(latency_count):
        pipeline = latency_candidates[rng.randrange(len(latency_candidates))]
        offset_seconds = rng.randint(0, latency_span_seconds)
        start_at = latency_start + timedelta(seconds=offset_seconds)
        progression = max(0.0, min(1.0, offset_seconds / latency_span_seconds))
        multiplier = 2.0 + (3.0 * progression)

        status = "success" if rng.random() < 0.93 else "failed"
        run_rows.append(
            _create_run_row(
                rng,
                pipeline,
                start_at,
                sequence_by_key,
                status_override=status,
                duration_multiplier=multiplier,
                incident_tag="dbt_transform_latency_degradation",
            )
        )

    for _ in range(running_tail_count):
        pipeline = pipelines[rng.randrange(len(pipelines))]
        start_at = end_window - timedelta(minutes=rng.randint(1, 30))
        run_rows.append(
            _create_run_row(
                rng,
                pipeline,
                start_at,
                sequence_by_key,
                status_override="running",
                incident_tag="near_window_tail",
            )
        )

    run_rows.sort(key=lambda row: row["started_at"])
    _write_csv(runs_path, RUN_HEADERS, run_rows)

    status_counts: dict[str, int] = {}
    for row in run_rows:
        status = row["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "files_written": [str(runs_path)],
        "rows": len(run_rows),
        "status_counts": status_counts,
        "summary": "generated runs batch with incident and latency patterns",
    }


def _alert_destination(channel: str, rng: random.Random) -> str:
    if channel == "slack":
        options = ["#data-alerts", "#ops-oncall", "#etl-reliability"]
    elif channel == "email":
        options = ["data-alerts@example.com", "oncall@example.com", "platform-alerts@example.com"]
    else:
        options = [
            "https://ops.example.internal/hooks/chm-data",
            "https://ops.example.internal/hooks/chm-oncall",
            "https://ops.example.internal/hooks/chm-reliability",
        ]
    return options[rng.randrange(len(options))]


def generate_alert_rules(registry_path: Path, alert_rules_path: Path, row_count: int = 35) -> dict[str, Any]:
    """Generate alert_rules.csv referencing existing registry entities."""
    clients, pipelines = _build_pipeline_contexts(registry_path)

    clients_by_id = {row["entity_id"]: row for row in clients}
    if not clients_by_id:
        raise StepExecutionError("id_registry.csv has no client rows")

    rng = random.Random(20260222)
    now_ref = datetime(2026, 2, 21, 23, 0, 0, tzinfo=UTC)

    rows: list[dict[str, str]] = []
    for index in range(row_count):
        channel = rng.choices(["slack", "email", "webhook"], weights=[0.45, 0.35, 0.2], k=1)[0]
        rule_type = rng.choices(["on_failure", "failures_in_window"], weights=[0.4, 0.6], k=1)[0]

        link_to_pipeline = rng.random() < 0.8
        if link_to_pipeline:
            pipeline = pipelines[rng.randrange(len(pipelines))]
            client_id = pipeline.client_id
            pipeline_id = pipeline.pipeline_id
        else:
            pipeline = None
            client_id = clients[rng.randrange(len(clients))]["entity_id"]
            pipeline_id = ""

        created_at = now_ref - timedelta(days=rng.randint(0, 120), minutes=rng.randint(0, 1_440))
        updated_at = min(now_ref, created_at + timedelta(days=rng.randint(0, 30)))

        threshold = ""
        window_minutes = ""
        if rule_type == "failures_in_window":
            threshold = str(rng.randint(2, 8))
            window_minutes = str(rng.choice([10, 15, 20, 30, 45, 60]))

        materialized = {
            "id": str(uuid.uuid5(NAMESPACE_UUID, f"alert-rule:{index}:{client_id}:{pipeline_id}:{rule_type}:{channel}")),
            "client_id": client_id,
            "pipeline_id": pipeline_id,
            "rule_type": rule_type,
            "threshold": threshold,
            "window_minutes": window_minutes,
            "channel": channel,
            "destination": _alert_destination(channel, rng),
            "is_enabled": "true" if rng.random() < 0.86 else "false",
            "created_at": _to_iso_utc(created_at),
            "updated_at": _to_iso_utc(updated_at),
        }

        if pipeline is None and client_id not in clients_by_id:
            raise StepExecutionError(f"alert rule references unknown client {client_id}")

        rows.append(materialized)

    _write_csv(alert_rules_path, ALERT_RULE_HEADERS, rows)

    enabled_count = sum(1 for row in rows if row["is_enabled"] == "true")
    return {
        "files_written": [str(alert_rules_path)],
        "rows": len(rows),
        "enabled_rows": enabled_count,
        "summary": "generated alert rules across slack/email/webhook channels",
    }


def _validate_timestamp(value: str, allow_empty: bool = False) -> bool:
    if value == "":
        return allow_empty
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return parsed.tzinfo is None


def _add_issue(
    issues: list[dict[str, str]],
    *,
    severity: str,
    file: str,
    row: int,
    column: str,
    rule: str,
    details: str,
) -> None:
    issues.append(
        {
            "severity": severity,
            "file": file,
            "row": str(row),
            "column": column,
            "rule": rule,
            "details": details,
        }
    )


def validate_csv_set(
    clients_path: Path,
    pipelines_path: Path,
    registry_path: Path,
    runs_path: Path,
    alert_rules_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    """Validate generated CSV files and write validation report."""
    clients = _read_csv(clients_path)
    pipelines = _read_csv(pipelines_path)
    registry = _read_csv(registry_path)
    runs = _read_csv(runs_path)
    alert_rules = _read_csv(alert_rules_path)

    issues: list[dict[str, str]] = []

    expected_headers = {
        str(clients_path): CLIENT_HEADERS,
        str(pipelines_path): PIPELINE_HEADERS,
        str(registry_path): ID_REGISTRY_HEADERS,
        str(runs_path): RUN_HEADERS,
        str(alert_rules_path): ALERT_RULE_HEADERS,
    }
    for file_name, expected in expected_headers.items():
        actual = _read_headers(Path(file_name))
        if actual != expected:
            _add_issue(
                issues,
                severity="high",
                file=file_name,
                row=1,
                column="*",
                rule="required_columns",
                details=f"expected {expected} got {actual}",
            )

    client_ids = {row.get("id", "") for row in clients}
    pipeline_ids = {row.get("id", "") for row in pipelines}

    if len(client_ids) != len(clients):
        _add_issue(
            issues,
            severity="high",
            file=str(clients_path),
            row=0,
            column="id",
            rule="unique_ids",
            details="duplicate client id detected",
        )
    if len(pipeline_ids) != len(pipelines):
        _add_issue(
            issues,
            severity="high",
            file=str(pipelines_path),
            row=0,
            column="id",
            rule="unique_ids",
            details="duplicate pipeline id detected",
        )

    for index, row in enumerate(pipelines, start=2):
        if row["client_id"] not in client_ids:
            _add_issue(
                issues,
                severity="high",
                file=str(pipelines_path),
                row=index,
                column="client_id",
                rule="fk_client",
                details=f"unknown client_id {row['client_id']}",
            )
        if row["platform"] not in PLATFORMS:
            _add_issue(
                issues,
                severity="high",
                file=str(pipelines_path),
                row=index,
                column="platform",
                rule="enum_platform",
                details=f"invalid platform {row['platform']}",
            )
        if row["pipeline_type"] not in PIPELINE_TYPES:
            _add_issue(
                issues,
                severity="high",
                file=str(pipelines_path),
                row=index,
                column="pipeline_type",
                rule="enum_pipeline_type",
                details=f"invalid pipeline_type {row['pipeline_type']}",
            )

    registry_pipeline_ids = {row["entity_id"] for row in registry if row.get("entity_type") == "pipeline"}
    registry_client_ids = {row["entity_id"] for row in registry if row.get("entity_type") == "client"}

    seen_external_run_ids: set[str] = set()
    for index, row in enumerate(runs, start=2):
        if row["pipeline_id"] not in pipeline_ids or row["pipeline_id"] not in registry_pipeline_ids:
            _add_issue(
                issues,
                severity="high",
                file=str(runs_path),
                row=index,
                column="pipeline_id",
                rule="fk_pipeline",
                details=f"unknown pipeline_id {row['pipeline_id']}",
            )

        if row["status"] not in RUN_STATUSES:
            _add_issue(
                issues,
                severity="high",
                file=str(runs_path),
                row=index,
                column="status",
                rule="enum_status",
                details=f"invalid status {row['status']}",
            )

        external_run_id = row["external_run_id"]
        if external_run_id in seen_external_run_ids:
            _add_issue(
                issues,
                severity="high",
                file=str(runs_path),
                row=index,
                column="external_run_id",
                rule="unique_external_run_id",
                details=f"duplicate external_run_id {external_run_id}",
            )
        seen_external_run_ids.add(external_run_id)

        if not _validate_timestamp(row["started_at"]):
            _add_issue(
                issues,
                severity="high",
                file=str(runs_path),
                row=index,
                column="started_at",
                rule="timestamp_format",
                details=f"invalid timestamp {row['started_at']}",
            )

        if row["status"] == "running":
            if row["finished_at"] or row["duration_seconds"]:
                _add_issue(
                    issues,
                    severity="medium",
                    file=str(runs_path),
                    row=index,
                    column="finished_at",
                    rule="running_fields",
                    details="running rows must not have finished_at/duration_seconds",
                )
        else:
            if not row["finished_at"] or not row["duration_seconds"]:
                _add_issue(
                    issues,
                    severity="high",
                    file=str(runs_path),
                    row=index,
                    column="finished_at",
                    rule="completed_fields",
                    details="non-running rows must have finished_at and duration_seconds",
                )
            if row["finished_at"] and not _validate_timestamp(row["finished_at"]):
                _add_issue(
                    issues,
                    severity="high",
                    file=str(runs_path),
                    row=index,
                    column="finished_at",
                    rule="timestamp_format",
                    details=f"invalid timestamp {row['finished_at']}",
                )
            if row["finished_at"]:
                start_at = _parse_datetime_utc(row["started_at"])
                finish_at = _parse_datetime_utc(row["finished_at"])
                if finish_at < start_at:
                    _add_issue(
                        issues,
                        severity="high",
                        file=str(runs_path),
                        row=index,
                        column="finished_at",
                        rule="timestamp_order",
                        details="finished_at is earlier than started_at",
                    )

            try:
                duration = int(row["duration_seconds"])
                if duration < 0:
                    raise ValueError
            except ValueError:
                _add_issue(
                    issues,
                    severity="high",
                    file=str(runs_path),
                    row=index,
                    column="duration_seconds",
                    rule="duration_non_negative",
                    details=f"invalid duration {row['duration_seconds']}",
                )

        if row["status"] == "failed":
            if not row["error_message"] or not row["status_reason"]:
                _add_issue(
                    issues,
                    severity="high",
                    file=str(runs_path),
                    row=index,
                    column="error_message",
                    rule="failed_fields",
                    details="failed rows require error_message and status_reason",
                )
        else:
            if row["error_message"] or row["status_reason"]:
                _add_issue(
                    issues,
                    severity="medium",
                    file=str(runs_path),
                    row=index,
                    column="status_reason",
                    rule="non_failed_fields",
                    details="non-failed rows must leave error_message/status_reason empty",
                )

        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = None
        if not isinstance(payload, dict):
            _add_issue(
                issues,
                severity="high",
                file=str(runs_path),
                row=index,
                column="payload",
                rule="payload_json",
                details="payload must be a valid JSON object",
            )

    for index, row in enumerate(alert_rules, start=2):
        if row["rule_type"] not in RULE_TYPES:
            _add_issue(
                issues,
                severity="high",
                file=str(alert_rules_path),
                row=index,
                column="rule_type",
                rule="enum_rule_type",
                details=f"invalid rule_type {row['rule_type']}",
            )
        if row["channel"] not in CHANNELS:
            _add_issue(
                issues,
                severity="high",
                file=str(alert_rules_path),
                row=index,
                column="channel",
                rule="enum_channel",
                details=f"invalid channel {row['channel']}",
            )

        client_id = row.get("client_id", "")
        if client_id and client_id not in client_ids and client_id not in registry_client_ids:
            _add_issue(
                issues,
                severity="high",
                file=str(alert_rules_path),
                row=index,
                column="client_id",
                rule="fk_client",
                details=f"unknown client_id {client_id}",
            )

        pipeline_id = row.get("pipeline_id", "")
        if pipeline_id and pipeline_id not in pipeline_ids and pipeline_id not in registry_pipeline_ids:
            _add_issue(
                issues,
                severity="high",
                file=str(alert_rules_path),
                row=index,
                column="pipeline_id",
                rule="fk_pipeline",
                details=f"unknown pipeline_id {pipeline_id}",
            )

    if issues:
        _write_csv(
            report_path,
            ["severity", "file", "row", "column", "rule", "details"],
            issues,
        )
    else:
        _write_csv(
            report_path,
            ["status", "message"],
            [{"status": "ok", "message": "validation passed"}],
        )

    return {
        "files_written": [str(report_path)],
        "issues": len(issues),
        "summary": "validation completed" if not issues else "validation reported issues",
    }


def _check_step_a(step: dict[str, Any]) -> None:
    clients_path = Path(step["outputs"][0])
    pipelines_path = Path(step["outputs"][1])

    if _read_headers(clients_path) != CLIENT_HEADERS:
        raise StepExecutionError("clients.csv headers do not match CHM contract")
    if _read_headers(pipelines_path) != PIPELINE_HEADERS:
        raise StepExecutionError("pipelines.csv headers do not match CHM contract")

    pipelines = _read_csv(pipelines_path)
    platforms = {row["platform"] for row in pipelines}
    pipeline_types = {row["pipeline_type"] for row in pipelines}

    if not platforms.issubset(PLATFORMS):
        raise StepExecutionError(f"platform values outside enum: {sorted(platforms - PLATFORMS)}")
    if not pipeline_types.issubset(PIPELINE_TYPES):
        raise StepExecutionError(f"pipeline_type values outside enum: {sorted(pipeline_types - PIPELINE_TYPES)}")


def _check_step_b(step: dict[str, Any]) -> None:
    registry_path = Path(step["outputs"][0])
    rows = _read_csv(registry_path)

    clients = {row["entity_id"] for row in rows if row.get("entity_type") == "client"}
    pipelines = [row for row in rows if row.get("entity_type") == "pipeline"]

    if not clients or not pipelines:
        raise StepExecutionError("id_registry.csv must include both client and pipeline rows")

    missing_parents = [row["entity_id"] for row in pipelines if row.get("parent_entity_id") not in clients]
    if missing_parents:
        raise StepExecutionError(f"pipeline rows with missing parent client ids: {missing_parents[:5]}")


def _check_step_c(step: dict[str, Any], state: dict[str, Any]) -> None:
    runs_path = Path(step["outputs"][0])
    runs = _read_csv(runs_path)

    if len(runs) < 2000:
        raise StepExecutionError("runs batch has fewer than 2000 rows")

    registry_step = next(item for item in state["steps"] if item["id"] == "B")
    registry_rows = _read_csv(Path(registry_step["outputs"][0]))
    pipeline_ids = {row["entity_id"] for row in registry_rows if row.get("entity_type") == "pipeline"}

    invalid_pipeline_ids = {row["pipeline_id"] for row in runs if row["pipeline_id"] not in pipeline_ids}
    if invalid_pipeline_ids:
        raise StepExecutionError(f"runs contain unknown pipeline ids: {sorted(invalid_pipeline_ids)[:5]}")

    invalid_statuses = {row["status"] for row in runs if row["status"] not in RUN_STATUSES}
    if invalid_statuses:
        raise StepExecutionError(f"runs contain invalid statuses: {sorted(invalid_statuses)}")


def _check_step_d(step: dict[str, Any], state: dict[str, Any]) -> None:
    alert_rules_path = Path(step["outputs"][0])
    rules = _read_csv(alert_rules_path)

    invalid_rule_types = {row["rule_type"] for row in rules if row["rule_type"] not in RULE_TYPES}
    invalid_channels = {row["channel"] for row in rules if row["channel"] not in CHANNELS}

    if invalid_rule_types:
        raise StepExecutionError(f"alert_rules has invalid rule_type values: {sorted(invalid_rule_types)}")
    if invalid_channels:
        raise StepExecutionError(f"alert_rules has invalid channel values: {sorted(invalid_channels)}")

    registry_step = next(item for item in state["steps"] if item["id"] == "B")
    registry_rows = _read_csv(Path(registry_step["outputs"][0]))

    client_ids = {row["entity_id"] for row in registry_rows if row["entity_type"] == "client"}
    pipeline_ids = {row["entity_id"] for row in registry_rows if row["entity_type"] == "pipeline"}

    bad_client_refs = {row["client_id"] for row in rules if row["client_id"] and row["client_id"] not in client_ids}
    bad_pipeline_refs = {
        row["pipeline_id"] for row in rules if row["pipeline_id"] and row["pipeline_id"] not in pipeline_ids
    }

    if bad_client_refs:
        raise StepExecutionError(f"alert_rules has unknown client ids: {sorted(bad_client_refs)[:5]}")
    if bad_pipeline_refs:
        raise StepExecutionError(f"alert_rules has unknown pipeline ids: {sorted(bad_pipeline_refs)[:5]}")


def _check_step_e(step: dict[str, Any]) -> None:
    report_path = Path(step["outputs"][0])
    rows = _read_csv(report_path)

    if not rows:
        raise StepExecutionError("validation_report.csv has no data rows")

    header = _read_headers(report_path)
    if header == ["status", "message"]:
        if rows[0].get("status") != "ok" or rows[0].get("message") != "validation passed":
            raise StepExecutionError("validation report ok row is invalid")
        return

    if header != ["severity", "file", "row", "column", "rule", "details"]:
        raise StepExecutionError("validation report has unexpected schema")


def _step_artifacts(step: dict[str, Any], outputs: dict[str, Any], success: bool) -> dict[str, Any]:
    artifacts: dict[str, Any] = dict(outputs)
    artifacts["pass"] = success
    if "files_written" not in artifacts:
        artifacts["files_written"] = list(step.get("outputs", []))
    return artifacts


def _touch_state(state: dict[str, Any]) -> None:
    state["updated_at_utc"] = _now_utc_iso()


def _load_state(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _save_state(path: Path, state: dict[str, Any]) -> None:
    _touch_state(state)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")


def _next_pending_step(state: dict[str, Any]) -> dict[str, Any] | None:
    steps = state.get("steps", [])
    in_progress_steps = [step for step in steps if step.get("status") == "in_progress"]
    if in_progress_steps:
        raise StepExecutionError(
            f"state file already has in_progress step(s): {[step['id'] for step in in_progress_steps]}"
        )

    for index, step in enumerate(steps):
        if step.get("status") != "pending":
            continue
        if all(previous.get("status") == "completed" for previous in steps[:index]):
            return step
        return None
    return None


def _next_pending_step_id(state: dict[str, Any]) -> str | None:
    steps = state.get("steps", [])
    for index, step in enumerate(steps):
        if step.get("status") != "pending":
            continue
        if all(previous.get("status") == "completed" for previous in steps[:index]):
            return step.get("id")
        return None
    return None


def _run_step(step: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    step_id = step["id"]

    if step_id == "A":
        outputs = normalize_base_files(Path(step["inputs"][0]), Path(step["inputs"][1]))
        _check_step_a(step)
        return outputs

    if step_id == "B":
        outputs = build_id_registry(
            Path(step["inputs"][0]),
            Path(step["inputs"][1]),
            Path(step["outputs"][0]),
        )
        _check_step_b(step)
        return outputs

    if step_id == "C":
        outputs = generate_runs_batch(Path(step["inputs"][0]), Path(step["outputs"][0]))
        _check_step_c(step, state)
        return outputs

    if step_id == "D":
        outputs = generate_alert_rules(Path(step["inputs"][0]), Path(step["outputs"][0]))
        _check_step_d(step, state)
        return outputs

    if step_id == "E":
        outputs = validate_csv_set(
            clients_path=Path(step["inputs"][0]),
            pipelines_path=Path(step["inputs"][1]),
            registry_path=Path(step["inputs"][2]),
            runs_path=Path(step["inputs"][3]),
            alert_rules_path=Path(step["inputs"][4]),
            report_path=Path(step["outputs"][0]),
        )
        _check_step_e(step)
        return outputs

    raise StepExecutionError(f"unsupported step id {step_id}")


def execute_next_pending_step(state_path: Path = DEFAULT_STATE_FILE) -> dict[str, Any]:
    """Execute exactly one next pending step and persist state transitions."""
    state = _load_state(state_path)
    step = _next_pending_step(state)

    if step is None:
        return {
            "step_executed": None,
            "files_written": [],
            "pass": True,
            "next_step_id": None,
            "message": "no pending step available",
        }

    step["status"] = "in_progress"
    step["artifacts"] = {}
    _save_state(state_path, state)

    try:
        outputs = _run_step(step, state)
    except Exception as exc:  # noqa: BLE001 - preserve exact failure details for state artifacts.
        step["status"] = "blocked"
        step["artifacts"] = {
            "error": str(exc),
            "files_written": list(step.get("outputs", [])),
            "pass": False,
        }
        _save_state(state_path, state)
        return {
            "step_executed": step["id"],
            "files_written": list(step.get("outputs", [])),
            "pass": False,
            "next_step_id": _next_pending_step_id(state),
            "message": str(exc),
        }

    step["status"] = "completed"
    step["artifacts"] = _step_artifacts(step, outputs, success=True)
    _save_state(state_path, state)

    return {
        "step_executed": step["id"],
        "files_written": step["artifacts"].get("files_written", []),
        "pass": True,
        "next_step_id": _next_pending_step_id(state),
        "message": "step completed",
    }


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute the next pending synthetic-data workflow step.")
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help="Path to session_state.json",
    )
    args = parser.parse_args(argv)

    result = execute_next_pending_step(args.state_file)

    print(f"step executed: {result['step_executed']}")
    print(f"files written: {', '.join(result['files_written']) if result['files_written'] else '-'}")
    print(f"pass/fail: {'pass' if result['pass'] else 'fail'}")
    print(f"next step id: {result['next_step_id']}")

    return 0 if result["pass"] else 1


def main() -> None:
    """CLI entrypoint."""
    raise SystemExit(_cli())


if __name__ == "__main__":
    main()
