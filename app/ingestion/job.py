"""Ingestion orchestration for external partner run synchronization."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.repository.pipelines import list_ingestion_pipelines_with_external_id
from app.db.repository.runs import upsert_run
from app.ingestion.mapper import map_partner_run_event


def ingest_external_runs(
    *,
    session: Session,
    partner_client: Any,
) -> dict[str, int]:
    """Ingest external partner runs for eligible pipelines."""
    pipelines = list_ingestion_pipelines_with_external_id(session)

    pipelines_processed = 0
    pages_processed = 0
    runs_processed = 0

    for pipeline in pipelines:
        if not pipeline.external_id:
            continue
        pipeline_result = _ingest_pipeline(
            session=session,
            partner_client=partner_client,
            pipeline_id=pipeline.id,
            pipeline_external_id=pipeline.external_id,
        )
        pages_processed += pipeline_result["pages_processed"]
        runs_processed += pipeline_result["runs_processed"]
        pipelines_processed += 1

    return {
        "pipelines_processed": pipelines_processed,
        "pages_processed": pages_processed,
        "runs_processed": runs_processed,
    }


def _ingest_pipeline(
    *,
    session: Session,
    partner_client: Any,
    pipeline_id: UUID,
    pipeline_external_id: str,
) -> dict[str, int]:
    cursor: str | None = None
    pages_processed = 0
    runs_processed = 0

    while True:
        page = _fetch_partner_page(
            partner_client=partner_client,
            pipeline_external_id=pipeline_external_id,
            cursor=cursor,
        )
        pages_processed += 1

        runs = page.get("runs") or []
        if not isinstance(runs, list):
            raise TypeError("Partner page field `runs` must be a list")

        for raw_event in runs:
            mapped = map_partner_run_event(raw_event)
            upsert_run(
                session,
                pipeline_id=pipeline_id,
                external_run_id=mapped["external_run_id"],
                status=mapped["status"],
                started_at=mapped["started_at"],
                finished_at=mapped["finished_at"],
                duration_seconds=mapped["duration_seconds"],
                rows_processed=mapped["rows_processed"],
                error_message=mapped["error_message"],
                status_reason=mapped["status_reason"],
                payload=mapped["payload"],
                ingested_at=datetime.now(timezone.utc),
            )
            runs_processed += 1

        next_cursor = page.get("next_cursor")
        if next_cursor in (None, ""):
            break
        cursor = str(next_cursor)

    return {
        "pages_processed": pages_processed,
        "runs_processed": runs_processed,
    }


def _fetch_partner_page(
    *,
    partner_client: Any,
    pipeline_external_id: str,
    cursor: str | None,
) -> dict[str, Any]:
    for method_name in ("fetch_runs", "list_runs", "fetch_pipeline_runs"):
        method = getattr(partner_client, method_name, None)
        if callable(method):
            return method(pipeline_external_id, cursor=cursor)

    raise TypeError(
        "Partner client must provide one of: fetch_runs, list_runs, fetch_pipeline_runs",
    )

