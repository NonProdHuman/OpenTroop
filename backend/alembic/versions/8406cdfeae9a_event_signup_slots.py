"""Universal event sign-up slots — event_slots + event_slot_signups (GH-152).

Both tables are ``TrackedBase`` (RLS enforced). Neither is ``Syncable`` in v1 —
events aren't in the sync protocol yet, so slots join whenever events do
(online-first, ADR 0006). ``applies_to`` reuses the existing ``positionscope``
enum type (create_type=False so this migration never re-CREATE TYPEs it).

Revision ID: 8406cdfeae9a
Revises: ccce68b113ed
Create Date: 2026-07-07
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core import rls

# revision identifiers, used by Alembic.
revision: str = "8406cdfeae9a"
down_revision: Union[str, None] = "ccce68b113ed"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

# Reuse the enum type created for the positions table; do not re-create it here.
position_scope = postgresql.ENUM("scout", "adult", "any", name="positionscope", create_type=False)


def upgrade() -> None:
    op.create_table(
        "event_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("applies_to", position_scope, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "event_id", "name", name="uq_event_slots_event_name"),
    )
    op.create_index("ix_event_slots_is_deleted", "event_slots", ["is_deleted"])
    op.create_index("ix_event_slots_tenant_id", "event_slots", ["tenant_id"])
    op.create_index("ix_event_slots_tenant_event", "event_slots", ["tenant_id", "event_id"])
    rls.enable_rls_for(op, "event_slots")

    op.create_table(
        "event_slot_signups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("slot_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("signed_up_by_id", sa.Uuid(), nullable=True),
        sa.Column("signed_up_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["slot_id"], ["event_slots.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["signed_up_by_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "slot_id", "member_id", name="uq_event_slot_signups_slot_member"
        ),
    )
    op.create_index("ix_event_slot_signups_is_deleted", "event_slot_signups", ["is_deleted"])
    op.create_index("ix_event_slot_signups_tenant_id", "event_slot_signups", ["tenant_id"])
    op.create_index(
        "ix_event_slot_signups_tenant_slot", "event_slot_signups", ["tenant_id", "slot_id"]
    )
    rls.enable_rls_for(op, "event_slot_signups")


def downgrade() -> None:
    rls.disable_rls_for(op, "event_slot_signups")
    op.drop_index("ix_event_slot_signups_tenant_slot", table_name="event_slot_signups")
    op.drop_index("ix_event_slot_signups_tenant_id", table_name="event_slot_signups")
    op.drop_index("ix_event_slot_signups_is_deleted", table_name="event_slot_signups")
    op.drop_table("event_slot_signups")

    rls.disable_rls_for(op, "event_slots")
    op.drop_index("ix_event_slots_tenant_event", table_name="event_slots")
    op.drop_index("ix_event_slots_tenant_id", table_name="event_slots")
    op.drop_index("ix_event_slots_is_deleted", table_name="event_slots")
    op.drop_table("event_slots")
