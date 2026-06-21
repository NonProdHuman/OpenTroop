from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TrackedBase
from app.models.enums import MemberStatus, MemberType, SwimClassification, TroopRole

if TYPE_CHECKING:
    from app.models.patrol import Patrol
    from app.models.relationship import MemberRelationship


class Member(TrackedBase):
    __tablename__ = "members"

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
    troop_role: Mapped[TroopRole] = mapped_column(
        SAEnum(TroopRole), default=TroopRole.NONE, nullable=False
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

    patrol_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrols.id"), nullable=True)
    patrol: Mapped[Patrol | None] = relationship(back_populates="members")

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
