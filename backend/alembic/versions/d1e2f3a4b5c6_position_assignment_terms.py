"""position assignment terms (start/end dates)

Turn ``MemberPositionAssignment`` into a dated term: add nullable ``start_date`` /
``end_date`` and drop the ``(member_id, position_id)`` unique constraint so a member
can hold the same position across multiple (historical) terms. "At most one current
term per (member, position)" is enforced in the API, not the DB.

Existing rows get NULL dates, which the currency rule reads as "current, start
unknown" — preserving prior behavior. RLS is already enabled on this table; adding
columns needs no ``rls.*`` call and adds no new table.

Revision ID: d1e2f3a4b5c6
Revises: c2d3e4f5a6b7
Create Date: 2026-06-29 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "member_position_assignments",
        sa.Column("start_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "member_position_assignments",
        sa.Column("end_date", sa.Date(), nullable=True),
    )
    op.drop_constraint(
        "uq_member_position_assignments",
        "member_position_assignments",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_member_position_assignments",
        "member_position_assignments",
        ["member_id", "position_id"],
    )
    op.drop_column("member_position_assignments", "end_date")
    op.drop_column("member_position_assignments", "start_date")
