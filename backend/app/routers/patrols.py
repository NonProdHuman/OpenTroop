import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.deps import DbDep, TenantDep, get_or_404, require
from app.models.enums import Permission
from app.models.patrol import Patrol
from app.schemas.patrol import PatrolBase, PatrolRead, PatrolUpdate

router = APIRouter(prefix="/patrols", tags=["patrols"])


@router.get(
    "/", response_model=list[PatrolRead], dependencies=[Depends(require(Permission.MEMBER_READ))]
)
def list_patrols(tenant_id: TenantDep, db: DbDep) -> Sequence[Patrol]:
    return db.scalars(
        select(Patrol).where(Patrol.tenant_id == tenant_id, Patrol.is_deleted.is_(False))
    ).all()


@router.post(
    "/",
    response_model=PatrolRead,
    status_code=201,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def create_patrol(body: PatrolBase, tenant_id: TenantDep, db: DbDep) -> Patrol:
    patrol = Patrol(tenant_id=tenant_id, **body.model_dump())
    db.add(patrol)
    db.commit()
    db.refresh(patrol)
    return patrol


@router.get(
    "/{patrol_id}",
    response_model=PatrolRead,
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def get_patrol(patrol_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Patrol:
    return get_or_404(db, Patrol, patrol_id, tenant_id, "Patrol not found")


@router.patch(
    "/{patrol_id}",
    response_model=PatrolRead,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def update_patrol(
    patrol_id: uuid.UUID, body: PatrolUpdate, tenant_id: TenantDep, db: DbDep
) -> Patrol:
    patrol = get_or_404(db, Patrol, patrol_id, tenant_id, "Patrol not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(patrol, k, v)
    db.commit()
    db.refresh(patrol)
    return patrol


@router.delete(
    "/{patrol_id}", status_code=204, dependencies=[Depends(require(Permission.MEMBER_DELETE))]
)
def delete_patrol(patrol_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    patrol = get_or_404(db, Patrol, patrol_id, tenant_id, "Patrol not found")
    patrol.is_deleted = True
    db.commit()
