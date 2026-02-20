"""Create enum types used by CHM domain tables."""

from typing import Sequence
from typing import Union

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_create_enums"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

platform_enum = postgresql.ENUM(
    "airflow",
    "dbt",
    "cron",
    "vendor_api",
    "custom",
    name="platform",
)

pipeline_type_enum = postgresql.ENUM(
    "ingestion",
    "transform",
    "quality",
    "export",
    "healthcheck",
    name="pipeline_type",
)

run_status_enum = postgresql.ENUM(
    "running",
    "success",
    "failed",
    "canceled",
    "skipped",
    name="run_status",
)

rule_type_enum = postgresql.ENUM(
    "on_failure",
    "failures_in_window",
    name="rule_type",
)

channel_enum = postgresql.ENUM(
    "slack",
    "email",
    "webhook",
    name="channel",
)


def upgrade() -> None:
    """Create all enum types before dependent tables are introduced."""
    bind = op.get_bind()
    platform_enum.create(bind, checkfirst=True)
    pipeline_type_enum.create(bind, checkfirst=True)
    run_status_enum.create(bind, checkfirst=True)
    rule_type_enum.create(bind, checkfirst=True)
    channel_enum.create(bind, checkfirst=True)


def downgrade() -> None:
    """Drop enum types in reverse dependency-safe order."""
    bind = op.get_bind()
    channel_enum.drop(bind, checkfirst=True)
    rule_type_enum.drop(bind, checkfirst=True)
    run_status_enum.drop(bind, checkfirst=True)
    pipeline_type_enum.drop(bind, checkfirst=True)
    platform_enum.drop(bind, checkfirst=True)
