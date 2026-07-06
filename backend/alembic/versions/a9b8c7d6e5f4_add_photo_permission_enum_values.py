"""Add photo:* labels to the Postgres `permission` enum (GH-145 hotfix).

The photo gallery added PHOTO_READ / PHOTO_UPLOAD / PHOTO_MODERATE to the
Python `Permission` enum and seeds them in `seed_default_rbac`, but the native
Postgres enum type (created by the initial schema with the member-name labels)
was never extended. Every `POST /platform/tenants` then failed on the first
`functional_role_permissions` insert with
`invalid input value for enum permission: "PHOTO_READ"`. SQLite tests could
not catch it — SQLite rebuilds its CHECK constraint from the current Python
enum. The Postgres tier now has an enum-drift test so this class of bug fails
CI instead of production (tests/rls/test_enum_drift.py).

Revision ID: a9b8c7d6e5f4
Revises: e8f9a0b1c2d3
Create Date: 2026-07-06
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

_NEW_LABELS = ("PHOTO_READ", "PHOTO_UPLOAD", "PHOTO_MODERATE")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    # ADD VALUE is legal inside a transaction on PG ≥ 12 as long as the new
    # label isn't *used* in the same transaction — this migration only adds.
    for label in _NEW_LABELS:
        op.execute(sa.text(f"ALTER TYPE permission ADD VALUE IF NOT EXISTS '{label}'"))


def downgrade() -> None:
    # Postgres cannot drop enum labels. Leaving them is harmless: nothing
    # references them once the application code is rolled back.
    pass
