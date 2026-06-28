"""Unit tests for resolve_group_members (manual + dynamic, multi-dimension rules, AND/OR logic, cycle detection)."""

import uuid

from app.core.groups import resolve_group_members
from app.models.enums import (
    GroupType,
    MemberStatus,
    MemberType,
    RelationshipType,
    RuleDimension,
    RuleLogic,
)
from app.models.group import Group, GroupMember, GroupRule
from app.models.member import Member
from app.models.rbac import MemberPositionAssignment, Position
from app.models.relationship import MemberRelationship

_TENANT = uuid.UUID("10000000-0000-0000-0000-000000000001")


def _member(
    session,
    first_name: str,
    member_type: MemberType = MemberType.SCOUT,
    membership_status: MemberStatus = MemberStatus.ACTIVE,
    oa_member: bool = False,
) -> Member:
    m = Member(
        tenant_id=_TENANT,
        first_name=first_name,
        last_name="Test",
        member_type=member_type,
        membership_status=membership_status,
        oa_member=oa_member,
    )
    session.add(m)
    session.flush()
    return m


def test_union_of_manual_and_dynamic_position_rule(db_session) -> None:
    group = Group(
        tenant_id=_TENANT, name="PLC", group_type=GroupType.DYNAMIC, rule_logic=RuleLogic.OR
    )
    position = Position(tenant_id=_TENANT, name="Patrol Leader", slug="patrol-leader")
    session = db_session
    session.add_all([group, position])
    session.flush()

    manual_m = _member(session, "Manual")
    dynamic_m = _member(session, "Dynamic")
    both_m = _member(session, "Both")

    session.add(GroupMember(tenant_id=_TENANT, group_id=group.id, member_id=manual_m.id))
    session.add(GroupMember(tenant_id=_TENANT, group_id=group.id, member_id=both_m.id))
    session.add(
        GroupRule(
            tenant_id=_TENANT,
            group_id=group.id,
            dimension=RuleDimension.POSITION,
            values=[str(position.id)],
        )
    )
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


def test_boolean_and_attribute_rules(db_session) -> None:
    session = db_session
    group = Group(
        tenant_id=_TENANT,
        name="Active OA Scouts",
        group_type=GroupType.DYNAMIC,
        rule_logic=RuleLogic.AND,
    )
    session.add(group)
    session.flush()

    scout_oa = _member(session, "ScoutOA", member_type=MemberType.SCOUT, oa_member=True)
    adult_oa = _member(session, "AdultOA", member_type=MemberType.ADULT, oa_member=True)
    scout_non_oa = _member(session, "ScoutNonOA", member_type=MemberType.SCOUT, oa_member=False)

    # Rule 1: MemberType = SCOUT
    session.add(
        GroupRule(
            tenant_id=_TENANT,
            group_id=group.id,
            dimension=RuleDimension.MEMBER_TYPE,
            values=["scout"],
        )
    )
    # Rule 2: OA member = True
    session.add(
        GroupRule(
            tenant_id=_TENANT, group_id=group.id, dimension=RuleDimension.OA_MEMBER, values=None
        )
    )
    session.flush()

    # With AND, only ScoutOA matches both
    assert resolve_group_members(group.id, session) == frozenset({scout_oa.id})

    # Change to OR logic
    group.rule_logic = RuleLogic.OR
    session.flush()

    # With OR, scout_oa (both), adult_oa (OA), scout_non_oa (Scout) all match
    assert resolve_group_members(group.id, session) == frozenset(
        {scout_oa.id, adult_oa.id, scout_non_oa.id}
    )


def test_group_member_recursive_rule(db_session) -> None:
    session = db_session
    parent_group = Group(
        tenant_id=_TENANT, name="ParentGroup", group_type=GroupType.DYNAMIC, rule_logic=RuleLogic.OR
    )
    child_group = Group(tenant_id=_TENANT, name="ChildGroup", group_type=GroupType.MANUAL)
    session.add_all([parent_group, child_group])
    session.flush()

    member_in_child = _member(session, "ChildMember")
    member_in_parent = _member(session, "ParentMember")

    session.add(
        GroupMember(tenant_id=_TENANT, group_id=child_group.id, member_id=member_in_child.id)
    )
    session.add(
        GroupMember(tenant_id=_TENANT, group_id=parent_group.id, member_id=member_in_parent.id)
    )
    session.add(
        GroupRule(
            tenant_id=_TENANT,
            group_id=parent_group.id,
            dimension=RuleDimension.GROUP_MEMBER,
            values=[str(child_group.id)],
        )
    )
    session.flush()

    # Parent group should resolve both members
    assert resolve_group_members(parent_group.id, session) == frozenset(
        {member_in_child.id, member_in_parent.id}
    )


def test_relationship_rule(db_session) -> None:
    session = db_session
    parents_group = Group(tenant_id=_TENANT, name="Eagle Parents", group_type=GroupType.DYNAMIC)
    scouts_group = Group(tenant_id=_TENANT, name="Eagle Scouts", group_type=GroupType.MANUAL)
    session.add_all([parents_group, scouts_group])
    session.flush()

    scout = _member(session, "Scout")
    parent = _member(session, "Parent", member_type=MemberType.ADULT)

    # Add relationship
    session.add(
        MemberRelationship(
            tenant_id=_TENANT,
            from_member_id=parent.id,
            to_member_id=scout.id,
            relationship_type=RelationshipType.PARENT_OF,
        )
    )
    session.add(GroupMember(tenant_id=_TENANT, group_id=scouts_group.id, member_id=scout.id))
    session.add(
        GroupRule(
            tenant_id=_TENANT,
            group_id=parents_group.id,
            dimension=RuleDimension.RELATIONSHIP,
            values=[str(scouts_group.id)],
        )
    )
    session.flush()

    # Parents group should resolve parent
    assert resolve_group_members(parents_group.id, session) == frozenset({parent.id})


def test_cycle_detection(db_session) -> None:
    session = db_session
    group_a = Group(tenant_id=_TENANT, name="GroupA", group_type=GroupType.DYNAMIC)
    group_b = Group(tenant_id=_TENANT, name="GroupB", group_type=GroupType.DYNAMIC)
    session.add_all([group_a, group_b])
    session.flush()

    member_a = _member(session, "MemberA")
    member_b = _member(session, "MemberB")

    session.add(GroupMember(tenant_id=_TENANT, group_id=group_a.id, member_id=member_a.id))
    session.add(GroupMember(tenant_id=_TENANT, group_id=group_b.id, member_id=member_b.id))

    # A depends on B, B depends on A (cycle)
    session.add(
        GroupRule(
            tenant_id=_TENANT,
            group_id=group_a.id,
            dimension=RuleDimension.GROUP_MEMBER,
            values=[str(group_b.id)],
        )
    )
    session.add(
        GroupRule(
            tenant_id=_TENANT,
            group_id=group_b.id,
            dimension=RuleDimension.GROUP_MEMBER,
            values=[str(group_a.id)],
        )
    )
    session.flush()

    # Resolving either should not crash and should union both members cleanly
    assert resolve_group_members(group_a.id, session) == frozenset({member_a.id, member_b.id})
    assert resolve_group_members(group_b.id, session) == frozenset({member_a.id, member_b.id})
