"""Event photo gallery + upload pipeline (GH-145; spec in the issue).

Bytes never transit this API. ``initiate`` reserves quota and mints presigned
PUT URLs (ADR 0011); the client uploads straight to the bucket, then calls
``complete``, where the server HEAD-verifies the object and confirms the quota
reservation. Gallery reads return short-lived presigned GETs per photo — no
object is ever public.

Visibility is the event's visibility (``app/core/event_visibility.py``): photos
of a troop-wide event are troop-wide; an audience-restricted event's album stays
restricted to that audience, and hidden events 404 (existence not leaked).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from uuid6 import uuid7

from app.core.config import settings
from app.core.deps import DbDep, MemberContextDep, TenantDep, get_or_404, require
from app.core.event_visibility import event_visible_to_member
from app.core.groups import member_group_ids
from app.core.photo_quota import (
    confirm_upload,
    effective_quota_bytes,
    release_photo,
    reserved_bytes,
    would_exceed_quota,
)
from app.core.storage import StorageService, get_storage_service
from app.models.enums import Permission, PhotoStatus
from app.models.event import Event
from app.models.event_photo import EventPhoto
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.event_photo import (
    ALLOWED_PHOTO_CONTENT_TYPES,
    EventPhotoRead,
    EventPhotoWithUrl,
    PhotoDownload,
    PhotoInitiateRequest,
    PhotoInitiateResponse,
    PhotoUpdate,
    PhotoUploadTarget,
    StorageUsageRead,
)

router = APIRouter(tags=["photos"])

StorageDep = Annotated[StorageService, Depends(get_storage_service)]


def _visible_event_or_404(
    event_id: uuid.UUID, member: Member, permissions: frozenset[Permission], db: DbDep
) -> Event:
    """The event, if the caller may see it — 404 otherwise (existence not leaked)."""
    event = get_or_404(db, Event, event_id, "Event not found")
    if Permission.EVENT_WRITE not in permissions and not event_visible_to_member(
        event_id, member_group_ids(member.id, db), db
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


def _get_tenant(db: DbDep, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        # Tenant resolution already validated the id; a missing row here means
        # the tenant was purged mid-request.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def _photo_or_404(db: DbDep, photo_id: uuid.UUID) -> EventPhoto:
    return get_or_404(db, EventPhoto, photo_id, "Photo not found")


def _require_owner_or_moderator(
    photo: EventPhoto, member: Member, permissions: frozenset[Permission]
) -> None:
    if photo.uploaded_by_member_id != member.id and Permission.PHOTO_MODERATE not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )


@router.post(
    "/events/{event_id}/photos/initiate",
    response_model=PhotoInitiateResponse,
    status_code=201,
    dependencies=[Depends(require(Permission.PHOTO_UPLOAD))],
)
def initiate_photo_upload(
    event_id: uuid.UUID,
    body: PhotoInitiateRequest,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
    storage: StorageDep,
) -> PhotoInitiateResponse:
    """Reserve quota and mint presigned PUT URLs for a batch of photos."""
    member, permissions = member_ctx
    _visible_event_or_404(event_id, member, permissions, db)

    if len(body.photos) > settings.photo_max_batch:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"At most {settings.photo_max_batch} photos per request",
        )
    for item in body.photos:
        if item.content_type not in ALLOWED_PHOTO_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unsupported content type: {item.content_type}",
            )
        if item.byte_length > settings.photo_max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Each photo must be at most {settings.photo_max_upload_bytes} bytes",
            )

    tenant = _get_tenant(db, tenant_id)
    batch_bytes = sum(item.byte_length for item in body.photos)
    if would_exceed_quota(db, tenant, batch_bytes):
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Troop storage quota exceeded",
        )

    uploads: list[PhotoUploadTarget] = []
    for item in body.photos:
        photo_id = uuid7()
        storage_key = f"{tenant_id}/photo/{photo_id}/display.jpg"
        photo = EventPhoto(
            id=photo_id,
            event_id=event_id,
            uploaded_by_member_id=member.id,
            storage_key=storage_key,
            content_type=item.content_type,
            width=item.width,
            height=item.height,
            thumbhash=item.thumbhash,
            checksum_sha256=item.checksum_sha256,
            caption=item.caption,
            taken_at=item.taken_at,
            status=PhotoStatus.PENDING,
            reserved_bytes=item.byte_length,
        )
        db.add(photo)
        uploads.append(
            PhotoUploadTarget(
                photo_id=photo_id,
                upload_url=storage.presign_put(storage_key, content_type=item.content_type),
                expires_in_seconds=settings.storage_presign_ttl_seconds,
            )
        )
    db.commit()
    return PhotoInitiateResponse(uploads=uploads)


@router.post(
    "/photos/{photo_id}/complete",
    response_model=EventPhotoRead,
    dependencies=[Depends(require(Permission.PHOTO_UPLOAD))],
)
def complete_photo_upload(
    photo_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
    storage: StorageDep,
) -> EventPhoto:
    """Confirm an upload: HEAD-verify the object, flip to READY, settle quota."""
    member, permissions = member_ctx
    photo = _photo_or_404(db, photo_id)
    _require_owner_or_moderator(photo, member, permissions)

    if photo.status == PhotoStatus.READY:
        return photo  # idempotent — a retried complete is not an error
    if photo.status != PhotoStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Photo is not awaiting completion"
        )

    info = storage.head(photo.storage_key)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload not found in storage — retry the PUT, then complete again",
        )
    if info.size_bytes > settings.photo_max_upload_bytes:
        # The client lied in the reservation; drop the oversized object.
        storage.delete(photo.storage_key)
        release_photo(db, photo)
        photo.status = PhotoStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Uploaded object exceeds the per-photo size cap",
        )

    confirm_upload(db, photo, info.size_bytes)
    db.commit()
    db.refresh(photo)
    return photo


@router.get(
    "/events/{event_id}/photos",
    response_model=list[EventPhotoWithUrl],
    dependencies=[Depends(require(Permission.PHOTO_READ))],
)
def list_event_photos(
    event_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
    storage: StorageDep,
    limit: int = 200,
    offset: int = 0,
) -> list[EventPhotoWithUrl]:
    """The event's gallery: READY photos plus short-lived presigned GETs."""
    member, permissions = member_ctx
    _visible_event_or_404(event_id, member, permissions, db)
    limit = max(1, min(limit, 500))
    photos = db.scalars(
        select(EventPhoto)
        .where(EventPhoto.event_id == event_id, EventPhoto.status == PhotoStatus.READY)
        .order_by(EventPhoto.created_at, EventPhoto.id)
        .limit(limit)
        .offset(max(offset, 0))
    ).all()
    return [
        EventPhotoWithUrl(
            **EventPhotoRead.model_validate(photo).model_dump(),
            display_url=storage.presign_get(photo.storage_key),
        )
        for photo in photos
    ]


