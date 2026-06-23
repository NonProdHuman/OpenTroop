import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.core.deps import DbDep, TenantDep
from app.models.member import Member
from app.models.role import MemberRoleAssignment, Role
from app.schemas.role import MemberRoleAssignmentBase, MemberRoleAssignmentRead

router = APIRouter(prefix="/role-assignments", tags=["role-assignments"])


def _get_or_404(db: Session, assignment_id: uuid.UUID, tenant_id: uuid.UUID) -> MemberRoleAssignment:
    a = db.get(MemberRoleAssignment, assignment_id)
    if not a or a.tenant_id != tenant_id or a.is_deleted:
        raise HTTPException(status_code=404, detail="Role assignment not found")
    return a


def _check_member_tenant(db: Session, member_id: uuid.UUID, tenant_id: uuid.UUID, field: str) -> None:
    m = db.get(Member, member_id)
    if not m or m.tenant_id != tenant_id or m.is_deleted:
        raise HTTPException(status_code=422, detail=f"{field} not found in this tenant")


def _check_role_tenant(db: Session, role_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    r = db.get(Role, role_id)
    if not r or r.tenant_id != tenant_id or r.is_deleted:
        raise HTTPException(status_code=422, detail="role_id not found in this tenant")


@router.get("/", response_model=list[MemberRoleAssignmentRead])
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


@router.post("/", response_model=MemberRoleAssignmentRead, status_code=201)
def create_role_assignment(body: MemberRoleAssignmentBase, tenant_id: TenantDep, db: DbDep) -> MemberRoleAssignment:
    _check_member_tenant(db, body.member_id, tenant_id, "member_id")
    _check_role_tenant(db, body.role_id, tenant_id)
    if body.assigned_by_id is not None:
        _check_member_tenant(db, body.assigned_by_id, tenant_id, "assigned_by_id")
    assignment = MemberRoleAssignment(id=uuid7(), tenant_id=tenant_id, **body.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/{assignment_id}", response_model=MemberRoleAssignmentRead)
def get_role_assignment(assignment_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> MemberRoleAssignment:
    return _get_or_404(db, assignment_id, tenant_id)


@router.delete("/{assignment_id}", status_code=204)
def delete_role_assignment(assignment_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    assignment = _get_or_404(db, assignment_id, tenant_id)
    assignment.is_deleted = True
    db.commit()
