from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import PlatformBase


class Tenant(PlatformBase):
    """A troop (or other organizational unit) using OpenTroop.

    ``Tenant.id`` is the ``tenant_id`` that appears as the partition key on
    every ``TrackedBase`` row.  Provisioning a new troop in SaaS mode means
    creating one ``Tenant`` row; self-hosted deployments have exactly one.

    ``suspended_at`` is the SaaS control-plane suspension marker (e.g. non-payment
    or abuse) — distinct from ``is_deleted`` (the sync-tombstone soft delete). A
    suspended tenant still exists but all tenant-scoped requests are rejected
    (see ``get_tenant_id``); a platform admin can unsuspend it.
    """

    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Customizable parental permission-slip language shown before a parent clicks "I Agree".
    # Static text (no merge fields). Null ⇒ a built-in default is shown (see DEFAULT_PERMISSION_MESSAGE).
    permission_message: Mapped[str | None] = mapped_column(Text, nullable=True)
