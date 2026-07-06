"""Messaging core (GH-146): audience resolution, send, and the outbox drain.

The audience resolves at send time — no persistent shadow groups. Parent
expansion is the single implementation here (docs/spec/messaging.md). The
email queue is the ``MessageRecipient`` rows themselves (GH-78): ``pending``
rows drain in the background with per-tenant pacing and exponential backoff;
terminal failures stay visible as the dead-letter surface (GH-79). Push is a
one-shot alert at send time (GH-82) — the inbox entry is the durable record.
"""

from __future__ import annotations

import html
import logging
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.groups import resolve_group_members
from app.core.notifications import (
    EmailMessage,
    EmailSendError,
    NotificationService,
    PushMessage,
)
from app.core.relationships import _parents_of  # single home of the family-edge rules
from app.models.enums import AudienceType, EmailState, MessageStatus, PushState
from app.models.member import Member
from app.models.message import Message, MessageGroup, MessageRecipient
from app.models.push import PushToken

logger = logging.getLogger(__name__)

MAX_EMAIL_ATTEMPTS = 5
_BACKOFF_BASE_SECONDS = 60  # 1m, 2m, 4m, 8m between retries


def _now() -> datetime:
    return datetime.now(UTC)


def all_member_ids(tenant_id: uuid.UUID, db: Session) -> set[uuid.UUID]:
    """Every non-deleted member in the tenant — the 'entire troop' audience (#217)."""
    return set(
        db.scalars(
            select(Member.id).where(Member.tenant_id == tenant_id, Member.is_deleted.is_(False))
        ).all()
    )


def resolve_group_targets(
    targets: Iterable[tuple[uuid.UUID, AudienceType]], db: Session
) -> set[uuid.UUID]:
    """Deduplicated member ids reached by a set of (group_id, audience_type) targets.

    Shared by the persisted send path and the stateless compose preview (#217).
    """
    audience: set[uuid.UUID] = set()
    for group_id, audience_type in targets:
        members = set(resolve_group_members(group_id, db))
        if audience_type == AudienceType.MEMBERS:
            audience |= members
        elif audience_type == AudienceType.MEMBERS_AND_PARENTS:
            audience |= members | _parents_of(members, db)
        else:  # PARENTS_ONLY
            audience |= _parents_of(members, db)
    return audience


def resolve_message_audience(message: Message, db: Session) -> set[uuid.UUID]:
    """The deduplicated member ids a message reaches (entire-troop or its group targets)."""
    if message.send_to_all:
        return all_member_ids(message.tenant_id, db)
    targets = db.scalars(select(MessageGroup).where(MessageGroup.message_id == message.id)).all()
    return resolve_group_targets(((t.group_id, t.audience_type) for t in targets), db)


def initial_email_state(member: Member, *, send_email: bool) -> EmailState:
    """Decided at resolve time; skipped states are never queued (CAN-SPAM)."""
    if not send_email:
        return EmailState.SKIPPED_NO_EMAIL
    if member.email is None or not member.email.strip():
        return EmailState.SKIPPED_NO_EMAIL
    if member.email_bounced:
        return EmailState.SKIPPED_BOUNCED
    if member.email_opt_out:
        return EmailState.SKIPPED_OPT_OUT
    return EmailState.PENDING


def build_message_email(message: Message, member: Member) -> EmailMessage:
    assert member.email is not None  # gated by initial_email_state  # noqa: S101
    escaped = html.escape(message.body).replace("\n", "<br>")
    return EmailMessage(
        to=member.email,
        subject=message.subject,
        html_body=f"<p>Hi {html.escape(member.first_name)},</p><p>{escaped}</p>",
        text_body=f"Hi {member.first_name},\n\n{message.body}",
    )


def send_message(
    message: Message, db: Session, service: NotificationService
) -> list[MessageRecipient]:
    """Resolve the audience, write the inbox snapshot, and fire push alerts.

    Email stays queued (``pending``) for the outbox drain — never sent on the
    request path (GH-78). Idempotent guard is the caller's status check.
    """
    audience = resolve_message_audience(message, db)
    members = db.scalars(select(Member).where(Member.id.in_(audience))).all() if audience else []

    recipients: list[MessageRecipient] = []
    for member in members:
        recipients.append(
            MessageRecipient(
                message_id=message.id,
                member_id=member.id,
                email_state=initial_email_state(member, send_email=message.send_email),
                push_state=PushState.NO_DEVICES,
            )
        )
    db.add_all(recipients)
    message.status = MessageStatus.SENDING
    db.flush()

    if message.send_push and recipients:
        _push_message_alerts(message, recipients, db, service)

    _finalize_if_drained(message, db)
    db.commit()
    return recipients


