import uuid

from pydantic import BaseModel

from app.models.enums import Permission
from app.schemas.member import MemberRead


class SessionRoleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str


class SessionRead(BaseModel):
    tenant_id: uuid.UUID
    member: MemberRead | None
    permissions: list[Permission]
    roles: list[SessionRoleRead]
