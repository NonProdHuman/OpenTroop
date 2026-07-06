from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import PlatformBase
from app.models.enums import AdvancementMode


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
    # When a platform admin last took a full data export (GH-222). Tenant deletion
    # requires an export *after* suspension — the export is the recovery path for
    # an accidental delete, since the purge itself is immediate and irreversible.
    last_export_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Highest sync_seq among rows the tombstone reaper has physically deleted for
    # this tenant (GH-222; sync-protocol Decision 5). A pull cursor behind this
    # watermark may have missed tombstones — the sync endpoints answer 410 so the
    # client full-refetches from since_seq=0. Null ⇒ nothing ever reaped.
    purged_through_seq: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Customizable parental permission-slip language shown before a parent clicks "I Agree".
    # Static text (no merge fields). Null ⇒ a built-in default is shown (see DEFAULT_PERMISSION_MESSAGE).
    permission_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Advancement workflow switch (GH-92): disabled / chair_entry / scout_reported.
    # Governs whether the advancement endpoints exist for this tenant and whether
    # scouts/parents may self-report. Default for new tenants: chair_entry.
    advancement_mode: Mapped[AdvancementMode] = mapped_column(
        SAEnum(AdvancementMode, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AdvancementMode.CHAIR_ENTRY,
    )
    # Object-storage metering (GH-145; the platform's first storage meter).
    # `used_storage_bytes` counts HEAD-verified bytes plus live PENDING
    # reservations are tracked on EventPhoto rows — enforcement compares
    # used + reserved against the effective quota. `storage_quota_bytes` is the
    # per-tenant override; null falls back to
    # settings.tenant_storage_quota_default_bytes (the tier placeholder until
    # billing lands).
    used_storage_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    storage_quota_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
