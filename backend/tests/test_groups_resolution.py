"""Unit tests for resolve_group_members (manual + dynamic union, soft-delete)."""

import uuid

from app.core.groups import resolve_group_members
from app.models.enums import GroupType, MemberType
from app.models.group import Group, GroupMember, GroupPositionRule
from app.models.member import Member
from app.models.rbac import MemberPositionAssignment, Position

_TENANT = uuid.UUID("10000000-0000-0000-0000-000000000001")


def _member(session, first_name: str) -> Member:
    m = Member(
        tenant_id=_TENANT,
        first_name=first_name,
        last_name="Test",
        member_type=MemberType.SCOUT,
    )
    session.add(m)
    session.flush()
    return m


def test_union_of_manual_and_dynamic(db_session) -> None:
    group = Group(tenant_id=_TENANT, name="PLC", group_type=GroupType.DYNAMIC)
    position = Position(tenant_id=_TENANT, name="Patrol Leader", slug="patrol-leader")
    session = db_session
    session.add_all([group, position])
    session.flush()

    manual_m = _member(session, "Manual")
    dynamic_m = _member(session, "Dynamic")
    both_m = _member(session, "Both")

    session.add(GroupMember(tenant_id=_TENANT, group_id=group.id, member_id=manual_m.id))
    session.add(GroupMember(tenant_id=_TENANT, group_id=group.id, member_id=both_m.id))
    session.add(GroupPositionRule(tenant_id=_TENANT, group_id=group.id, position_id=position.id))
    session.add(
        MemberPositionAssignment(tenant_id=_TENANT, member_id=dynamic_m.id, position_id=position.id)
    )
    session.add(
        MemberPositionAssignment(tenant_id=_TENANT, member_id=both_m.id, position_id=position.id)
    )
    session.flush()

    resolved = resolve_group_members(group.id, session)
    assert resolved == frozenset({manual_m.id, dynamic_m.id, both_m.id})


def test_soft_deleted_members_excluded(db_session) -> None:
    session = db_session
    group = Group(tenant_id=_TENANT, name="Wolf", group_type=GroupType.PATROL)
    session.add(group)
    session.flush()

    live = _member(session, "Live")
    gone = _member(session, "Gone")
    gone.is_deleted = True
    session.add(GroupMember(tenant_id=_TENANT, group_id=group.id, member_id=live.id))
    session.add(GroupMember(tenant_id=_TENANT, group_id=group.id, member_id=gone.id))
    session.flush()

    assert resolve_group_members(group.id, session) == frozenset({live.id})


def test_empty_group_resolves_empty(db_session) -> None:
    session = db_session
    group = Group(tenant_id=_TENANT, name="Empty", group_type=GroupType.MANUAL)
    session.add(group)
    session.flush()
    assert resolve_group_members(group.id, session) == frozenset()
