"""Store the iCal feed token as a SHA-256 hash, not plaintext (GH-114).

Replaces ``members.calendar_token`` with ``members.calendar_token_hash``. Existing
tokens are backfilled as ``sha256(token)`` so every feed URL already pasted into a
member's calendar app keeps working — the raw token in the URL hashes to the stored
digest on lookup.

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-07-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("members", sa.Column("calendar_token_hash", sa.String(length=64), nullable=True))
    # Postgres 11+ ships sha256() natively; encode(..., 'hex') matches Python's
    # hashlib.sha256(token.encode()).hexdigest() used by the app on lookup.
    op.execute(
        """
        UPDATE members
        SET calendar_token_hash = encode(sha256(calendar_token::bytea), 'hex')
        WHERE calendar_token IS NOT NULL
        """
    )
    op.create_index(
        op.f("ix_members_calendar_token_hash"), "members", ["calendar_token_hash"], unique=True
    )
    op.drop_index(op.f("ix_members_calendar_token"), table_name="members")
    op.drop_column("members", "calendar_token")


def downgrade() -> None:
    # The raw tokens are unrecoverable from hashes; restore the column empty —
    # members re-mint via POST /calendar/subscription.
    op.add_column("members", sa.Column("calendar_token", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_members_calendar_token"), "members", ["calendar_token"], unique=True)
    op.drop_index(op.f("ix_members_calendar_token_hash"), table_name="members")
    op.drop_column("members", "calendar_token_hash")
