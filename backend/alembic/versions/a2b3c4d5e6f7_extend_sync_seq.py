"""Extend the sync_seq pull cursor to the Mobile v1 entities (GH-153, GH-93).

Adds ``sync_seq`` to event_types, locations, events, event_participants, and
member_relationships — the tables the offline client mirrors — following the
members adoption pattern (b1c2d3e4f5a6): deterministic ``(updated_at, id)``
backfill drawn above the sequence's current position, a ``nextval`` server
default for raw-SQL writers, and a ``(tenant_id, sync_seq)`` keyset index.

Revision ID: a2b3c4d5e6f7
Revises: f1b2c3d4e5f6
Create Date: 2026-07-04
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f1b2c3d4e5f6"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

TABLES = [
    "event_types",
    "locations",
    "events",
    "event_participants",
    "member_relationships",
]


def upgrade() -> None:
    # The global sequence exists since the members adoption (b1c2d3e4f5a6); this
    # is belt-and-suspenders for databases created straight from a later head.
    op.execute("CREATE SEQUENCE IF NOT EXISTS sync_seq")
    op.execute("GRANT USAGE, SELECT ON SEQUENCE sync_seq TO opentroop_app, opentroop_admin")

    for table in TABLES:
        op.add_column(table, sa.Column("sync_seq", sa.BigInteger(), nullable=True))
        # Deterministic backfill in updated_at order, placed above everything the
        # sequence has handed out so far (and above earlier tables in this loop).
        op.execute(
            f"""
            UPDATE {table} t
            SET sync_seq = numbered.seq + (SELECT last_value FROM sync_seq)
            FROM (
                SELECT id, row_number() OVER (ORDER BY updated_at, id) AS seq
                FROM {table}
            ) numbered
            WHERE t.id = numbered.id
            """
        )
        op.execute(
            f"""
            SELECT setval(
                'sync_seq',
                GREATEST(
                    (SELECT last_value FROM sync_seq),
                    (SELECT COALESCE(MAX(sync_seq), 1) FROM {table})
                )
            )
            """
        )
        op.alter_column(
            table,
            "sync_seq",
            nullable=False,
            server_default=sa.text("nextval('sync_seq')"),
        )
        op.create_index(f"ix_{table}_tenant_sync_seq", table, ["tenant_id", "sync_seq"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_tenant_sync_seq", table_name=table)
        op.drop_column(table, "sync_seq")
    # The sequence stays — members still uses it.
