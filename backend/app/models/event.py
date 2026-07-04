from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import SourceTracked, Syncable, TrackedBase
from app.models.enums import PermissionSlipStatus, RsvpStatus

if TYPE_CHECKING:
    from app.models.event_type import EventType
    from app.models.location import Location
    from app.models.member import Member


class Event(SourceTracked, Syncable, TrackedBase):
    __tablename__ = "events"
    # RLS injects tenant_id into every query; leading with it keeps the hot
    # date-ordered event list a single index range scan per tenant (GH-115).
    __table_args__ = (
        Index("ix_events_tenant_scheduled_start", "tenant_id", "scheduled_start"),
        Index("ix_events_tenant_sync_seq", "tenant_id", "sync_seq"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event_types.id"), nullable=False, index=True
    )
    event_type: Mapped[EventType] = relationship()

    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    location: Mapped[Location | None] = relationship()
    location_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    departure_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    return_location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Set when a leader cancels the event (POST /events/{id}/cancel). A cancelled
    # event still exists and renders struck-through; distinct from is_deleted.
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    signup_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    signup_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    signup_limit_scouts: Mapped[int | None] = mapped_column(nullable=True)
    signup_limit_adults: Mapped[int | None] = mapped_column(nullable=True)

    cost_youth: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    cost_adult: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    video_conference_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agenda: Mapped[str | None] = mapped_column(Text, nullable=True)

    tour_permit_submitted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    attendance_taken: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    linked_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("events.id"), nullable=True
    )

    community_service_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    conservation_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    hiking_miles: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    backpacking_miles: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    paddling_miles: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    cycling_miles: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    water_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    camping_nights: Mapped[int | None] = mapped_column(nullable=True)

    organizers: Mapped[list[EventOrganizer]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    participants: Mapped[list[EventParticipant]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventOrganizer(TrackedBase):
    __tablename__ = "event_organizers"

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )

    event: Mapped[Event] = relationship(back_populates="organizers")
    member: Mapped[Member] = relationship()


class EventParticipant(SourceTracked, Syncable, TrackedBase):
    __tablename__ = "event_participants"
    # Hot paths: participants-per-event (event pages) and per-member RSVP state
    # (iCal feed, member views) — both always tenant-scoped under RLS (GH-115).
    __table_args__ = (
        Index("ix_event_participants_tenant_event", "tenant_id", "event_id"),
        Index("ix_event_participants_tenant_member", "tenant_id", "member_id"),
        Index("ix_event_participants_tenant_sync_seq", "tenant_id", "sync_seq"),
    )

    # Derived per-request, never persisted (not a Mapped column ⇒ ignored by the mapper).
    # The router fills it via app.core.permission_slip before serialization.
    permission_status: PermissionSlipStatus = PermissionSlipStatus.NOT_REQUIRED

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )

    signed_up: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Explicit member response, distinct from signed_up/attended. DECLINED drives
    # gray-out in the app and omission from the member's personal iCal feed.
    rsvp_status: Mapped[RsvpStatus] = mapped_column(
        SAEnum(RsvpStatus, values_callable=lambda x: [e.value for e in x]),
        default=RsvpStatus.NO_RESPONSE,
        nullable=False,
        index=True,
    )
    attended: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    guest_count: Mapped[int] = mapped_column(default=0, nullable=False)
    driver: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Informational carpool legs (only meaningful when driver=True). No capacity math
    # is done with these yet — they're stored to enable a future seat-allocation feature.
    drives_to: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    drives_from: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seat_count: Mapped[int | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    hiking_miles_override: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    backpacking_miles_override: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    paddling_miles_override: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    cycling_miles_override: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    community_service_hours_override: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    conservation_hours_override: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    water_hours_override: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    camping_nights_override: Mapped[int | None] = mapped_column(nullable=True)

    permission_slip_submitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    electronic_permission: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    electronic_permission_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    electronic_permission_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    electronic_permission_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The exact tenant permission language the parent agreed to, captured at sign time.
    # Editing Tenant.permission_message never rewrites already-signed slips (legal record);
    # the future permission-slip PDF renders from this snapshot.
    permission_message_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped[Event] = relationship(back_populates="participants")
    member: Mapped[Member] = relationship(foreign_keys=[member_id])
    electronic_permission_by: Mapped[Member | None] = relationship(
        foreign_keys=[electronic_permission_by_id]
    )
