import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.advancement import (
    apply_auto_credits,
    auto_credit_enabled,
    recompute_member_advancement,
)
from app.core.deps import (
    CurrentMemberDep,
    DbDep,
    MemberContextDep,
    NotificationServiceDep,
    TenantDep,
    get_or_404,
    require,
    require_tenant_fk,
)
from app.core.event_notifications import (
    build_cancellation_email,
    build_permission_request_email,
    cancellation_recipients,
    event_when,
    permission_request_recipients,
)
from app.core.event_visibility import event_visible_to_member, visibility_clause
from app.core.groups import member_group_ids
from app.core.notifications import EmailSendError
from app.core.permission_slip import (
    DEFAULT_PERMISSION_MESSAGE,
    effective_permission_message,
    permission_required,
    permission_status,
)
from app.core.relationships import family_member_ids, is_guardian_of
from app.models.enums import MemberType, Permission, RsvpStatus
from app.models.event import Event, EventOrganizer, EventParticipant
from app.models.event_audience import EventAudience
from app.models.event_type import EventType
from app.models.group import Group
from app.models.location import Location
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.event import (
    EventAudienceCreate,
    EventAudienceRead,
    EventBase,
    EventNotifyResult,
    EventOrganizerBase,
    EventOrganizerRead,
    EventParticipantBase,
    EventParticipantCounts,
    EventParticipantPermission,
    EventParticipantRead,
    EventParticipantUpdate,
    EventRead,
    EventUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])

# Participant / event fields whose changes feed the advancement auto-credit
# engine (GH-92). Kept next to the handlers that consult them.
_ADVANCEMENT_PARTICIPANT_FIELDS = frozenset(
    {
        "attended",
        "community_service_hours_override",
        "conservation_hours_override",
        "hiking_miles_override",
        "camping_nights_override",
    }
)
_ADVANCEMENT_EVENT_FIELDS = frozenset(
    {
        "community_service_hours",
        "conservation_hours",
        "hiking_miles",
        "camping_nights",
        "event_type_id",
        "scheduled_start",
    }
)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@router.get("", response_model=list[EventRead])
def list_events(tenant_id: TenantDep, db: DbDep, member_ctx: MemberContextDep) -> Sequence[Event]:
    """List events visible to the caller.

    Event managers (``event:write``) see every event; everyone else sees troop-wide
    events plus events whose audience includes one of their groups.
    """
    member, permissions = member_ctx
    if Permission.EVENT_READ not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    query = select(Event)
    if Permission.EVENT_WRITE not in permissions:
        query = query.where(visibility_clause(member_group_ids(member.id, db)))
    return db.scalars(query).all()


