import uuid
from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.core.deps import DbDep, TenantDep
from app.models.enums import Permission
from app.models.role import Role, RoleMembership, RolePermission
from app.schemas.role import (
    RoleBase,
    RoleMembershipBase,
    RoleMembershipRead,
    RolePermissionRead,
    RoleRead,
    RoleUpdate,
)

router = APIRouter(tags=["roles"])


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def _get_role_or_404(db: Session, role_id: uuid.UUID, tenant_id: uuid.UUID) -> Role:
    role = db.get(Role, role_id)
    if not role or role.tenant_id != tenant_id or role.is_deleted:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.get("/roles/", response_model=list[RoleRead])
def list_roles(tenant_id: TenantDep, db: DbDep) -> Sequence[Role]:
    return db.scalars(
        select(Role).where(Role.tenant_id == tenant_id, Role.is_deleted.is_(False))
    ).all()


@router.post("/roles/", response_model=RoleRead, status_code=201)
def create_role(body: RoleBase, tenant_id: TenantDep, db: DbDep) -> Role:
    role = Role(id=uuid7(), tenant_id=tenant_id, **body.model_dump())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.get("/roles/{role_id}", response_model=RoleRead)
def get_role(role_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Role:
    return _get_role_or_404(db, role_id, tenant_id)


@router.patch("/roles/{role_id}", response_model=RoleRead)
def update_role(role_id: uuid.UUID, body: RoleUpdate, tenant_id: TenantDep, db: DbDep) -> Role:
    role = _get_role_or_404(db, role_id, tenant_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(role, k, v)
    db.commit()
    db.refresh(role)
    return role


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(role_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    role = _get_role_or_404(db, role_id, tenant_id)
    if role.is_system:
        raise HTTPException(status_code=403, detail="System roles cannot be deleted")
    role.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Role permissions (nested under /roles/{role_id}/permissions/)
# ---------------------------------------------------------------------------


class _PermissionBody(BaseModel):
    permission: Permission


def _get_perm_or_404(
    db: Session, perm_id: uuid.UUID, role_id: uuid.UUID, tenant_id: uuid.UUID
) -> RolePermission:
    perm = db.get(RolePermission, perm_id)
    if not perm or perm.tenant_id != tenant_id or perm.role_id != role_id or perm.is_deleted:
        raise HTTPException(status_code=404, detail="Permission not found")
    return perm


@router.get("/roles/{role_id}/permissions/", response_model=list[RolePermissionRead])
def list_role_permissions(role_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Sequence[RolePermission]:
    _get_role_or_404(db, role_id, tenant_id)
    return db.scalars(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.tenant_id == tenant_id,
            RolePermission.is_deleted.is_(False),
        )
    ).all()


@router.post("/roles/{role_id}/permissions/", response_model=RolePermissionRead, status_code=201)
def add_role_permission(role_id: uuid.UUID, body: _PermissionBody, tenant_id: TenantDep, db: DbDep) -> RolePermission:
    _get_role_or_404(db, role_id, tenant_id)
    perm = RolePermission(
        id=uuid7(), tenant_id=tenant_id, role_id=role_id, permission=body.permission
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


@router.delete("/roles/{role_id}/permissions/{perm_id}", status_code=204)
def remove_role_permission(role_id: uuid.UUID, perm_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    perm = _get_perm_or_404(db, perm_id, role_id, tenant_id)
    perm.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Role memberships (position → functional group links)
# ---------------------------------------------------------------------------


def _get_membership_or_404(db: Session, membership_id: uuid.UUID, tenant_id: uuid.UUID) -> RoleMembership:
    m = db.get(RoleMembership, membership_id)
    if not m or m.tenant_id != tenant_id or m.is_deleted:
        raise HTTPException(status_code=404, detail="Role membership not found")
    return m


def _check_role_tenant(db: Session, role_id: uuid.UUID, tenant_id: uuid.UUID, field: str) -> None:
    role = db.get(Role, role_id)
    if not role or role.tenant_id != tenant_id or role.is_deleted:
        raise HTTPException(status_code=422, detail=f"{field} not found in this tenant")


@router.get("/role-memberships/", response_model=list[RoleMembershipRead])
def list_role_memberships(tenant_id: TenantDep, db: DbDep) -> Sequence[RoleMembership]:
    return db.scalars(
        select(RoleMembership).where(
            RoleMembership.tenant_id == tenant_id,
            RoleMembership.is_deleted.is_(False),
        )
    ).all()


@router.post("/role-memberships/", response_model=RoleMembershipRead, status_code=201)
def create_role_membership(body: RoleMembershipBase, tenant_id: TenantDep, db: DbDep) -> RoleMembership:
    _check_role_tenant(db, body.group_role_id, tenant_id, "group_role_id")
    _check_role_tenant(db, body.member_role_id, tenant_id, "member_role_id")
    membership = RoleMembership(id=uuid7(), tenant_id=tenant_id, **body.model_dump())
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


@router.get("/role-memberships/{membership_id}", response_model=RoleMembershipRead)
def get_role_membership(membership_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> RoleMembership:
    return _get_membership_or_404(db, membership_id, tenant_id)


@router.delete("/role-memberships/{membership_id}", status_code=204)
def delete_role_membership(membership_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    membership = _get_membership_or_404(db, membership_id, tenant_id)
    membership.is_deleted = True
    db.commit()
