from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import PlatformBase


class Tenant(PlatformBase):
    """A troop (or other organizational unit) using OpenTroop.

    ``Tenant.id`` is the ``tenant_id`` that appears as the partition key on
    every ``TrackedBase`` row.  Provisioning a new troop in SaaS mode means
    creating one ``Tenant`` row; self-hosted deployments have exactly one.
    """

    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