@router.post(
    "",
    response_model=EventRead,
    status_code=201,
    dependencies=[Depends(require(Permission.EVENT_CREATE))],
)
def create_event(body: EventBase, tenant_id: TenantDep, db: DbDep) -> Event:
    require_tenant_fk(db, EventType, body.event_type_id, "event_type_id")
    if body.location_id is not None:
        require_tenant_fk(db, Location, body.location_id, "location_id")
    if body.linked_event_id is not None:
        require_tenant_fk(db, Event, body.linked_event_id, "linked_event_id")
    event = Event(**body.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/{event_id}", response_model=EventRead)
def get_event(
    event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep, member_ctx: MemberContextDep
) -> Event:
    member, permissions = member_ctx
    if Permission.EVENT_READ not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    event = get_or_404(db, Event, event_id, "Event not found")
    # Hide audience-scoped events from members outside the audience (404, not 403,
    # so their existence isn't leaked). Managers bypass.
    if Permission.EVENT_WRITE not in permissions and (
        not event_visible_to_member(event_id, member_group_ids(member.id, db), db)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.patch(
    "/{event_id}",
    response_model=EventRead,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def update_event(event_id: uuid.UUID, body: EventUpdate, tenant_id: TenantDep, db: DbDep) -> Event:
    event = get_or_404(db, Event, event_id, "Event not found")
    updates = body.model_dump(exclude_unset=True)
    if "event_type_id" in updates:
        require_tenant_fk(db, EventType, updates["event_type_id"], "event_type_id")
    if "location_id" in updates and updates["location_id"] is not None:
        require_tenant_fk(db, Location, updates["location_id"], "location_id")
    if "linked_event_id" in updates and updates["linked_event_id"] is not None:
        require_tenant_fk(db, Event, updates["linked_event_id"], "linked_event_id")
    for k, v in updates.items():
        setattr(event, k, v)
    db.commit()
    db.refresh(event)
    # Editing an event's activity metrics moves every attendee's advancement
    # meters (GH-92): re-run auto-credit for each attended member. Bounded by
    # troop size; one commit for the batch.
    if updates.keys() & _ADVANCEMENT_EVENT_FIELDS and auto_credit_enabled(tenant_id, db):
        attendee_ids = db.scalars(
            select(EventParticipant.member_id).where(
                EventParticipant.event_id == event.id,
                EventParticipant.attended.is_(True),
            )
        ).all()
        credited = False
        for attendee_id in attendee_ids:
            credited = bool(apply_auto_credits(attendee_id, db)) or credited
        if credited:
            db.commit()
    return event


@router.delete(
    "/{event_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.EVENT_DELETE))],
)
def delete_event(event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    event = get_or_404(db, Event, event_id, "Event not found")
    event.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Audiences (visibility)
# ---------------------------------------------------------------------------


@router.get(
    "/{event_id}/audiences",
    response_model=list[EventAudienceRead],
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def list_event_audiences(
    event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> Sequence[EventAudience]:
    """List the groups an event is scoped to. Empty = troop-wide."""
    get_or_404(db, Event, event_id, "Event not found")
    return db.scalars(select(EventAudience).where(EventAudience.event_id == event_id)).all()


@router.post(
    "/{event_id}/audiences",
    response_model=EventAudienceRead,
    status_code=201,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def add_event_audience(
    event_id: uuid.UUID, body: EventAudienceCreate, tenant_id: TenantDep, db: DbDep
) -> EventAudience:
    """Scope an event to a group. Idempotent. The first audience makes the event
    non-troop-wide."""
    get_or_404(db, Event, event_id, "Event not found")
    require_tenant_fk(db, Group, body.group_id, "group_id")
    existing = db.scalar(
        select(EventAudience).where(
            EventAudience.event_id == event_id,
            EventAudience.group_id == body.group_id,
        )
    )
    if existing is not None:
        return existing
    audience = EventAudience(event_id=event_id, group_id=body.group_id)
    db.add(audience)
    db.commit()
    db.refresh(audience)
    return audience


@router.delete(
    "/{event_id}/audiences/{group_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def remove_event_audience(
    event_id: uuid.UUID, group_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> None:
    """Remove a group from an event's audience. Removing the last one makes the
    event troop-wide again."""
    get_or_404(db, Event, event_id, "Event not found")
    audience = db.scalar(
        select(EventAudience).where(
            EventAudience.event_id == event_id,
            EventAudience.group_id == group_id,
        )
    )
    if audience is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audience not found")
    audience.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Organizers
# ---------------------------------------------------------------------------


@router.get(
    "/{event_id}/organizers",
    response_model=list[EventOrganizerRead],
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def list_organizers(
    event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> Sequence[EventOrganizer]:
    get_or_404(db, Event, event_id, "Event not found")
    return db.scalars(select(EventOrganizer).where(EventOrganizer.event_id == event_id)).all()


@router.post(
    "/{event_id}/organizers",
    response_model=EventOrganizerRead,
    status_code=201,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def add_organizer(
    event_id: uuid.UUID, body: EventOrganizerBase, tenant_id: TenantDep, db: DbDep
) -> EventOrganizer:
    get_or_404(db, Event, event_id, "Event not found")
    require_tenant_fk(db, Member, body.member_id, "member_id")
    existing = db.scalar(
        select(EventOrganizer).where(
            EventOrganizer.event_id == event_id,
            EventOrganizer.member_id == body.member_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Member is already an organizer"
        )
    organizer = EventOrganizer(event_id=event_id, member_id=body.member_id)
    db.add(organizer)
    db.commit()
    db.refresh(organizer)
    return organizer


@router.delete(
    "/{event_id}/organizers/{member_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def remove_organizer(
    event_id: uuid.UUID, member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> None:
    get_or_404(db, Event, event_id, "Event not found")
    organizer = db.scalar(
        select(EventOrganizer).where(
            EventOrganizer.event_id == event_id,
            EventOrganizer.member_id == member_id,
        )
    )
    if organizer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizer not found")
    organizer.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------


def _get_participant_or_404(
    db: DbDep, event_id: uuid.UUID, member_id: uuid.UUID
) -> EventParticipant:
    """Fetch a member's (non-deleted, tenant-scoped) participant row for an event, or 404."""
    participant = db.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id,
            EventParticipant.member_id == member_id,
        )
    )
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    return participant


def _require_can_act_for(
    caller: Member, target_member_id: uuid.UUID, db: DbDep, *, is_manager: bool
) -> None:
    """A non-manager may only RSVP for themselves or members of their household."""
    if is_manager:
        return
    if target_member_id not in family_member_ids(caller.id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only RSVP for yourself or your family",
        )


def _enforce_signup_window(event: Event, *, is_manager: bool) -> None:
    """Block RSVP outside the event's sign-up window. Null bounds are unrestricted."""
    if is_manager:
        return
    today = datetime.now(tz=UTC).date()
    if event.signup_start is not None and today < event.signup_start:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Sign-ups have not opened yet"
        )
    if event.signup_deadline is not None and today > event.signup_deadline:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="The sign-up deadline has passed"
        )


def _tenant_message(db: DbDep, tenant_id: uuid.UUID) -> str:
    """Effective permission language for the tenant (default when the row is absent)."""
    tenant = db.get(Tenant, tenant_id)
    return (
        effective_permission_message(tenant) if tenant is not None else DEFAULT_PERMISSION_MESSAGE
    )


def _with_permission_status(
    participant: EventParticipant, event: Event, effective_message: str, member: Member | None
) -> EventParticipant:
    """Attach the derived permission_status (read-only) for serialization.

    The caller supplies *member* so list endpoints can batch-load members once (one
    ``IN`` query) instead of firing a ``db.get`` per participant.
    """
    if member is not None:
        participant.permission_status = permission_status(
            participant, event.event_type, member, effective_message
        )
    return participant


@router.get(
    "/{event_id}/participants",
    response_model=list[EventParticipantRead],
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def list_participants(
    event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> Sequence[EventParticipant]:
    event = get_or_404(db, Event, event_id, "Event not found")
    effective_message = _tenant_message(db, tenant_id)
    participants = db.scalars(
        select(EventParticipant).where(EventParticipant.event_id == event_id)
    ).all()
    # Batch-load the members once instead of a db.get per participant (avoids N+1).
    member_ids = {p.member_id for p in participants}
    members = (
        {m.id: m for m in db.scalars(select(Member).where(Member.id.in_(member_ids))).all()}
        if member_ids
        else {}
    )
    return [
        _with_permission_status(p, event, effective_message, members.get(p.member_id))
        for p in participants
    ]


@router.get(
    "/{event_id}/counts",
    response_model=EventParticipantCounts,
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def participant_counts(
    event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> EventParticipantCounts:
    get_or_404(db, Event, event_id, "Event not found")
    rows = db.execute(
        select(EventParticipant, Member.member_type)
        .join(Member, Member.id == EventParticipant.member_id)
        .where(EventParticipant.event_id == event_id)
    ).all()
    scouts = adults = drivers = guests = 0
    for participant, member_type in rows:
        going = participant.rsvp_status == RsvpStatus.GOING
        if going and member_type == MemberType.SCOUT:
            scouts += 1
        if going and member_type == MemberType.ADULT:
            adults += 1
        if participant.driver:
            drivers += 1
        if going:
            guests += participant.guest_count
    return EventParticipantCounts(scouts=scouts, adults=adults, drivers=drivers, guests=guests)


@router.post(
    "/{event_id}/participants",
    response_model=EventParticipantRead,
    status_code=201,
)
def add_participant(
    event_id: uuid.UUID,
    body: EventParticipantBase,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
) -> EventParticipant:
    member, permissions = member_ctx
    is_manager = Permission.EVENT_WRITE in permissions
    event = get_or_404(db, Event, event_id, "Event not found")
    require_tenant_fk(db, Member, body.member_id, "member_id")
    _require_can_act_for(member, body.member_id, db, is_manager=is_manager)
    _enforce_signup_window(event, is_manager=is_manager)
    existing = db.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id,
            EventParticipant.member_id == body.member_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Member is already a participant"
        )
    participant = EventParticipant(event_id=event_id, **body.model_dump())
    db.add(participant)
    db.commit()
    db.refresh(participant)
    target = db.get(Member, participant.member_id)
    return _with_permission_status(participant, event, _tenant_message(db, tenant_id), target)


@router.patch(
    "/{event_id}/participants/{member_id}",
    response_model=EventParticipantRead,
)
def update_participant(
    event_id: uuid.UUID,
    member_id: uuid.UUID,
    body: EventParticipantUpdate,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
) -> EventParticipant:
    member, permissions = member_ctx
    is_manager = Permission.EVENT_WRITE in permissions
    event = get_or_404(db, Event, event_id, "Event not found")
    participant = _get_participant_or_404(db, event_id, member_id)
    updates = body.model_dump(exclude_unset=True)
    _require_can_act_for(member, member_id, db, is_manager=is_manager)
    if "rsvp_status" in updates:
        _enforce_signup_window(event, is_manager=is_manager)
    if "attended" in updates and not event.attendance_taken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance has not been opened for this event",
        )
    for k, v in updates.items():
        setattr(participant, k, v)
    db.commit()
    db.refresh(participant)
    # Attendance and per-person activity overrides feed the advancement
    # auto-credit engine (GH-92) — recompute this member synchronously.
    if updates.keys() & _ADVANCEMENT_PARTICIPANT_FIELDS:
        recompute_member_advancement(member_id, tenant_id, db)
    target = db.get(Member, participant.member_id)
    return _with_permission_status(participant, event, _tenant_message(db, tenant_id), target)


@router.post(
    "/{event_id}/participants/{member_id}/permission",
    response_model=EventParticipantRead,
)
def grant_permission(
    event_id: uuid.UUID,
    member_id: uuid.UUID,
    body: EventParticipantPermission,
    tenant_id: TenantDep,
    db: DbDep,
    member: CurrentMemberDep,
) -> EventParticipant:
    """A parent/guardian signs a scout's permission slip — the official digital record.

    Only a *direct* parent/guardian may sign (no manager/leader bypass: a leader cannot
    record permission on a parent's behalf). The exact tenant language is snapshotted.
    """
    event = get_or_404(db, Event, event_id, "Event not found")
    participant = _get_participant_or_404(db, event_id, member_id)
    target = db.get(Member, member_id)
    if target is None or not permission_required(event.event_type, target):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A permission slip is not applicable for this member and event",
        )
    if participant.rsvp_status != RsvpStatus.GOING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The scout must be going before permission can be granted",
        )
    if not is_guardian_of(member.id, member_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a parent or guardian may sign this permission slip",
        )
    effective_message = _tenant_message(db, tenant_id)
    participant.electronic_permission = True
    participant.electronic_permission_at = datetime.now(tz=UTC)
    participant.electronic_permission_by_id = member.id
    participant.electronic_permission_signature = body.signature
    participant.permission_message_snapshot = effective_message
    db.commit()
    db.refresh(participant)
    return _with_permission_status(participant, event, effective_message, target)


@router.delete(
    "/{event_id}/participants/{member_id}",
    status_code=204,
)
def remove_participant(
    event_id: uuid.UUID,
    member_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
) -> None:
    member, permissions = member_ctx
    get_or_404(db, Event, event_id, "Event not found")
    participant = _get_participant_or_404(db, event_id, member_id)
    _require_can_act_for(member, member_id, db, is_manager=Permission.EVENT_WRITE in permissions)
    participant.is_deleted = True
    db.commit()


@router.post(
    "/{event_id}/cancel",
    response_model=EventRead,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def cancel_event(
    event_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    notification_service: NotificationServiceDep,
) -> Event:
    """Cancel an event and email everyone it was visible to (plus scouts' parents).

    Cancellation commits before any email goes out — the record is the source of
    truth and sends are best-effort. Firing again is a 409, so the notification
    can never double-send.
    """
    event = get_or_404(db, Event, event_id, "Event not found")
    if event.cancelled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Event is already cancelled"
        )
    event.cancelled_at = datetime.now(UTC)
    recipients = cancellation_recipients(event, db)
    db.commit()
    db.refresh(event)

    tenant = db.get(Tenant, tenant_id)
    tenant_name = tenant.name if tenant is not None else "your troop"
    when = event_when(event)
    for member in recipients:
        assert member.email is not None  # _emailable guarantees it  # noqa: S101
        message = build_cancellation_email(
            to=member.email,
            first_name=member.first_name,
            event_name=event.name,
            when=when,
            tenant_name=tenant_name,
        )
        try:
            notification_service.send_email(message)
        except EmailSendError:
            logger.warning(
                "Cancellation email failed for member %s on event %s",
                member.id.hex,
                event_id.hex,
            )
    return event


@router.post(
    "/{event_id}/notify-permissions",
    response_model=EventNotifyResult,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def notify_permission_requests(
    event_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    notification_service: NotificationServiceDep,
) -> EventNotifyResult:
    """Email the parents of scout participants who still owe a permission slip.

    Explicit admin action (not automatic on signup) so a leader controls when the
    ask goes out and can re-send later; 409 when the event's type doesn't require
    permission slips.
    """
    event = get_or_404(db, Event, event_id, "Event not found")
    if not event.event_type.require_permission_slip:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This event's type does not require permission slips",
        )

    tenant = db.get(Tenant, tenant_id)
    tenant_name = tenant.name if tenant is not None else "your troop"
    when = event_when(event)
    emails_sent = 0
    for parent, scouts in permission_request_recipients(event, db).values():
        assert parent.email is not None  # _emailable guarantees it  # noqa: S101
        message = build_permission_request_email(
            to=parent.email,
            first_name=parent.first_name,
            scout_names=[s.first_name for s in scouts],
            event_name=event.name,
            when=when,
            tenant_name=tenant_name,
        )
        try:
            notification_service.send_email(message)
            emails_sent += 1
        except EmailSendError:
            logger.warning(
                "Permission-request email failed for member %s on event %s",
                parent.id.hex,
                event_id.hex,
            )
    return EventNotifyResult(emails_sent=emails_sent)
