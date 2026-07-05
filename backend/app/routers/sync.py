"""Offline sync pull endpoints — see ``docs/spec/sync-protocol.md`` and GH-153.

Each entity gets its own endpoint gated by that entity's read permission. The pull
stream is keyset-paged over ``(sync_seq, id)`` and — uniquely among read paths —
includes soft-deleted rows, because tombstones are how offline clients learn about
deletions.

Visibility: the events stream applies the same audience rules as the interactive
list (``event:write`` holders see everything; everyone else sees troop-wide events
plus their groups' events), and the participants stream is scoped to participants
of events the caller can see. A client that *loses* visibility to an event does not
receive a tombstone for it — reconciliation is the client's mark-and-sweep full
refetch (GH-153 §C2).
"""

import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import ColumnElement, and_, or_, select

from app.core.deps import DbDep, MemberContextDep, TenantDep, require
from app.core.event_visibility import visibility_clause
from app.core.groups import member_group_ids
from app.core.relationships import family_member_ids
from app.core.tenant_context import include_deleted
from app.models.enums import Permission
from app.models.event import Event, EventParticipant
from app.models.event_type import EventType
from app.models.location import Location
from app.models.member import Member, MemberRelationship
from app.schemas.event import EventParticipantRead, EventRead
from app.schemas.event_type import EventTypeRead
from app.schemas.location import LocationRead
from app.schemas.member import MemberRead
from app.schemas.relationship import MemberRelationshipRead
from app.schemas.sync import (
    SyncEventParticipantsPage,
    SyncEventsPage,
    SyncEventTypesPage,
    SyncLocationsPage,
    SyncMemberRelationshipsPage,
    SyncMembersPage,
)

router = APIRouter(prefix="/sync", tags=["sync"])

_LIMIT = Query(default=500, ge=1, le=1000)


def _pull_page[T](
    model: type[T],
    db: Any,
    since_seq: int,
    since_id: uuid.UUID | None,
    limit: int,
    extra_clause: ColumnElement[bool] | None = None,
) -> tuple[Sequence[T], int, uuid.UUID | None, bool]:
    """Fetch one keyset page of *model*'s change stream, tombstones included.

    Returns ``(rows, next_since_seq, next_since_id, has_more)``. Tenant scoping is
    automatic; the soft-delete filter is deliberately lifted so tombstones flow.
    """
    seq = model.sync_seq  # type: ignore[attr-defined]
    id_col = model.id  # type: ignore[attr-defined]
    after_cursor: ColumnElement[bool]
    if since_id is not None:
        after_cursor = or_(seq > since_seq, and_(seq == since_seq, id_col > since_id))
    else:
        after_cursor = seq > since_seq

    query = select(model).where(after_cursor)
    if extra_clause is not None:
        query = query.where(extra_clause)

    with include_deleted():
        rows = db.scalars(
            query.order_by(seq, id_col).limit(
                limit + 1
            )  # fetch one extra row to learn has_more without a COUNT
        ).all()

    has_more = len(rows) > limit
    page = rows[:limit]
    if page:
        next_since_seq: int = page[-1].sync_seq
        next_since_id: uuid.UUID | None = page[-1].id
    else:
        next_since_seq = since_seq
        next_since_id = since_id
    return page, next_since_seq, next_since_id, has_more


def _require_from_ctx(ctx: MemberContextDep, permission: Permission) -> None:
    """Permission check for endpoints that already resolve the member context."""
    _, permissions = ctx
    if permission not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )


def _event_visibility_for(ctx: MemberContextDep, db: DbDep) -> ColumnElement[bool] | None:
    """The events-stream narrowing for this caller (None = manager, sees all)."""
    member, permissions = ctx
    if Permission.EVENT_WRITE in permissions:
        return None
    return visibility_clause(member_group_ids(member.id, db))


def _family_scope(ctx: MemberContextDep, db: DbDep) -> frozenset[uuid.UUID] | None:
    """Member-stream narrowing: ``member:read`` mirrors the roster; everyone
    else mirrors their household (self + wards + co-parents) so family RSVP
    works offline (GH-153 §C3 / the interactive baseline-access rule)."""
    actor, permissions = ctx
    if Permission.MEMBER_READ in permissions:
        return None
    return family_member_ids(actor.id, db)


@router.get("/members", response_model=SyncMembersPage)
def sync_members(
    tenant_id: TenantDep,
    db: DbDep,
    ctx: MemberContextDep,
    since_seq: int = Query(default=0, ge=0),
    since_id: uuid.UUID | None = None,
    limit: int = _LIMIT,
) -> SyncMembersPage:
    """Pull members changed since the ``(since_seq, since_id)`` cursor.

    ``since_seq=0`` (the default) is the initial full sync.
    """
    family = _family_scope(ctx, db)
    extra = Member.id.in_(family) if family is not None else None
    page, next_seq, next_id, has_more = _pull_page(
        Member, db, since_seq, since_id, limit, extra_clause=extra
    )
    items = [MemberRead.model_validate(m) for m in page]
    if family is not None:
        # Family scope carries the household's own data (contact, medical —
        # fields the family already edits interactively). Leader-facing notes
        # were never visible without member:read; keep it that way.
        for item in items:
            item.notes = None
            item.oa_notes = None
    return SyncMembersPage(
        items=items,
        next_since_seq=next_seq,
        next_since_id=next_id,
        has_more=has_more,
    )


