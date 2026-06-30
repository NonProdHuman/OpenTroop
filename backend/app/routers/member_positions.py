"""Assigning positions to members — the only routine RBAC write.

An assignment is a **term**: a member held a position from ``start_date`` to an
optional ``end_date`` (null ⇒ current). A member may hold the same position across
several historical terms, so terms are addressed by their own ``assignment_id`` (not
by ``position_id``). Currency follows the single rule in ``app.core.permissions``.

There is deliberately no endpoint to assign a functional role or a raw permission to
a member: positions are the sole member-facing link (see ``docs/spec/roles-rbac.md``
and ``docs/spec/position-history.md``).
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.deps import CurrentMemberDep, DbDep, TenantDep, get_or_404, require, require_tenant_fk
from app.core.permissions import current_assignment_clause
from app.models.enums import Permission
from app.models.member import Member
from app.models.rbac import MemberPositionAssignment, Position
from app.schemas.rbac import (
    MemberPositionAssignmentCreate,
    MemberPositionAssignmentRead,
    MemberPositionAssignmentUpdate,
)

router = APIRouter(prefix="/members/{member_id}/positions", tags=["member-positions"])


def _get_assignment(
    db: DbDep, member_id: uuid.UUID, assignment_id: uuid.UUID
) -> MemberPositionAssignment:
    """Fetch a non-deleted term belonging to *member_id*, or 404."""
    assignment = db.scalar(
        select(MemberPositionAssignment).where(
            MemberPositionAssignment.id == assignment_id,
            MemberPositionAssignment.member_id == member_id,
            MemberPositionAssignment.is_deleted.is_(False),
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Position assignment not found")
    return assignment


def _validate_dates(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and end < start:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")


@router.get(
    "",
    response_model=list[MemberPositionAssignmentRead],
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def list_member_positions(
    member_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    current: bool = True,
) -> Sequence[MemberPositionAssignment]:
    """List a member's position terms.

    ``current=true`` (default) returns only live terms; ``current=false`` returns the
    full non-deleted history, newest term first.
    """
    get_or_404(db, Member, member_id, tenant_id, "Member not found")
    stmt = select(MemberPositionAssignment).where(
        MemberPositionAssignment.member_id == member_id,
    )
    if current:
        stmt = stmt.where(current_assignment_clause())
    else:
        stmt = stmt.where(MemberPositionAssignment.is_deleted.is_(False)).order_by(
            MemberPositionAssignment.start_date.desc().nullslast(),
            MemberPositionAssignment.created_at.desc(),
        )
    return db.scalars(stmt).all()


@router.post(
    "",
    response_model=MemberPositionAssignmentRead,
    status_code=201,
    dependencies=[Depends(require(Permission.ROLE_ASSIGN))],
)
def assign_position(
    member_id: uuid.UUID,
    body: MemberPositionAssignmentCreate,
    tenant_id: TenantDep,
    db: DbDep,
    actor: CurrentMemberDep,
) -> MemberPositionAssignment:
    """Start a term: assign a position to a member.

    Returns 409 if the member already holds a **current** term for that position
    (ended terms don't block re-assignment). ``start_date`` defaults to today.
    """
    get_or_404(db, Member, member_id, tenant_id, "Member not found")
    require_tenant_fk(db, Position, body.position_id, tenant_id, "position_id")
    _validate_dates(body.start_date, body.end_date)

    current_term = db.scalar(
        select(MemberPositionAssignment).where(
            MemberPositionAssignment.member_id == member_id,
            MemberPositionAssignment.position_id == body.position_id,
            current_assignment_clause(),
        )
    )
    if current_term is not None:
        raise HTTPException(status_code=409, detail="Member already currently holds this position")

    assignment = MemberPositionAssignment(
        tenant_id=tenant_id,
        member_id=member_id,
        position_id=body.position_id,
        assigned_by_id=actor.id,
        start_date=body.start_date or datetime.now(UTC).date(),
        end_date=body.end_date,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.patch(
    "/{assignment_id}",
    response_model=MemberPositionAssignmentRead,
    dependencies=[Depends(require(Permission.ROLE_ASSIGN))],
)
def update_position_term(
    member_id: uuid.UUID,
    assignment_id: uuid.UUID,
    body: MemberPositionAssignmentUpdate,
    tenant_id: TenantDep,
    db: DbDep,
) -> MemberPositionAssignment:
    """Edit a term's dates — correct ``start_date``, end a term (set ``end_date``),
    or reopen one (pass ``end_date: null``). Enforces ``end_date >= start_date``."""
    get_or_404(db, Member, member_id, tenant_id, "Member not found")
    assignment = _get_assignment(db, member_id, assignment_id)

    fields = body.model_dump(exclude_unset=True)
    new_start = fields.get("start_date", assignment.start_date)
    new_end = fields.get("end_date", assignment.end_date)
    _validate_dates(new_start, new_end)

    if "start_date" in fields:
        assignment.start_date = fields["start_date"]
    if "end_date" in fields:
        assignment.end_date = fields["end_date"]
    db.commit()
    db.refresh(assignment)
    return assignment


@router.delete(
    "/{assignment_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.ROLE_ASSIGN))],
)
def delete_position_term(
    member_id: uuid.UUID, assignment_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> None:
    """Soft-delete a term — "created in error". Removes it from history entirely;
    distinct from *ending* a term (PATCH ``end_date``), which preserves it."""
    get_or_404(db, Member, member_id, tenant_id, "Member not found")
    assignment = _get_assignment(db, member_id, assignment_id)
    assignment.is_deleted = True
    db.commit()
