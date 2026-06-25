"""Group membership resolution.

A Group's effective membership is the union of explicit (manual) inclusions and
any dynamically rule-derived members. Event visibility, distribution lists, and
report scoping all resolve groups through ``resolve_group_members`` so the rules
live in exactly one place — mirroring ``app.core.permissions.resolve_permissions``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.group import GroupMember, GroupRoleRule
from app.models.member import Member
from app.models.role import MemberRoleAssignment


def resolve_group_members(group_id: uuid.UUID, session: Session) -> frozenset[uuid.UUID]:
    """Return the resolved set of member IDs belonging to a group.

    The set is the union of:
    - manual inclusions (``GroupMember`` rows), and
    - dynamic members — everyone *directly* assigned a role named by a
      ``GroupRoleRule`` (no role-hierarchy expansion).

    Soft-deleted members, memberships, and rules are excluded.
    """
    manual = set(
        session.scalars(
            select(GroupMember.member_id).where(
                GroupMember.group_id == group_id,
                GroupMember.is_deleted.is_(False),
            )
        ).all()
    )

    rule_role_ids = set(
        session.scalars(
            select(GroupRoleRule.role_id).where(
                GroupRoleRule.group_id == group_id,
                GroupRoleRule.is_deleted.is_(False),
            )
        ).all()
    )

    dynamic: set[uuid.UUID] = set()
    if rule_role_ids:
        dynamic = set(
            session.scalars(
                select(MemberRoleAssignment.member_id).where(
                    MemberRoleAssignment.role_id.in_(rule_role_ids),
                    MemberRoleAssignment.is_deleted.is_(False),
                )
            ).all()
        )

    candidates = manual | dynamic
    if not candidates:
        return frozenset()

    # Drop any candidate that has since been soft-deleted as a member.
    live = session.scalars(
        select(Member.id).where(
            Member.id.in_(candidates),
            Member.is_deleted.is_(False),
        )
    ).all()
    return frozenset(live)


def member_group_ids(member_id: uuid.UUID, session: Session) -> frozenset[uuid.UUID]:
    """Return the set of group IDs a member belongs to — the inverse of resolution.

    Unions the member's manual ``GroupMember`` inclusions with the dynamic groups
    whose ``GroupRoleRule`` names a role the member is directly assigned. Used by
    event-visibility filtering (and, later, the per-member iCal feed).
    """
    manual = set(
        session.scalars(
            select(GroupMember.group_id).where(
                GroupMember.member_id == member_id,
                GroupMember.is_deleted.is_(False),
            )
        ).all()
    )

    role_ids = set(
        session.scalars(
            select(MemberRoleAssignment.role_id).where(
                MemberRoleAssignment.member_id == member_id,
                MemberRoleAssignment.is_deleted.is_(False),
            )
        ).all()
    )

    dynamic: set[uuid.UUID] = set()
    if role_ids:
        dynamic = set(
            session.scalars(
                select(GroupRoleRule.group_id).where(
                    GroupRoleRule.role_id.in_(role_ids),
                    GroupRoleRule.is_deleted.is_(False),
                )
            ).all()
        )

    return frozenset(manual | dynamic)
