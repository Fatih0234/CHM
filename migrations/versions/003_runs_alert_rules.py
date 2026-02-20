"""Add runs and alert_rules schema with ingestion and rule constraints."""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_runs_alert_rules"
down_revision: Union[str, None] = "002_clients_pipelines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create runs and alert_rules tables with hard schema checks."""
    run_status_enum = postgresql.ENUM(name="run_status", create_type=False)
    rule_type_enum = postgresql.ENUM(name="rule_type", create_type=False)
    channel_enum = postgresql.ENUM(name="channel", create_type=False)

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_run_id", sa.String(length=255), nullable=False),
        sa.Column("status", run_status_enum, nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("rows_processed", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_runs_duration_non_negative",
        ),
        sa.CheckConstraint(
            "rows_processed IS NULL OR rows_processed >= 0",
            name="ck_runs_rows_processed_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_id"],
            ["pipelines.id"],
            name="fk_runs_pipeline_id_pipelines",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_runs"),
        sa.UniqueConstraint(
            "pipeline_id",
            "external_run_id",
            name="uq_runs_pipeline_id_external_run_id",
        ),
    )

    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rule_type", rule_type_enum, nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=True),
        sa.Column("window_minutes", sa.Integer(), nullable=True),
        sa.Column("channel", channel_enum, nullable=False),
        sa.Column("destination", sa.String(length=512), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "client_id IS NOT NULL OR pipeline_id IS NOT NULL",
            name="ck_alert_rules_scope_required",
        ),
        sa.CheckConstraint(
            "threshold IS NULL OR threshold > 0",
            name="ck_alert_rules_threshold_positive",
        ),
        sa.CheckConstraint(
            "window_minutes IS NULL OR window_minutes > 0",
            name="ck_alert_rules_window_minutes_positive",
        ),
        sa.CheckConstraint(
            "("
            "rule_type = 'on_failure'"
            " OR "
            "("
            "rule_type = 'failures_in_window'"
            " AND threshold IS NOT NULL"
            " AND window_minutes IS NOT NULL"
            ")"
            ")",
            name="ck_alert_rules_rule_type_params",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name="fk_alert_rules_client_id_clients",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_id"],
            ["pipelines.id"],
            name="fk_alert_rules_pipeline_id_pipelines",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_alert_rules"),
    )


def downgrade() -> None:
    """Drop runs and alert_rules tables."""
    op.drop_table("alert_rules")
    op.drop_table("runs")
