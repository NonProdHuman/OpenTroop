"""Event visibility — who may see which events, based on audience Groups.

Rules (see ``EventAudience``):
- An event with **no** audience rows is **troop-wide** (visible to all readers).
- Otherwise it is visible only to members of its audience groups.
- Event managers (callers with ``event:write``) bypass the filter entirely.

Both the list query (``visibility_clause``) and single-event checks
(``event_visible_to_member``) share the same semantics so the calendar, detail
view, and future iCal feed agree.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.event_audience import EventAudience


def visibility_clause(member_group_ids: Collection[uuid.UUID]) -> ColumnElement[bool]:
    """SQLAlchemy predicate selecting events visible to a member with these groups.

    An event is visible when it has no audience (troop-wide) or its audience
    includes one of the member's groups. Tenant scoping comes from the session-level
    filter, but the soft-delete predicate is carried **explicitly**: the sync pull
    endpoints evaluate this clause under ``include_deleted()`` (tombstones must
    flow), and without it deleted audience rows would grant or withhold visibility.
    """
    scoped = select(EventAudience.event_id).where(EventAudience.is_deleted.is_(False)).distinct()
    allowed = (
        select(EventAudience.event_id)
        .where(
            EventAudience.group_id.in_(member_group_ids),
            EventAudience.is_deleted.is_(False),
        )
        .distinct()
    )
    return or_(Event.id.not_in(scoped), Event.id.in_(allowed))


def event_visible_to_member(
    event_id: uuid.UUID,
    member_group_ids: Collection[uuid.UUID],
    session: Session,
) -> bool:
    """Return whether a single event is visible to a member with these groups."""
    audience = set(
        session.scalars(
            select(EventAudience.group_id).where(EventAudience.event_id == event_id)
        ).all()
    )
    if not audience:
        return True
    return bool(audience & set(member_group_ids))
