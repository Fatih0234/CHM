"""Add run/query indexes for API filters, latest queries, and dashboards."""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004_run_indexes"
down_revision: Union[str, None] = "003_runs_alert_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create performance indexes for run-heavy read paths."""
    op.create_index(
        "ix_runs_pipeline_latest_order",
        "runs",
        [
            "pipeline_id",
            sa.text("started_at DESC NULLS LAST"),
            sa.text("finished_at DESC NULLS LAST"),
            sa.text("id DESC"),
        ],
        unique=False,
    )

    op.create_index(
        "ix_runs_pipeline_status_started_at",
        "runs",
        ["pipeline_id", "status", sa.text("started_at DESC NULLS LAST")],
        unique=False,
    )

    op.create_index(
        "ix_runs_status_event_time",
        "runs",
        ["status", sa.text("COALESCE(finished_at, started_at, created_at)")],
        unique=False,
    )

    op.create_index(
        "ix_runs_event_time",
        "runs",
        [sa.text("COALESCE(finished_at, started_at, created_at)")],
        unique=False,
    )

    op.create_index("ix_pipelines_client_id", "pipelines", ["client_id"], unique=False)
    op.create_index("ix_alert_rules_client_id", "alert_rules", ["client_id"], unique=False)
    op.create_index("ix_alert_rules_pipeline_id", "alert_rules", ["pipeline_id"], unique=False)


def downgrade() -> None:
    """Drop performance indexes introduced for query workloads."""
    op.drop_index("ix_alert_rules_pipeline_id", table_name="alert_rules")
    op.drop_index("ix_alert_rules_client_id", table_name="alert_rules")
    op.drop_index("ix_pipelines_client_id", table_name="pipelines")
    op.drop_index("ix_runs_event_time", table_name="runs")
    op.drop_index("ix_runs_status_event_time", table_name="runs")
    op.drop_index("ix_runs_pipeline_status_started_at", table_name="runs")
    op.drop_index("ix_runs_pipeline_latest_order", table_name="runs")
