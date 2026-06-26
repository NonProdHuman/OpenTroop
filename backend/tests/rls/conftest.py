# ruff: noqa: S608
"""Fixtures for the Postgres RLS test tier.

These tests require a live Postgres database with migrations applied and the
``opentroop_app`` / ``opentroop_admin`` roles created by the RLS migration.
Set ``PG_TEST_URL`` to the DSN (e.g. ``postgresql+psycopg://...``) to enable.

All tests in this directory are auto-marked ``pg`` and skipped when the env
var is absent so the default ``uv run pytest`` stays infra-free.
"""

from __future__ import annotations

import os
import subprocess

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

PG_URL = os.environ.get("PG_TEST_URL", "")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-mark every test in this package with ``pg``."""
    pg_mark = pytest.mark.pg
    skip_mark = pytest.mark.skipif(not PG_URL, reason="PG_TEST_URL not set")
    for item in items:
        if "rls" in str(item.fspath):
            item.add_marker(pg_mark)
            item.add_marker(skip_mark)


@pytest.fixture(scope="session")
def pg_engine() -> Engine:
    """Owner-role engine against the migrated test database."""
    if not PG_URL:
        pytest.skip("PG_TEST_URL not set")

    # Apply migrations so roles and policies are present.
    env = {**os.environ, "DATABASE_URL": PG_URL}
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],  # noqa: S607
        cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        env=env,
        check=True,
        capture_output=True,
    )

    engine = create_engine(PG_URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def owner_conn(pg_engine: Engine):  # type: ignore[type-arg]
    """Connection as the database owner (bypasses RLS naturally without FORCE)."""
    with pg_engine.connect() as conn:
        yield conn
        conn.rollback()


@pytest.fixture
def app_conn(pg_engine: Engine):  # type: ignore[type-arg]
    """Connection impersonating ``opentroop_app`` (restricted, RLS enforced)."""
    with pg_engine.connect() as conn:
        conn.execute(text("SET ROLE opentroop_app"))
        yield conn
        conn.rollback()


@pytest.fixture
def admin_conn(pg_engine: Engine):  # type: ignore[type-arg]
    """Connection impersonating ``opentroop_admin`` (BYPASSRLS)."""
    with pg_engine.connect() as conn:
        conn.execute(text("SET ROLE opentroop_admin"))
        yield conn
        conn.rollback()


@pytest.fixture
def two_tenant_seed(owner_conn):  # type: ignore[type-arg]
    """Seed two tenants with one member each; return (tenant_a_id, tenant_b_id)."""
    from uuid6 import uuid7

    tenant_a = uuid7()
    tenant_b = uuid7()
    member_a = uuid7()
    member_b = uuid7()
    deleted_in_a = uuid7()
    now = "NOW()"

    owner_conn.execute(
        text(
            f"""
            INSERT INTO tenants (id, name, slug, created_at, updated_at, is_deleted)
            VALUES
              ('{tenant_a}', 'Troop A', 'troop-a', {now}, {now}, false),
              ('{tenant_b}', 'Troop B', 'troop-b', {now}, {now}, false)
            """
        )
    )
    owner_conn.execute(
        text(
            f"""
            INSERT INTO members
              (id, tenant_id, first_name, last_name, member_type,
               membership_status, swim_classification, created_at, updated_at,
               is_deleted)
            VALUES
              ('{member_a}', '{tenant_a}', 'Alice', 'A', 'adult',
               'active', 'nonswimmer', {now}, {now}, false),
              ('{member_b}', '{tenant_b}', 'Bob',   'B', 'adult',
               'active', 'nonswimmer', {now}, {now}, false),
              ('{deleted_in_a}', '{tenant_a}', 'Del', 'A', 'adult',
               'active', 'nonswimmer', {now}, {now}, true)
            """
        )
    )
    owner_conn.execute(text("SAVEPOINT seed_done"))

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "member_a": member_a,
        "member_b": member_b,
        "deleted_in_a": deleted_in_a,
    }
