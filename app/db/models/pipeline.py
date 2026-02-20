"""SQLAlchemy model for CHM pipelines."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.models.client import Base


class PlatformEnum(str, Enum):
    AIRFLOW = "airflow"
    DBT = "dbt"
    CRON = "cron"
    VENDOR_API = "vendor_api"
    CUSTOM = "custom"


class PipelineTypeEnum(str, Enum):
    INGESTION = "ingestion"
    TRANSFORM = "transform"
    QUALITY = "quality"
    EXPORT = "export"
    HEALTHCHECK = "healthcheck"


if TYPE_CHECKING:
    from app.db.models.alert_rule import AlertRule
    from app.db.models.client import Client
    from app.db.models.run import Run


class Pipeline(Base):
    """Pipeline inventory entity under a client."""

    __tablename__ = "pipelines"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_pipelines"),
        UniqueConstraint("client_id", "name", name="uq_pipelines_client_id_name"),
        CheckConstraint(
            "environment IN ('dev', 'staging', 'prod')",
            name="ck_pipelines_environment",
        ),
        Index(
            "uq_pipelines_client_platform_external_id",
            "client_id",
            "platform",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", name="fk_pipelines_client_id_clients", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[PlatformEnum] = mapped_column(
        postgresql.ENUM(
            PlatformEnum,
            name="platform",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_type=False,
        ),
        nullable=False,
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pipeline_type: Mapped[PipelineTypeEnum] = mapped_column(
        postgresql.ENUM(
            PipelineTypeEnum,
            name="pipeline_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_type=False,
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'prod'"),
    )
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

    client: Mapped["Client"] = relationship("Client", back_populates="pipelines")
    runs: Mapped[list["Run"]] = relationship("Run", back_populates="pipeline")
    alert_rules: Mapped[list["AlertRule"]] = relationship("AlertRule", back_populates="pipeline")
