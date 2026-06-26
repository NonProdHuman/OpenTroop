"""Permission resolution: member → positions → functional roles → permissions.

The model is two levels deep (see ``docs/spec/roles-rbac.md``), so resolution is a
flat join with no recursion. ``resolve_permissions`` is written as a **union over
permission sources** so a future direct ``PositionPermission`` source can be added
additively — implement ``_permissions_via_positions`` and add it to ``sources``,
no caller or signature changes. v1 ships only the functional-role source.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Permission
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)


def resolve_permissions(member_id: uuid.UUID, session: Session) -> frozenset[Permission]:
    """Return the full permission set for a member.

    Walks the member's live positions → functional roles → permissions. Returns
    the **full** permission set if any reached functional role is ``is_admin``.
    Soft-deleted assignments, positions, mappings, roles, and permission rows are
    excluded at every hop.
    """
    functional_role_ids = _member_functional_role_ids(member_id, session)
    if not functional_role_ids:
        return frozenset()

    if _has_admin_role(functional_role_ids, session):
        return frozenset(Permission)

    sources: list[frozenset[Permission]] = [
        _permissions_via_functional_roles(functional_role_ids, session),
        # _permissions_via_positions(member_id, session),  # future: direct position grants
    ]
    return frozenset().union(*sources)


def _member_functional_role_ids(member_id: uuid.UUID, session: Session) -> set[uuid.UUID]:
    """Live functional-role IDs reachable from a member's positions."""
    return set(
        session.scalars(
            select(PositionFunctionalRole.functional_role_id)
            .join(
                MemberPositionAssignment,
                MemberPositionAssignment.position_id == PositionFunctionalRole.position_id,
            )
            .join(Position, Position.id == PositionFunctionalRole.position_id)
            .join(
                FunctionalRole,
                FunctionalRole.id == PositionFunctionalRole.functional_role_id,
            )
            .where(
                MemberPositionAssignment.member_id == member_id,
                MemberPositionAssignment.is_deleted.is_(False),
                PositionFunctionalRole.is_deleted.is_(False),
                Position.is_deleted.is_(False),
                FunctionalRole.is_deleted.is_(False),
            )
        ).all()
    )


def _has_admin_role(functional_role_ids: set[uuid.UUID], session: Session) -> bool:
    return (
        session.scalars(
            select(FunctionalRole.id).where(
                FunctionalRole.id.in_(functional_role_ids),
                FunctionalRole.is_admin.is_(True),
                FunctionalRole.is_deleted.is_(False),
            )
        ).first()
        is not None
    )


def _permissions_via_functional_roles(
    functional_role_ids: set[uuid.UUID], session: Session
) -> frozenset[Permission]:
    return frozenset(
        session.scalars(
            select(FunctionalRolePermission.permission).where(
                FunctionalRolePermission.functional_role_id.in_(functional_role_ids),
                FunctionalRolePermission.is_deleted.is_(False),
            )
        ).all()
    )
