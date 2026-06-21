from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TrackedBase
from app.models.enums import MemberType, SwimClassification, TroopRole

if TYPE_CHECKING:
    from app.models.patrol import Patrol
    from app.models.relationship import MemberRelationship


class Member(TrackedBase):
    __tablename__ = "members"

    bsa_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    member_type: Mapped[MemberType] = mapped_column(SAEnum(MemberType), nullable=False)
    troop_role: Mapped[TroopRole] = mapped_column(
        SAEnum(TroopRole), default=TroopRole.NONE, nullable=False
    )
    swim_classification: Mapped[SwimClassification] = mapped_column(
        SAEnum(SwimClassification), default=SwimClassification.NONSWIMMER, nullable=False
    )

    patrol_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrols.id"), nullable=True)
    patrol: Mapped[Patrol | None] = relationship(back_populates="members")

    # Guardian graph. A scout has many adult guardians (guardian_links); an adult
    # has many dependent scouts (dependent_links). Both resolve through the
    # MemberRelationship junction.
    guardian_links: Mapped[list[MemberRelationship]] = relationship(
        "MemberRelationship",
        foreign_keys="MemberRelationship.scout_id",
        back_populates="scout",
    )
    dependent_links: Mapped[list[MemberRelationship]] = relationship(
        "MemberRelationship",
        foreign_keys="MemberRelationship.adult_id",
        back_populates="adult",
    )
