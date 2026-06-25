from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    auth,
    calendar,
    event_types,
    events,
    groups,
    imports,
    locations,
    members,
    platform,
    relationships,
    role_assignments,
    roles,
)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(groups.router)
app.include_router(members.router)
app.include_router(relationships.router)
app.include_router(roles.router)
app.include_router(role_assignments.router)
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
