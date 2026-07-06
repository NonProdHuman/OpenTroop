"""Event photo schemas (GH-145)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import PhotoStatus
from app.schemas.base import TrackedRead
from app.schemas.types import UtcDateTime

# Image types the pipeline accepts. Clients re-encode to JPEG during the
# downscale/EXIF-strip step, so this list is deliberately narrow.
ALLOWED_PHOTO_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


class PhotoInitiateItem(BaseModel):
    """One photo the client wants to upload (post-downscale facts)."""

    content_type: str
    # Client's post-downscale size — used only for the quota reservation; the
    # authoritative size comes from the server-side HEAD at complete time.
    byte_length: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    thumbhash: str | None = Field(default=None, max_length=64)
    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    caption: str | None = None
    taken_at: UtcDateTime | None = None


class PhotoInitiateRequest(BaseModel):
    photos: list[PhotoInitiateItem] = Field(min_length=1)


class PhotoUploadTarget(BaseModel):
    """Where the client PUTs one photo's bytes."""

    photo_id: uuid.UUID
    upload_url: str
    expires_in_seconds: int


class PhotoInitiateResponse(BaseModel):
    uploads: list[PhotoUploadTarget]


class EventPhotoRead(TrackedRead):
    event_id: uuid.UUID
    uploaded_by_member_id: uuid.UUID
    content_type: str
    byte_size: int | None = None
    width: int
    height: int
    thumbhash: str | None = None
    checksum_sha256: str | None = None
    status: PhotoStatus
    caption: str | None = None
    taken_at: UtcDateTime | None = None


class EventPhotoWithUrl(EventPhotoRead):
    """A READY photo plus a short-lived presigned GET for its bytes."""

    display_url: str


class PhotoUpdate(BaseModel):
    caption: str | None = None


class PhotoDownload(BaseModel):
    url: str
    expires_in_seconds: int


class StorageUsageRead(BaseModel):
    """The tenant's storage meter, for upload UIs (GH-145 §7)."""

    used_bytes: int
    reserved_bytes: int
    quota_bytes: int
    remaining_bytes: int
