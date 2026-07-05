import asyncio
import contextlib
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.edge_security import OriginAuthMiddleware, RateLimitMiddleware
from app.routers import (
    advancement,
    auth,
    calendar,
    event_types,
    events,
    functional_roles,
    groups,
    imports,
    locations,
    member_positions,
    members,
    messages,
    platform,
    positions,
    push_tokens,
    relationships,
    sync,
    tenant_settings,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Start the messaging outbox loop (GH-78) when enabled.

    Off by default (tests, one-shot commands); production/dev API processes set
    OUTBOX_LOOP_ENABLED=true. The drain-outbox CLI is the cron belt either way.
    """
    task: asyncio.Task[None] | None = None
    if settings.outbox_loop_enabled:
        from app.core.outbox import outbox_loop

        task = asyncio.create_task(outbox_loop())
    yield
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# App-layer rate limiting (GH-116). Added before CORS so preflights short-circuit in
# CORSMiddleware without consuming budget; inert unless RATE_LIMIT_ENABLED=true.
app.add_middleware(RateLimitMiddleware)

# Compute regex for CORS origins based on app_domain.
# Allows https://opentroop.app and https://<one-label>.opentroop.app — a single
# subdomain label only (tenant slugs, admin, www), never nested subdomains,
# mirroring the nested-subdomain rejection in tenant resolution (GH-118).
cors_regex = None
if settings.app_domain:
    domain_escaped = re.escape(settings.app_domain)
    # e.g. ^https://([a-zA-Z0-9-]+\.)?opentroop\.app$
    cors_regex = rf"^https://([a-zA-Z0-9-]+\.)?{domain_escaped}$"

# With allow_credentials=True the browser will attach auth to whatever this
# middleware reflects, so methods and headers are enumerated instead of "*"
# to keep the credentialed cross-origin surface as small as possible (GH-118).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=cors_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID"],
)

# Outermost belt (GH-116): when ORIGIN_SHARED_SECRET is set, reject any request that
# didn't traverse the edge proxy before touching CORS, routing, or the database.
app.add_middleware(OriginAuthMiddleware)

app.include_router(groups.router)
app.include_router(members.router)
app.include_router(messages.router)
app.include_router(relationships.router)
app.include_router(positions.router)
app.include_router(push_tokens.router)
app.include_router(functional_roles.router)
app.include_router(member_positions.router)
app.include_router(auth.router)
app.include_router(platform.router)
app.include_router(locations.router)
app.include_router(event_types.router)
app.include_router(events.router)
app.include_router(calendar.router)
app.include_router(imports.router)
app.include_router(tenant_settings.router)
app.include_router(sync.router)
app.include_router(advancement.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
