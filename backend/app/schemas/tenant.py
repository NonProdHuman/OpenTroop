from pydantic import BaseModel

from app.schemas.base import PlatformRead


class TenantCreate(BaseModel):
    name: str
    slug: str


class TenantProvision(TenantCreate):
    """Request body for the tenant onboarding endpoint.

    Includes the founding admin's name so their Member record can be created
    atomically in the same transaction.
    """

    founder_first_name: str
    founder_last_name: str


class TenantRead(PlatformRead):
    name: str
    slug: str
