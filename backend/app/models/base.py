import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid6 import uuid7


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SourceTracked:
    """Mixin: provenance for rows imported/synced from an external system (e.g. TWH).

    Applied **alongside** ``TrackedBase`` to the entities a bulk import creates, so a
    later *incremental sync* can match an external record to its OpenTroop row
    (match-and-upsert instead of duplicating) and detect what changed upstream. All
    three fields are NULL for rows created natively in OpenTroop. This is groundwork
    only — no sync engine reads them yet; capturing provenance now means today's
    imports are upgradeable instead of orphaned. See ``docs/spec/twh-sync.md``.

      * ``source_system``     - originating system id (e.g. ``"twh"``)
      * ``source_id``         - that system's stable record id (TWH ``<i>``), indexed
      * ``source_updated_at`` - the source's own last-modified time (TWH
        ``Last_Update_UTC``); the change-detection + last-writer-wins signal for sync
    """

    source_system: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PlatformBase(Base):
    """Abstract base for platform-level entities that span tenants.

    Omits ``tenant_id`` intentionally — User, Identity, and Tenant records are
    global to the platform, not scoped to a single troop.  Every other table
    MUST use ``TrackedBase`` instead.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class TrackedBase(Base):
    """Abstract base applying the offline-sync tracking contract to every table.

    Every persisted table carries:
      * ``id``         - UUIDv7 primary key (time-ordered, client-generatable offline)
      * ``tenant_id``  - multi-tenant partition key (indexed)
      * ``created_at`` / ``updated_at`` - audit + last-writer-wins conflict signals
      * ``is_deleted`` - soft-delete tombstone for sync reconciliation
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
