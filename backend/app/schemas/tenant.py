import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AdvancementMode
from app.schemas.base import PlatformRead


class TenantProvision(BaseModel):
    """Request body for the platform-admin tenant onboarding endpoint.

    The founding admin is created as an *unclaimed* Member (``user_id`` is null)
    and invited by email — the platform admin who provisions the tenant does not
    become a member of it. The founder claims their account via POST /auth/claim
    using the returned invite token.
    """

    name: str
    slug: str
    founder_first_name: str
    founder_last_name: str
    founder_email: str | None = None


class TenantRead(PlatformRead):
    name: str
    slug: str
    suspended_at: datetime | None = None
    # When a platform admin last exported this tenant's data (GH-222). The admin
    # UI uses it to arm the delete flow: deletion requires an export after suspension.
    last_export_at: datetime | None = None
    permission_message: str | None = None


class TenantDeleteRequest(BaseModel):
    """Body for DELETE /platform/tenants/{id} — type-to-confirm (GH-222).

    Must match the tenant's slug exactly; enforced server-side.
    """

    confirm_slug: str


class TenantSettingsRead(BaseModel):
    """Tenant-scoped, member-readable settings (the troop's configurable text/options)."""

    # The effective permission language shown to parents — the troop's text or the
    # built-in default when unset. Always populated.
    permission_message: str
    # Advancement workflow switch (GH-92): disabled / chair_entry / scout_reported.
    advancement_mode: AdvancementMode
    # Announcement digest cadence (GH-218). digest_day follows date.weekday():
    # 0 = Monday … 6 = Sunday. digest_hour_utc is 0–23 UTC.
    digest_day: int
    digest_hour_utc: int


class TenantSettingsUpdate(BaseModel):
    # Set to null to fall back to the built-in default permission language.
    permission_message: str | None = None
    advancement_mode: AdvancementMode | None = None
    digest_day: int | None = Field(default=None, ge=0, le=6)
    digest_hour_utc: int | None = Field(default=None, ge=0, le=23)


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