@router.get("/member_relationships", response_model=SyncMemberRelationshipsPage)
def sync_member_relationships(
    tenant_id: TenantDep,
    db: DbDep,
    ctx: MemberContextDep,
    since_seq: int = Query(default=0, ge=0),
    since_id: uuid.UUID | None = None,
    limit: int = _LIMIT,
) -> SyncMemberRelationshipsPage:
    """Family edges follow the member stream's scope: full for ``member:read``,
    household-touching edges for everyone else."""
    family = _family_scope(ctx, db)
    extra = (
        or_(
            MemberRelationship.from_member_id.in_(family),
            MemberRelationship.to_member_id.in_(family),
        )
        if family is not None
        else None
    )
    page, next_seq, next_id, has_more = _pull_page(
        MemberRelationship, db, since_seq, since_id, limit, extra_clause=extra
    )
    return SyncMemberRelationshipsPage(
        items=[MemberRelationshipRead.model_validate(r) for r in page],
        next_since_seq=next_seq,
        next_since_id=next_id,
        has_more=has_more,
    )


@router.get(
    "/event_types",
    response_model=SyncEventTypesPage,
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def sync_event_types(
    tenant_id: TenantDep,
    db: DbDep,
    since_seq: int = Query(default=0, ge=0),
    since_id: uuid.UUID | None = None,
    limit: int = _LIMIT,
) -> SyncEventTypesPage:
    page, next_seq, next_id, has_more = _pull_page(EventType, db, since_seq, since_id, limit)
    return SyncEventTypesPage(
        items=[EventTypeRead.model_validate(t) for t in page],
        next_since_seq=next_seq,
        next_since_id=next_id,
        has_more=has_more,
    )


@router.get(
    "/locations",
    response_model=SyncLocationsPage,
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def sync_locations(
    tenant_id: TenantDep,
    db: DbDep,
    since_seq: int = Query(default=0, ge=0),
    since_id: uuid.UUID | None = None,
    limit: int = _LIMIT,
) -> SyncLocationsPage:
    page, next_seq, next_id, has_more = _pull_page(Location, db, since_seq, since_id, limit)
    return SyncLocationsPage(
        items=[LocationRead.model_validate(loc) for loc in page],
        next_since_seq=next_seq,
        next_since_id=next_id,
        has_more=has_more,
    )


@router.get("/events", response_model=SyncEventsPage)
def sync_events(
    tenant_id: TenantDep,
    db: DbDep,
    ctx: MemberContextDep,
    since_seq: int = Query(default=0, ge=0),
    since_id: uuid.UUID | None = None,
    limit: int = _LIMIT,
) -> SyncEventsPage:
    """Pull events, narrowed by the caller's audience visibility (GH-153)."""
    _require_from_ctx(ctx, Permission.EVENT_READ)
    page, next_seq, next_id, has_more = _pull_page(
        Event, db, since_seq, since_id, limit, extra_clause=_event_visibility_for(ctx, db)
    )
    return SyncEventsPage(
        items=[EventRead.model_validate(e) for e in page],
        next_since_seq=next_seq,
        next_since_id=next_id,
        has_more=has_more,
    )


@router.get("/event_participants", response_model=SyncEventParticipantsPage)
def sync_event_participants(
    tenant_id: TenantDep,
    db: DbDep,
    ctx: MemberContextDep,
    since_seq: int = Query(default=0, ge=0),
    since_id: uuid.UUID | None = None,
    limit: int = _LIMIT,
) -> SyncEventParticipantsPage:
    """Pull participants of events the caller can see (GH-153).

    Mirrors the interactive gate: any ``event:read`` member receives all
    participants of visible events (no field trimming — GH-153 default 3).
    """
    _require_from_ctx(ctx, Permission.EVENT_READ)
    visibility = _event_visibility_for(ctx, db)
    extra: ColumnElement[bool] | None = None
    if visibility is not None:
        extra = EventParticipant.event_id.in_(select(Event.id).where(visibility))
    page, next_seq, next_id, has_more = _pull_page(
        EventParticipant, db, since_seq, since_id, limit, extra_clause=extra
    )
    return SyncEventParticipantsPage(
        items=[EventParticipantRead.model_validate(p) for p in page],
        next_since_seq=next_seq,
        next_since_id=next_id,
        has_more=has_more,
    )
