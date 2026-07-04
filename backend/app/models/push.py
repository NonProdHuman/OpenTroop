from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TrackedBase


class PushToken(TrackedBase):
    """A device's push registration for one member in one tenant (GH-82).

    ``token`` is an Expo push token in v1 (the backend is vendor-agnostic —
    see ``app.core.notifications.PushBackend``). A device signed into two
    troops holds one row per tenant; re-registering a token that moved to a
    different user re-points ``member_id``. Rows are hard-pruned when the
    vendor reports the device gone — a dead token is not history worth keeping.
    """

    __tablename__ = "push_tokens"
    __table_args__ = (
        UniqueConstraint("tenant_id", "token", name="uq_push_tokens_tenant_token"),
        Index("ix_push_tokens_tenant_member", "tenant_id", "member_id"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
