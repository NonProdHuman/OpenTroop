"""harden_account_linking

GH-110: adds ``users.email_verified`` (email-based account matching only runs on
provider-verified emails) and ``members.invite_token_jti`` (invite/claim tokens
become single-use and revocable — a token is honored only while its jti matches
the stored value).

Revision ID: a1b2c3d4e5f6
Revises: 0f594c122322
Create Date: 2026-07-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "0f594c122322"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing User.email values predate verification tracking and cannot be
    # trusted retroactively, so they start as unverified (fail closed); the flag
    # flips on each user's next sign-in with a verified email claim.
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Outstanding tokens minted before this migration carry no jti and are
    # rejected; admins re-invite to issue new single-use tokens.
    op.add_column("members", sa.Column("invite_token_jti", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("members", "invite_token_jti")
    op.drop_column("users", "email_verified")
