"""Tenant-scoped RBAC: Positions, Functional roles, and their wiring.

The authorization model is deliberately two levels deep (see
``docs/spec/roles-rbac.md``):

    member ──assign──▶ Position(s) ──mapping──▶ FunctionalRole(s) ──▶ Permission(s)

- A **Position** is what a member *is* in the troop (Scoutmaster, Patrol Leader).
  It is the only thing assigned to a member.
- A **FunctionalRole** is a named permission bundle (Member Admins, Event Admins).
  Positions belong to functional roles; that membership conveys permissions.
- Permissions live *only* on functional roles in v1 — a position never holds one
  directly. The resolver (``app.core.permissions``) is shaped as a union over
  permission sources so a future ``PositionPermission`` source can be added
  additively without touching callers.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TrackedBase
from app.models.enums import Permission, PositionScope

if TYPE_CHECKING:
    from app.models.member import Member


class Position(TrackedBase):
    """What a member *is* in the troop — the assignable unit.

    Maps to functional roles via ``PositionFunctionalRole``; a member holding the
    position inherits the union of those roles' permissions. ``is_system`` marks
    seeded positions that can be reconfigured but not deleted.
    """

    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_positions_tenant_slug"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    applies_to: Mapped[PositionScope] = mapped_column(
        SAEnum(PositionScope, values_callable=lambda x: [e.value for e in x]),
        default=PositionScope.ANY,
        nullable=False,
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    functional_role_links: Mapped[list[PositionFunctionalRole]] = relationship(
        "PositionFunctionalRole",
        back_populates="position",
        cascade="all, delete-orphan",
    )
    member_assignments: Mapped[list[MemberPositionAssignment]] = relationship(
        "MemberPositionAssignment",
        foreign_keys="MemberPositionAssignment.position_id",
        back_populates="position",
    )


class FunctionalRole(TrackedBase):
    """A named permission bundle. Positions map into it; it carries permissions.

    ``is_admin=True`` short-circuits to the full permission set (reserved for the
    Administrators role). ``is_system`` marks seeded roles — reconfigurable but
    not deletable.
    """

    __tablename__ = "functional_roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_functional_roles_tenant_slug"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list[FunctionalRolePermission]] = relationship(
        "FunctionalRolePermission",
        back_populates="functional_role",
        cascade="all, delete-orphan",
    )
    position_links: Mapped[list[PositionFunctionalRole]] = relationship(
        "PositionFunctionalRole",
        back_populates="functional_role",
        cascade="all, delete-orphan",
    )


class FunctionalRolePermission(TrackedBase):
    """Grants a single Permission to a FunctionalRole."""

    __tablename__ = "functional_role_permissions"
    __table_args__ = (
        UniqueConstraint(
            "functional_role_id", "permission", name="uq_functional_role_permissions_role_perm"
        ),
    )

    functional_role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("functional_roles.id"), nullable=False, index=True
    )
    permission: Mapped[Permission] = mapped_column(SAEnum(Permission), nullable=False)

    functional_role: Mapped[FunctionalRole] = relationship(
        "FunctionalRole", back_populates="permissions"
    )


class PositionFunctionalRole(TrackedBase):
    """Maps a Position into a FunctionalRole — *the* product surface.

    Members holding ``position_id`` inherit every permission of
    ``functional_role_id``. Seeded with sensible defaults at provisioning; this is
    what a troop edits to tune governance.
    """

    __tablename__ = "position_functional_roles"
    __table_args__ = (
        UniqueConstraint("position_id", "functional_role_id", name="uq_position_functional_roles"),
    )

    position_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("positions.id"), nullable=False, index=True
    )
    functional_role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("functional_roles.id"), nullable=False, index=True
    )

    position: Mapped[Position] = relationship("Position", back_populates="functional_role_links")
    functional_role: Mapped[FunctionalRole] = relationship(
        "FunctionalRole", back_populates="position_links"
    )


class MemberPositionAssignment(TrackedBase):
    """Assigns a member to a position — the only routine RBAC write.

    There is deliberately no path to assign a functional role or raw permission
    to a member; positions are the sole member-facing link. ``assigned_by_id``
    is the audit trail; soft-delete preserves assignment history.
    """

    __tablename__ = "member_position_assignments"
    __table_args__ = (
        UniqueConstraint("member_id", "position_id", name="uq_member_position_assignments"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    position_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("positions.id"), nullable=False, index=True
    )
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )

    member: Mapped[Member] = relationship(
        "Member", foreign_keys=[member_id], back_populates="position_assignments"
    )
    position: Mapped[Position] = relationship(
        "Position", foreign_keys=[position_id], back_populates="member_assignments"
    )
    assigned_by: Mapped[Member | None] = relationship("Member", foreign_keys=[assigned_by_id])
