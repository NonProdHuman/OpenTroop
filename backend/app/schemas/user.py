import uuid

from app.schemas.base import PlatformRead


class IdentityRead(PlatformRead):
    user_id: uuid.UUID
    provider: str
    issuer: str
    email: str | None


class UserRead(PlatformRead):
    email: str | None
    display_name: str | None
    identities: list[IdentityRead] = []
