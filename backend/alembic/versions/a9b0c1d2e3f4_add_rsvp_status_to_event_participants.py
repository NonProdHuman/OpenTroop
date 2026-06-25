"""add_rsvp_status_to_event_participants

Adds the ``rsvp_status`` enum to ``event_participants`` — a member's explicit
response (no_response / going / declined / maybe), distinct from ``signed_up``
and ``attended``. DECLINED drives gray-out in the app and omission from the
member's personal iCal feed.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-06-25 07:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

rsvp_enum = sa.Enum("no_response", "going", "declined", "maybe", name="rsvpstatus")


def upgrade() -> None:
    rsvp_enum.create(op.get_bind(), checkfirst=True)
    # Backfill existing rows via a server default, then drop it so the column
    # matches the ORM (which has no server_default, only a Python-side default).
    op.add_column(
        "event_participants",
        sa.Column("rsvp_status", rsvp_enum, nullable=False, server_default="no_response"),
    )
    op.alter_column("event_participants", "rsvp_status", server_default=None)
    op.create_index(
        op.f("ix_event_participants_rsvp_status"),
        "event_participants",
        ["rsvp_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_event_participants_rsvp_status"), table_name="event_participants")
    op.drop_column("event_participants", "rsvp_status")
    rsvp_enum.drop(op.get_bind(), checkfirst=True)
