import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbDep, TenantDep, get_or_404, require, require_tenant_fk
from app.models.enums import Permission
from app.models.event import Event, EventOrganizer, EventParticipant
from app.models.event_type import EventType
from app.models.location import Location
from app.models.member import Member
from app.schemas.event import (
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
def list_events(tenant_id: TenantDep, db: DbDep) -> Sequence[Event]:
    return db.scalars(
        select(Event).where(Event.tenant_id == tenant_id, Event.is_deleted.is_(False))
    ).all()


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
def get_event(event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Event:
    return get_or_404(db, Event, event_id, tenant_id, "Event not found")


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
