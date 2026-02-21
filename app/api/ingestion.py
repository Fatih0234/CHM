"""Operational ingestion trigger routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import IngestionSettings
from app.core.config import get_ingestion_settings
from app.db.base import get_db_session
from app.ingestion.client import PartnerIngestionClient
from app.ingestion.job import ingest_external_runs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ingestion"])


class IngestionSyncResponse(BaseModel):
    """Response payload for ingestion trigger runs."""

    pipelines_processed: int
    pages_processed: int
    runs_processed: int


@router.post("/ingestion/runs/sync", response_model=IngestionSyncResponse)
def trigger_ingestion_sync(
    session: Session = Depends(get_db_session),
    settings: IngestionSettings = Depends(get_ingestion_settings),
) -> IngestionSyncResponse:
    """Trigger partner ingestion and persist normalized run events."""
    logger.info("Starting ingestion sync with settings=%s", settings.safe_for_logging())

    partner_client = PartnerIngestionClient(
        base_url=settings.partner_api_base_url,
        api_token=settings.partner_api_token,
        timeout_seconds=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
        backoff_seconds=settings.http_backoff_seconds,
    )

    try:
        result = ingest_external_runs(session=session, partner_client=partner_client)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Ingestion sync failed")
        raise

    logger.info("Completed ingestion sync with result=%s", result)
    return IngestionSyncResponse(**result)

