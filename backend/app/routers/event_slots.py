"""Universal event sign-up slots (GH-152).

Named, capacity-limited commitments *within* an event — drivers to/from camp,
grubmaster, merit-badge sessions, fundraiser shifts, cleanup crews. A slot is
orthogonal to the whole-event RSVP (``EventParticipant``): RSVP answers "are you
coming?", a slot answers "what are you doing there?". Signing up for a slot does
**not** create or imply an RSVP, and vice-versa.

Authorization follows two patterns:

- **Slot definition** (create/edit/delete) is manager work — ``event:write``.
- **Sign-up / withdraw** is self-service — the same self+household rule RSVP uses
  (``family_member_ids``), with an ``event:manage_attendance`` bypass so leaders
  can place or remove anyone.

Every route rides event visibility (``event_visible_to_member``): an
audience-hidden event 404s, exactly like ``GET /events/{id}`` — existence is not
leaked. Mirrors ``app/routers/photos.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import DbDep, MemberContextDep, TenantDep, get_or_404, require
from app.core.event_visibility import event_visible_to_member
from app.core.groups import member_group_ids
from app.core.relationships import family_member_ids
from app.core.tenant_context import include_deleted
from app.models.enums import MemberType, Permission, PositionScope
from app.models.event import Event
from app.models.event_slot import EventSlot, EventSlotSignup
from app.models.member import Member
from app.schemas.event_slot import (
    EventSlotCreate,
    EventSlotRead,
    EventSlotSignupCreate,
    EventSlotSignupRead,
    EventSlotUpdate,
)

router = APIRouter(tags=["event-slots"])


def _member_name(member: Member) -> str:
    return f"{member.first_name} {member.last_name}".strip()


def _visible_event_or_404(
    event_id: uuid.UUID, member: Member, permissions: frozenset[Permission], db: DbDep
) -> Event:
    """The event, if the caller may see it — 404 otherwise (existence not leaked)."""
    event = get_or_404(db, Event, event_id, "Event not found")
    if Permission.EVENT_WRITE not in permissions and not event_visible_to_member(
        event_id, member_group_ids(member.id, db), db
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


def _slot_or_404(db: DbDep, event_id: uuid.UUID, slot_id: uuid.UUID) -> EventSlot:
    slot = get_or_404(db, EventSlot, slot_id, "Slot not found")
    if slot.event_id != event_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
    return slot


def _active_signup_count(db: DbDep, slot_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(EventSlotSignup)
            .where(EventSlotSignup.slot_id == slot_id)
        )
        or 0
    )


def _require_can_act_for(
    caller: Member, target_member_id: uuid.UUID, db: DbDep, *, is_manager: bool
) -> None:
    """A non-manager may only sign up / withdraw themselves or their household."""
    if is_manager:
        return
    if target_member_id not in family_member_ids(caller.id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only sign up for yourself or your family",
        )


def _enforce_applies_to(slot: EventSlot, target: Member) -> None:
    if slot.applies_to == PositionScope.SCOUT and target.member_type != MemberType.SCOUT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This slot is for scouts only",
        )
    if slot.applies_to == PositionScope.ADULT and target.member_type != MemberType.ADULT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This slot is for adults only",
        )


def _signup_read(signup: EventSlotSignup, name: str) -> EventSlotSignupRead:
    return EventSlotSignupRead(
        id=signup.id,
        tenant_id=signup.tenant_id,
        created_at=signup.created_at,
        updated_at=signup.updated_at,
        is_deleted=signup.is_deleted,
        slot_id=signup.slot_id,
        member_id=signup.member_id,
        member_name=name,
        comment=signup.comment,
        signed_up_by_id=signup.signed_up_by_id,
        signed_up_at=signup.signed_up_at,
    )


def _serialize_slot(
    slot: EventSlot, signups: list[EventSlotSignup], names: dict[uuid.UUID, str]
) -> EventSlotRead:
    remaining = None if slot.capacity is None else max(slot.capacity - len(signups), 0)
    return EventSlotRead(
        id=slot.id,
        tenant_id=slot.tenant_id,
        created_at=slot.created_at,
        updated_at=slot.updated_at,
        is_deleted=slot.is_deleted,
        event_id=slot.event_id,
        name=slot.name,
        description=slot.description,
        capacity=slot.capacity,
        applies_to=slot.applies_to,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        sort_order=slot.sort_order,
        signups=[_signup_read(s, names.get(s.member_id, "")) for s in signups],
        remaining=remaining,
    )


@router.get("/events/{event_id}/slots", response_model=list[EventSlotRead])
def list_slots(
    event_id: uuid.UUID, tenant_id: TenantDep, db: DbDep, member_ctx: MemberContextDep
) -> list[EventSlotRead]:
    """Slots for an event, ordered by ``sort_order``, each with its signups + remaining."""
    member, permissions = member_ctx
    _visible_event_or_404(event_id, member, permissions, db)
    slots = db.scalars(
        select(EventSlot)
        .where(EventSlot.event_id == event_id)
        .order_by(EventSlot.sort_order, EventSlot.created_at, EventSlot.id)
    ).all()
    if not slots:
        return []
    signups = db.scalars(
        select(EventSlotSignup).where(EventSlotSignup.slot_id.in_([s.id for s in slots]))
    ).all()
    by_slot: dict[uuid.UUID, list[EventSlotSignup]] = {s.id: [] for s in slots}
    for signup in signups:
        by_slot[signup.slot_id].append(signup)
    member_ids = {s.member_id for s in signups}
    names = (
        {
            m.id: _member_name(m)
            for m in db.scalars(select(Member).where(Member.id.in_(member_ids))).all()
        }
        if member_ids
        else {}
    )
    return [_serialize_slot(slot, by_slot[slot.id], names) for slot in slots]


@router.post(
    "/events/{event_id}/slots",
    response_model=EventSlotRead,
    status_code=201,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def create_slot(
    event_id: uuid.UUID,
    body: EventSlotCreate,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
) -> EventSlotRead:
    member, permissions = member_ctx
    _visible_event_or_404(event_id, member, permissions, db)
    if db.scalar(
        select(EventSlot).where(EventSlot.event_id == event_id, EventSlot.name == body.name)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A slot with this name already exists"
        )
    slot = EventSlot(event_id=event_id, **body.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return _serialize_slot(slot, [], {})


@router.patch(
    "/events/{event_id}/slots/{slot_id}",
    response_model=EventSlotRead,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def update_slot(
    event_id: uuid.UUID,
    slot_id: uuid.UUID,
    body: EventSlotUpdate,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
) -> EventSlotRead:
    """Edit a slot. Lowering capacity below the current signup count is allowed —
    existing signups stay and ``remaining`` clamps at 0; managers resolve overflow
    socially, the API never evicts."""
    member, permissions = member_ctx
    _visible_event_or_404(event_id, member, permissions, db)
    slot = _slot_or_404(db, event_id, slot_id)
    updates = body.model_dump(exclude_unset=True)
    new_name = updates.get("name")
    if new_name is not None and new_name != slot.name:
        clash = db.scalar(
            select(EventSlot).where(
                EventSlot.event_id == event_id,
                EventSlot.name == new_name,
                EventSlot.id != slot_id,
            )
        )
        if clash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="A slot with this name already exists"
            )
    for key, value in updates.items():
        setattr(slot, key, value)
    # Window coherence after applying the partial update (start/end may arrive apart).
    if slot.starts_at is not None and slot.ends_at is not None and slot.ends_at < slot.starts_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="ends_at must be on or after starts_at",
        )
    db.commit()
    db.refresh(slot)
    signups = list(
        db.scalars(select(EventSlotSignup).where(EventSlotSignup.slot_id == slot.id)).all()
    )
    names = {
        m.id: _member_name(m)
        for m in db.scalars(
            select(Member).where(Member.id.in_([s.member_id for s in signups]))
        ).all()
    }
    return _serialize_slot(slot, signups, names)


@router.delete(
    "/events/{event_id}/slots/{slot_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def delete_slot(
    event_id: uuid.UUID,
    slot_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
) -> None:
    """Soft-delete a slot and its signups (participants are untouched)."""
    member, permissions = member_ctx
    _visible_event_or_404(event_id, member, permissions, db)
    slot = _slot_or_404(db, event_id, slot_id)
    slot.is_deleted = True
    for signup in db.scalars(
        select(EventSlotSignup).where(EventSlotSignup.slot_id == slot_id)
    ).all():
        signup.is_deleted = True
    db.commit()


@router.post(
    "/events/{event_id}/slots/{slot_id}/signups",
    response_model=EventSlotSignupRead,
    status_code=201,
)
def create_signup(
    event_id: uuid.UUID,
    slot_id: uuid.UUID,
    body: EventSlotSignupCreate,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
) -> EventSlotSignupRead:
    """Claim a slot for a member (self, household, or — with manage_attendance — anyone)."""
    member, permissions = member_ctx
    is_manager = Permission.EVENT_MANAGE_ATTENDANCE in permissions
    _visible_event_or_404(event_id, member, permissions, db)
    slot = _slot_or_404(db, event_id, slot_id)
    target = db.get(Member, body.member_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="member_id not found in this tenant",
        )
    _require_can_act_for(member, body.member_id, db, is_manager=is_manager)
    _enforce_applies_to(slot, target)

    if db.scalar(
        select(EventSlotSignup).where(
            EventSlotSignup.slot_id == slot_id,
            EventSlotSignup.member_id == body.member_id,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Member is already signed up for this slot"
        )

    # Capacity is check-then-insert, which races under concurrency. On Postgres we
    # lock the slot row (SELECT ... FOR UPDATE) so a second signup for the last seat
    # blocks until this transaction commits, then re-counts and 409s. On SQLite
    # (tests) with_for_update is a no-op — a single-threaded race is unreachable, and
    # the unique constraint still prevents duplicates.
    if slot.capacity is not None:
        db.execute(select(EventSlot.id).where(EventSlot.id == slot_id).with_for_update())
        if _active_signup_count(db, slot_id) >= slot.capacity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is full")

    with include_deleted():
        revived = db.scalar(
            select(EventSlotSignup).where(
                EventSlotSignup.slot_id == slot_id,
                EventSlotSignup.member_id == body.member_id,
                EventSlotSignup.is_deleted.is_(True),
            )
        )
    if revived is not None:
        revived.is_deleted = False
        revived.comment = body.comment
        revived.signed_up_by_id = member.id
        revived.signed_up_at = datetime.now(tz=UTC)
        signup = revived
    else:
        signup = EventSlotSignup(
            slot_id=slot_id,
            member_id=body.member_id,
            comment=body.comment,
            signed_up_by_id=member.id,
            signed_up_at=datetime.now(tz=UTC),
        )
        db.add(signup)
    db.commit()
    db.refresh(signup)
    return _signup_read(signup, _member_name(target))


@router.delete(
    "/events/{event_id}/slots/{slot_id}/signups/{member_id}",
    status_code=204,
)
def delete_signup(
    event_id: uuid.UUID,
    slot_id: uuid.UUID,
    member_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    member_ctx: MemberContextDep,
) -> None:
    """Withdraw a member from a slot (soft-delete); 404 if no active signup."""
    member, permissions = member_ctx
    is_manager = Permission.EVENT_MANAGE_ATTENDANCE in permissions
    _visible_event_or_404(event_id, member, permissions, db)
    _slot_or_404(db, event_id, slot_id)
    _require_can_act_for(member, member_id, db, is_manager=is_manager)
    signup = db.scalar(
        select(EventSlotSignup).where(
            EventSlotSignup.slot_id == slot_id,
            EventSlotSignup.member_id == member_id,
        )
    )
    if signup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signup not found")
    signup.is_deleted = True
    db.commit()
