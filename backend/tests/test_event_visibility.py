"""Unit tests for event visibility helpers and member_group_ids."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.event_visibility import event_visible_to_member, visibility_clause
from app.core.groups import member_group_ids
from app.core.tenant_context import tenant_scope
from app.models.enums import GroupType, MemberType, RelationshipType, RuleDimension
from app.models.event import Event
from app.models.event_audience import EventAudience
from app.models.group import Group, GroupMember, GroupRule
from app.models.member import Member
from app.models.rbac import MemberPositionAssignment, Position
from app.models.relationship import MemberRelationship

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


def _group(session, name: str, group_type: GroupType = GroupType.CUSTOM) -> Group:
    g = Group(tenant_id=_TENANT, name=name, group_type=group_type)
    session.add(g)
    session.flush()
    return g


def test_member_group_ids_manual_and_dynamic(db_session) -> None:
    session = db_session
    manual_g = _group(session, "Wolf", GroupType.PATROL)
    dynamic_g = _group(session, "PLC", GroupType.CUSTOM)
    position = Position(tenant_id=_TENANT, name="Patrol Leader", slug="pl")
    member = _member(session)
    session.add(position)
    session.flush()

    session.add(GroupMember(tenant_id=_TENANT, group_id=manual_g.id, member_id=member.id))
    session.add(
        GroupRule(
            tenant_id=_TENANT,
            group_id=dynamic_g.id,
            dimension=RuleDimension.POSITION,
            values=[str(position.id)],
        )
    )
    session.add(
        MemberPositionAssignment(tenant_id=_TENANT, member_id=member.id, position_id=position.id)
    )
    session.flush()

    assert member_group_ids(member.id, session) == frozenset({manual_g.id, dynamic_g.id})


def test_member_group_ids_credits_include_parents(db_session) -> None:
    """A parent belongs to an include_parents group even when it has only manual members
    (no rules) — so event visibility and the iCal feed treat the parent as a member."""
    session = db_session
    group = _group(session, "Patrol + Parents", GroupType.CUSTOM)
    group.include_parents = True
    scout = _member(session, "Scout")
    parent = Member(
        tenant_id=_TENANT, first_name="Parent", last_name="X", member_type=MemberType.ADULT
    )
    session.add(parent)
    session.flush()
    session.add(
        MemberRelationship(
            tenant_id=_TENANT,
            from_member_id=parent.id,
            to_member_id=scout.id,
            relationship_type=RelationshipType.PARENT_OF,
        )
    )
    session.add(GroupMember(tenant_id=_TENANT, group_id=group.id, member_id=scout.id))
    session.flush()

    assert group.id in member_group_ids(parent.id, session)
    assert group.id in member_group_ids(scout.id, session)


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

    # The soft-deleted audience is excluded by the session-level filter (tenant scope).
    with tenant_scope(_TENANT):
        assert event_visible_to_member(event.id, frozenset(), session) is True


def test_visibility_clause_in_query(db_session) -> None:
    session = db_session
    group = _group(session, "Wolf", GroupType.PATROL)
    troop_wide = _event(session, "Troop-wide")
    scoped = _event(session, "Scoped")
    session.add(EventAudience(tenant_id=_TENANT, event_id=scoped.id, group_id=group.id))
    session.flush()

    with tenant_scope(_TENANT):
        in_group = session.scalars(
            select(Event).where(visibility_clause(frozenset({group.id})))
        ).all()
        assert {e.id for e in in_group} == {troop_wide.id, scoped.id}

        no_group = session.scalars(select(Event).where(visibility_clause(frozenset()))).all()
        assert {e.id for e in no_group} == {troop_wide.id}
