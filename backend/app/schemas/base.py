import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlatformRead(BaseModel):
    """Shared read fields for platform-level (cross-tenant) resources."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: bool


class TrackedRead(BaseModel):
    """Shared read-side tracking fields surfaced on every resource."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
