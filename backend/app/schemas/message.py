"""Pydantic schemas for messaging (GH-146)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import AudienceType, EmailState, MessageStatus, PushState
from app.schemas.base import TrackedRead
from app.schemas.types import UtcDateTime


class MessageGroupTarget(BaseModel):
    group_id: uuid.UUID
    audience_type: AudienceType = AudienceType.MEMBERS


class MessageCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    group_targets: list[MessageGroupTarget] = Field(min_length=1)
    send_email: bool = True
    send_push: bool = True
    scheduled_at: UtcDateTime | None = None


class MessageRead(TrackedRead):
    subject: str
    body: str
    status: MessageStatus
    send_email: bool
    send_push: bool
    scheduled_at: UtcDateTime | None
    sent_at: UtcDateTime | None
    sent_by_id: uuid.UUID


class MessageGroupRead(TrackedRead):
    message_id: uuid.UUID
    group_id: uuid.UUID
    audience_type: AudienceType


class AudiencePreview(BaseModel):
    """Recipient counts for the compose screen (docs/spec/messaging.md)."""

    total: int
    email: int
    push_devices: int
    opted_out: int
    bounced: int
    no_email: int


class MessageWithPreview(BaseModel):
    message: MessageRead
    groups: list[MessageGroupRead]
    preview: AudiencePreview


class RecipientPreviewEntry(BaseModel):
    member_id: uuid.UUID
    first_name: str
    last_name: str
    email_state: EmailState
    has_push_device: bool


class MessageRecipientRead(TrackedRead):
    message_id: uuid.UUID
    member_id: uuid.UUID
    read_at: UtcDateTime | None
    email_state: EmailState
    push_state: PushState
    attempts: int
    last_error: str | None


class DeliveryStats(BaseModel):
    total: int
    email_sent: int
    email_pending: int
    email_failed: int
    email_skipped: int
    push_sent: int
    read: int


class MessageDetail(BaseModel):
    message: MessageRead
    groups: list[MessageGroupRead]
    stats: DeliveryStats


class InboxEntry(BaseModel):
    """One inbox row + the message content it points at (member-facing)."""

    recipient_id: uuid.UUID
    message_id: uuid.UUID
    subject: str
    body: str
    sent_at: UtcDateTime | None
    read_at: UtcDateTime | None


class InboxPage(BaseModel):
    items: list[InboxEntry]
    unread_count: int
