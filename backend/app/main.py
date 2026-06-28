import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
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
    platform,
    positions,
    relationships,
)

app = FastAPI(title=settings.app_name)

# Compute regex for CORS origins based on app_domain
# This allows https://opentroop.app and https://*.opentroop.app
cors_regex = None
if settings.app_domain:
    domain_escaped = re.escape(settings.app_domain)
    # e.g. ^https://([a-zA-Z0-9-]+\.)?opentroop\.app$
    cors_regex = rf"^https://([a-zA-Z0-9-]+\.)?{domain_escaped}$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(groups.router)
app.include_router(members.router)
app.include_router(relationships.router)
app.include_router(positions.router)
app.include_router(functional_roles.router)
app.include_router(member_positions.router)
app.include_router(auth.router)
app.include_router(platform.router)
app.include_router(locations.router)
app.include_router(event_types.router)
app.include_router(events.router)
app.include_router(calendar.router)
app.include_router(imports.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
