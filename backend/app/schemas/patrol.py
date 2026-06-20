import uuid

from pydantic import BaseModel

from app.schemas.base import TrackedRead


class PatrolBase(BaseModel):
    name: str


class PatrolCreate(PatrolBase):
    tenant_id: uuid.UUID


class PatrolUpdate(BaseModel):
    name: str | None = None


class PatrolRead(PatrolBase, TrackedRead):
    pass
