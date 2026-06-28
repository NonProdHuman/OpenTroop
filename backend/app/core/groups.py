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

from app.models.group import GroupMember, GroupPositionRule
from app.models.member import Member
from app.models.rbac import MemberPositionAssignment


def resolve_group_members(group_id: uuid.UUID, session: Session) -> frozenset[uuid.UUID]:
    """Return the resolved set of member IDs belonging to a group.

    The set is the union of:
    - manual inclusions (``GroupMember`` rows), and
    - dynamic members — everyone holding a position named by a
      ``GroupPositionRule``.

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

    rule_position_ids = set(
        session.scalars(
            select(GroupPositionRule.position_id).where(
                GroupPositionRule.group_id == group_id,
                GroupPositionRule.is_deleted.is_(False),
            )
        ).all()
    )

    dynamic: set[uuid.UUID] = set()
    if rule_position_ids:
        dynamic = set(
            session.scalars(
                select(MemberPositionAssignment.member_id).where(
                    MemberPositionAssignment.position_id.in_(rule_position_ids),
                    MemberPositionAssignment.is_deleted.is_(False),
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
    whose ``GroupPositionRule`` names a position the member holds. Used by
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

    position_ids = set(
        session.scalars(
            select(MemberPositionAssignment.position_id).where(
                MemberPositionAssignment.member_id == member_id,
                MemberPositionAssignment.is_deleted.is_(False),
            )
        ).all()
    )

    dynamic: set[uuid.UUID] = set()
    if position_ids:
        dynamic = set(
            session.scalars(
                select(GroupPositionRule.group_id).where(
                    GroupPositionRule.position_id.in_(position_ids),
                    GroupPositionRule.is_deleted.is_(False),
                )
            ).all()
        )

    return frozenset(manual | dynamic)
