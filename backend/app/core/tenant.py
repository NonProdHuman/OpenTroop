from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.tenant import Tenant


def _extract_subdomain(host: str, app_domain: str) -> str | None:
    """Return the single subdomain prefix if *host* is a direct subdomain of *app_domain*.

    ``troop123.opentroop.org`` → ``"troop123"``
    Nested subdomains (``a.troop123.opentroop.org``) are rejected to prevent
    tenant spoofing via crafted Host headers.
    """
    host = host.lower().split(":")[0]  # strip optional port
    suffix = f".{app_domain.lower()}"
    if not host.endswith(suffix):
        return None
    prefix = host[: -len(suffix)]
    if not prefix or "." in prefix:
        return None
    return prefix


async def get_tenant_id(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """Resolve the tenant for a request.

    Resolution order:
    1. Subdomain — ``troop123.opentroop.org`` → slug lookup in DB.
    2. ``X-Tenant-ID`` header — raw UUID → DB validation.
    """
    host = request.headers.get("host", "")
    slug = _extract_subdomain(host, settings.app_domain)

    if slug:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == slug, Tenant.is_deleted.is_(False)))
        if tenant is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return tenant.id

    if x_tenant_id is not None:
        try:
            tid = uuid.UUID(x_tenant_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="X-Tenant-ID must be a valid UUID") from exc
        tenant = db.get(Tenant, tid)
        if tenant is None or tenant.is_deleted:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return tid

    raise HTTPException(
        status_code=400,
        detail="Tenant context required: use subdomain or X-Tenant-ID header",
    )
