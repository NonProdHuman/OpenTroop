"""add_event_audiences

Adds the ``event_audiences`` table — links an event to the Groups allowed to see
it. No audience rows = troop-wide; any rows = visible only to those groups (plus
event managers). Backs patrol-only events and the calendar/iCal visibility filter.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-06-25 06:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_audiences",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "group_id", name="uq_event_audiences_event_group"),
    )
    op.create_index(
        op.f("ix_event_audiences_event_id"), "event_audiences", ["event_id"], unique=False
    )
    op.create_index(
        op.f("ix_event_audiences_group_id"), "event_audiences", ["group_id"], unique=False
    )
    op.create_index(
        op.f("ix_event_audiences_is_deleted"), "event_audiences", ["is_deleted"], unique=False
    )
    op.create_index(
        op.f("ix_event_audiences_tenant_id"), "event_audiences", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("event_audiences")
