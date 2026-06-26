import uuid

from pydantic import BaseModel


class MembershipRead(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    member_id: uuid.UUID
    is_admin: bool
