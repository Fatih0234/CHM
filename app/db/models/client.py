"""SQLAlchemy model for CHM clients."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship


class Base(DeclarativeBase):
    """Declarative base for CHM ORM models."""


if TYPE_CHECKING:
    from app.db.models.alert_rule import AlertRule
    from app.db.models.pipeline import Pipeline


class Client(Base):
    """Client inventory entity."""

    __tablename__ = "clients"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_clients"),
        UniqueConstraint("name", name="uq_clients_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    pipelines: Mapped[list["Pipeline"]] = relationship("Pipeline", back_populates="client")
    alert_rules: Mapped[list["AlertRule"]] = relationship("AlertRule", back_populates="client")
