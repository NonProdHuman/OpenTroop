"""Schemas for the platform (global) control-plane API under /platform."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class TenantAdminInvite(BaseModel):
    """Request body to invite a new administrator into an existing tenant."""

    first_name: str
    last_name: str
    email: str | None = None


class TenantAdminInviteResult(BaseModel):
    """Returned when a tenant admin is invited — the unclaimed member + claim token."""

    member_id: uuid.UUID
    token: str
    expires_at: datetime


class TenantAdminRead(BaseModel):
    """A member holding the administrators role in a tenant (platform-admin view)."""

    member_id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None
    user_id: uuid.UUID | None
    claimed: bool
