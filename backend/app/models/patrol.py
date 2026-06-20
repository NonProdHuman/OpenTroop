from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TrackedBase

if TYPE_CHECKING:
    from app.models.member import Member


class Patrol(TrackedBase):
    __tablename__ = "patrols"

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    members: Mapped[list["Member"]] = relationship(back_populates="patrol")
