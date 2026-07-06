"""Sweep abandoned and deleted event-photo uploads (GH-145 §7).

Two jobs, both idempotent, run by ``uv run reap-photo-uploads``:

1. **Stale PENDING uploads** — a client that initiated but never confirmed
   (app killed mid-upload, presign expired). After
   ``PHOTO_PENDING_REAP_HOURS`` the reservation is released, any orphaned
   object is deleted, and the row is tombstoned as PURGED so offline mirrors
   drop it. The quota meter is untouched — PENDING rows never incremented it.

2. **Soft-deleted photos** — the DELETE endpoint releases quota immediately but
   leaves the object bytes for this job. Objects (display + any original) are
   deleted and the row's status set to PURGED, which is the idempotency marker:
   a PURGED row is never re-processed, so a re-run (or a crash between object
   delete and commit) can only repeat harmless deletes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import StorageService
from app.core.tenant_context import include_deleted, unscoped
from app.models.enums import PhotoStatus
from app.models.event_photo import EventPhoto


def _delete_objects(storage: StorageService, photo: EventPhoto) -> None:
    storage.delete(photo.storage_key)
    if photo.original_key is not None:
        storage.delete(photo.original_key)


def reap_photo_uploads(
    session: Session, storage: StorageService, *, dry_run: bool = False
) -> tuple[int, int]:
    """Run both sweeps; returns ``(stale_pending, purged_deleted)`` counts.

    A cross-tenant platform maintenance job, like ``reap_purged_members`` —
    runs inside ``unscoped()`` + ``include_deleted()`` so it sees every
    tenant's rows and the tombstones the automatic filters would hide.
    Does not commit. ``dry_run`` skips the storage deletes too — object
    deletion is not transactional, so the caller's rollback alone would not
    undo it.
    """
    now = datetime.now(UTC)
    stale_cutoff = now - timedelta(hours=settings.photo_pending_reap_hours)

    with unscoped(), include_deleted():
        stale = session.scalars(
            select(EventPhoto).where(
                EventPhoto.status == PhotoStatus.PENDING,
                EventPhoto.is_deleted.is_(False),
                EventPhoto.created_at < stale_cutoff,
            )
        ).all()
        for photo in stale:
            if not dry_run:
                _delete_objects(storage, photo)
            photo.reserved_bytes = 0
            photo.status = PhotoStatus.PURGED
            photo.is_deleted = True

        deleted = session.scalars(
            select(EventPhoto).where(
                EventPhoto.is_deleted.is_(True),
                EventPhoto.status != PhotoStatus.PURGED,
            )
        ).all()
        for photo in deleted:
            if not dry_run:
                _delete_objects(storage, photo)
            # Quota was already released by the DELETE endpoint (or the stale
            # sweep); PURGED only marks the object bytes gone.
            photo.reserved_bytes = 0
            photo.status = PhotoStatus.PURGED

    return len(stale), len(deleted)
