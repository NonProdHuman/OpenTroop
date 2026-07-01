from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import SourceTracked, TrackedBase
from app.models.enums import MemberStatus, MemberType, RelationshipType, SwimClassification

if TYPE_CHECKING:
    from app.models.user import User  # User does not import Member, so no cycle


class Member(SourceTracked, TrackedBase):
    __tablename__ = "members"
    __table_args__ = (
        Index(
            "uix_members_tenant_bsa_id",
            "tenant_id",
            "bsa_id",
            unique=True,
            postgresql_where=text("bsa_id IS NOT NULL"),
        ),
    )

    bsa_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_suffix: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(120), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(60), nullable=True, default="US")

    member_type: Mapped[MemberType] = mapped_column(SAEnum(MemberType), nullable=False)
    membership_status: Mapped[MemberStatus] = mapped_column(
        SAEnum(MemberStatus), default=MemberStatus.ACTIVE, nullable=False, index=True
    )
    swim_classification: Mapped[SwimClassification] = mapped_column(
        SAEnum(SwimClassification), default=SwimClassification.NONSWIMMER, nullable=False
    )

    troop_membership_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    troop_membership_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    swim_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    medical_form_ab_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    medical_form_c_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    dietary_restrictions: Mapped[str | None] = mapped_column(Text, nullable=True)

    emergency_contact_1_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_1_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    emergency_contact_2_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_2_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Notification preferences and delivery state. email_opt_out is set by the
    # member; email_bounced is set automatically by bounce webhook processing.
    # sms_opt_in requires explicit consent — never default True.
    email_opt_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_bounced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    oa_member: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    oa_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    oa_election_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    oa_call_out_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    oa_ordeal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    oa_brotherhood_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    oa_vigil_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    oa_vigil_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oa_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    user: Mapped[User | None] = relationship("User")

    # Secret bearer token for the member's personal iCal subscription feed
    # (GET /calendar/{token}.ics). Null until the member subscribes; rotatable.
    calendar_token: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )

    # jti of the currently valid invite/claim token. A claim token is honored only
    # while its jti matches this value, which makes tokens single-use (cleared on
    # claim) and revocable (overwritten when a new invite is minted).
    invite_token_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Patrol membership is folded into the general Group model: a member's patrol
    # is a GroupMember row whose Group is of type PATROL. See app.models.group.

    # Family relationship graph. outgoing_relationships: relationships where this
    # member is from_member (e.g. a parent's view of their children).
    # incoming_relationships: relationships where this member is to_member
    # (e.g. a scout's view of their parents/guardians).
    outgoing_relationships: Mapped[list[MemberRelationship]] = relationship(
        "MemberRelationship",
        foreign_keys="MemberRelationship.from_member_id",
        back_populates="from_member",
    )
    incoming_relationships: Mapped[list[MemberRelationship]] = relationship(
        "MemberRelationship",
        foreign_keys="MemberRelationship.to_member_id",
        back_populates="to_member",
    )


class MemberRelationship(SourceTracked, TrackedBase):
    """Directional family link between two members.

    from_member holds the named role (parent_of, guardian_of); to_member is the child/ward.
    For sibling_of (symmetric), store with the lower UUID as from_member by convention.
    """

    __tablename__ = "member_relationships"

    from_member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    to_member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        SAEnum(RelationshipType), nullable=False
    )

    from_member: Mapped[Member] = relationship(
        "Member", foreign_keys=[from_member_id], back_populates="outgoing_relationships"
    )
    to_member: Mapped[Member] = relationship(
        "Member", foreign_keys=[to_member_id], back_populates="incoming_relationships"
    )
