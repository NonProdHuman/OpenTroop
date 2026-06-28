import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import (
    CurrentMemberDep,
    DbDep,
    TenantDep,
    get_or_404,
    require,
    require_tenant_fk,
)
from app.core.event_visibility import event_visible_to_member, visibility_clause
from app.core.groups import member_group_ids
from app.core.permissions import resolve_permissions
from app.models.enums import Permission
from app.models.event import Event, EventOrganizer, EventParticipant
from app.models.event_audience import EventAudience
from app.models.event_type import EventType
from app.models.group import Group
from app.models.location import Location
from app.models.member import Member
from app.schemas.event import (
    EventAudienceCreate,
    EventAudienceRead,
    EventBase,
    EventOrganizerBase,
    EventOrganizerRead,
    EventParticipantBase,
    EventParticipantRead,
    EventParticipantUpdate,
    EventRead,
    EventUpdate,
)

router = APIRouter(prefix="/events", tags=["events"])


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@router.get(
    "/", response_model=list[EventRead], dependencies=[Depends(require(Permission.EVENT_READ))]
)
def list_events(tenant_id: TenantDep, db: DbDep, member: CurrentMemberDep) -> Sequence[Event]:
    """List events visible to the caller.

    Event managers (``event:write``) see every event; everyone else sees troop-wide
    events plus events whose audience includes one of their groups.
    """
    query = select(Event).where(Event.is_deleted.is_(False))
    if Permission.EVENT_WRITE not in resolve_permissions(member.id, db):
        query = query.where(visibility_clause(member_group_ids(member.id, db), tenant_id))
    return db.scalars(query).all()


