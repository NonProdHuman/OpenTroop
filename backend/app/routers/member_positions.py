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

from app.core.deps import CurrentMemberDep, DbDep, TenantDep, get_or_404, require
from app.core.permissions import (
    admin_assignments,
    current_assignment_clause,
    is_assignment_current,
    member_is_admin,
    position_is_privileged,
)
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
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Position assignment not found")
    return assignment


def _validate_dates(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and end < start:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")


def _require_admin_for_privileged_position(
    position_id: uuid.UUID, tenant_id: uuid.UUID, actor: Member, db: DbDep, detail: str
) -> None:
    """403 unless the actor is an admin, when the position confers admin/meta-governance.

    "You can't grant what you don't have": a ``role:assign`` holder may delegate
    ordinary functional positions (Treasurer, …) but must not be able to create,
    edit, or remove terms of a position that reaches ``is_admin`` or ``role:manage``
    (GH-175 Finding 1). Deliberately *not* a full permission-subset check — see the
    spec in GH-175 for why routine delegation must keep working.
    """
    if position_is_privileged(position_id, tenant_id, db) and not member_is_admin(actor.id, db):
        raise HTTPException(status_code=403, detail=detail)


def _guard_last_admin(
    assignment: MemberPositionAssignment, tenant_id: uuid.UUID, db: DbDep
) -> None:
    """409 if removing/ending this term would leave the tenant with zero administrators.

    Mirrors ``platform.py::revoke_tenant_admin`` via the shared ``admin_assignments``
    definition. Counts distinct *members*: a member holding a second live
    admin-conferring term still counts after this one goes.
    """
    admins = admin_assignments(tenant_id, db)
    if not any(a.id == assignment.id for a in admins):
        return  # not a live admin-conferring term — nothing to protect
    if not {a.member_id for a in admins if a.id != assignment.id}:
        raise HTTPException(status_code=409, detail="Cannot remove the tenant's last administrator")


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
    get_or_404(db, Member, member_id, "Member not found")
    stmt = select(MemberPositionAssignment).where(
        MemberPositionAssignment.member_id == member_id,
    )
    if current:
        stmt = stmt.where(current_assignment_clause())
    else:
        stmt = stmt.order_by(
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
    get_or_404(db, Member, member_id, "Member not found")
    position = get_or_404(db, Position, body.position_id, "position_id")
    if position.is_default:
        raise HTTPException(status_code=409, detail="Default positions cannot be manually assigned")
    _require_admin_for_privileged_position(
        body.position_id, tenant_id, actor, db, "Only administrators can assign this position"
    )

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
    actor: CurrentMemberDep,
) -> MemberPositionAssignment:
    """Edit a term's dates — correct ``start_date``, end a term (set ``end_date``),
    or reopen one (pass ``end_date: null``). Enforces ``end_date >= start_date``.

    Terms of privileged (admin/``role:manage``-conferring) positions may only be
    edited by administrators (403), and ending the tenant's last live
    administrator term is refused (409)."""
    get_or_404(db, Member, member_id, "Member not found")
    assignment = _get_assignment(db, member_id, assignment_id)
    _require_admin_for_privileged_position(
        assignment.position_id,
        tenant_id,
        actor,
        db,
        "Only administrators can modify terms of this position",
    )

    fields = body.model_dump(exclude_unset=True)
    new_start = fields.get("start_date", assignment.start_date)
    new_end = fields.get("end_date", assignment.end_date)
    _validate_dates(new_start, new_end)

    # Ending a currently-live term? Refuse if it's the tenant's last admin term.
    if not is_assignment_current(assignment.is_deleted, new_end):
        _guard_last_admin(assignment, tenant_id, db)

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
    member_id: uuid.UUID,
    assignment_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    actor: CurrentMemberDep,
) -> None:
    """Soft-delete a term — "created in error". Removes it from history entirely;
    distinct from *ending* a term (PATCH ``end_date``), which preserves it.

    Terms of privileged positions may only be deleted by administrators (403),
    and deleting the tenant's last live administrator term is refused (409)."""
    get_or_404(db, Member, member_id, "Member not found")
    assignment = _get_assignment(db, member_id, assignment_id)
    position = db.get(Position, assignment.position_id)
    if position and position.is_default:
        raise HTTPException(status_code=409, detail="Default positions cannot be deleted")
    _require_admin_for_privileged_position(
        assignment.position_id,
        tenant_id,
        actor,
        db,
        "Only administrators can modify terms of this position",
    )
    _guard_last_admin(assignment, tenant_id, db)
    assignment.is_deleted = True
    db.commit()
