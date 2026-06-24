from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TrackedBase


class Location(TrackedBase):
    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    street1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    street2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(60), nullable=True, default="US")
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    directions: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    distance_miles: Mapped[float | None] = mapped_column(nullable=True)
