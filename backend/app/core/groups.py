"""Group membership resolution.

A Group's effective membership is the union of explicit (manual) inclusions and
dynamically rule-derived members. Rules are evaluated per dimension and combined
using the group's ``rule_logic`` (AND = intersection, OR = union). Manual members
are always included regardless of rule logic.

Event visibility, distribution lists, and report scoping all resolve groups
through ``resolve_group_members`` so the rules live in exactly one place —
mirroring ``app.core.permissions.resolve_permissions``.
"""

from __future__ import annotations

import uuid
from functools import reduce
from typing import TYPE_CHECKING

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import current_assignment_clause
from app.models.enums import MemberStatus, MemberType, RuleDimension, RuleLogic
from app.models.group import Group, GroupMember, GroupRule
from app.models.member import Member
from app.models.rbac import MemberPositionAssignment
from app.models.relationship import MemberRelationship

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Rule evaluation — one function per dimension
# ---------------------------------------------------------------------------


def _members_by_type(values: list[str], session: Session) -> set[uuid.UUID]:
    """Members whose member_type is in *values*."""
    types = [MemberType(v) for v in values]
    return set(
        session.scalars(
            select(Member.id).where(
                Member.member_type.in_(types),
                Member.is_deleted.is_(False),
            )
        ).all()
    )


def _members_by_status(values: list[str], session: Session) -> set[uuid.UUID]:
    """Members whose membership_status is in *values*."""
    statuses = [MemberStatus(v) for v in values]
    return set(
        session.scalars(
            select(Member.id).where(
                Member.membership_status.in_(statuses),
                Member.is_deleted.is_(False),
            )
        ).all()
    )


def _members_by_bool_field(field_name: str, session: Session) -> set[uuid.UUID]:
    """Members where a boolean field is True."""
    col = getattr(Member, field_name)
    return set(
        session.scalars(
            select(Member.id).where(
                col.is_(True),
                Member.is_deleted.is_(False),
            )
        ).all()
    )


def _members_by_position(values: list[str], session: Session) -> set[uuid.UUID]:
    """Members *currently* holding any of the named positions.

    Filters to live terms (``current_assignment_clause``) so a member who termed out
    of a position no longer matches a position rule (e.g. an ex-SPL drops out of PLC).
    """
    position_ids = [uuid.UUID(v) for v in values]
    return set(
        session.scalars(
            select(MemberPositionAssignment.member_id).where(
                MemberPositionAssignment.position_id.in_(position_ids),
                current_assignment_clause(),
            )
        ).all()
    )


def _parents_of(
    child_ids: set[uuid.UUID] | frozenset[uuid.UUID], session: Session
) -> set[uuid.UUID]:
    """Members who are a parent or guardian of any of the given child IDs."""
    if not child_ids:
        return set()
    from app.models.enums import RelationshipType

    return set(
        session.scalars(
            select(MemberRelationship.from_member_id).where(
                MemberRelationship.to_member_id.in_(child_ids),
                MemberRelationship.relationship_type.in_(
                    [RelationshipType.PARENT_OF, RelationshipType.GUARDIAN_OF]
                ),
                MemberRelationship.is_deleted.is_(False),
            )
        ).all()
    )


def evaluate_rule(
    dimension: RuleDimension,
    values: list[str] | None,
    session: Session,
    *,
    _visited: set[uuid.UUID] | None = None,
) -> set[uuid.UUID]:
    """Evaluate a single rule dimension, returning the matching member IDs.

    This function is the shared building block for group resolution and,
    eventually, the report builder's filter engine.
    """
    match dimension:
        case RuleDimension.MEMBER_TYPE:
            return _members_by_type(values or [], session)
        case RuleDimension.MEMBERSHIP_STATUS:
            return _members_by_status(values or [], session)
        case RuleDimension.OA_MEMBER:
            return _members_by_bool_field("oa_member", session)
        case RuleDimension.OA_ACTIVE:
            return _members_by_bool_field("oa_active", session)
        case RuleDimension.POSITION:
            return _members_by_position(values or [], session)
        case RuleDimension.GROUP_MEMBER:
            combined: set[uuid.UUID] = set()
            for ref_group_id in values or []:
                combined |= resolve_group_members(
                    uuid.UUID(ref_group_id), session, _visited=_visited
                )
            return combined
        case RuleDimension.RANK:
            # Phase 2 — no-op until Pillar 4 advancement model exists
            return set()

    return set()


# ---------------------------------------------------------------------------
# Public resolvers
# ---------------------------------------------------------------------------


