"""Push token registrations for mobile notifications (GH-82).

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-04
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

from app.core import rls

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "push_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=200), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "token", name="uq_push_tokens_tenant_token"),
    )
    op.create_index("ix_push_tokens_tenant_id", "push_tokens", ["tenant_id"])
    op.create_index("ix_push_tokens_tenant_member", "push_tokens", ["tenant_id", "member_id"])
    rls.enable_rls_for(op, "push_tokens")


def downgrade() -> None:
    rls.disable_rls_for(op, "push_tokens")
    op.drop_index("ix_push_tokens_tenant_member", table_name="push_tokens")
    op.drop_index("ix_push_tokens_tenant_id", table_name="push_tokens")
    op.drop_table("push_tokens")
