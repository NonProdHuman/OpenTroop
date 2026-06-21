from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TrackedBase
from app.models.enums import RelationshipType

if TYPE_CHECKING:
    from app.models.member import Member


class MemberRelationship(TrackedBase):
    """Junction linking an adult member to a scout member (guardian graph)."""

    __tablename__ = "member_relationships"

    adult_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    scout_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        SAEnum(RelationshipType), default=RelationshipType.GUARDIAN, nullable=False
    )

    adult: Mapped[Member] = relationship(
        "Member", foreign_keys=[adult_id], back_populates="dependent_links"
    )
    scout: Mapped[Member] = relationship(
        "Member", foreign_keys=[scout_id], back_populates="guardian_links"
    )
