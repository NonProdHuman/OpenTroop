"""Tenant-leading composite indexes for RLS hot paths (GH-115).

RLS injects ``tenant_id = current_setting('app.current_tenant')`` into every
query, so hot-path lookups want composite indexes that lead with ``tenant_id``:

- ``events (tenant_id, scheduled_start)`` — the date-ordered event list
- ``event_participants (tenant_id, event_id)`` / ``(tenant_id, member_id)`` —
  participants per event; per-member RSVP state (iCal feed, member views)
- ``group_members (tenant_id, group_id)`` / ``(tenant_id, member_id)`` — group
  resolution and ``member_group_ids`` (run on most event reads for visibility)
- ``member_position_assignments (tenant_id, member_id)`` — ``resolve_permissions``
  behind every ``require()`` guard

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-02

"""

from typing import Sequence, Union

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_events_tenant_scheduled_start", "events", ["tenant_id", "scheduled_start"]),
    ("ix_event_participants_tenant_event", "event_participants", ["tenant_id", "event_id"]),
    ("ix_event_participants_tenant_member", "event_participants", ["tenant_id", "member_id"]),
    ("ix_group_members_tenant_group", "group_members", ["tenant_id", "group_id"]),
    ("ix_group_members_tenant_member", "group_members", ["tenant_id", "member_id"]),
    (
        "ix_member_position_assignments_tenant_member",
        "member_position_assignments",
        ["tenant_id", "member_id"],
    ),
]


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in _INDEXES:
        op.drop_index(name, table_name=table)
