from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker, with_loader_criteria

from app.core.config import settings
from app.core.tenant_context import (
    bypass_active,
    current_tenant,
    include_deleted_active,
    unscoped,
)
from app.models.base import TrackedBase

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Admin engine: lazy, created on first call to get_admin_db().
# Points at opentroop_admin (BYPASSRLS) for cross-tenant platform operations.
# Never created at import time so tenant-only processes that import database.py
# without DATABASE_URL_ADMIN set don't fail and don't open a bypass connection.
_admin_engine = None
_AdminSessionLocal = None


def _get_admin_engine() -> Engine:
    """Return the admin engine, creating it lazily on first call."""
    global _admin_engine, _AdminSessionLocal
    if _admin_engine is None:
        url = settings.database_url_admin
        if not url:
            raise RuntimeError(
                "DATABASE_URL_ADMIN is not configured. "
                "Set it to the opentroop_admin connection string (BYPASSRLS role). "
                "Self-hosted deployments may point it at the same URL as DATABASE_URL."
            )
        _admin_engine = create_engine(url, pool_size=2, future=True)
        _AdminSessionLocal = sessionmaker(
            bind=_admin_engine, autoflush=False, autocommit=False, future=True
        )
    return _admin_engine


@event.listens_for(Session, "after_begin")
def _stamp_tenant_guc(session: Session, transaction: Any, connection: Any) -> None:
    """Publish the active tenant to Postgres as a transaction-local GUC.

    ``SELECT set_config('app.current_tenant', ...)`` scopes the value to the current transaction,
    so it cannot leak across pooled connections.  The RLS policy on every
    ``TrackedBase`` table reads this GUC and enforces the tenant boundary at the
    database layer (see ``docs/spec/postgres-rls.md``).

    Skipped on non-Postgres dialects (e.g. SQLite in the test suite) and when
    no tenant is set (platform/cross-tenant paths).
    """
    if connection.dialect.name != "postgresql":
        return
    tid = current_tenant()
    if tid is None:
        return
    connection.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tid)},
    )


@event.listens_for(Session, "do_orm_execute")
def _apply_scoping_filters(state: ORMExecuteState) -> None:
    """Scope every ORM SELECT touching a TrackedBase entity to the current tenant and
    exclude soft-deleted rows.

    Applies two ``with_loader_criteria`` predicates to top-level selects *and*
    relationship loads (``include_aliases=True``), so route code carries neither by hand:

    - ``tenant_id == current_tenant()`` — the multi-tenant partition boundary.
    - ``is_deleted == False`` — the soft-delete tombstone filter, unless
      :func:`app.core.tenant_context.include_deleted` is active for the block (e.g.
      reviving a soft-deleted row).

    PlatformBase entities have no ``tenant_id``/automatic scoping and are untouched — their
    queries still filter ``is_deleted`` by hand. Both predicates are skipped inside
    :func:`app.core.tenant_context.unscoped` and when no tenant is set (platform requests,
    fixture setup) — see ``docs/spec/tenant-data-access.md``.
    """
    if bypass_active() or not state.is_select:
        return
    tid = current_tenant()
    if tid is None:
        return
    options = [
        with_loader_criteria(
            TrackedBase,
            lambda cls: cls.tenant_id == tid,
            include_aliases=True,
        )
    ]
    if not include_deleted_active():
        options.append(
            with_loader_criteria(
                TrackedBase,
                lambda cls: cls.is_deleted.is_(False),
                include_aliases=True,
            )
        )
    state.statement = state.statement.options(*options)


@event.listens_for(Session, "before_flush")
def _stamp_tenant(session: Session, flush_context: Any, instances: Any) -> None:
    """Stamp ``tenant_id`` onto new TrackedBase rows that don't already carry one.

    The write-side complement to :func:`_apply_tenant_filter`: removes ``tenant_id=...``
    from create paths and prevents writing a row into the wrong tenant. No-op under
    :func:`app.core.tenant_context.unscoped` or when no tenant is set.
    """
    if bypass_active():
        return
    tid = current_tenant()
    if tid is None:
        return
    for obj in session.new:
        if isinstance(obj, TrackedBase) and obj.tenant_id is None:
            obj.tenant_id = tid


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_admin_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a BYPASSRLS admin session inside unscoped().

    Routes using AdminDbDep operate on the opentroop_admin role (BYPASSRLS) and
    have the app-layer tenant filter disabled for the duration of the request.
    Use only from platform control-plane routes — never from tenant-scoped paths.
    """
    _get_admin_engine()  # raises loudly if DATABASE_URL_ADMIN is not set
    assert _AdminSessionLocal is not None  # noqa: S101 — ensured by _get_admin_engine
    db = _AdminSessionLocal()
    try:
        with unscoped():
            yield db
    finally:
        db.close()
