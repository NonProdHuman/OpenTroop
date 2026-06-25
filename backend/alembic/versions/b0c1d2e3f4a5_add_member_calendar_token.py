"""add_member_calendar_token

Adds ``members.calendar_token`` — the secret bearer token for a member's personal
iCal subscription feed (``GET /calendar/{token}.ics``). Nullable (set when the
member subscribes) and uniquely indexed.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-06-25 08:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("members", sa.Column("calendar_token", sa.String(length=64), nullable=True))
    op.create_index(
        op.f("ix_members_calendar_token"), "members", ["calendar_token"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_members_calendar_token"), table_name="members")
    op.drop_column("members", "calendar_token")
