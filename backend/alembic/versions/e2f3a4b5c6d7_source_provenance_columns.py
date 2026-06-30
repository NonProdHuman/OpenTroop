"""external-source provenance columns (TWH sync groundwork)

Add ``source_system`` / ``source_id`` / ``source_updated_at`` to the tenant
entities that a bulk import creates, so a later incremental sync can match an
external record to its OpenTroop row and detect upstream changes. All columns are
nullable (NULL for natively-created rows); ``source_id`` is indexed per table for
match-and-upsert lookups. No new tables → no RLS changes. See docs/spec/twh-sync.md.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-29 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Entities the TWH importer creates that carry a stable upstream id + Last_Update_UTC.
SOURCE_TABLES: tuple[str, ...] = (
    "groups",
    "members",
    "member_relationships",
    "locations",
    "event_types",
    "events",
    "event_participants",
    "positions",
    "member_position_assignments",
)


def upgrade() -> None:
    for table in SOURCE_TABLES:
        op.add_column(table, sa.Column("source_system", sa.String(length=32), nullable=True))
        op.add_column(table, sa.Column("source_id", sa.String(length=64), nullable=True))
        op.add_column(
            table,
            sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(op.f(f"ix_{table}_source_id"), table, ["source_id"])


def downgrade() -> None:
    for table in reversed(SOURCE_TABLES):
        op.drop_index(op.f(f"ix_{table}_source_id"), table_name=table)
        op.drop_column(table, "source_updated_at")
        op.drop_column(table, "source_id")
        op.drop_column(table, "source_system")
