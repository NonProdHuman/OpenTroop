"""Force Row-Level Security on all tenant-scoped tables.

Adds ``FORCE ROW LEVEL SECURITY`` to every ``TrackedBase`` table so the tenant
boundary is enforced even when connecting as the table owner.  Without FORCE,
the policies installed in revision ``09a1b2c3d4e5`` are consulted only when the
connection role is **not** the owner — i.e. they were dormant.

This revision also:

1. **Fixes reproducibility.** The previous revision introspected live models
   (``TrackedBase.__subclasses__()`` at apply time), so its effective table list
   depended on which models happened to be imported.  This revision captures an
   explicit, frozen list of all tables that exist when it is written.  Future
   ``TrackedBase`` migrations must call ``rls.enable_rls_for(op, table_name)``
   in their own ``upgrade()`` — see ``app/core/rls.py``.

2. **Re-runs grants** to ensure ``opentroop_app`` / ``opentroop_admin`` have DML
   access even on databases where the previous revision was applied before a role
   existed.

Revision ID: 1a2b3c4d5e6f
Revises: 09a1b2c3d4e5
Create Date: 2026-06-26 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "09a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Explicit, frozen list of all TrackedBase tables at the time this migration
# was written.  Do NOT replace this with a __subclasses__() walk — that makes
# applied revisions non-reproducible (the list changes as models are added).
# Add new tables in their own migration using app.core.rls.enable_rls_for().
_TRACKED_TABLES: list[str] = [
    "event_audiences",
    "event_organizers",
    "event_participants",
    "event_types",
    "events",
    "group_members",
    "group_role_rules",
    "groups",
    "locations",
    "member_relationships",
    "member_role_assignments",
    "members",
    "role_memberships",
    "role_permissions",
    "roles",
]

_POLICY_EXPR = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name in _TRACKED_TABLES:
        # Re-issue grants in case the prior migration applied before the roles
        # existed or before the table was created.
        op.execute(
            sa.text(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO opentroop_app, opentroop_admin"  # noqa: S608
            )
        )

        # Drop and recreate the policy so this migration is idempotent (safe to
        # re-run on a DB that already has the policy from revision 09a1b2c3d4e5).
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}"))
        op.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation ON {table_name}
                  USING      ({_POLICY_EXPR})
                  WITH CHECK ({_POLICY_EXPR})
                """
            )
        )

        # ENABLE (idempotent) then FORCE.
        op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name in _TRACKED_TABLES:
        op.execute(sa.text(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY"))
