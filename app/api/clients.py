"""Client API routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Response
from sqlalchemy.orm import Session

from app.db.base import get_db_session
from app.schemas.client import Client
from app.schemas.client import ClientCreate
from app.schemas.client import ClientListResponse
from app.schemas.client import ClientRunSummary
from app.schemas.client import ClientUpdate
from app.services.clients import create_client_service
from app.services.clients import disable_client_service
from app.services.clients import get_client_service
from app.services.clients import list_clients_service
from app.services.clients import update_client_service
from app.services.summaries import get_client_run_summary_service

router = APIRouter(prefix="/api/v1", tags=["clients"])


@router.post("/clients", response_model=Client, status_code=201)
def create_client_endpoint(
    payload: ClientCreate,
    session: Session = Depends(get_db_session),
) -> Client:
    """Create a client."""
    return create_client_service(session, payload)


@router.get("/clients", response_model=ClientListResponse)
def list_clients_endpoint(
    is_active: bool | None = None,
    session: Session = Depends(get_db_session),
) -> ClientListResponse:
    """List clients with optional active-state filter."""
    clients = list_clients_service(session, is_active=is_active)
    return ClientListResponse(items=clients)


@router.get("/clients/{client_id}", response_model=Client)
def get_client_endpoint(
    client_id: UUID,
    session: Session = Depends(get_db_session),
) -> Client:
    """Get a single client by id."""
    return get_client_service(session, client_id)


@router.patch("/clients/{client_id}", response_model=Client)
def update_client_endpoint(
    client_id: UUID,
    payload: ClientUpdate,
    session: Session = Depends(get_db_session),
) -> Client:
    """Update a client."""
    return update_client_service(session, client_id, payload)


@router.delete("/clients/{client_id}", status_code=204)
def delete_client_endpoint(
    client_id: UUID,
    session: Session = Depends(get_db_session),
) -> Response:
    """Soft-disable a client."""
    disable_client_service(session, client_id)
    return Response(status_code=204)


@router.get("/clients/{client_id}/runs/summary", response_model=ClientRunSummary)
def get_client_run_summary_endpoint(
    client_id: UUID,
    since: datetime | None = None,
    until: datetime | None = None,
    session: Session = Depends(get_db_session),
) -> ClientRunSummary:
    """Get run summary for a client."""
    return get_client_run_summary_service(
        session,
        client_id=client_id,
        since=since,
        until=until,
    )
