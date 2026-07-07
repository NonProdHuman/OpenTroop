"""Async TWH import jobs (#240).

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-07-06
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

from app.core import rls

# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

import_job_status = sa.Enum(
    "queued", "running", "succeeded", "failed", name="importjobstatus"
)


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("status", import_job_status, nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=True),
        sa.Column("progress", sa.JSON(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requested_by_id", sa.Uuid(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("source_timezone", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("payload_bytes", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["requested_by_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_jobs_is_deleted", "import_jobs", ["is_deleted"])
    op.create_index("ix_import_jobs_tenant_id", "import_jobs", ["tenant_id"])
    op.create_index("ix_import_jobs_tenant_status", "import_jobs", ["tenant_id", "status"])
    # At most one active (queued/running) import per tenant — the idempotency guard.
    op.create_index(
        "uix_import_jobs_one_active_per_tenant",
        "import_jobs",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    rls.enable_rls_for(op, "import_jobs")


def downgrade() -> None:
    rls.disable_rls_for(op, "import_jobs")
    op.drop_index("uix_import_jobs_one_active_per_tenant", table_name="import_jobs")
    op.drop_index("ix_import_jobs_tenant_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_tenant_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_is_deleted", table_name="import_jobs")
    op.drop_table("import_jobs")
    bind = op.get_bind()
    import_job_status.drop(bind, checkfirst=True)
