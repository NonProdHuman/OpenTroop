from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Syncable, TrackedBase
from app.models.enums import AudienceType, EmailState, MessageStatus, PushState


class Message(Syncable, TrackedBase):
    """A group-targeted announcement (GH-146; docs/spec/messaging.md).

    ``Syncable`` so the mobile inbox mirrors offline — the sync stream is
    scoped to messages the caller received (see ``routers/sync.py``).
    """

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_tenant_sync_seq", "tenant_id", "sync_seq"),)

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MessageStatus] = mapped_column(
        SAEnum(MessageStatus, values_callable=lambda x: [e.value for e in x]),
        default=MessageStatus.DRAFT,
        nullable=False,
    )
    # Send push alerts for this message (email gating is per-member opt-out).
    send_push: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    send_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), nullable=False)


class MessageGroup(TrackedBase):
    """One target group of a message, with its audience expansion."""

    __tablename__ = "message_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "message_id", "group_id", name="uq_message_groups_target"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id"), nullable=False, index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), nullable=False)
    audience_type: Mapped[AudienceType] = mapped_column(
        SAEnum(AudienceType, values_callable=lambda x: [e.value for e in x]),
        default=AudienceType.MEMBERS,
        nullable=False,
    )


class MessageRecipient(Syncable, TrackedBase):
    """One member's inbox entry for one message (GH-146 delta 1).

    Written at send time as the resolved-audience snapshot (the audit trail),
    then serves three roles: the member's inbox row (``read_at``), the email
    outbox queue (``email_state = pending`` rows drain in the background,
    GH-78/GH-79), and the delivery stats behind the message detail view.
    """

    __tablename__ = "message_recipients"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "message_id", "member_id", name="uq_message_recipients_entry"
        ),
        Index("ix_message_recipients_tenant_member", "tenant_id", "member_id"),
        Index("ix_message_recipients_tenant_sync_seq", "tenant_id", "sync_seq"),
        # The outbox drain scan: pending rows due for (re)attempt.
        Index("ix_message_recipients_email_queue", "email_state", "next_attempt_at"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id"), nullable=False, index=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    email_state: Mapped[EmailState] = mapped_column(
        SAEnum(EmailState, values_callable=lambda x: [e.value for e in x]),
        default=EmailState.PENDING,
        nullable=False,
    )
    push_state: Mapped[PushState] = mapped_column(
        SAEnum(PushState, values_callable=lambda x: [e.value for e in x]),
        default=PushState.NO_DEVICES,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
