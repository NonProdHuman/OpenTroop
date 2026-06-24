import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.deps import DbDep, TenantDep, get_or_404, require, require_tenant_fk
from app.models.enums import Permission
from app.models.member import Member
from app.models.role import MemberRoleAssignment, Role
from app.schemas.role import MemberRoleAssignmentBase, MemberRoleAssignmentRead

router = APIRouter(prefix="/role-assignments", tags=["role-assignments"])


@router.get(
    "/",
    response_model=list[MemberRoleAssignmentRead],
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def list_role_assignments(
    tenant_id: TenantDep,
    db: DbDep,
    member_id: Annotated[uuid.UUID | None, Query()] = None,
    role_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Sequence[MemberRoleAssignment]:
    q = select(MemberRoleAssignment).where(
        MemberRoleAssignment.tenant_id == tenant_id,
        MemberRoleAssignment.is_deleted.is_(False),
    )
    if member_id is not None:
        q = q.where(MemberRoleAssignment.member_id == member_id)
    if role_id is not None:
        q = q.where(MemberRoleAssignment.role_id == role_id)
    return db.scalars(q).all()


@router.post(
    "/",
    response_model=MemberRoleAssignmentRead,
    status_code=201,
    dependencies=[Depends(require(Permission.ROLE_ASSIGN))],
)
def create_role_assignment(
    body: MemberRoleAssignmentBase, tenant_id: TenantDep, db: DbDep
) -> MemberRoleAssignment:
    require_tenant_fk(db, Member, body.member_id, tenant_id, "member_id")
    require_tenant_fk(db, Role, body.role_id, tenant_id, "role_id")
    if body.assigned_by_id is not None:
        require_tenant_fk(db, Member, body.assigned_by_id, tenant_id, "assigned_by_id")
    assignment = MemberRoleAssignment(tenant_id=tenant_id, **body.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get(
    "/{assignment_id}",
    response_model=MemberRoleAssignmentRead,
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def get_role_assignment(
    assignment_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> MemberRoleAssignment:
    return get_or_404(
        db, MemberRoleAssignment, assignment_id, tenant_id, "Role assignment not found"
    )


@router.delete(
    "/{assignment_id}", status_code=204, dependencies=[Depends(require(Permission.ROLE_ASSIGN))]
)
def delete_role_assignment(assignment_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    assignment = get_or_404(
        db, MemberRoleAssignment, assignment_id, tenant_id, "Role assignment not found"
    )
    assignment.is_deleted = True
    db.commit()
