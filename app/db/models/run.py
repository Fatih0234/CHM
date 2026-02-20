"""SQLAlchemy model for CHM pipeline runs."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.models.client import Base


class RunStatusEnum(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"
    SKIPPED = "skipped"


if TYPE_CHECKING:
    from app.db.models.pipeline import Pipeline


class Run(Base):
    """Execution record for a pipeline run."""

    __tablename__ = "runs"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_runs"),
        UniqueConstraint(
            "pipeline_id",
            "external_run_id",
            name="uq_runs_pipeline_id_external_run_id",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_runs_duration_non_negative",
        ),
        CheckConstraint(
            "rows_processed IS NULL OR rows_processed >= 0",
            name="ck_runs_rows_processed_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipelines.id", name="fk_runs_pipeline_id_pipelines", ondelete="RESTRICT"),
        nullable=False,
    )
    external_run_id: Mapped[str] = mapped_column(postgresql.VARCHAR(255), nullable=False)
    status: Mapped[RunStatusEnum] = mapped_column(
        postgresql.ENUM(RunStatusEnum, name="run_status", create_type=False),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_processed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
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

    pipeline: Mapped["Pipeline"] = relationship("Pipeline", back_populates="runs")
