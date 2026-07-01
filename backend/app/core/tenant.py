from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.tenant_context import reset_current_tenant, set_current_tenant
from app.models.tenant import Tenant

# Subdomains that name platform surfaces, not tenants. They must never resolve to a
# tenant slug — e.g. ``admin.opentroop.app`` is the platform console, ``www`` the
# landing alias. Mirrors the ``admin.`` special-casing in the web middleware (proxy.ts).
RESERVED_SUBDOMAINS: frozenset[str] = frozenset({"admin", "www"})


def _extract_subdomain(host: str, app_domain: str) -> str | None:
    """Return the single subdomain prefix if *host* is a direct subdomain of *app_domain*.

    ``troop123.opentroop.app`` → ``"troop123"``
    Nested subdomains (``a.troop123.opentroop.app``) are rejected to prevent
    tenant spoofing via crafted Host headers. Reserved platform subdomains
    (``admin``, ``www``) return ``None`` so they're never treated as tenants.
    """
    host = host.lower().split(":")[0]  # strip optional port
    suffix = f".{app_domain.lower()}"
    if not host.endswith(suffix):
        return None
    prefix = host[: -len(suffix)]
    if not prefix or "." in prefix:
        return None
    if prefix in RESERVED_SUBDOMAINS:
        return None
    return prefix


def _resolve_request_host(request: Request) -> str:
    """Return the host to use for subdomain tenant resolution.

    ``X-Forwarded-Host`` is client-supplied; honoring it unconditionally would let an
    attacker pick the tenant on any deployment whose proxy doesn't strip the header.
    It is only trusted when the deployment declares a trusted proxy in front
    (``TRUST_FORWARDED_HOST=true``); otherwise ``Host`` is used.
    """
    if settings.trust_forwarded_host:
        forwarded_host = request.headers.get("x-forwarded-host")
        if forwarded_host:
            return forwarded_host
    return request.headers.get("host", "")


def _reject_if_suspended(tenant: Tenant) -> None:
    """Block tenant-scoped access to a suspended tenant (a platform admin can lift it)."""
    if tenant.suspended_at is not None:
        raise HTTPException(status_code=403, detail="Tenant is suspended")


async def get_tenant_id(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """Resolve the tenant for a request.

    Resolution order:
    1. Subdomain — ``troop123.opentroop.app`` → slug lookup in DB.
    2. ``X-Tenant-ID`` header — raw UUID → DB validation.
    """
    slug = _extract_subdomain(_resolve_request_host(request), settings.app_domain)

    if slug:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == slug, Tenant.is_deleted.is_(False)))
        if tenant is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        _reject_if_suspended(tenant)
        return tenant.id

    if x_tenant_id is not None:
        try:
            tid = uuid.UUID(x_tenant_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="X-Tenant-ID must be a valid UUID") from exc
        tenant = db.get(Tenant, tid)
        if tenant is None or tenant.is_deleted:
            raise HTTPException(status_code=404, detail="Tenant not found")
        _reject_if_suspended(tenant)
        return tid

    raise HTTPException(
        status_code=400,
        detail="Tenant context required: use subdomain or X-Tenant-ID header",
    )


async def scope_calendar_feed_tenant(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> AsyncGenerator[uuid.UUID, None]:
    """Resolve and scope the tenant for the unauthenticated iCal feed.

    The feed (``GET /calendar/{token}.ics``) carries no JWT and no ``TenantDep``, so
    nothing else sets the current-tenant context. Without it the Postgres GUC
    ``app.current_tenant`` stays unset and, under ``FORCE ROW LEVEL SECURITY``, the
    member-by-token lookup matches zero rows — every feed 404s. We resolve the tenant
    the same way as :func:`get_tenant_id` (subdomain, then ``X-Tenant-ID``) and publish
    it to the tenant context so the lookup runs inside the right tenant with RLS
    satisfied. Every resolution miss (unknown, deleted, or suspended tenant) collapses
    into a single 404, matching the feed's "never leak existence" contract — this is
    why the feed resolves the tenant here instead of reusing ``get_tenant_id`` (which
    raises 403 on suspension and 400 on a missing context).
    """
    slug = _extract_subdomain(_resolve_request_host(request), settings.app_domain)

    tenant: Tenant | None = None
    if slug:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
    elif x_tenant_id is not None:
        try:
            tid = uuid.UUID(x_tenant_id)
        except ValueError:
            tenant = None
        else:
            tenant = db.get(Tenant, tid)

    if tenant is None or tenant.is_deleted or tenant.suspended_at is not None:
        raise HTTPException(status_code=404, detail="Calendar not found")

    token = set_current_tenant(tenant.id)
    try:
        yield tenant.id
    finally:
        reset_current_tenant(token)
