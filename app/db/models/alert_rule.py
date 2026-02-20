"""SQLAlchemy model for CHM alert rules."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import String
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.models.client import Base


class RuleTypeEnum(str, Enum):
    ON_FAILURE = "on_failure"
    FAILURES_IN_WINDOW = "failures_in_window"


class ChannelEnum(str, Enum):
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"


if TYPE_CHECKING:
    from app.db.models.client import Client
    from app.db.models.pipeline import Pipeline


class AlertRule(Base):
    """Rule definition for alerting scope and thresholds."""

    __tablename__ = "alert_rules"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_alert_rules"),
        CheckConstraint(
            "client_id IS NOT NULL OR pipeline_id IS NOT NULL",
            name="ck_alert_rules_scope_required",
        ),
        CheckConstraint(
            "threshold IS NULL OR threshold > 0",
            name="ck_alert_rules_threshold_positive",
        ),
        CheckConstraint(
            "window_minutes IS NULL OR window_minutes > 0",
            name="ck_alert_rules_window_minutes_positive",
        ),
        CheckConstraint(
            "(rule_type = 'on_failure' OR (rule_type = 'failures_in_window' AND threshold IS NOT NULL AND window_minutes IS NOT NULL))",
            name="ck_alert_rules_rule_type_params",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", name="fk_alert_rules_client_id_clients", ondelete="RESTRICT"),
        nullable=True,
    )
    pipeline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipelines.id", name="fk_alert_rules_pipeline_id_pipelines", ondelete="RESTRICT"),
        nullable=True,
    )
    rule_type: Mapped[RuleTypeEnum] = mapped_column(
        postgresql.ENUM(
            RuleTypeEnum,
            name="rule_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_type=False,
        ),
        nullable=False,
    )
    threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    window_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channel: Mapped[ChannelEnum] = mapped_column(
        postgresql.ENUM(
            ChannelEnum,
            name="channel",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_type=False,
        ),
        nullable=False,
    )
    destination: Mapped[str] = mapped_column(String(512), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(
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

    client: Mapped["Client | None"] = relationship("Client", back_populates="alert_rules")
    pipeline: Mapped["Pipeline | None"] = relationship("Pipeline", back_populates="alert_rules")
