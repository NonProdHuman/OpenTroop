from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TrackedBase
from app.models.enums import PositionScope


class EventSlot(TrackedBase):
    """A named, optionally capacity-limited sign-up slot on an event (GH-152).

    Generalizes TWH's event-shift model: drivers to/from camp, grubmaster,
    merit-badge sessions, fundraiser shifts, cleanup crews. A slot is a
    *commitment within* an event, orthogonal to the whole-event RSVP
    (``EventParticipant``) — RSVP answers "are you coming?", a slot answers
    "what are you doing there?". One flat level: a slot *may* carry a time
    window (``starts_at``/``ends_at``) or not; ``sort_order`` + naming cover
    the grouping case. Not ``Syncable`` in v1 — events aren't in the sync
    protocol yet, so slots join whenever events do (online-first, ADR 0006).
    """

    __tablename__ = "event_slots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_id", "name", name="uq_event_slots_event_name"),
        Index("ix_event_slots_tenant_event", "tenant_id", "event_id"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # null = unlimited; 0 is invalid (rejected 422 at the API).
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Validation hint enforced on sign-up (422 for a mismatched member_type).
    applies_to: Mapped[PositionScope] = mapped_column(
        SAEnum(PositionScope, values_callable=lambda x: [e.value for e in x]),
        default=PositionScope.ANY,
        nullable=False,
    )
    # Optional shift window; when both set, ``ends_at >= starts_at`` (422).
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class EventSlotSignup(TrackedBase):
    """One member claiming one slot (GH-152); soft delete = withdrawal.

    At most one *active* signup per ``(slot_id, member_id)`` — the unique
    constraint keeps that honest, and re-signing up after a withdrawal revives
    the tombstone via the ``include_deleted()`` upsert pattern (as ``GroupRule``
    does). ``signed_up_by_id`` records who acted (self / parent / manager).
    """

    __tablename__ = "event_slot_signups"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "slot_id", "member_id", name="uq_event_slot_signups_slot_member"
        ),
        Index("ix_event_slot_signups_tenant_slot", "tenant_id", "slot_id"),
    )

    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_slots.id"), nullable=False)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Audit trail: the member who performed the sign-up (self / parent / manager).
    signed_up_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    signed_up_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
