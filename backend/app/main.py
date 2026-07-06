import asyncio
import contextlib
import logging
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
    consents,
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

logger = logging.getLogger("app.startup")


def _warn_if_advancement_catalog_empty() -> None:
    """Log a loud WARNING when the global advancement catalog is unseeded (GH-241).

    A deployed environment that never ran ``seed-advancement`` has no ``Rank`` rows,
    so the TWH importer silently skips every advancement record behind one warning.
    Surfacing it at startup turns an invisible data-loss condition into a visible
    signal that the deploy path (Dockerfile CMD / release step) is missing the seed.
    Best-effort: a lookup failure must never block the app from serving.
    """
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.advancement_catalog import catalog_is_empty
    from app.core.database import SessionLocal

    try:
        with SessionLocal() as session:
            empty = catalog_is_empty(session)
    except SQLAlchemyError:
        logger.exception("Could not check the advancement catalog at startup")
        return
    if empty:
        logger.warning(
            "Advancement catalog is empty — no Rank rows. TWH imports will skip ALL "
            "advancement data. Run `seed-advancement` in the deploy path (see GH-241)."
        )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Start the background drain loops (GH-78 outbox, GH-240 import) when enabled.

    Off by default (tests, one-shot commands); production/dev API processes set
    OUTBOX_LOOP_ENABLED / IMPORT_LOOP_ENABLED as appropriate. The drain-outbox and
    drain-import-jobs CLIs are the cron belts either way. (On SaaS, imports are
    pushed to a Cloud Tasks worker instead — IMPORT_QUEUE_BACKEND=cloudtasks.)
    """
    _warn_if_advancement_catalog_empty()
    tasks: list[asyncio.Task[None]] = []
    if settings.outbox_loop_enabled:
        from app.core.outbox import outbox_loop

        tasks.append(asyncio.create_task(outbox_loop()))
    if settings.import_loop_enabled:
        from app.core.import_jobs import import_loop

        tasks.append(asyncio.create_task(import_loop()))
    yield
    for task in tasks:
        task.cancel()
    if tasks:
        with contextlib.suppress(asyncio.CancelledError):
            # Await the cancelled background loops so they can unwind before
            # shutdown continues (gather keeps this a call expression, not a bare
            # awaited-name that static analysis reads as having no effect).
            await asyncio.gather(*tasks)


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
app.include_router(consents.router)
app.include_router(advancement.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
