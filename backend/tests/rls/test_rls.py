"""Postgres Row-Level Security boundary tests.

Every test here connects as ``opentroop_app`` (restricted, RLS enforced) and
verifies that the database itself enforces tenant isolation — independent of
any app-layer filtering.  Skipped unless ``PG_TEST_URL`` is set.

See ``docs/spec/postgres-rls.md`` for the full design rationale.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

import app.models  # noqa: F401 — register all tables on Base.metadata
from app.models.base import TrackedBase

# ── Policy completeness ───────────────────────────────────────────────────────


def test_all_tracked_tables_have_rls(owner_conn) -> None:  # type: ignore[type-arg]
    """Every TrackedBase table must have RLS enabled.

    This test auto-detects the table list from the model registry, so a new
    tenant table added without a policy will fail here automatically.
    """

    def _tracked_names(cls: type) -> list[str]:
        names: list[str] = []
        for sub in cls.__subclasses__():
            tbl = getattr(sub, "__table__", None)
            if tbl is not None:
                names.append(tbl.name)
            names.extend(_tracked_names(sub))
        return names

    expected = set(_tracked_names(TrackedBase))
    assert expected, "No TrackedBase subclasses found — model import error?"

    rows = owner_conn.execute(
        text(
            """
            SELECT relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relrowsecurity = true
            """
        )
    ).fetchall()
    rls_tables = {r[0] for r in rows}

    missing = expected - rls_tables
    assert not missing, f"TrackedBase tables without RLS enabled: {sorted(missing)}"


def test_all_tracked_tables_have_isolation_policy(owner_conn) -> None:  # type: ignore[type-arg]
    """Every TrackedBase table must have the ``tenant_isolation`` policy."""

    def _tracked_names(cls: type) -> list[str]:
        names: list[str] = []
        for sub in cls.__subclasses__():
            tbl = getattr(sub, "__table__", None)
            if tbl is not None:
                names.append(tbl.name)
            names.extend(_tracked_names(sub))
        return names

    expected = set(_tracked_names(TrackedBase))

    rows = owner_conn.execute(
        text(
            """
            SELECT tablename
            FROM pg_policies
            WHERE schemaname = 'public'
              AND policyname = 'tenant_isolation'
            """
        )
    ).fetchall()
    policy_tables = {r[0] for r in rows}

    missing = expected - policy_tables
    assert not missing, f"TrackedBase tables without tenant_isolation policy: {sorted(missing)}"


# ── Tenant isolation ──────────────────────────────────────────────────────────


def test_app_role_sees_only_own_tenant(app_conn, two_tenant_seed) -> None:  # type: ignore[type-arg]
    """With the GUC set to tenant A, only tenant A's members are visible."""
    tenant_a = two_tenant_seed["tenant_a"]
    member_a = two_tenant_seed["member_a"]
    member_b = two_tenant_seed["member_b"]

    app_conn.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": str(tenant_a)})
    rows = app_conn.execute(text("SELECT id FROM members")).fetchall()
    ids = {r[0] for r in rows}

    assert str(member_a) in ids or member_a in ids, "Tenant A member should be visible"
    assert str(member_b) not in ids and member_b not in ids, "Tenant B member must not be visible"


def test_no_guc_returns_zero_rows(app_conn, two_tenant_seed) -> None:  # type: ignore[type-arg]
    """Without a GUC, the policy yields zero rows (fail-closed)."""
    rows = app_conn.execute(text("SELECT id FROM members")).fetchall()
    assert rows == [], f"Expected 0 rows without GUC, got {len(rows)}"


def test_empty_guc_returns_zero_rows(app_conn, two_tenant_seed) -> None:  # type: ignore[type-arg]
    """An empty GUC string also yields zero rows."""
    app_conn.execute(text("SET LOCAL app.current_tenant = ''"))
    rows = app_conn.execute(text("SELECT id FROM members")).fetchall()
    assert rows == [], f"Expected 0 rows with empty GUC, got {len(rows)}"


def test_tombstones_visible_within_tenant(app_conn, two_tenant_seed) -> None:  # type: ignore[type-arg]
    """Soft-deleted rows (is_deleted=true) within the tenant remain visible.

    The sync pull must be able to read tombstones to converge deletions on device;
    the RLS policy must NOT filter on is_deleted.
    """
    tenant_a = two_tenant_seed["tenant_a"]
    deleted_in_a = two_tenant_seed["deleted_in_a"]

    app_conn.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": str(tenant_a)})
    rows = app_conn.execute(text("SELECT id FROM members WHERE is_deleted = true")).fetchall()
    ids = {str(r[0]) for r in rows}
    assert str(deleted_in_a) in ids, "Tombstone must be visible to sync pull"


def test_insert_wrong_tenant_rejected(app_conn, two_tenant_seed) -> None:  # type: ignore[type-arg]
    """INSERT with a tenant_id that doesn't match the GUC is rejected by WITH CHECK."""
    from uuid6 import uuid7

    tenant_a = two_tenant_seed["tenant_a"]
    tenant_b = two_tenant_seed["tenant_b"]

    # Connect as tenant A but try to write into tenant B
    app_conn.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": str(tenant_a)})
    new_id = uuid7()
    with pytest.raises(Exception, match="row-level security"):
        app_conn.execute(
            text(
                """
                INSERT INTO members
                  (id, tenant_id, first_name, last_name, member_type,
                   membership_status, swim_classification, created_at,
                   updated_at, is_deleted)
                VALUES
                  (:id, :tid, 'Eve', 'X', 'ADULT',
                   'ACTIVE', 'NONSWIMMER', NOW(), NOW(), false)
                """
            ),
            {"id": str(new_id), "tid": str(tenant_b)},
        )


# ── Admin bypass ──────────────────────────────────────────────────────────────


def test_admin_role_sees_all_tenants(admin_conn, two_tenant_seed) -> None:  # type: ignore[type-arg]
    """opentroop_admin (BYPASSRLS) can read rows from all tenants without a GUC."""
    member_a = two_tenant_seed["member_a"]
    member_b = two_tenant_seed["member_b"]

    rows = admin_conn.execute(text("SELECT id FROM members")).fetchall()
    ids = {str(r[0]) for r in rows}

    assert str(member_a) in ids, "Admin should see tenant A member"
    assert str(member_b) in ids, "Admin should see tenant B member"