def _push_message_alerts(
    message: Message,
    recipients: list[MessageRecipient],
    db: Session,
    service: NotificationService,
) -> None:
    member_ids = [r.member_id for r in recipients]
    tokens = db.scalars(select(PushToken).where(PushToken.member_id.in_(member_ids))).all()
    by_member: dict[uuid.UUID, list[PushToken]] = {}
    for token in tokens:
        by_member.setdefault(token.member_id, []).append(token)

    snippet = message.body if len(message.body) <= 140 else message.body[:137] + "…"
    pushes: list[PushMessage] = []
    for recipient in recipients:
        device_tokens = by_member.get(recipient.member_id, [])
        if not device_tokens:
            recipient.push_state = PushState.NO_DEVICES
            continue
        recipient.push_state = PushState.SENT
        pushes.extend(
            PushMessage(
                token=t.token,
                title=message.subject,
                body=snippet,
                data={"message_id": str(message.id)},
            )
            for t in device_tokens
        )
    try:
        dead = service.send_push(pushes)
    except Exception:  # noqa: BLE001 — push is best-effort by contract
        logger.warning("Push alerts failed for message %s", message.id.hex)
        return
    if dead:
        dead_set = set(dead)
        for token in tokens:
            if token.token in dead_set:
                db.delete(token)


def _finalize_if_drained(message: Message, db: Session) -> None:
    """SENDING → SENT once no recipient email remains pending."""
    remaining = db.scalar(
        select(MessageRecipient.id).where(
            MessageRecipient.message_id == message.id,
            MessageRecipient.email_state == EmailState.PENDING,
        )
    )
    if remaining is None and message.status == MessageStatus.SENDING:
        message.status = MessageStatus.SENT
        message.sent_at = _now()


def promote_due_scheduled(db: Session, service: NotificationService) -> int:
    """SCHEDULED → send, for messages whose time has come (outbox loop)."""
    due = db.scalars(
        select(Message).where(
            Message.status == MessageStatus.SCHEDULED,
            Message.scheduled_at.is_not(None),
            Message.scheduled_at <= _now(),
        )
    ).all()
    for message in due:
        send_message(message, db, service)
    return len(due)


def drain_email_outbox(db: Session, service: NotificationService, limit: int | None = None) -> int:
    """Send due pending emails, oldest first, with backoff on failure.

    ``limit`` is the per-tick batch (the per-tenant pacing lever: the caller
    runs inside one tenant's scope, so the cap is per tenant by construction).
    Returns how many emails were attempted.
    """
    batch = limit if limit is not None else settings.message_rate_per_minute
    now = _now()
    rows = db.scalars(
        select(MessageRecipient)
        .where(
            MessageRecipient.email_state == EmailState.PENDING,
            (MessageRecipient.next_attempt_at.is_(None))
            | (MessageRecipient.next_attempt_at <= now),
        )
        .order_by(MessageRecipient.created_at)
        .limit(batch)
    ).all()

    touched_messages: set[uuid.UUID] = set()
    for recipient in rows:
        message = db.get(Message, recipient.message_id)
        member = db.get(Member, recipient.member_id)
        if message is None or member is None or member.email is None:
            recipient.email_state = EmailState.FAILED
            recipient.last_error = "Recipient or message no longer available"
            continue
        try:
            service.send_email(build_message_email(message, member))
        except EmailSendError as exc:
            recipient.attempts += 1
            if recipient.attempts >= MAX_EMAIL_ATTEMPTS:
                recipient.email_state = EmailState.FAILED  # dead-letter (GH-79)
                recipient.last_error = str(exc)[:500]
            else:
                backoff = _BACKOFF_BASE_SECONDS * (2 ** (recipient.attempts - 1))
                recipient.next_attempt_at = now + timedelta(seconds=backoff)
                recipient.last_error = str(exc)[:500]
        else:
            recipient.email_state = EmailState.SENT
            recipient.last_error = None
        touched_messages.add(recipient.message_id)

    db.flush()  # the session runs autoflush=False; finalize must see new states
    for message_id in touched_messages:
        message = db.get(Message, message_id)
        if message is not None:
            _finalize_if_drained(message, db)
    db.commit()
    return len(rows)
