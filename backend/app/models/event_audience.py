from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TrackedBase

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.group import Group


class EventAudience(TrackedBase):
    """Scopes an event's visibility to one or more Groups.

    An event with **no** (non-deleted) audience rows is **troop-wide** — visible to
    everyone with ``event:read``. Once any audience row exists, the event is visible
    only to members of those groups (plus event managers, who see everything). This
    is the single mechanism behind patrol-only events, and the same filter feeds the
    calendar and the per-member iCal feed.
    """

    __tablename__ = "event_audiences"
    __table_args__ = (
        UniqueConstraint("event_id", "group_id", name="uq_event_audiences_event_group"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), nullable=False, index=True)

    event: Mapped[Event] = relationship("Event")
    group: Mapped[Group] = relationship("Group")
