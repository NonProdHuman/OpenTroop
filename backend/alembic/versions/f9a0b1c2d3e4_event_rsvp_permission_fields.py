"""event RSVP + parental permission fields

Adds the columns backing the RSVP / parent-permission workflow
(docs/spec/event-rsvp-permission.md):

- ``event_participants.drives_to`` / ``drives_from`` — informational carpool legs.
- ``event_participants.permission_message_snapshot`` — the exact tenant permission
  language captured when a parent signs (legal record / future PDF source).
- ``event_types.allow_guests`` — exposes a guest-count field on the RSVP form.
- ``tenants.permission_message`` — the troop's customizable permission language.

No new tables → no RLS changes. New boolean columns are NOT NULL with a server
default of false so existing rows backfill cleanly.

Revision ID: f9a0b1c2d3e4
Revises: e2f3a4b5c6d7
Create Date: 2026-06-29 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event_participants",
        sa.Column("drives_to", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "event_participants",
        sa.Column("drives_from", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "event_participants",
        sa.Column("permission_message_snapshot", sa.Text(), nullable=True),
    )
    op.add_column(
        "event_types",
        sa.Column("allow_guests", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("tenants", sa.Column("permission_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "permission_message")
    op.drop_column("event_types", "allow_guests")
    op.drop_column("event_participants", "permission_message_snapshot")
    op.drop_column("event_participants", "drives_from")
    op.drop_column("event_participants", "drives_to")
