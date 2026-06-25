import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import PlatformRead


class TenantCreate(BaseModel):
    name: str
    slug: str


class TenantProvision(TenantCreate):
    """Request body for the platform-admin tenant onboarding endpoint.

    The founding admin is created as an *unclaimed* Member (``user_id`` is null)
    and invited by email — the platform admin who provisions the tenant does not
    become a member of it. The founder claims their account via POST /auth/claim
    using the returned invite token.
    """

    founder_first_name: str
    founder_last_name: str
    founder_email: str | None = None


class TenantRead(PlatformRead):
    name: str
    slug: str
    suspended_at: datetime | None = None


class TenantProvisioned(TenantRead):
    """Response for POST /platform/tenants — the new tenant plus the founder's invite.

    ``invite_token`` is a 7-day HS256 claim token for the founding admin Member.
    Deliver it to the founder (manually for now; emailed automatically once the
    notification infrastructure lands); they sign in via OIDC and POST it to
    /auth/claim to link their account to the founding admin Member.
    """

    founder_member_id: uuid.UUID
    invite_token: str
    invite_expires_at: datetime