@router.get(
    "/photos/{photo_id}/download",
    response_model=PhotoDownload,
    dependencies=[Depends(require(Permission.PHOTO_READ))],
)
def download_photo(
    photo_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
    storage: StorageDep,
    variant: str = "display",
) -> PhotoDownload:
    """A short-lived presigned GET for saving the photo back to a device."""
    member, permissions = member_ctx
    photo = _photo_or_404(db, photo_id)
    _visible_event_or_404(photo.event_id, member, permissions, db)
    if photo.status != PhotoStatus.READY:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    if variant == "original":
        if photo.original_key is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No original kept for this photo"
            )
        key = photo.original_key
    elif variant == "display":
        key = photo.storage_key
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="variant must be 'display' or 'original'",
        )
    return PhotoDownload(
        url=storage.presign_get(key),
        expires_in_seconds=settings.storage_presign_ttl_seconds,
    )


@router.patch(
    "/photos/{photo_id}",
    response_model=EventPhotoRead,
    dependencies=[Depends(require(Permission.PHOTO_UPLOAD))],
)
def update_photo(
    photo_id: uuid.UUID,
    body: PhotoUpdate,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
) -> EventPhoto:
    member, permissions = member_ctx
    photo = _photo_or_404(db, photo_id)
    _require_owner_or_moderator(photo, member, permissions)
    photo.caption = body.caption
    db.commit()
    db.refresh(photo)
    return photo


@router.delete(
    "/photos/{photo_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.PHOTO_READ))],
)
def delete_photo(
    photo_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
) -> None:
    """Soft-delete a photo (owner, or ``photo:moderate`` for anyone's).

    Quota is given back immediately; the object bytes are removed later by
    ``uv run reap-photo-uploads`` (the tombstone row stays for sync).
    """
    member, permissions = member_ctx
    photo = _photo_or_404(db, photo_id)
    _require_owner_or_moderator(photo, member, permissions)
    release_photo(db, photo)
    photo.is_deleted = True
    db.commit()


@router.get(
    "/storage/usage",
    response_model=StorageUsageRead,
    dependencies=[Depends(require(Permission.PHOTO_READ))],
)
def storage_usage(tenant_id: TenantDep, db: DbDep) -> StorageUsageRead:
    """The tenant's storage meter, for upload UIs."""
    tenant = _get_tenant(db, tenant_id)
    reserved = reserved_bytes(db, tenant_id)
    quota = effective_quota_bytes(tenant)
    return StorageUsageRead(
        used_bytes=tenant.used_storage_bytes,
        reserved_bytes=reserved,
        quota_bytes=quota,
        remaining_bytes=max(quota - tenant.used_storage_bytes - reserved, 0),
    )
