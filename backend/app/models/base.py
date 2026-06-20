import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid6 import uuid7


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
