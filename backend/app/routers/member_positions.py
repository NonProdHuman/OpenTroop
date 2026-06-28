"""Assigning positions to members — the only routine RBAC write.

There is deliberately no endpoint to assign a functional role or a raw permission
to a member: positions are the sole member-facing link (see
``docs/spec/roles-rbac.md``).
"""

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.deps import CurrentMemberDep, DbDep, TenantDep, get_or_404, require, require_tenant_fk
from app.models.enums import Permission
from app.models.member import Member
from app.models.rbac import MemberPositionAssignment, Position
from app.schemas.rbac import MemberPositionAssignmentCreate, MemberPositionAssignmentRead

router = APIRouter(prefix="/members/{member_id}/positions", tags=["member-positions"])


@router.get(
    "",
    response_model=list[MemberPositionAssignmentRead],
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def list_member_positions(
    member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> Sequence[MemberPositionAssignment]:
    get_or_404(db, Member, member_id, tenant_id, "Member not found")
    return db.scalars(
        select(MemberPositionAssignment).where(
            MemberPositionAssignment.member_id == member_id,
            MemberPositionAssignment.is_deleted.is_(False),
        )
    ).all()


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
    """Assign a position to a member. Idempotent (revives a prior unassignment)."""
    get_or_404(db, Member, member_id, tenant_id, "Member not found")
    require_tenant_fk(db, Position, body.position_id, tenant_id, "position_id")

    existing = db.scalar(
        select(MemberPositionAssignment).where(
            MemberPositionAssignment.member_id == member_id,
            MemberPositionAssignment.position_id == body.position_id,
        )
    )
    if existing is not None:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.assigned_by_id = actor.id
            db.commit()
            db.refresh(existing)
        return existing

    assignment = MemberPositionAssignment(
        tenant_id=tenant_id,
        member_id=member_id,
        position_id=body.position_id,
        assigned_by_id=actor.id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.delete(
    "/{position_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.ROLE_ASSIGN))],
)
def unassign_position(
    member_id: uuid.UUID, position_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> None:
    get_or_404(db, Member, member_id, tenant_id, "Member not found")
    assignment = db.scalar(
        select(MemberPositionAssignment).where(
            MemberPositionAssignment.member_id == member_id,
            MemberPositionAssignment.position_id == position_id,
            MemberPositionAssignment.is_deleted.is_(False),
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Member does not hold this position")
    assignment.is_deleted = True
    db.commit()
