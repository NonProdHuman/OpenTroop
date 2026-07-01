# ruff: noqa: S608
"""RLS regression test for the unauthenticated iCal calendar feed.

``GET /calendar/{token}.ics`` resolves a Member by an unguessable per-member token and
carries no JWT. The route must therefore resolve and scope the tenant itself
(``app.core.tenant.scope_calendar_feed_tenant``); otherwise the ``app.current_tenant``
GUC is never set and, under ``FORCE ROW LEVEL SECURITY``, the token lookup matches zero
rows so every feed 404s. This test pins that contract at the database layer: the query
the feed runs is invisible without the tenant GUC and visible once it is set.

Skipped unless ``PG_TEST_URL`` is set (see ``tests/rls/conftest.py``).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine
from uuid6 import uuid7

_LOOKUP = text("SELECT id FROM members WHERE calendar_token = :t AND is_deleted = false")


def test_feed_token_lookup_requires_tenant_guc(pg_engine: Engine, app_conn) -> None:  # type: ignore[type-arg]
    """The feed's token lookup is RLS-blocked with no GUC and permitted once scoped."""
    tenant_id = uuid7()
    member_id = uuid7()
    token = f"feed-{uuid7().hex}"

    # Seed a member carrying a calendar token, committed via the owner role so a
    # separate connection (app_conn) can see it (mirrors the two_tenant_seed fixture).
    with pg_engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, slug, created_at, updated_at, is_deleted)
                VALUES (:id, 'Feed Troop', :slug, NOW(), NOW(), false)
                """
            ),
            {"id": str(tenant_id), "slug": f"feed-{tenant_id.hex[:8]}"},
        )
        conn.execute(
            text(
                """
                INSERT INTO members
                  (id, tenant_id, first_name, last_name, member_type,
                   membership_status, swim_classification,
                   email_opt_out, email_bounced, sms_opt_in, calendar_token,
                   created_at, updated_at, is_deleted)
                VALUES
                  (:id, :tid, 'Cal', 'Feed', 'ADULT',
                   'ACTIVE', 'NONSWIMMER', false, false, false, :token,
                   NOW(), NOW(), false)
                """
            ),
            {"id": str(member_id), "tid": str(tenant_id), "token": token},
        )
        conn.commit()

    try:
        # BUG path — what the un-scoped feed did: no tenant GUC ⇒ RLS hides the row ⇒ 404.
        assert app_conn.execute(_LOOKUP, {"t": token}).first() is None

        # FIX path — the route scopes the tenant, so the GUC is set ⇒ the row is visible.
        app_conn.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        assert app_conn.execute(_LOOKUP, {"t": token}).first() is not None
    finally:
        with pg_engine.connect() as conn:
            conn.execute(text("DELETE FROM members WHERE id = :id"), {"id": str(member_id)})
            conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": str(tenant_id)})
            conn.commit()
