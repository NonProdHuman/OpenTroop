"""Permission resolution: member → positions → functional roles → permissions.

The model is two levels deep (see ``docs/spec/roles-rbac.md``), so resolution is a
flat join with no recursion. ``resolve_permissions`` is written as a **union over
permission sources** so a future direct ``PositionPermission`` source can be added
additively — implement ``_permissions_via_positions`` and add it to ``sources``,
no caller or signature changes. v1 ships only the functional-role source.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.orm import Session

from app.models.enums import Permission
from app.models.member import Member
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)


def _utc_today() -> date:
    """Today's date in UTC — the platform stores everything UTC, so term boundaries are too."""
    return datetime.now(UTC).date()


def is_assignment_current(
    is_deleted: bool, end_date: date | None, today: date | None = None
) -> bool:
    """Python form of the assignment currency rule (single source of truth).

    A term is current iff it is not tombstoned and has not ended:
    ``not is_deleted AND (end_date is None OR end_date >= today)``. A *future*
    end_date still counts as current (scheduled turnover). ``start_date`` is not
    gated — a future-dated term is shown as current. Used by the read schema's
    ``is_current``; the SQL twin is :func:`current_assignment_clause`.
    """
    if is_deleted:
        return False
    if end_date is None:
        return True
    return end_date >= (today or _utc_today())


def current_assignment_clause(today: date | None = None) -> ColumnElement[bool]:
    """SQL form of the assignment currency rule, for use in ``.where(...)``.

    Mirrors :func:`is_assignment_current`. Every query that asks "does this member
    *currently* hold a position" — the permission resolver, group position rules —
    filters on this so the rule lives in exactly one place.
    """
    cutoff = today or _utc_today()
    return and_(
        MemberPositionAssignment.is_deleted.is_(False),
        or_(
            MemberPositionAssignment.end_date.is_(None),
            MemberPositionAssignment.end_date >= cutoff,
        ),
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


def member_is_admin(member_id: uuid.UUID, session: Session) -> bool:
    """True iff the member *currently* holds a position mapped to an ``is_admin`` role.

    Structural check, distinct from ``resolve_permissions`` — an admin's resolved set
    is *all* permissions, which can't be told apart from a custom role that merely
    grants everything. Guardrails on privileged position writes need the structural
    fact, so this walks the same live-position → functional-role hops directly.
    """
    functional_role_ids = _member_functional_role_ids(member_id, session)
    return bool(functional_role_ids) and _has_admin_role(functional_role_ids, session)


def position_is_privileged(position_id: uuid.UUID, tenant_id: uuid.UUID, session: Session) -> bool:
    """True iff assigning this position confers admin or meta-governance power.

    A position is privileged when any live mapping reaches a live functional role
    that is ``is_admin`` or grants ``Permission.ROLE_MANAGE``. Writes to terms of a
    privileged position are restricted to administrators (``member_is_admin``) so a
    ``role:assign`` holder cannot escalate themselves (GH-175 Finding 1).
    """
    return (
        session.scalars(
            select(FunctionalRole.id)
            .join(
                PositionFunctionalRole,
                PositionFunctionalRole.functional_role_id == FunctionalRole.id,
            )
            .outerjoin(
                FunctionalRolePermission,
                FunctionalRolePermission.functional_role_id == FunctionalRole.id,
            )
            .where(
                PositionFunctionalRole.position_id == position_id,
                PositionFunctionalRole.tenant_id == tenant_id,
                or_(
                    FunctionalRole.is_admin.is_(True),
                    FunctionalRolePermission.permission == Permission.ROLE_MANAGE,
                ),
            )
        ).first()
        is not None
    )


def admin_assignments(tenant_id: uuid.UUID, session: Session) -> Sequence[MemberPositionAssignment]:
    """Current assignments that make a member a tenant administrator.

    The single definition of "who is a tenant admin" — a live (current, non-deleted)
    term for a position mapped to an ``is_admin`` functional role, held by a
    non-deleted member. Shared by the platform control plane (revoke last-admin
    guard) and the tenant-facing term endpoints (their mirror guard), so the two
    paths cannot drift. Predicates are explicit rather than relying on the automatic
    tenant/soft-delete scoping because the platform side calls this under
    ``unscoped()``.
    """
    return session.scalars(
        select(MemberPositionAssignment)
        .join(Member, Member.id == MemberPositionAssignment.member_id)
        .join(Position, Position.id == MemberPositionAssignment.position_id)
        .join(
            PositionFunctionalRole,
            PositionFunctionalRole.position_id == MemberPositionAssignment.position_id,
        )
        .join(FunctionalRole, FunctionalRole.id == PositionFunctionalRole.functional_role_id)
        .where(
            MemberPositionAssignment.tenant_id == tenant_id,
            current_assignment_clause(),
            Member.is_deleted.is_(False),
            Position.is_deleted.is_(False),
            PositionFunctionalRole.is_deleted.is_(False),
            FunctionalRole.is_admin.is_(True),
            FunctionalRole.is_deleted.is_(False),
        )
        .distinct()
    ).all()


def admin_member_ids(tenant_id: uuid.UUID, session: Session) -> set[uuid.UUID]:
    """Distinct members currently holding an admin-conferring term in the tenant."""
    return {a.member_id for a in admin_assignments(tenant_id, session)}


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
                current_assignment_clause(),
            )
        ).all()
    )


def _has_admin_role(functional_role_ids: set[uuid.UUID], session: Session) -> bool:
    return (
        session.scalars(
            select(FunctionalRole.id).where(
                FunctionalRole.id.in_(functional_role_ids),
                FunctionalRole.is_admin.is_(True),
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
                FunctionalRolePermission.functional_role_id.in_(functional_role_ids)
            )
        ).all()
    )
