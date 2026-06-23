from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import PlatformBase

if TYPE_CHECKING:
    from app.models.member import Member


class User(PlatformBase):
    """A platform-level person identity.

    One User may hold many Identity records (one per OIDC provider) and may
    have Member records in multiple tenants (troops).  The link from Member
    to User is nullable so that roster-only contacts (non-registered parents,
    family members) can exist without a login account.
    """

    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    identities: Mapped[list[Identity]] = relationship("Identity", back_populates="user")
    member_records: Mapped[list[Member]] = relationship("Member", back_populates="user")


class Identity(PlatformBase):
    """A single OIDC provider credential bound to a User.

    ``(issuer, provider_sub)`` is globally unique — the same OIDC subject
    cannot be linked to two different User accounts.  ``issuer`` is the JWT
    ``iss`` claim (e.g. ``https://accounts.google.com``); ``provider_sub`` is
    the JWT ``sub`` claim.
    """

    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("issuer", "provider_sub", name="uq_identities_issuer_sub"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="identities")
