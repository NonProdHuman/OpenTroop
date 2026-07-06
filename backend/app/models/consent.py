from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TrackedBase
from app.models.enums import ConsentMethod, ConsentScope


class ConsentRecord(TrackedBase):
    """An auditable, revocable consent event (#223; docs/spec compliance review).

    One ledger, many scopes (``tos`` / ``account`` / ``media`` / ``sms``) so the
    same table backs ToS acceptance, COPPA parental consent, media/photo release,
    and SMS opt-in. ``subject_member_id`` is who the consent is *about* (the child,
    or the adult for ToS); ``consented_by_member_id`` is the granting
    parent/guardian (null when an adult self-accepts); ``consented_by_user_id`` is
    the authenticated actor for the audit trail. Consent is revocable
    (``revoked_at``) and never hard-deleted here — the ledger is the record.
    """

    __tablename__ = "consent_records"
    __table_args__ = (Index("ix_consent_records_tenant_subject", "tenant_id", "subject_member_id"),)

    subject_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), nullable=False)
    consented_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    consented_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    scope: Mapped[ConsentScope] = mapped_column(
        SAEnum(ConsentScope, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    method: Mapped[ConsentMethod] = mapped_column(
        SAEnum(ConsentMethod, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
