"""Add Postgres Row-Level Security roles and tenant-isolation policies.

Creates two DB roles:
- ``opentroop_app``:  restricted, no LOGIN, RLS enforced — the intended
  ``DATABASE_URL`` role for normal tenant request traffic.
- ``opentroop_admin``: BYPASSRLS, no LOGIN — for the platform control plane,
  Alembic migrations, and cross-tenant reads. Use via ``SET ROLE``.

Enables RLS (without FORCE yet) on every ``TrackedBase`` table and installs a
``tenant_isolation`` policy that uses the ``app.current_tenant`` GUC set by
``app.core.database.after_begin``.

**Fail-closed**: a missing or empty ``app.current_tenant`` GUC yields **zero
rows** rather than all rows, so a connection that forgets to stamp the GUC
leaks nothing.

**No FORCE ROW LEVEL SECURITY** in this revision.  The table owner (used by
the current ``DATABASE_URL``) bypasses RLS naturally — platform routes work
unchanged.  FORCE is the next step, after:
  1. The control plane wraps all TrackedBase access in ``unscoped()`` / a
     bypass GUC, and
  2. ``DATABASE_URL`` is pointed at ``opentroop_app``.

Revision ID: 09a1b2c3d4e5
Revises: f8a9b0c1d2e3
Create Date: 2026-06-26 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.base import TrackedBase

revision: str = "09a1b2c3d4e5"
down_revision: Union[str, None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tracked_table_names(bind: sa.engine.Connection) -> list[str]:
    """Return TrackedBase table names that actually exist in the DB at apply time.

    Walks ``TrackedBase.__subclasses__()`` for the model set, then intersects with
    the live schema. The intersection makes this revision **reproducible** despite
    the dynamic walk: later model changes (e.g. renamed tables created by a future
    migration) don't make this historical revision touch tables that don't yet
    exist. The original frozen behaviour is preserved for the model set present
    when this revision runs.
    """

    def _recurse(cls: type) -> list[str]:
        names: list[str] = []
        for sub in cls.__subclasses__():
            table = getattr(sub, "__table__", None)
            if table is not None:
                names.append(table.name)
            names.extend(_recurse(sub))
        return names

    existing = set(sa.inspect(bind).get_table_names())
    return [name for name in _recurse(TrackedBase) if name in existing]


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect != "postgresql":
        return

    # ── Roles ────────────────────────────────────────────────────────────────
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'opentroop_app') THEN
                CREATE ROLE opentroop_app;
              END IF;
            END
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'opentroop_admin') THEN
                CREATE ROLE opentroop_admin BYPASSRLS;
              END IF;
            END
            $$;
            """
        )
    )

    # ── Grants ───────────────────────────────────────────────────────────────
    op.execute(sa.text("GRANT USAGE ON SCHEMA public TO opentroop_app"))
    op.execute(sa.text("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO opentroop_app"))
    op.execute(sa.text("GRANT USAGE ON SCHEMA public TO opentroop_admin"))
    op.execute(sa.text("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO opentroop_admin"))

    for table_name in _tracked_table_names(bind):
        op.execute(
            sa.text(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO opentroop_app"  # noqa: S608
            )
        )
        op.execute(
            sa.text(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO opentroop_admin"  # noqa: S608
            )
        )

    # ── Row-Level Security ───────────────────────────────────────────────────
    # Policy expression: NULLIF(..., '') casts the GUC to uuid safely —
    # a missing or empty GUC returns NULL, and tenant_id = NULL is NULL (falsy),
    # so the query returns zero rows (fail-closed).
    policy_expr = (
        "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"
    )

    for table_name in _tracked_table_names(bind):
        op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation ON {table_name}
                  USING      ({policy_expr})
                  WITH CHECK ({policy_expr})
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name in _tracked_table_names(bind):
        op.execute(
            sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")
        )
        op.execute(sa.text(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"))

    op.execute(sa.text("REVOKE USAGE ON SCHEMA public FROM opentroop_app"))
    op.execute(sa.text("REVOKE USAGE ON ALL SEQUENCES IN SCHEMA public FROM opentroop_app"))
    op.execute(sa.text("REVOKE USAGE ON SCHEMA public FROM opentroop_admin"))
    op.execute(sa.text("REVOKE USAGE ON ALL SEQUENCES IN SCHEMA public FROM opentroop_admin"))
    for table_name in _tracked_table_names(bind):
        op.execute(
            sa.text(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table_name} FROM opentroop_app")
        )
        op.execute(
            sa.text(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table_name} FROM opentroop_admin")
        )

    op.execute(sa.text("DROP ROLE IF EXISTS opentroop_app"))
    op.execute(sa.text("DROP ROLE IF EXISTS opentroop_admin"))
