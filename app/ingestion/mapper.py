"""Partner source-to-run mapping helpers for ingestion normalization."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from datetime import timezone
from typing import Any

from app.db.models.run import RunStatusEnum

_STATUS_MAP: dict[str, RunStatusEnum] = {
    "running": RunStatusEnum.RUNNING,
    "in_progress": RunStatusEnum.RUNNING,
    "queued": RunStatusEnum.RUNNING,
    "pending": RunStatusEnum.RUNNING,
    "success": RunStatusEnum.SUCCESS,
    "succeeded": RunStatusEnum.SUCCESS,
    "completed": RunStatusEnum.SUCCESS,
    "failed": RunStatusEnum.FAILED,
    "failure": RunStatusEnum.FAILED,
    "error": RunStatusEnum.FAILED,
    "errored": RunStatusEnum.FAILED,
    "canceled": RunStatusEnum.CANCELED,
    "cancelled": RunStatusEnum.CANCELED,
    "aborted": RunStatusEnum.CANCELED,
    "skipped": RunStatusEnum.SKIPPED,
}


class IngestionMappingError(ValueError):
    """Raised when partner payload cannot be normalized into canonical run fields."""


def map_partner_run_event(raw_event: Mapping[str, Any]) -> dict[str, Any]:
    """Map a partner run payload into canonical run repository fields."""
    external_run_id = _extract_external_run_id(raw_event)
    status, normalization_reason = normalize_partner_status(raw_event.get("status"))
    started_at = _parse_utc_timestamp(raw_event.get("started_at"))
    finished_at = _parse_utc_timestamp(raw_event.get("finished_at"))

    status_reason = _as_optional_string(raw_event.get("status_reason"))
    if status_reason is None and normalization_reason is not None:
        status_reason = normalization_reason

    return {
        "external_run_id": external_run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": _as_optional_int(raw_event.get("duration_seconds")),
        "rows_processed": _as_optional_int(raw_event.get("rows_processed")),
        "error_message": _as_optional_string(raw_event.get("error_message")),
        "status_reason": status_reason,
        "payload": dict(raw_event),
    }


def normalize_partner_status(raw_status: Any) -> tuple[RunStatusEnum, str | None]:
    """Normalize source status to the canonical enum with reason on unknown values."""
    if raw_status is None:
        return RunStatusEnum.FAILED, "Missing source status; defaulted to `failed`"

    normalized = str(raw_status).strip().lower()
    mapped = _STATUS_MAP.get(normalized)
    if mapped is not None:
        return mapped, None

    return (
        RunStatusEnum.FAILED,
        f"Unknown source status `{raw_status}` normalized to `failed`",
    )


def _extract_external_run_id(raw_event: Mapping[str, Any]) -> str:
    candidate = raw_event.get("external_run_id")
    if candidate in (None, ""):
        candidate = raw_event.get("id")

    if candidate in (None, ""):
        raise IngestionMappingError("Missing required run identity field `external_run_id` or `id`")

    return str(candidate)


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise IngestionMappingError("Timestamp fields must be ISO-8601 strings")

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise IngestionMappingError(f"Invalid timestamp value: {value}") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise IngestionMappingError(f"Expected integer-compatible value, got {value!r}") from exc


def _as_optional_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)

