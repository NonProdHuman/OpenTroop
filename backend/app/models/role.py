from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TrackedBase
from app.models.enums import Permission

if TYPE_CHECKING:
    from app.models.member import Member


class Role(TrackedBase):
    """A named set of permissions, scoped to a tenant.

    Two kinds of roles exist in practice:
    - Functional groups (event_admin, member_admin, …) — hold permissions directly.
    - Positions (scoutmaster, patrol_leader, …) — inherit from functional groups
      via RoleMembership; may also hold permissions directly.

    Members can be assigned to any role. is_admin=True bypasses all permission
    checks (reserved for the 'administrators' role).
    is_system=True marks seeded roles that cannot be deleted, though their
    permission mappings can be reconfigured per tenant.
    """

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_roles_tenant_slug"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    # Functional groups this role is a member of (i.e., inherits permissions from)
    group_memberships: Mapped[list[RoleMembership]] = relationship(
        "RoleMembership",
        foreign_keys="RoleMembership.member_role_id",
        back_populates="member_role",
    )
    # Positions/roles that are members of this role (when this role is a functional group)
    role_members: Mapped[list[RoleMembership]] = relationship(
        "RoleMembership",
        foreign_keys="RoleMembership.group_role_id",
        back_populates="group_role",
    )
    member_assignments: Mapped[list[MemberRoleAssignment]] = relationship(
        "MemberRoleAssignment",
        back_populates="role",
    )


class RolePermission(TrackedBase):
    """Grants a single Permission to a Role."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission", name="uq_role_permissions_role_perm"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    permission: Mapped[Permission] = mapped_column(SAEnum(Permission), nullable=False)

    role: Mapped[Role] = relationship("Role", back_populates="permissions")


class RoleMembership(TrackedBase):
    """Records that a position role is a member of a functional group role.

    member_role (e.g. Scoutmaster) is a member of group_role (e.g. Event Admin),
    so any member assigned to member_role inherits group_role's permissions.
    Individual members can also be assigned directly to a functional group role
    via MemberRoleAssignment, bypassing this table.
    """

    __tablename__ = "role_memberships"
    __table_args__ = (
        UniqueConstraint(
            "group_role_id", "member_role_id", name="uq_role_memberships_group_member"
        ),
    )

    group_role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id"), nullable=False, index=True
    )
    member_role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id"), nullable=False, index=True
    )

    group_role: Mapped[Role] = relationship(
        "Role", foreign_keys=[group_role_id], back_populates="role_members"
    )
    member_role: Mapped[Role] = relationship(
        "Role", foreign_keys=[member_role_id], back_populates="group_memberships"
    )


class MemberRoleAssignment(TrackedBase):
    """Assigns a member to a role (position or functional group directly).

    created_at serves as the assignment timestamp.
    assigned_by_id records which member made the assignment (audit trail).
    Soft-delete via is_deleted preserves assignment history for leadership audits.
    """

    __tablename__ = "member_role_assignments"
    __table_args__ = (
        UniqueConstraint("member_id", "role_id", name="uq_member_role_assignments_member_role"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )

    member: Mapped[Member] = relationship(
        "Member", foreign_keys=[member_id], back_populates="role_assignments"
    )
    role: Mapped[Role] = relationship("Role", back_populates="member_assignments")
    assigned_by: Mapped[Member | None] = relationship("Member", foreign_keys=[assigned_by_id])
