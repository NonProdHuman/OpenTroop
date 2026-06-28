import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.deps import DbDep, TenantDep, get_or_404, require
from app.models.enums import Permission
from app.models.location import Location
from app.schemas.location import LocationBase, LocationRead, LocationUpdate

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get(
    "/", response_model=list[LocationRead], dependencies=[Depends(require(Permission.EVENT_READ))]
)
def list_locations(tenant_id: TenantDep, db: DbDep) -> Sequence[Location]:
    return db.scalars(select(Location).where(Location.is_deleted.is_(False))).all()


@router.post(
    "/",
    response_model=LocationRead,
    status_code=201,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def create_location(body: LocationBase, tenant_id: TenantDep, db: DbDep) -> Location:
    location = Location(tenant_id=tenant_id, **body.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get(
    "/{location_id}",
    response_model=LocationRead,
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def get_location(location_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Location:
    return get_or_404(db, Location, location_id, tenant_id, "Location not found")


@router.patch(
    "/{location_id}",
    response_model=LocationRead,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def update_location(
    location_id: uuid.UUID, body: LocationUpdate, tenant_id: TenantDep, db: DbDep
) -> Location:
    location = get_or_404(db, Location, location_id, tenant_id, "Location not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(location, k, v)
    db.commit()
    db.refresh(location)
    return location


@router.delete(
    "/{location_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.EVENT_DELETE))],
)
def delete_location(location_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    location = get_or_404(db, Location, location_id, tenant_id, "Location not found")
    location.is_deleted = True
    db.commit()
