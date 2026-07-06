"""Pydantic schemas for the consent ledger (#223)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import ConsentMethod, ConsentScope
from app.schemas.base import TrackedRead
from app.schemas.types import UtcDateTime


class ConsentRecordCreate(BaseModel):
    subject_member_id: uuid.UUID
    scope: ConsentScope
    method: ConsentMethod = ConsentMethod.SELF
    consented_by_member_id: uuid.UUID | None = None
    # Defaults to the server's now when omitted.
    granted_at: UtcDateTime | None = None
    policy_version: str | None = Field(default=None, max_length=64)
    notes: str | None = None


class ConsentRecordRead(TrackedRead):
    subject_member_id: uuid.UUID
    consented_by_member_id: uuid.UUID | None
    consented_by_user_id: uuid.UUID | None
    scope: ConsentScope
    method: ConsentMethod
    granted_at: UtcDateTime
    revoked_at: UtcDateTime | None
    policy_version: str | None
    notes: str | None
