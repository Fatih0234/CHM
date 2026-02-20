"""Add clients and pipelines tables with FK and uniqueness constraints."""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_clients_pipelines"
down_revision: Union[str, None] = "001_create_enums"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create core inventory tables for clients and pipelines."""
    platform_enum = postgresql.ENUM(name="platform", create_type=False)
    pipeline_type_enum = postgresql.ENUM(name="pipeline_type", create_type=False)

    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id", name="pk_clients"),
        sa.UniqueConstraint("name", name="uq_clients_name"),
    )

    op.create_table(
        "pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("pipeline_type", pipeline_type_enum, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "environment",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'prod'"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
            "environment IN ('dev', 'staging', 'prod')",
            name="ck_pipelines_environment",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name="fk_pipelines_client_id_clients",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pipelines"),
        sa.UniqueConstraint("client_id", "name", name="uq_pipelines_client_id_name"),
    )

    op.create_index(
        "uq_pipelines_client_platform_external_id",
        "pipelines",
        ["client_id", "platform", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Drop core inventory tables for clients and pipelines."""
    op.drop_index("uq_pipelines_client_platform_external_id", table_name="pipelines")
    op.drop_table("pipelines")
    op.drop_table("clients")
