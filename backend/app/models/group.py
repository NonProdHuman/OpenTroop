from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import SourceTracked, TrackedBase
from app.models.enums import GroupType, RuleDimension, RuleLogic
from app.models.types import JsonList

if TYPE_CHECKING:
    from app.models.member import Member


class Group(SourceTracked, TrackedBase):
    """A named, resolvable set of members — the unifying targeting primitive.

    A group's membership is the union of:
    - manual inclusions (``GroupMember`` rows), and
    - dynamic, rule-based members (``GroupRule`` rows evaluated per dimension).

    ``group_type`` is either ``CUSTOM`` (the general group: manual members and/or
    rules) or ``PATROL`` (the roster's unit-of-belonging — manual members only, one
    per member, adults excluded; patrols carry no rules).

    ``rule_logic`` controls how multiple rules combine:
    - AND (default): a member must match all rules (intersection).
    - OR: a member matching any rule is included (union).
    Manual members are always included regardless of rule_logic.

    ``include_parents`` (membership): when set, the parents/guardians of the
    resolved members are added to the group **after** rule resolution — so the
    expansion reads as "...and their parents/guardians". ``cc_parents_on_messages``
    (communications): the future messaging layer also sends to resolved members'
    parents/guardians, **without** making them group members — it does not affect
    ``resolve_group_members``, visibility, or the iCal feed.

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
        default=GroupType.CUSTOM,
        nullable=False,
    )
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rule_logic: Mapped[RuleLogic] = mapped_column(
        SAEnum(RuleLogic, values_callable=lambda x: [e.value for e in x]),
        default=RuleLogic.AND,
        nullable=False,
        server_default="and",
    )
    include_parents: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    cc_parents_on_messages: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )

    members: Mapped[list[GroupMember]] = relationship(
        "GroupMember", back_populates="group", cascade="all, delete-orphan"
    )
    rules: Mapped[list[GroupRule]] = relationship(
        "GroupRule", back_populates="group", cascade="all, delete-orphan"
    )


class GroupMember(TrackedBase):
    """An explicit (manual) inclusion of a member in a group.

    Also stores patrol membership (the group's ``group_type`` is ``PATROL``).
    Soft-deletable so membership history is preserved for audits and sync.
    """

    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "member_id", name="uq_group_members_group_member"),
        # Group resolution and member_group_ids run on most event reads (visibility);
        # tenant-leading composites keep them index-only under RLS (GH-115).
        Index("ix_group_members_tenant_group", "tenant_id", "group_id"),
        Index("ix_group_members_tenant_member", "tenant_id", "member_id"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    added_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"), nullable=True)

    group: Mapped[Group] = relationship("Group", back_populates="members")
    member: Mapped[Member] = relationship("Member", foreign_keys=[member_id])
    added_by: Mapped[Member | None] = relationship("Member", foreign_keys=[added_by_id])


class GroupRule(TrackedBase):
    """A dynamic membership rule for one dimension.

    Each rule targets a ``RuleDimension`` (member type, OA status, position, etc.)
    and optionally carries a ``values`` list specifying what to match (enum values,
    UUIDs, etc.). Boolean dimensions like ``oa_member`` use ``values=None`` — the
    presence of the rule is the predicate.

    A group has at most one rule per dimension (enforced by unique constraint).
    Multiple values for a dimension (e.g. positions PL + SPL + SM) are stored
    as a JSON list in ``values``.
    """

    __tablename__ = "group_rules"
    __table_args__ = (
        UniqueConstraint("group_id", "dimension", name="uq_group_rules_group_dimension"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), nullable=False, index=True)
    dimension: Mapped[RuleDimension] = mapped_column(
        SAEnum(RuleDimension, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    values: Mapped[list[str] | None] = mapped_column(JsonList, nullable=True)

    group: Mapped[Group] = relationship("Group", back_populates="rules")
