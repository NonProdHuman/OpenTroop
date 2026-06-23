import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import DbDep, TenantDep, get_or_404, require, require_tenant_fk
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


@router.get("/roles/", response_model=list[RoleRead], dependencies=[Depends(require(Permission.MEMBER_READ))])
def list_roles(tenant_id: TenantDep, db: DbDep) -> Sequence[Role]:
    return db.scalars(
        select(Role).where(Role.tenant_id == tenant_id, Role.is_deleted.is_(False))
    ).all()


@router.post("/roles/", response_model=RoleRead, status_code=201, dependencies=[Depends(require(Permission.ROLE_MANAGE))])
def create_role(body: RoleBase, tenant_id: TenantDep, db: DbDep) -> Role:
    role = Role(tenant_id=tenant_id, **body.model_dump())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.get("/roles/{role_id}", response_model=RoleRead, dependencies=[Depends(require(Permission.MEMBER_READ))])
def get_role(role_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Role:
    return get_or_404(db, Role, role_id, tenant_id, "Role not found")


@router.patch("/roles/{role_id}", response_model=RoleRead, dependencies=[Depends(require(Permission.ROLE_MANAGE))])
def update_role(role_id: uuid.UUID, body: RoleUpdate, tenant_id: TenantDep, db: DbDep) -> Role:
    role = get_or_404(db, Role, role_id, tenant_id, "Role not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(role, k, v)
    db.commit()
    db.refresh(role)
    return role


@router.delete("/roles/{role_id}", status_code=204, dependencies=[Depends(require(Permission.ROLE_MANAGE))])
def delete_role(role_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    role = get_or_404(db, Role, role_id, tenant_id, "Role not found")
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


@router.get("/roles/{role_id}/permissions/", response_model=list[RolePermissionRead], dependencies=[Depends(require(Permission.MEMBER_READ))])
def list_role_permissions(
    role_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> Sequence[RolePermission]:
    get_or_404(db, Role, role_id, tenant_id, "Role not found")
    return db.scalars(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.tenant_id == tenant_id,
            RolePermission.is_deleted.is_(False),
        )
    ).all()


@router.post("/roles/{role_id}/permissions/", response_model=RolePermissionRead, status_code=201, dependencies=[Depends(require(Permission.ROLE_MANAGE))])
def add_role_permission(
    role_id: uuid.UUID, body: _PermissionBody, tenant_id: TenantDep, db: DbDep
) -> RolePermission:
    get_or_404(db, Role, role_id, tenant_id, "Role not found")
    perm = RolePermission(tenant_id=tenant_id, role_id=role_id, permission=body.permission)
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


@router.delete("/roles/{role_id}/permissions/{perm_id}", status_code=204, dependencies=[Depends(require(Permission.ROLE_MANAGE))])
def remove_role_permission(
    role_id: uuid.UUID, perm_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> None:
    perm = _get_perm_or_404(db, perm_id, role_id, tenant_id)
    perm.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Role memberships (position → functional group links)
# ---------------------------------------------------------------------------


@router.get("/role-memberships/", response_model=list[RoleMembershipRead], dependencies=[Depends(require(Permission.MEMBER_READ))])
def list_role_memberships(tenant_id: TenantDep, db: DbDep) -> Sequence[RoleMembership]:
    return db.scalars(
        select(RoleMembership).where(
            RoleMembership.tenant_id == tenant_id,
            RoleMembership.is_deleted.is_(False),
        )
    ).all()


@router.post("/role-memberships/", response_model=RoleMembershipRead, status_code=201, dependencies=[Depends(require(Permission.ROLE_MANAGE))])
def create_role_membership(
    body: RoleMembershipBase, tenant_id: TenantDep, db: DbDep
) -> RoleMembership:
    require_tenant_fk(db, Role, body.group_role_id, tenant_id, "group_role_id")
    require_tenant_fk(db, Role, body.member_role_id, tenant_id, "member_role_id")
    membership = RoleMembership(tenant_id=tenant_id, **body.model_dump())
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


@router.get("/role-memberships/{membership_id}", response_model=RoleMembershipRead, dependencies=[Depends(require(Permission.MEMBER_READ))])
def get_role_membership(
    membership_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> RoleMembership:
    return get_or_404(db, RoleMembership, membership_id, tenant_id, "Role membership not found")


@router.delete("/role-memberships/{membership_id}", status_code=204, dependencies=[Depends(require(Permission.ROLE_MANAGE))])
def delete_role_membership(membership_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    membership = get_or_404(
        db, RoleMembership, membership_id, tenant_id, "Role membership not found"
    )
    membership.is_deleted = True
    db.commit()
