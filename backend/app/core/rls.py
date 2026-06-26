"""Helpers for Postgres Row-Level Security in Alembic migrations.

Every new ``TrackedBase`` table migration must call ``enable_rls_for(op, table_name)``
to install the ``tenant_isolation`` policy and grant DML to the app/admin roles.
The per-PR Postgres RLS tier in CI will catch any table that ships without coverage.

See ``docs/spec/postgres-rls.md`` and ``docs/spec/rls-enforcement-rollout.md``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic.operations import Operations

_POLICY_EXPR = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def enable_rls_for(op: Operations, table_name: str) -> None:
    """Enable and force RLS on *table_name* and install the tenant isolation policy.

    Issues:
      - ``ENABLE ROW LEVEL SECURITY`` — activates the policy engine.
      - ``FORCE ROW LEVEL SECURITY`` — applies even to the table owner so the
        boundary doesn't depend on which role connects.
      - ``CREATE POLICY tenant_isolation`` — USING + WITH CHECK on tenant_id;
        fail-closed (empty GUC → zero rows, never all rows).
      - ``GRANT SELECT, INSERT, UPDATE, DELETE`` to ``opentroop_app`` and
        ``opentroop_admin`` so both runtime roles can reach the table.

    No-op on non-Postgres dialects (e.g. SQLite in the test suite).
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation ON {table_name}
              USING      ({_POLICY_EXPR})
              WITH CHECK ({_POLICY_EXPR})
            """
        )
    )
    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO opentroop_app, opentroop_admin"  # noqa: S608
        )
    )


def disable_rls_for(op: Operations, table_name: str) -> None:
    """Reverse of ``enable_rls_for`` — drop the policy and disable RLS."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}"))
    op.execute(sa.text(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table_name} FROM opentroop_app, opentroop_admin"  # noqa: S608
        )
    )
