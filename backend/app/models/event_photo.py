from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Syncable, TrackedBase
from app.models.enums import PhotoStatus


class EventPhoto(Syncable, TrackedBase):
    """One photo in an event's gallery (GH-145; spec in the issue).

    The event *is* the album — visibility follows the event's audience rules
    (``app/core/event_visibility.py``). Bytes live in object storage (ADR 0011)
    under ``storage_key``; this row is metadata only, and it is ``Syncable`` so
    galleries lay out offline on mobile before any bytes arrive.

    Rows are born ``PENDING`` with a quota reservation (``reserved_bytes``) when
    the presigned PUT is minted, and flip to ``READY`` — with the HEAD-verified
    ``byte_size`` — only after the upload is confirmed. The reaper
    (``uv run reap-photo-uploads``) sweeps abandoned PENDING/FAILED rows and
    releases their reservations.
    """

    __tablename__ = "event_photos"
    __table_args__ = (
        Index("ix_event_photos_tenant_event", "tenant_id", "event_id"),
        Index("ix_event_photos_tenant_sync_seq", "tenant_id", "sync_seq"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), nullable=False)
    uploaded_by_member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False
    )
    # Object key in the bucket: "<tenant_id>/photo/<photo_id>/display.jpg".
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # Present only when the tenant keeps untouched originals (photo_keep_original).
    original_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # HEAD-verified size once READY; null while PENDING (the client's estimate is
    # only ever used for the reservation, never persisted as truth).
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Client-computed placeholder hash so grids paint before thumbnails load.
    thumbhash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[PhotoStatus] = mapped_column(
        SAEnum(PhotoStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PhotoStatus.PENDING,
    )
    # Bytes counted against the tenant quota while PENDING; zeroed on confirm/fail.
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When the photo was taken (client-supplied, read before EXIF stripping).
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
