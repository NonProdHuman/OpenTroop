"""Tenant storage-quota accounting for event photos (GH-145 §7).

The platform's first storage meter. The flow is **reserve → confirm**:

- *Reserve* (initiate): before any presigned PUT is minted, the client's claimed
  post-downscale sizes are checked against ``used + reserved + new ≤ quota`` and
  written as ``EventPhoto.reserved_bytes`` on PENDING rows. Over quota → 413,
  mirroring the TWH-import byte-cap precedent.
- *Confirm* (complete): the server HEADs the object for the **actual** size —
  the client's estimate is never persisted as truth — zeroes the reservation and
  bumps ``Tenant.used_storage_bytes`` with a guarded in-place UPDATE so
  concurrent completes can't lose increments to a read-modify-write race.

Releasing (delete/reap) is the mirror image: zero the reservation for PENDING
rows, decrement the meter for READY ones (clamped at zero).
"""

from __future__ import annotations

import uuid

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import PhotoStatus
from app.models.event_photo import EventPhoto
from app.models.tenant import Tenant


def effective_quota_bytes(tenant: Tenant) -> int:
    """The tenant's quota: per-tenant override, else the platform default."""
    if tenant.storage_quota_bytes is not None:
        return tenant.storage_quota_bytes
    return settings.tenant_storage_quota_default_bytes


def reserved_bytes(db: Session, tenant_id: uuid.UUID) -> int:
    """Live PENDING reservations for the tenant (soft-deleted rows excluded)."""
    total = db.scalar(
        select(func.coalesce(func.sum(EventPhoto.reserved_bytes), 0)).where(
            EventPhoto.tenant_id == tenant_id,
            EventPhoto.status == PhotoStatus.PENDING,
            EventPhoto.is_deleted.is_(False),
        )
    )
    return int(total or 0)


def would_exceed_quota(db: Session, tenant: Tenant, new_bytes: int) -> bool:
    return tenant.used_storage_bytes + reserved_bytes(
        db, tenant.id
    ) + new_bytes > effective_quota_bytes(tenant)


def add_used_bytes(db: Session, tenant_id: uuid.UUID, delta: int) -> None:
    """Adjust the meter in place, clamped at zero — race-safe under concurrency.

    ``used = used + delta`` as a single SQL UPDATE (not ORM read-modify-write),
    so two requests confirming at once both land their increments.
    """
    db.execute(
        update(Tenant)
        .where(Tenant.id == tenant_id)
        .values(
            used_storage_bytes=case(
                (Tenant.used_storage_bytes + delta > 0, Tenant.used_storage_bytes + delta),
                else_=0,
            )
        )
    )


def confirm_upload(db: Session, photo: EventPhoto, actual_bytes: int) -> None:
    """Flip a PENDING photo to READY with its HEAD-verified size."""
    photo.byte_size = actual_bytes
    photo.status = PhotoStatus.READY
    photo.reserved_bytes = 0
    add_used_bytes(db, photo.tenant_id, actual_bytes)


def release_photo(db: Session, photo: EventPhoto) -> None:
    """Give a photo's bytes back to the tenant, whatever state it is in.

    PENDING → just drop the reservation; READY → decrement the meter. Safe to
    call from both the DELETE endpoint and the reaper.
    """
    if photo.status == PhotoStatus.READY and photo.byte_size:
        add_used_bytes(db, photo.tenant_id, -photo.byte_size)
    photo.reserved_bytes = 0
