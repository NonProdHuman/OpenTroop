from fastapi import FastAPI

from app.core.config import settings
from app.routers import members, patrols, relationships, role_assignments, roles

app = FastAPI(title=settings.app_name)

app.include_router(patrols.router)
app.include_router(members.router)
app.include_router(relationships.router)
app.include_router(roles.router)
app.include_router(role_assignments.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
