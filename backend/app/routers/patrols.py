import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from uuid6 import uuid7

from app.core.deps import DbDep, TenantDep
from app.models.patrol import Patrol
from app.schemas.patrol import PatrolBase, PatrolRead, PatrolUpdate

router = APIRouter(prefix="/patrols", tags=["patrols"])


def _get_or_404(db, patrol_id: uuid.UUID, tenant_id: uuid.UUID) -> Patrol:
    patrol = db.get(Patrol, patrol_id)
    if not patrol or patrol.tenant_id != tenant_id or patrol.is_deleted:
        raise HTTPException(status_code=404, detail="Patrol not found")
    return patrol


@router.get("/", response_model=list[PatrolRead])
def list_patrols(tenant_id: TenantDep, db: DbDep):
    return db.scalars(
        select(Patrol).where(Patrol.tenant_id == tenant_id, Patrol.is_deleted.is_(False))
    ).all()


@router.post("/", response_model=PatrolRead, status_code=201)
def create_patrol(body: PatrolBase, tenant_id: TenantDep, db: DbDep):
    patrol = Patrol(id=uuid7(), tenant_id=tenant_id, **body.model_dump())
    db.add(patrol)
    db.commit()
    db.refresh(patrol)
    return patrol


@router.get("/{patrol_id}", response_model=PatrolRead)
def get_patrol(patrol_id: uuid.UUID, tenant_id: TenantDep, db: DbDep):
    return _get_or_404(db, patrol_id, tenant_id)


@router.patch("/{patrol_id}", response_model=PatrolRead)
def update_patrol(patrol_id: uuid.UUID, body: PatrolUpdate, tenant_id: TenantDep, db: DbDep):
    patrol = _get_or_404(db, patrol_id, tenant_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(patrol, k, v)
    db.commit()
    db.refresh(patrol)
    return patrol


@router.delete("/{patrol_id}", status_code=204)
def delete_patrol(patrol_id: uuid.UUID, tenant_id: TenantDep, db: DbDep):
    patrol = _get_or_404(db, patrol_id, tenant_id)
    patrol.is_deleted = True
    db.commit()
