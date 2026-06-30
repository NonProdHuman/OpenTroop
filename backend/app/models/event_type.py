from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SourceTracked, TrackedBase


class EventType(SourceTracked, TrackedBase):
    __tablename__ = "event_types"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uix_event_types_tenant_name"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tracks_service_hours: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tracks_camping_nights: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tracks_mileage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_signups: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    require_permission_slip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # When True, the RSVP form exposes a guest-count field for non-roster attendees
    # (e.g. a family BBQ where grandparents come). Independent of allow_signups gating.
    allow_guests: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
