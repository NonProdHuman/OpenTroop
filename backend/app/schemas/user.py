import uuid

from app.models.enums import PlatformRole
from app.schemas.base import PlatformRead


class IdentityRead(PlatformRead):
    user_id: uuid.UUID
    provider: str
    issuer: str
    email: str | None


class UserRead(PlatformRead):
    email: str | None
    display_name: str | None
    platform_role: PlatformRole | None = None
    identities: list[IdentityRead] = []
