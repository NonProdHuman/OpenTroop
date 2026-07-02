import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import DbDep, TenantDep, get_or_404, require
from app.models.enums import Permission
from app.models.rbac import FunctionalRole, FunctionalRolePermission
from app.schemas.rbac import (
    FunctionalRoleCreate,
    FunctionalRolePermissionRead,
    FunctionalRoleRead,
    FunctionalRoleUpdate,
)

router = APIRouter(prefix="/functional-roles", tags=["functional-roles"])


@router.get(
    "",
    response_model=list[FunctionalRoleRead],
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def list_functional_roles(tenant_id: TenantDep, db: DbDep) -> Sequence[FunctionalRole]:
    return db.scalars(select(FunctionalRole)).all()


@router.post(
    "",
    response_model=FunctionalRoleRead,
    status_code=201,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def create_functional_role(
    body: FunctionalRoleCreate, tenant_id: TenantDep, db: DbDep
) -> FunctionalRole:
    # Custom functional roles are never is_admin — that is reserved for the seeded
    # administrators role, so it cannot be conferred by creating a new role.
    role = FunctionalRole(is_admin=False, **body.model_dump())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.get(
    "/{role_id}",
    response_model=FunctionalRoleRead,
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def get_functional_role(role_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> FunctionalRole:
    return get_or_404(db, FunctionalRole, role_id, "Functional role not found")


@router.patch(
    "/{role_id}",
    response_model=FunctionalRoleRead,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def update_functional_role(
    role_id: uuid.UUID, body: FunctionalRoleUpdate, tenant_id: TenantDep, db: DbDep
) -> FunctionalRole:
    role = get_or_404(db, FunctionalRole, role_id, "Functional role not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(role, k, v)
    db.commit()
    db.refresh(role)
    return role


@router.delete(
    "/{role_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def delete_functional_role(role_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    role = get_or_404(db, FunctionalRole, role_id, "Functional role not found")
    if role.is_system:
        raise HTTPException(status_code=403, detail="System functional roles cannot be deleted")
    role.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Permissions on a functional role
# ---------------------------------------------------------------------------


class _PermissionBody(BaseModel):
    permission: Permission


@router.get(
    "/{role_id}/permissions",
    response_model=list[FunctionalRolePermissionRead],
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def list_functional_role_permissions(
    role_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> Sequence[FunctionalRolePermission]:
    get_or_404(db, FunctionalRole, role_id, "Functional role not found")
    return db.scalars(
        select(FunctionalRolePermission).where(
            FunctionalRolePermission.functional_role_id == role_id
        )
    ).all()


@router.post(
    "/{role_id}/permissions",
    response_model=FunctionalRolePermissionRead,
    status_code=201,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def add_functional_role_permission(
    role_id: uuid.UUID, body: _PermissionBody, tenant_id: TenantDep, db: DbDep
) -> FunctionalRolePermission:
    """Grant a permission to a functional role. Idempotent."""
    get_or_404(db, FunctionalRole, role_id, "Functional role not found")
    existing = db.scalar(
        select(FunctionalRolePermission).where(
            FunctionalRolePermission.functional_role_id == role_id,
            FunctionalRolePermission.permission == body.permission,
        )
    )
    if existing is not None:
        return existing
    perm = FunctionalRolePermission(functional_role_id=role_id, permission=body.permission)
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


@router.delete(
    "/{role_id}/permissions/{permission}",
    status_code=204,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def remove_functional_role_permission(
    role_id: uuid.UUID, permission: Permission, tenant_id: TenantDep, db: DbDep
) -> None:
    get_or_404(db, FunctionalRole, role_id, "Functional role not found")
    perm = db.scalar(
        select(FunctionalRolePermission).where(
            FunctionalRolePermission.functional_role_id == role_id,
            FunctionalRolePermission.permission == permission,
        )
    )
    if perm is None:
        raise HTTPException(status_code=404, detail="Permission not granted to this role")
    perm.is_deleted = True
    db.commit()
