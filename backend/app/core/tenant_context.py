"""Request-scoped current-tenant context for automatic tenant scoping.

This is the single source of truth for "which tenant is this request acting in".
It is read by the ``do_orm_execute`` read filter and the ``before_flush`` write
stamp registered in :mod:`app.core.database`, so route code never has to carry the
``tenant_id`` predicate by hand. Cross-tenant platform work opts out explicitly via
:func:`unscoped`.

See ``docs/spec/tenant-data-access.md``. Once Postgres RLS lands
(``docs/spec/postgres-rls.md``), the same dependency that sets this ContextVar will
also issue ``SELECT set_config('app.current_tenant', ...)`` so the app layer and the DB layer share
one value.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token

_current_tenant: ContextVar[uuid.UUID | None] = ContextVar("current_tenant", default=None)
_bypass: ContextVar[bool] = ContextVar("tenant_bypass", default=False)
_include_deleted: ContextVar[bool] = ContextVar("include_deleted", default=False)


def set_current_tenant(tenant_id: uuid.UUID) -> Token[uuid.UUID | None]:
    """Set the active tenant for the current context, returning a reset token."""
    return _current_tenant.set(tenant_id)


def reset_current_tenant(token: Token[uuid.UUID | None]) -> None:
    """Restore the active tenant to its prior value using *token*."""
    _current_tenant.reset(token)


def current_tenant() -> uuid.UUID | None:
    """Return the active tenant, or ``None`` if none is set (or scoping is bypassed)."""
    return _current_tenant.get()


def bypass_active() -> bool:
    """Whether automatic tenant scoping is currently bypassed (see :func:`unscoped`)."""
    return _bypass.get()


def include_deleted_active() -> bool:
    """Whether the automatic soft-delete filter is currently disabled (see :func:`include_deleted`)."""
    return _include_deleted.get()


@contextmanager
def tenant_scope(tenant_id: uuid.UUID) -> Generator[None, None, None]:
    """Run a block with the active tenant set to *tenant_id*.

    Convenience wrapper around :func:`set_current_tenant` / :func:`reset_current_tenant`
    for non-request code paths (scripts, tests, background jobs).
    """
    token = set_current_tenant(tenant_id)
    try:
        yield
    finally:
        reset_current_tenant(token)


@contextmanager
def unscoped() -> Generator[None, None, None]:
    """Disable automatic tenant filtering for cross-tenant platform work.

    The only sanctioned way to read across tenants. Greppable, auditable, and (once
    RLS lands) paired with the BYPASSRLS DB role so it still works when the database
    enforces the boundary. Used by the platform control plane and the
    ``GET /auth/memberships`` lookup — which must still constrain ``user_id == me``
    inside the bypass.
    """
    token = _bypass.set(True)
    try:
        yield
    finally:
        try:
            _bypass.reset(token)
        except ValueError:
            # Starlette runs a sync yield-dependency's enter and exit (on the error
            # path) in different contexts via the threadpool, which invalidates the
            # token here and would otherwise mask the real exception as a 500. The
            # ContextVar copy in this context is independent, so clear the flag directly.
            _bypass.set(False)


@contextmanager
def include_deleted() -> Generator[None, None, None]:
    """Disable the automatic soft-delete filter for a block, keeping tenant scoping.

    The sibling of :func:`unscoped` for the ``is_deleted`` dimension: tenant filtering
    stays on, but ``do_orm_execute`` stops appending ``is_deleted == False`` so a query
    can see (and revive) soft-deleted rows. Greppable and narrow — used only where a
    tombstone must be read back, e.g. reviving a soft-deleted ``GroupRule`` on upsert.
    """
    token = _include_deleted.set(True)
    try:
        yield
    finally:
        _include_deleted.reset(token)
