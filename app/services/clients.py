"""Service helpers for client API operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.core.errors import NotFoundError
from app.db.repository.clients import create_client
from app.db.repository.clients import disable_client
from app.db.repository.clients import get_client
from app.db.repository.clients import list_clients
from app.db.repository.clients import update_client
from app.schemas.client import ClientCreate
from app.schemas.client import ClientUpdate
from app.schemas.error import ErrorDetail


def _raise_validation_error(message: str, *, field: str = "request") -> None:
    raise APIError(
        status_code=400,
        code="validation_error",
        message=message,
        details=[ErrorDetail(field=field, issue=message)],
    )


def create_client_service(session: Session, payload: ClientCreate):
    """Create and persist a new client."""
    try:
        client = create_client(session, name=payload.name)
        session.commit()
        return client
    except IntegrityError:
        session.rollback()
        _raise_validation_error("Client name must be unique", field="name")


def list_clients_service(session: Session, *, is_active: bool | None = None):
    """List clients with optional active-state filtering."""
    return list_clients(session, is_active=is_active)


def get_client_service(session: Session, client_id: UUID):
    """Fetch a client or raise not found."""
    client = get_client(session, client_id)
    if client is None:
        raise NotFoundError(message="Client not found")
    return client


def update_client_service(session: Session, client_id: UUID, payload: ClientUpdate):
    """Update mutable client fields for an existing client."""
    client = get_client_service(session, client_id)
    try:
        client = update_client(
            session,
            client,
            name=payload.name,
            is_active=payload.is_active,
        )
        session.commit()
        return client
    except IntegrityError:
        session.rollback()
        _raise_validation_error("Client name must be unique", field="name")


def disable_client_service(session: Session, client_id: UUID):
    """Soft-disable a client and persist the change."""
    client = get_client_service(session, client_id)
    client = disable_client(session, client)
    session.commit()
    return client
