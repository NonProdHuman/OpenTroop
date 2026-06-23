from pydantic import BaseModel

from app.schemas.base import PlatformRead


class TenantCreate(BaseModel):
    name: str
    slug: str


class TenantRead(PlatformRead):
    name: str
    slug: str
