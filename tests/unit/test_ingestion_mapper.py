"""Unit tests for partner ingestion payload normalization."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

import pytest

from app.db.models.run import RunStatusEnum
from app.ingestion.mapper import IngestionMappingError
from app.ingestion.mapper import map_partner_run_event
from app.ingestion.mapper import normalize_partner_status


def test_map_partner_run_event_normalizes_required_and_optional_fields() -> None:
    event = {
        "external_run_id": "run-001",
        "status": "success",
        "started_at": "2026-02-20T11:00:00Z",
        "finished_at": "2026-02-20T11:05:00+00:00",
        "duration_seconds": "300",
        "rows_processed": 2500,
        "error_message": None,
        "status_reason": "completed",
    }

    mapped = map_partner_run_event(event)

    assert mapped["external_run_id"] == "run-001"
    assert mapped["status"] == RunStatusEnum.SUCCESS
    assert mapped["started_at"] == datetime(2026, 2, 20, 11, 0, tzinfo=timezone.utc)
    assert mapped["finished_at"] == datetime(2026, 2, 20, 11, 5, tzinfo=timezone.utc)
    assert mapped["duration_seconds"] == 300
    assert mapped["rows_processed"] == 2500
    assert mapped["status_reason"] == "completed"
    assert mapped["payload"] == event


def test_map_partner_run_event_uses_id_as_external_identity_fallback() -> None:
    mapped = map_partner_run_event(
        {
            "id": "vendor-run-100",
            "status": "running",
            "started_at": "2026-02-20T09:00:00",
        }
    )

    assert mapped["external_run_id"] == "vendor-run-100"
    assert mapped["status"] == RunStatusEnum.RUNNING
    assert mapped["started_at"] == datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc)


def test_unknown_status_defaults_to_failed_and_tracks_normalization_reason() -> None:
    mapped = map_partner_run_event(
        {
            "external_run_id": "run-unknown-status",
            "status": "paused",
        }
    )

    assert mapped["status"] == RunStatusEnum.FAILED
    assert mapped["status_reason"] == "Unknown source status `paused` normalized to `failed`"


def test_normalize_partner_status_handles_missing_value() -> None:
    status, reason = normalize_partner_status(None)

    assert status == RunStatusEnum.FAILED
    assert reason == "Missing source status; defaulted to `failed`"


def test_map_partner_run_event_rejects_missing_identity() -> None:
    with pytest.raises(IngestionMappingError):
        map_partner_run_event({"status": "success"})


def test_map_partner_run_event_rejects_invalid_timestamp() -> None:
    with pytest.raises(IngestionMappingError):
        map_partner_run_event(
            {
                "external_run_id": "run-002",
                "status": "success",
                "started_at": "not-a-date",
            }
        )

