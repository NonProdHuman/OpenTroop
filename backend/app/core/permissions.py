from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Permission
from app.models.role import MemberRoleAssignment, Role, RoleMembership, RolePermission


def resolve_permissions(member_id: uuid.UUID, session: Session) -> frozenset[Permission]:
    """Return the full permission set for a member, following role hierarchy.

    Walks RoleMembership upward transitively — a member assigned to Scoutmaster
    inherits all permissions of every functional group Scoutmaster belongs to.
    Short-circuits to all permissions if any resolved role has is_admin=True.
    """
    direct_role_ids = set(
        session.scalars(
            select(MemberRoleAssignment.role_id).where(
                MemberRoleAssignment.member_id == member_id,
                MemberRoleAssignment.is_deleted.is_(False),
            )
        ).all()
    )

    all_role_ids = _expand_role_ids(direct_role_ids, session)

    is_admin = session.scalars(
        select(Role.id).where(
            Role.id.in_(all_role_ids),
            Role.is_admin.is_(True),
            Role.is_deleted.is_(False),
        )
    ).first()
    if is_admin is not None:
        return frozenset(Permission)

    perms = session.scalars(
        select(RolePermission.permission).where(
            RolePermission.role_id.in_(all_role_ids),
            RolePermission.is_deleted.is_(False),
        )
    ).all()

    return frozenset(perms)


def _expand_role_ids(
    role_ids: set[uuid.UUID],
    session: Session,
    visited: set[uuid.UUID] | None = None,
) -> set[uuid.UUID]:
    """Walk RoleMembership upward, collecting all group role IDs transitively.

    Cycle-safe: visited tracks every role ID already processed.
    In practice depth is 1–2 levels (position → functional group).
    """
    if visited is None:
        visited = set()

    new_ids = role_ids - visited
    if not new_ids:
        return visited

    visited |= new_ids

    parent_ids = set(
        session.scalars(
            select(RoleMembership.group_role_id).where(
                RoleMembership.member_role_id.in_(new_ids),
                RoleMembership.is_deleted.is_(False),
            )
        ).all()
    )

    return _expand_role_ids(parent_ids, session, visited)
