"""Tests for the application-layer automatic tenant scoping.

Exercises the ``do_orm_execute`` read filter and ``before_flush`` write stamp
(registered in ``app.core.database``) directly against ``db_session``, driving the
current-tenant context with ``tenant_scope`` / ``unscoped`` rather than through the
HTTP request path. See ``docs/spec/tenant-data-access.md``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenant_context import tenant_scope, unscoped
from app.models.enums import MemberType
from app.models.event import Event
from app.models.event_type import EventType
from app.models.location import Location
from app.models.member import Member
from tests.conftest import TENANT_A, TENANT_B


def _make_member(tenant_id: uuid.UUID, first: str, **kw: object) -> Member:
    return Member(
        tenant_id=tenant_id,
        first_name=first,
        last_name="Test",
        member_type=MemberType.ADULT,
        **kw,
    )


def test_read_filter_scopes_select_to_current_tenant(db_session: Session) -> None:
    db_session.add(_make_member(TENANT_A, "Anna"))
    db_session.add(_make_member(TENANT_B, "Bob"))
    db_session.commit()

    with tenant_scope(TENANT_A):
        rows = db_session.scalars(select(Member)).all()

    assert {m.first_name for m in rows} == {"Anna"}


def test_read_filter_inactive_without_tenant_returns_all(db_session: Session) -> None:
    """With no tenant set (platform / fixture path) the filter is a no-op."""
    db_session.add(_make_member(TENANT_A, "Anna"))
    db_session.add(_make_member(TENANT_B, "Bob"))
    db_session.commit()

    rows = db_session.scalars(select(Member)).all()

    assert {m.first_name for m in rows} == {"Anna", "Bob"}


def test_write_stamp_sets_tenant_id_from_context(db_session: Session) -> None:
    with tenant_scope(TENANT_A):
        member = Member(
            first_name="Unstamped",
            last_name="Test",
            member_type=MemberType.ADULT,
        )
        db_session.add(member)
        db_session.commit()

    assert member.tenant_id == TENANT_A


def test_write_stamp_does_not_override_explicit_tenant(db_session: Session) -> None:
    with tenant_scope(TENANT_A):
        member = _make_member(TENANT_B, "Explicit")
        db_session.add(member)
        db_session.commit()

    assert member.tenant_id == TENANT_B


def test_unscoped_returns_cross_tenant_rows(db_session: Session) -> None:
    db_session.add(_make_member(TENANT_A, "Anna"))
    db_session.add(_make_member(TENANT_B, "Bob"))
    db_session.commit()

    with tenant_scope(TENANT_A), unscoped():
        rows = db_session.scalars(select(Member)).all()

    assert {m.first_name for m in rows} == {"Anna", "Bob"}


def test_unscoped_still_honors_an_explicit_user_constraint(db_session: Session) -> None:
    """The memberships-lookup pattern: bypass removes tenant scoping, not user scoping."""
    me = uuid.uuid4()
    other = uuid.uuid4()
    db_session.add(_make_member(TENANT_A, "Mine-A", user_id=me))
    db_session.add(_make_member(TENANT_B, "Mine-B", user_id=me))
    db_session.add(_make_member(TENANT_A, "Theirs", user_id=other))
    db_session.commit()

    with unscoped():
        rows = db_session.scalars(select(Member).where(Member.user_id == me)).all()

    assert {m.first_name for m in rows} == {"Mine-A", "Mine-B"}


def test_join_filters_aliased_entity(db_session: Session) -> None:
    """include_aliases=True scopes joined/relationship entities, not just the top level."""
    for tid, label in ((TENANT_A, "A"), (TENANT_B, "B")):
        etype = EventType(tenant_id=tid, name=f"Meeting-{label}")
        loc = Location(tenant_id=tid, name=f"Hall-{label}")
        db_session.add_all([etype, loc])
        db_session.flush()
        db_session.add(
            Event(
                tenant_id=tid,
                name=f"Event-{label}",
                event_type_id=etype.id,
                location_id=loc.id,
                scheduled_start=datetime(2026, 1, 1, tzinfo=UTC),
                scheduled_end=datetime(2026, 1, 2, tzinfo=UTC),
            )
        )
    db_session.commit()

    with tenant_scope(TENANT_A):
        rows = db_session.scalars(select(Event).join(Event.location)).all()

    assert {e.name for e in rows} == {"Event-A"}


def test_relationship_load_is_tenant_filtered(db_session: Session) -> None:
    """A many-to-one relationship load whose target is in another tenant resolves None."""
    etype = EventType(tenant_id=TENANT_A, name="Meeting")
    loc = Location(tenant_id=TENANT_A, name="Hall")
    db_session.add_all([etype, loc])
    db_session.flush()
    event = Event(
        tenant_id=TENANT_A,
        name="Event-A",
        event_type_id=etype.id,
        location_id=loc.id,
        scheduled_start=datetime(2026, 1, 1, tzinfo=UTC),
        scheduled_end=datetime(2026, 1, 2, tzinfo=UTC),
    )
    db_session.add(event)
    db_session.commit()

    # Simulate the leak the filter must catch: the referenced location now lives in
    # another tenant. A fresh session avoids the identity map short-circuiting the load.
    loc.tenant_id = TENANT_B
    db_session.commit()
    db_session.expunge_all()

    with tenant_scope(TENANT_A):
        reloaded = db_session.scalars(select(Event)).one()
        assert reloaded.location is None