@router.post(
    "/",
    response_model=EventRead,
    status_code=201,
    dependencies=[Depends(require(Permission.EVENT_CREATE))],
)
def create_event(body: EventBase, tenant_id: TenantDep, db: DbDep) -> Event:
    require_tenant_fk(db, EventType, body.event_type_id, tenant_id, "event_type_id")
    if body.location_id is not None:
        require_tenant_fk(db, Location, body.location_id, tenant_id, "location_id")
    if body.linked_event_id is not None:
        require_tenant_fk(db, Event, body.linked_event_id, tenant_id, "linked_event_id")
    event = Event(tenant_id=tenant_id, **body.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get(
    "/{event_id}",
    response_model=EventRead,
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def get_event(
    event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep, member: CurrentMemberDep
) -> Event:
    event = get_or_404(db, Event, event_id, tenant_id, "Event not found")
    # Hide audience-scoped events from members outside the audience (404, not 403,
    # so their existence isn't leaked). Managers bypass.
    if Permission.EVENT_WRITE not in resolve_permissions(member.id, db) and (
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
    event = get_or_404(db, Event, event_id, tenant_id, "Event not found")
    updates = body.model_dump(exclude_unset=True)
    if "event_type_id" in updates:
        require_tenant_fk(db, EventType, updates["event_type_id"], tenant_id, "event_type_id")
    if "location_id" in updates and updates["location_id"] is not None:
        require_tenant_fk(db, Location, updates["location_id"], tenant_id, "location_id")
    if "linked_event_id" in updates and updates["linked_event_id"] is not None:
        require_tenant_fk(db, Event, updates["linked_event_id"], tenant_id, "linked_event_id")
    for k, v in updates.items():
        setattr(event, k, v)
    db.commit()
    db.refresh(event)
    return event


@router.delete(
    "/{event_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.EVENT_DELETE))],
)
def delete_event(event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    event = get_or_404(db, Event, event_id, tenant_id, "Event not found")
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
    get_or_404(db, Event, event_id, tenant_id, "Event not found")
    return db.scalars(
        select(EventAudience).where(
            EventAudience.event_id == event_id, EventAudience.is_deleted.is_(False)
        )
    ).all()


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
    get_or_404(db, Event, event_id, tenant_id, "Event not found")
    require_tenant_fk(db, Group, body.group_id, tenant_id, "group_id")
    existing = db.scalar(
        select(EventAudience).where(
            EventAudience.event_id == event_id,
            EventAudience.group_id == body.group_id,
            EventAudience.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing
    audience = EventAudience(tenant_id=tenant_id, event_id=event_id, group_id=body.group_id)
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
    get_or_404(db, Event, event_id, tenant_id, "Event not found")
    audience = db.scalar(
        select(EventAudience).where(
            EventAudience.event_id == event_id,
            EventAudience.group_id == group_id,
            EventAudience.is_deleted.is_(False),
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
    get_or_404(db, Event, event_id, tenant_id, "Event not found")
    return db.scalars(
        select(EventOrganizer).where(
            EventOrganizer.event_id == event_id, EventOrganizer.is_deleted.is_(False)
        )
    ).all()


@router.post(
    "/{event_id}/organizers",
    response_model=EventOrganizerRead,
    status_code=201,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def add_organizer(
    event_id: uuid.UUID, body: EventOrganizerBase, tenant_id: TenantDep, db: DbDep
) -> EventOrganizer:
    get_or_404(db, Event, event_id, tenant_id, "Event not found")
    require_tenant_fk(db, Member, body.member_id, tenant_id, "member_id")
    existing = db.scalar(
        select(EventOrganizer).where(
            EventOrganizer.event_id == event_id,
            EventOrganizer.member_id == body.member_id,
            EventOrganizer.is_deleted.is_(False),
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Member is already an organizer"
        )
    organizer = EventOrganizer(tenant_id=tenant_id, event_id=event_id, member_id=body.member_id)
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
    get_or_404(db, Event, event_id, tenant_id, "Event not found")
    organizer = db.scalar(
        select(EventOrganizer).where(
            EventOrganizer.event_id == event_id,
            EventOrganizer.member_id == member_id,
            EventOrganizer.is_deleted.is_(False),
        )
    )
    if organizer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizer not found")
    organizer.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------


@router.get(
    "/{event_id}/participants",
    response_model=list[EventParticipantRead],
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def list_participants(
    event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> Sequence[EventParticipant]:
    get_or_404(db, Event, event_id, tenant_id, "Event not found")
    return db.scalars(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id, EventParticipant.is_deleted.is_(False)
        )
    ).all()


@router.post(
    "/{event_id}/participants",
    response_model=EventParticipantRead,
    status_code=201,
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def add_participant(
    event_id: uuid.UUID, body: EventParticipantBase, tenant_id: TenantDep, db: DbDep
) -> EventParticipant:
    get_or_404(db, Event, event_id, tenant_id, "Event not found")
    require_tenant_fk(db, Member, body.member_id, tenant_id, "member_id")
    if body.electronic_permission_by_id is not None:
        require_tenant_fk(
            db, Member, body.electronic_permission_by_id, tenant_id, "electronic_permission_by_id"
        )
    existing = db.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id,
            EventParticipant.member_id == body.member_id,
            EventParticipant.is_deleted.is_(False),
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Member is already a participant"
        )
    participant = EventParticipant(tenant_id=tenant_id, event_id=event_id, **body.model_dump())
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


@router.patch(
    "/{event_id}/participants/{member_id}",
    response_model=EventParticipantRead,
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def update_participant(
    event_id: uuid.UUID,
    member_id: uuid.UUID,
    body: EventParticipantUpdate,
    tenant_id: TenantDep,
    db: DbDep,
) -> EventParticipant:
    get_or_404(db, Event, event_id, tenant_id, "Event not found")
    participant = db.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id,
            EventParticipant.member_id == member_id,
            EventParticipant.is_deleted.is_(False),
        )
    )
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    updates = body.model_dump(exclude_unset=True)
    if (
        "electronic_permission_by_id" in updates
        and updates["electronic_permission_by_id"] is not None
    ):
        require_tenant_fk(
            db,
            Member,
            updates["electronic_permission_by_id"],
            tenant_id,
            "electronic_permission_by_id",
        )
    if "attended" in updates:
        event = get_or_404(db, Event, event_id, tenant_id, "Event not found")
        if not event.attendance_taken:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Attendance has not been opened for this event",
            )
    for k, v in updates.items():
        setattr(participant, k, v)
    db.commit()
    db.refresh(participant)
    return participant


@router.delete(
    "/{event_id}/participants/{member_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def remove_participant(
    event_id: uuid.UUID, member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> None:
    get_or_404(db, Event, event_id, tenant_id, "Event not found")
    participant = db.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id,
            EventParticipant.member_id == member_id,
            EventParticipant.is_deleted.is_(False),
        )
    )
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    participant.is_deleted = True
    db.commit()
