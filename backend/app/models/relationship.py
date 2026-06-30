from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import SourceTracked, TrackedBase
from app.models.enums import RelationshipType

if TYPE_CHECKING:
    from app.models.member import Member


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
