"""Event photo gallery — event_photos table + tenant storage meter (GH-145).

Revision ID: e8f9a0b1c2d3
Revises: c8d9e0f1a2b3
Create Date: 2026-07-06
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

from app.core import rls

# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

photo_status = sa.Enum("pending", "ready", "failed", "purged", name="photostatus")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS sync_seq")

    op.create_table(
        "event_photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column(
            "sync_seq",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("nextval('sync_seq')"),
        ),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_member_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_key", sa.String(length=512), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("thumbhash", sa.String(length=64), nullable=True),
        sa.Column("status", photo_status, nullable=False),
        sa.Column("reserved_bytes", sa.BigInteger(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_photos_is_deleted", "event_photos", ["is_deleted"])
    op.create_index("ix_event_photos_tenant_id", "event_photos", ["tenant_id"])
    op.create_index("ix_event_photos_tenant_event", "event_photos", ["tenant_id", "event_id"])
    op.create_index("ix_event_photos_tenant_sync_seq", "event_photos", ["tenant_id", "sync_seq"])
    rls.enable_rls_for(op, "event_photos")

    # Tenant storage meter (the platform's first) — used bytes counted at upload
    # confirm, quota override per tenant (null ⇒ settings default).
    op.add_column(
        "tenants",
        sa.Column("used_storage_bytes", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column("tenants", sa.Column("storage_quota_bytes", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "storage_quota_bytes")
    op.drop_column("tenants", "used_storage_bytes")

    rls.disable_rls_for(op, "event_photos")
    op.drop_index("ix_event_photos_tenant_sync_seq", table_name="event_photos")
    op.drop_index("ix_event_photos_tenant_event", table_name="event_photos")
    op.drop_index("ix_event_photos_tenant_id", table_name="event_photos")
    op.drop_index("ix_event_photos_is_deleted", table_name="event_photos")
    op.drop_table("event_photos")
    bind = op.get_bind()
    photo_status.drop(bind, checkfirst=True)
