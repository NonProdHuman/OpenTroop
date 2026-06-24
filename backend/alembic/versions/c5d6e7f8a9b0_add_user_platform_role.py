"""add_user_platform_role

Adds the nullable ``platform_role`` column to ``users`` — the global SaaS
control-plane role (superadmin / support / billing). Null for ordinary users.

Revision ID: c5d6e7f8a9b0
Revises: 20418e37685b
Create Date: 2026-06-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "20418e37685b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False: we create/drop the enum type explicitly below so add_column
# never tries to CREATE TYPE a second time (the classic "type already exists" trap).
_platform_role = postgresql.ENUM(
    "SUPERADMIN", "SUPPORT", "BILLING", name="platformrole", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    _platform_role.create(bind, checkfirst=True)
    op.add_column("users", sa.Column("platform_role", _platform_role, nullable=True))


def downgrade() -> None:
    op.drop_column("users", "platform_role")
    _platform_role.drop(op.get_bind(), checkfirst=True)
