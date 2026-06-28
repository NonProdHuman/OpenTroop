"""Unit tests for event visibility helpers and member_group_ids."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.event_visibility import event_visible_to_member, visibility_clause
from app.core.groups import member_group_ids
from app.models.enums import GroupType, MemberType
from app.models.event import Event
from app.models.event_audience import EventAudience
from app.models.group import Group, GroupMember, GroupPositionRule
from app.models.member import Member
from app.models.rbac import MemberPositionAssignment, Position

_TENANT = uuid.UUID("10000000-0000-0000-0000-000000000001")


def _event(session, name: str) -> Event:
    e = Event(
        tenant_id=_TENANT,
        name=name,
        event_type_id=uuid.uuid4(),
        scheduled_start=datetime(2026, 7, 1, tzinfo=UTC),
        scheduled_end=datetime(2026, 7, 2, tzinfo=UTC),
    )
    session.add(e)
    session.flush()
    return e


def _member(session, name: str = "M") -> Member:
    m = Member(tenant_id=_TENANT, first_name=name, last_name="X", member_type=MemberType.SCOUT)
    session.add(m)
    session.flush()
    return m


def _group(session, name: str, group_type: GroupType = GroupType.MANUAL) -> Group:
    g = Group(tenant_id=_TENANT, name=name, group_type=group_type)
    session.add(g)
    session.flush()
    return g


def test_member_group_ids_manual_and_dynamic(db_session) -> None:
    session = db_session
    manual_g = _group(session, "Wolf", GroupType.PATROL)
    dynamic_g = _group(session, "PLC", GroupType.DYNAMIC)
    position = Position(tenant_id=_TENANT, name="Patrol Leader", slug="pl")
    member = _member(session)
    session.add(position)
    session.flush()

    session.add(GroupMember(tenant_id=_TENANT, group_id=manual_g.id, member_id=member.id))
    session.add(
        GroupPositionRule(tenant_id=_TENANT, group_id=dynamic_g.id, position_id=position.id)
    )
    session.add(
        MemberPositionAssignment(tenant_id=_TENANT, member_id=member.id, position_id=position.id)
    )
    session.flush()

    assert member_group_ids(member.id, session) == frozenset({manual_g.id, dynamic_g.id})


def test_event_with_no_audience_is_troop_wide(db_session) -> None:
    session = db_session
    event = _event(session, "All-troop meeting")
    # Visible even to a member with no groups at all.
    assert event_visible_to_member(event.id, frozenset(), session) is True


def test_scoped_event_visible_only_to_audience(db_session) -> None:
    session = db_session
    group = _group(session, "Wolf", GroupType.PATROL)
    other = _group(session, "Bear", GroupType.PATROL)
    event = _event(session, "Wolf-only hike")
    session.add(EventAudience(tenant_id=_TENANT, event_id=event.id, group_id=group.id))
    session.flush()

    assert event_visible_to_member(event.id, frozenset({group.id}), session) is True
    assert event_visible_to_member(event.id, frozenset({other.id}), session) is False
    assert event_visible_to_member(event.id, frozenset(), session) is False


def test_deleted_audience_reverts_to_troop_wide(db_session) -> None:
    session = db_session
    group = _group(session, "Wolf", GroupType.PATROL)
    event = _event(session, "Hike")
    audience = EventAudience(tenant_id=_TENANT, event_id=event.id, group_id=group.id)
    session.add(audience)
    session.flush()
    audience.is_deleted = True
    session.flush()

    assert event_visible_to_member(event.id, frozenset(), session) is True


def test_visibility_clause_in_query(db_session) -> None:
    session = db_session
    group = _group(session, "Wolf", GroupType.PATROL)
    troop_wide = _event(session, "Troop-wide")
    scoped = _event(session, "Scoped")
    session.add(EventAudience(tenant_id=_TENANT, event_id=scoped.id, group_id=group.id))
    session.flush()

    in_group = session.scalars(
        select(Event).where(
            Event.tenant_id == _TENANT, visibility_clause(frozenset({group.id}), _TENANT)
        )
    ).all()
    assert {e.id for e in in_group} == {troop_wide.id, scoped.id}

    no_group = session.scalars(
        select(Event).where(Event.tenant_id == _TENANT, visibility_clause(frozenset(), _TENANT))
    ).all()
    assert {e.id for e in no_group} == {troop_wide.id}
