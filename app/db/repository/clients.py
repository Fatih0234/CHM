"""Repository primitives for client entities."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.client import Client


def create_client(session: Session, *, name: str, is_active: bool = True) -> Client:
    """Create and return a client row."""
    client = Client(name=name, is_active=is_active)
    session.add(client)
    session.flush()
    session.refresh(client)
    return client


def get_client(session: Session, client_id: UUID) -> Client | None:
    """Fetch a client by id."""
    return session.get(Client, client_id)


def list_clients(
    session: Session,
    *,
    is_active: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Client]:
    """List clients with optional active-state filtering."""
    stmt = select(Client)
    if is_active is not None:
        stmt = stmt.where(Client.is_active == is_active)
    stmt = stmt.order_by(Client.created_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt))


def update_client(
    session: Session,
    client: Client,
    *,
    name: str | None = None,
    is_active: bool | None = None,
) -> Client:
    """Update mutable client fields."""
    if name is not None:
        client.name = name
    if is_active is not None:
        client.is_active = is_active
    session.flush()
    session.refresh(client)
    return client


def disable_client(session: Session, client: Client) -> Client:
    """Soft-disable a client."""
    client.is_active = False
    session.flush()
    session.refresh(client)
    return client
