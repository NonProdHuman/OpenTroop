"""hard_delete_flows

GH-222: member hard-delete (anonymize + reaper) and tenant delete.

- ``members.purged_at`` — set when an admin purges a member's PII in place;
  the reaper physically deletes the row after the tombstone retention window.
- ``tenants.last_export_at`` — when a platform admin last exported the tenant;
  tenant deletion requires an export taken after suspension.
- ``tenants.purged_through_seq`` — per-tenant reap watermark (sync-protocol
  Decision 5); pull cursors behind it are told to full-refetch (410).
- ``messages.sent_by_id`` becomes nullable — the reaper nulls it when the
  sender is hard-deleted.

Revision ID: b7c8d9e0f1a2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("members", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "tenants", sa.Column("last_export_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("tenants", sa.Column("purged_through_seq", sa.BigInteger(), nullable=True))
    op.alter_column("messages", "sent_by_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.alter_column("messages", "sent_by_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("tenants", "purged_through_seq")
    op.drop_column("tenants", "last_export_at")
    op.drop_column("members", "purged_at")
