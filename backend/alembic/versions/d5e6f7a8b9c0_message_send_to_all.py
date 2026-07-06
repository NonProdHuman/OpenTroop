"""Message.send_to_all — entire-troop announcement target (#217).

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-06
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Add NOT NULL with a server default to backfill existing rows, then drop the
    # default so the column matches the model (client-side default only).
    op.add_column(
        "messages",
        sa.Column("send_to_all", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("messages", "send_to_all", server_default=None)


def downgrade() -> None:
    op.drop_column("messages", "send_to_all")