def resolve_group_members(
    group_id: uuid.UUID,
    session: Session,
    _visited: set[uuid.UUID] | None = None,
) -> frozenset[uuid.UUID]:
    """Return the resolved set of member IDs belonging to a group.

    The set is the union of:
    - manual inclusions (``GroupMember`` rows), and
    - dynamic members — evaluated from ``GroupRule`` rows per dimension.

    Multiple rules are combined using the group's ``rule_logic``:
    - AND: a member must match *all* rules (intersection).
    - OR: a member matching *any* rule is included (union).

    Manual members are always included regardless of rule logic. If the group has
    ``include_parents`` set, the parents/guardians of the resolved set are added in
    a final pass (after manual ∪ dynamic). Soft-deleted members, memberships, and
    rules are excluded.
    """
    # Cycle guard — prevents infinite recursion for group-of-groups
    if _visited is None:
        _visited = set()
    if group_id in _visited:
        return frozenset()
    _visited.add(group_id)

    # Load the group to get rule_logic
    group = session.get(Group, group_id)
    if group is None or group.is_deleted:
        return frozenset()

    # 1. Manual members — always included
    manual = set(
        session.scalars(
            select(GroupMember.member_id).where(
                GroupMember.group_id == group_id,
                GroupMember.is_deleted.is_(False),
            )
        ).all()
    )

    # 2. Load and evaluate all rules
    rules = session.scalars(
        select(GroupRule).where(
            GroupRule.group_id == group_id,
            GroupRule.is_deleted.is_(False),
        )
    ).all()

    rule_sets: list[set[uuid.UUID]] = []
    for rule in rules:
        result = evaluate_rule(rule.dimension, rule.values, session, _visited=_visited)
        rule_sets.append(result)

    # 3. Combine rule results based on rule_logic
    if not rule_sets:
        dynamic: set[uuid.UUID] = set()
    elif group.rule_logic is RuleLogic.AND:
        dynamic = reduce(set.intersection, rule_sets)
    else:  # OR
        dynamic = reduce(set.union, rule_sets)

    # 4. Union manual + dynamic
    candidates = manual | dynamic
    if not candidates and not group.include_parents:
        return frozenset()

    # 5. Filter to non-deleted members
    resolved = set(
        session.scalars(
            select(Member.id).where(
                Member.id.in_(candidates),
                Member.is_deleted.is_(False),
            )
        ).all()
    )

    # 6. Optionally expand to include parents/guardians of the resolved set.
    #    Runs after manual ∪ dynamic so it reads as "...and their parents/guardians".
    if group.include_parents and resolved:
        parents = _parents_of(resolved, session)
        if parents:
            resolved |= set(
                session.scalars(
                    select(Member.id).where(
                        Member.id.in_(parents),
                        Member.is_deleted.is_(False),
                    )
                ).all()
            )

    return frozenset(resolved)


def member_group_ids(member_id: uuid.UUID, session: Session) -> frozenset[uuid.UUID]:
    """Return the set of group IDs a member belongs to — the inverse of resolution.

    Unions the member's manual ``GroupMember`` inclusions with any groups whose
    rules match this member. Used by event-visibility filtering and the per-member
    iCal feed.
    """
    # Manual memberships
    manual = set(
        session.scalars(
            select(GroupMember.group_id).where(
                GroupMember.member_id == member_id,
                GroupMember.is_deleted.is_(False),
            )
        ).all()
    )

    # Load the member to check attribute-based rules
    member = session.get(Member, member_id)
    if member is None or member.is_deleted:
        return frozenset(manual)

    # For each non-deleted group whose membership is computed (has rules) or expands to
    # parents (include_parents), check if this member is in the resolved set. The
    # include_parents groups must be scanned too: a parent of a *manually* added member
    # belongs to such a group even though it has no rules. Brute-force is acceptable for
    # troop-scale data (< 30 groups); for larger scale we'd want a reverse index.
    computed_group_ids = session.scalars(
        select(Group.id).where(
            Group.is_deleted.is_(False),
            or_(
                Group.id.in_(select(GroupRule.group_id).where(GroupRule.is_deleted.is_(False))),
                Group.include_parents.is_(True),
            ),
        )
    ).all()

    dynamic: set[uuid.UUID] = set()
    for gid in computed_group_ids:
        if gid in manual:
            continue  # Already included
        resolved = resolve_group_members(gid, session)
        if member_id in resolved:
            dynamic.add(gid)

    return frozenset(manual | dynamic)
