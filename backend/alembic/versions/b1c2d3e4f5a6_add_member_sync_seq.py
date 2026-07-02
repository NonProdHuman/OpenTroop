"""Add the sync_seq pull cursor to members (docs/spec/sync-protocol.md, GH-120).

Creates the global ``sync_seq`` sequence, adds ``members.sync_seq`` backfilled in
deterministic ``(updated_at, id)`` order, and indexes ``(tenant_id, sync_seq)`` for
keyset paging. The app/admin roles get USAGE on the sequence — the ORM draws values
via ``nextval`` at insert/update time.

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-07-02
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS sync_seq")
    op.execute("GRANT USAGE, SELECT ON SEQUENCE sync_seq TO opentroop_app, opentroop_admin")

    op.add_column("members", sa.Column("sync_seq", sa.BigInteger(), nullable=True))
    # Deterministic backfill: existing rows enter the stream in updated_at order so a
    # client's very first incremental pull sees a sensible history, then advance the
    # sequence past the backfilled range.
    op.execute(
        """
        UPDATE members m
        SET sync_seq = numbered.seq
        FROM (
            SELECT id, row_number() OVER (ORDER BY updated_at, id) AS seq
            FROM members
        ) numbered
        WHERE m.id = numbered.id
        """
    )
    op.execute("SELECT setval('sync_seq', (SELECT COALESCE(MAX(sync_seq), 1) FROM members))")
    # Server default so raw-SQL writers (ops scripts, the RLS test tier) never trip the
    # NOT NULL; the ORM draws its own nextval and passes the value explicitly.
    op.alter_column(
        "members",
        "sync_seq",
        nullable=False,
        server_default=sa.text("nextval('sync_seq')"),
    )
    op.create_index("ix_members_tenant_sync_seq", "members", ["tenant_id", "sync_seq"])


def downgrade() -> None:
    op.drop_index("ix_members_tenant_sync_seq", table_name="members")
    op.drop_column("members", "sync_seq")
    op.execute("DROP SEQUENCE IF EXISTS sync_seq")
