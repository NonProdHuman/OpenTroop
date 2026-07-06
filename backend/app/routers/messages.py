"""Messaging API (GH-146): compose, send, history, and the member inbox."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import (
    DbDep,
    MemberContextDep,
    NotificationServiceDep,
    TenantDep,
    get_or_404,
    require,
)
from app.core.messaging import (
    all_member_ids,
    drain_email_outbox,
    initial_email_state,
    resolve_group_targets,
    resolve_message_audience,
    send_message,
)
from app.core.notifications import get_notification_service
from app.models.enums import EmailState, MessageStatus, Permission, PushState
from app.models.group import Group
from app.models.member import Member
from app.models.message import Message, MessageGroup, MessageRecipient
from app.models.push import PushToken
from app.schemas.message import (
    AudiencePreview,
    DeliveryStats,
    InboxEntry,
    InboxPage,
    MessageCreate,
    MessageDetail,
    MessageGroupRead,
    MessageRead,
    MessageRecipientRead,
    MessageWithPreview,
    RecipientPreview,
    RecipientPreviewEntry,
    RecipientPreviewRequest,
)

router = APIRouter(prefix="/messages", tags=["messages"])

_SEND = Depends(require(Permission.COMMUNICATION_SEND_TROOP))


def _audience_members(message: Message, db: DbDep) -> list[Member]:
    audience = resolve_message_audience(message, db)
    if not audience:
        return []
    return list(
        db.scalars(select(Member).where(Member.id.in_(audience)).order_by(Member.last_name)).all()
    )


def _members_with_devices(member_ids: list[uuid.UUID], db: DbDep) -> set[uuid.UUID]:
    if not member_ids:
        return set()
    return set(
        db.scalars(
            select(PushToken.member_id).where(PushToken.member_id.in_(member_ids)).distinct()
        ).all()
    )


def _audience_preview(
    members: list[Member], send_email: bool, send_push: bool, db: DbDep
) -> AudiencePreview:
    with_devices = _members_with_devices([m.id for m in members], db)
    email = opted_out = bounced = no_email = 0
    for m in members:
        if m.email is None or not m.email.strip():
            no_email += 1
        elif m.email_bounced:
            bounced += 1
        elif m.email_opt_out:
            opted_out += 1
        else:
            email += 1
    return AudiencePreview(
        total=len(members),
        email=email if send_email else 0,
        push_devices=len(with_devices) if send_push else 0,
        opted_out=opted_out,
        bounced=bounced,
        no_email=no_email,
    )


def _recipient_entries(
    members: list[Member], send_email: bool, db: DbDep
) -> list[RecipientPreviewEntry]:
    with_devices = _members_with_devices([m.id for m in members], db)
    return [
        RecipientPreviewEntry(
            member_id=m.id,
            first_name=m.first_name,
            last_name=m.last_name,
            email_state=initial_email_state(m, send_email=send_email),
            has_push_device=m.id in with_devices,
        )
        for m in members
    ]


def _preview(message: Message, db: DbDep) -> AudiencePreview:
    return _audience_preview(
        _audience_members(message, db), message.send_email, message.send_push, db
    )


def _groups_of(message: Message, db: DbDep) -> list[MessageGroup]:
    return list(db.scalars(select(MessageGroup).where(MessageGroup.message_id == message.id)))


def _with_preview(message: Message, db: DbDep) -> MessageWithPreview:
    return MessageWithPreview(
        message=MessageRead.model_validate(message),
        groups=[MessageGroupRead.model_validate(g) for g in _groups_of(message, db)],
        preview=_preview(message, db),
    )


# --- Inbox (any member; own entries only) — declared before /{message_id} ----


@router.get("/inbox", response_model=InboxPage)
def get_inbox(ctx: MemberContextDep, tenant_id: TenantDep, db: DbDep) -> InboxPage:
    actor, _ = ctx
    rows = db.execute(
        select(MessageRecipient, Message)
        .join(Message, Message.id == MessageRecipient.message_id)
        .where(MessageRecipient.member_id == actor.id)
        .order_by(MessageRecipient.created_at.desc())
        .limit(200)
    ).all()
    unread = db.scalar(
        select(func.count())
        .select_from(MessageRecipient)
        .where(MessageRecipient.member_id == actor.id, MessageRecipient.read_at.is_(None))
    )
    return InboxPage(
        items=[
            InboxEntry(
                recipient_id=recipient.id,
                message_id=message.id,
                subject=message.subject,
                body=message.body,
                sent_at=message.sent_at or message.updated_at,
                read_at=recipient.read_at,
            )
            for recipient, message in rows
        ],
        unread_count=unread or 0,
    )


@router.post("/inbox/{recipient_id}/read", response_model=MessageRecipientRead)
def mark_read(
    recipient_id: uuid.UUID, ctx: MemberContextDep, tenant_id: TenantDep, db: DbDep
) -> MessageRecipientRead:
    actor, _ = ctx
    row = get_or_404(db, MessageRecipient, recipient_id, "Inbox entry not found")
    if row.member_id != actor.id:
        # Existence of other members' entries is not leaked.
        raise HTTPException(status_code=404, detail="Inbox entry not found")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return MessageRecipientRead.model_validate(row)


# --- Compose / send / history (communication:send_troop) ---------------------


@router.post(
    "",
    response_model=MessageWithPreview,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_SEND],
)
def create_message(
    body: MessageCreate, ctx: MemberContextDep, tenant_id: TenantDep, db: DbDep
) -> MessageWithPreview:
    actor, _ = ctx
    if not body.send_to_all:
        seen: set[uuid.UUID] = set()
        for target in body.group_targets:
            if target.group_id in seen:
                raise HTTPException(status_code=422, detail="Duplicate group target")
            seen.add(target.group_id)
            group = db.get(Group, target.group_id)
            if group is None or group.is_deleted:
                raise HTTPException(status_code=422, detail="group_id not found")

    message = Message(
        subject=body.subject,
        body=body.body,
        send_email=body.send_email,
        send_push=body.send_push,
        send_to_all=body.send_to_all,
        scheduled_at=body.scheduled_at,
        sent_by_id=actor.id,
    )
    db.add(message)
    db.flush()
    if not body.send_to_all:  # entire-troop targets everyone; no group rows to store
        db.add_all(
            MessageGroup(message_id=message.id, group_id=t.group_id, audience_type=t.audience_type)
            for t in body.group_targets
        )
    db.commit()
    db.refresh(message)
    return _with_preview(message, db)


@router.post("/recipients/preview", response_model=RecipientPreview, dependencies=[_SEND])
def preview_recipients_stateless(
    body: RecipientPreviewRequest, tenant_id: TenantDep, db: DbDep
) -> RecipientPreview:
    """Resolve who a not-yet-saved announcement would reach (#217).

    Powers the always-on live recipient list on compose — no draft Message row is
    created (unlike creating and reading back a draft).
    """
    if body.send_to_all:
        audience = all_member_ids(tenant_id, db)
    else:
        audience = resolve_group_targets(
            ((t.group_id, t.audience_type) for t in body.group_targets), db
        )
    members = (
        list(db.scalars(select(Member).where(Member.id.in_(audience)).order_by(Member.last_name)))
        if audience
        else []
    )
    return RecipientPreview(
        preview=_audience_preview(members, body.send_email, body.send_push, db),
        recipients=_recipient_entries(members, body.send_email, db),
    )


@router.get("", response_model=list[MessageRead], dependencies=[_SEND])
def list_messages(tenant_id: TenantDep, db: DbDep) -> list[MessageRead]:
    rows = db.scalars(select(Message).order_by(Message.created_at.desc()).limit(200)).all()
    return [MessageRead.model_validate(m) for m in rows]


@router.get("/{message_id}", response_model=MessageDetail, dependencies=[_SEND])
def get_message(message_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> MessageDetail:
    message = get_or_404(db, Message, message_id, "Message not found")

    def count(*conditions: object) -> int:
        return (
            db.scalar(
                select(func.count())
                .select_from(MessageRecipient)
                .where(MessageRecipient.message_id == message.id, *conditions)  # type: ignore[arg-type]
            )
            or 0
        )

    skipped = (
        EmailState.SKIPPED_OPT_OUT,
        EmailState.SKIPPED_BOUNCED,
        EmailState.SKIPPED_NO_EMAIL,
    )
    stats = DeliveryStats(
        total=count(),
        email_sent=count(MessageRecipient.email_state == EmailState.SENT),
        email_pending=count(MessageRecipient.email_state == EmailState.PENDING),
        email_failed=count(MessageRecipient.email_state == EmailState.FAILED),
        email_skipped=count(MessageRecipient.email_state.in_(skipped)),
        push_sent=count(MessageRecipient.push_state == PushState.SENT),
        read=count(MessageRecipient.read_at.is_not(None)),
    )
    return MessageDetail(
        message=MessageRead.model_validate(message),
        groups=[MessageGroupRead.model_validate(g) for g in _groups_of(message, db)],
        stats=stats,
    )


@router.get(
    "/{message_id}/recipients/preview",
    response_model=list[RecipientPreviewEntry],
    dependencies=[_SEND],
)
def preview_recipients(
    message_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> list[RecipientPreviewEntry]:
    message = get_or_404(db, Message, message_id, "Message not found")
    return _recipient_entries(_audience_members(message, db), message.send_email, db)


@router.get(
    "/{message_id}/recipients",
    response_model=list[MessageRecipientRead],
    dependencies=[_SEND],
)
def list_recipients(
    message_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> list[MessageRecipientRead]:
    get_or_404(db, Message, message_id, "Message not found")
    rows = db.scalars(
        select(MessageRecipient).where(MessageRecipient.message_id == message_id)
    ).all()
    return [MessageRecipientRead.model_validate(r) for r in rows]


def _drain_once(tenant_id: uuid.UUID) -> None:
    """Background-task hook: one immediate drain pass for snappy dev/self-host.

    The lifespan loop / CLI is the real driver (GH-78); this just avoids
    waiting a tick after an interactive send. Opens its own session because
    the request's session is gone by the time background tasks run.
    """
    import logging

    from app.core.database import SessionLocal
    from app.core.tenant_context import tenant_scope

    try:
        with SessionLocal() as db, tenant_scope(tenant_id):
            drain_email_outbox(db, get_notification_service())
    except Exception:  # noqa: BLE001 — the loop retries; never crash the worker
        logging.getLogger(__name__).warning("Post-send drain pass failed", exc_info=True)


@router.post("/{message_id}/send", response_model=MessageDetail)
def send_message_now(
    message_id: uuid.UUID,
    background: BackgroundTasks,
    ctx: MemberContextDep,
    tenant_id: TenantDep,
    db: DbDep,
    notification_service: NotificationServiceDep,
    _: None = _SEND,
) -> MessageDetail:
    message = get_or_404(db, Message, message_id, "Message not found")
    if message.status not in (MessageStatus.DRAFT, MessageStatus.SCHEDULED):
        raise HTTPException(status_code=409, detail="Message was already sent")

    scheduled_at = message.scheduled_at
    if scheduled_at is not None and scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=UTC)  # SQLite loses tz-awareness
    if scheduled_at is not None and scheduled_at > datetime.now(UTC):
        message.status = MessageStatus.SCHEDULED
        db.commit()
    else:
        send_message(message, db, notification_service)
        background.add_task(_drain_once, tenant_id)

    return get_message(message.id, tenant_id, db)
