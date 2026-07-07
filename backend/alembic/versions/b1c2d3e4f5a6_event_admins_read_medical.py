"""Grant MEMBER_READ_MEDICAL to existing system event-admins roles (GH-122).

The medical-field gating (PR #263) makes `member:read_medical` load-bearing:
without it, event admins lose the allergies/dietary/med-form/emergency-contact
visibility they previously had implicitly. New tenants get the permission from
`DEFAULT_FUNCTIONAL_ROLES`; this backfills tenants provisioned before the
change. Idempotent — only inserts where the grant is missing — and touches only
unmodified system roles (`slug='event-admins' AND is_system`); a troop that
deleted the role keeps its configuration.

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4
Create Date: 2026-07-07
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from uuid6 import uuid7

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite environments (tests, quick local dev) build the schema from the
        # models and seed via provisioning — nothing to backfill.
        return
    rows = bind.execute(
        sa.text(
            """
            SELECT id, tenant_id FROM functional_roles
            WHERE slug = 'event-admins' AND is_system AND NOT is_deleted
              AND id NOT IN (
                SELECT functional_role_id FROM functional_role_permissions
                WHERE permission = 'MEMBER_READ_MEDICAL' AND NOT is_deleted
              )
            """
        )
    ).fetchall()
    for role_id, tenant_id in rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO functional_role_permissions
                  (id, tenant_id, functional_role_id, permission,
                   created_at, updated_at, is_deleted)
                VALUES (:id, :tenant_id, :role_id, 'MEMBER_READ_MEDICAL',
                        now(), now(), false)
                """
            ),
            {"id": str(uuid7()), "tenant_id": str(tenant_id), "role_id": str(role_id)},
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # Best-effort: remove the grant from system event-admins roles. Grants a
    # troop added by hand to a renamed/custom role are indistinguishable and
    # stay — this only unwinds what upgrade() could have written.
    bind.execute(
        sa.text(
            """
            DELETE FROM functional_role_permissions
            WHERE permission = 'MEMBER_READ_MEDICAL'
              AND functional_role_id IN (
                SELECT id FROM functional_roles
                WHERE slug = 'event-admins' AND is_system
              )
            """
        )
    )
