from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TrackedBase
from app.models.enums import GroupType

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.role import Role


class Group(TrackedBase):
    """A named, resolvable set of members — the unifying targeting primitive.

    A group's membership is the union of:
    - manual inclusions (``GroupMember`` rows), and
    - dynamic, rule-based members (``GroupRoleRule`` — everyone holding a role).

    ``group_type`` classifies how a group is primarily managed and flags patrols,
    the roster's unit-of-belonging. Patrols are folded into Group: a patrol is a
    ``PATROL``-type group whose members are explicit ``GroupMember`` rows, and a
    member belongs to at most one ``PATROL`` group at a time.

    Groups drive event visibility (audiences) and, later, email/SMS distribution
    lists and report scoping — every consumer resolves them the same way via
    ``app.core.groups.resolve_group_members``.
    """

    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_groups_tenant_name"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_type: Mapped[GroupType] = mapped_column(
        SAEnum(GroupType, values_callable=lambda x: [e.value for e in x]),
        default=GroupType.MANUAL,
        nullable=False,
    )
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    members: Mapped[list[GroupMember]] = relationship(
        "GroupMember", back_populates="group", cascade="all, delete-orphan"
    )
    role_rules: Mapped[list[GroupRoleRule]] = relationship(
        "GroupRoleRule", back_populates="group", cascade="all, delete-orphan"
    )


class GroupMember(TrackedBase):
    """An explicit (manual) inclusion of a member in a group.

    Also stores patrol membership (the group's ``group_type`` is ``PATROL``).
    Soft-deletable so membership history is preserved for audits and sync.
    """

    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "member_id", name="uq_group_members_group_member"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    added_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"), nullable=True)

    group: Mapped[Group] = relationship("Group", back_populates="members")
    member: Mapped[Member] = relationship("Member", foreign_keys=[member_id])
    added_by: Mapped[Member | None] = relationship("Member", foreign_keys=[added_by_id])


class GroupRoleRule(TrackedBase):
    """Dynamic membership rule: members directly assigned ``role_id`` belong to the group.

    Matches *direct* ``MemberRoleAssignment`` to the named role (no role-hierarchy
    expansion), which keeps role-driven groups like the PLC predictable: add one
    rule per position role (PL, SPL, ASM, SM) and the group resolves to exactly
    the members holding those positions.
    """

    __tablename__ = "group_role_rules"
    __table_args__ = (
        UniqueConstraint("group_id", "role_id", name="uq_group_role_rules_group_role"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)

    group: Mapped[Group] = relationship("Group", back_populates="role_rules")
    role: Mapped[Role] = relationship("Role")
