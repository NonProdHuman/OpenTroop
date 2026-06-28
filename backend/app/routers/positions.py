import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.deps import DbDep, TenantDep, get_or_404, require, require_tenant_fk
from app.models.enums import Permission
from app.models.rbac import FunctionalRole, Position, PositionFunctionalRole
from app.schemas.rbac import (
    FunctionalRoleLinkCreate,
    PositionCreate,
    PositionFunctionalRoleRead,
    PositionRead,
    PositionUpdate,
)

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get(
    "/",
    response_model=list[PositionRead],
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def list_positions(tenant_id: TenantDep, db: DbDep) -> Sequence[Position]:
    return db.scalars(
        select(Position).where(Position.is_deleted.is_(False)).order_by(Position.sort_order)
    ).all()


@router.post(
    "/",
    response_model=PositionRead,
    status_code=201,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def create_position(body: PositionCreate, tenant_id: TenantDep, db: DbDep) -> Position:
    position = Position(tenant_id=tenant_id, **body.model_dump())
    db.add(position)
    db.commit()
    db.refresh(position)
    return position


@router.get(
    "/{position_id}",
    response_model=PositionRead,
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def get_position(position_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Position:
    return get_or_404(db, Position, position_id, tenant_id, "Position not found")


@router.patch(
    "/{position_id}",
    response_model=PositionRead,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def update_position(
    position_id: uuid.UUID, body: PositionUpdate, tenant_id: TenantDep, db: DbDep
) -> Position:
    position = get_or_404(db, Position, position_id, tenant_id, "Position not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(position, k, v)
    db.commit()
    db.refresh(position)
    return position


@router.delete(
    "/{position_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def delete_position(position_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    position = get_or_404(db, Position, position_id, tenant_id, "Position not found")
    if position.is_system:
        raise HTTPException(status_code=403, detail="System positions cannot be deleted")
    position.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Position ↔ functional-role mapping (the product surface)
# ---------------------------------------------------------------------------


@router.get(
    "/{position_id}/functional-roles",
    response_model=list[PositionFunctionalRoleRead],
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def list_position_functional_roles(
    position_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> Sequence[PositionFunctionalRole]:
    get_or_404(db, Position, position_id, tenant_id, "Position not found")
    return db.scalars(
        select(PositionFunctionalRole).where(
            PositionFunctionalRole.position_id == position_id,
            PositionFunctionalRole.is_deleted.is_(False),
        )
    ).all()


@router.post(
    "/{position_id}/functional-roles",
    response_model=PositionFunctionalRoleRead,
    status_code=201,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def attach_functional_role(
    position_id: uuid.UUID, body: FunctionalRoleLinkCreate, tenant_id: TenantDep, db: DbDep
) -> PositionFunctionalRole:
    """Map a functional role onto a position. Idempotent."""
    get_or_404(db, Position, position_id, tenant_id, "Position not found")
    require_tenant_fk(db, FunctionalRole, body.functional_role_id, tenant_id, "functional_role_id")

    existing = db.scalar(
        select(PositionFunctionalRole).where(
            PositionFunctionalRole.position_id == position_id,
            PositionFunctionalRole.functional_role_id == body.functional_role_id,
            PositionFunctionalRole.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing

    link = PositionFunctionalRole(
        tenant_id=tenant_id,
        position_id=position_id,
        functional_role_id=body.functional_role_id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete(
    "/{position_id}/functional-roles/{functional_role_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def detach_functional_role(
    position_id: uuid.UUID,
    functional_role_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
) -> None:
    get_or_404(db, Position, position_id, tenant_id, "Position not found")
    link = db.scalar(
        select(PositionFunctionalRole).where(
            PositionFunctionalRole.position_id == position_id,
            PositionFunctionalRole.functional_role_id == functional_role_id,
            PositionFunctionalRole.is_deleted.is_(False),
        )
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Functional role not mapped to this position")
    link.is_deleted = True
    db.commit()
