"""Offline sync pull endpoints — see ``docs/spec/sync-protocol.md``.

Each entity gets its own endpoint gated by that entity's read permission. The pull
stream is keyset-paged over ``(sync_seq, id)`` and — uniquely among read paths —
includes soft-deleted rows, because tombstones are how offline clients learn about
deletions.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.core.deps import DbDep, TenantDep, require
from app.core.tenant_context import include_deleted
from app.models.enums import Permission
from app.models.member import Member
from app.schemas.member import MemberRead
from app.schemas.sync import SyncMembersPage

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get(
    "/members",
    response_model=SyncMembersPage,
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def sync_members(
    tenant_id: TenantDep,
    db: DbDep,
    since_seq: int = Query(default=0, ge=0),
    since_id: uuid.UUID | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
) -> SyncMembersPage:
    """Pull members changed since the ``(since_seq, since_id)`` cursor.

    ``since_seq=0`` (the default) is the initial full sync. Tenant scoping is
    automatic; the soft-delete filter is deliberately lifted so tombstones flow.
    """
    after_cursor: ColumnElement[bool]
    if since_id is not None:
        after_cursor = or_(
            Member.sync_seq > since_seq,
            and_(Member.sync_seq == since_seq, Member.id > since_id),
        )
    else:
        after_cursor = Member.sync_seq > since_seq

    with include_deleted():
        rows = db.scalars(
            select(Member)
            .where(after_cursor)
            .order_by(Member.sync_seq, Member.id)
            .limit(limit + 1)  # fetch one extra row to learn has_more without a COUNT
        ).all()

    has_more = len(rows) > limit
    page = rows[:limit]
    if page:
        next_since_seq = page[-1].sync_seq
        next_since_id: uuid.UUID | None = page[-1].id
    else:
        next_since_seq = since_seq
        next_since_id = since_id
    return SyncMembersPage(
        items=[MemberRead.model_validate(m) for m in page],
        next_since_seq=next_since_seq,
        next_since_id=next_since_id,
        has_more=has_more,
    )
