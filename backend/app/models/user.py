from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import PlatformBase
from app.models.enums import PlatformRole


class User(PlatformBase):
    """A platform-level person identity.

    One User may hold many Identity records (one per OIDC provider) and may
    have Member records in multiple tenants (troops).  The link from Member
    to User is a one-directional FK on Member.user_id; navigate the reverse
    with a query rather than an ORM backref to avoid a module-level cyclic
    import between user.py and member.py.
    """

    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # True only when the OIDC provider asserted ``email_verified`` for the stored
    # email. Every email-based matching path (Member auto-link, admin-invite
    # pre-link, platform grant-by-email) must require this — an unverified email
    # claim is attacker-chosen.
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Global SaaS control-plane role. None for ordinary users; set only on the
    # handful of platform operators who manage tenants and tenant admins.
    platform_role: Mapped[PlatformRole | None] = mapped_column(SAEnum(PlatformRole), nullable=True)

    identities: Mapped[list[Identity]] = relationship("Identity", back_populates="user")


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
