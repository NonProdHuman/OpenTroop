from fastapi import FastAPI

from app.core.config import settings
from app.routers import (
    auth,
    event_types,
    events,
    imports,
    locations,
    members,
    patrols,
    relationships,
    role_assignments,
    roles,
    tenants,
)

app = FastAPI(title=settings.app_name)

app.include_router(patrols.router)
app.include_router(members.router)
app.include_router(relationships.router)
app.include_router(roles.router)
app.include_router(role_assignments.router)
app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(locations.router)
app.include_router(event_types.router)
app.include_router(events.router)
app.include_router(imports.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
