import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbDep, TenantDep, get_or_404, require
from app.models.enums import Permission
from app.models.event_type import EventType
from app.schemas.event_type import EventTypeBase, EventTypeRead, EventTypeUpdate

router = APIRouter(prefix="/event-types", tags=["event-types"])


def _validate_permission_slip_config(allow_signups: bool, require_permission_slip: bool) -> None:
    """A permission slip only makes sense on a type that collects RSVPs."""
    if require_permission_slip and not allow_signups:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="require_permission_slip requires allow_signups",
        )


@router.get(
    "/",
    response_model=list[EventTypeRead],
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def list_event_types(tenant_id: TenantDep, db: DbDep) -> Sequence[EventType]:
    return db.scalars(select(EventType).where(EventType.is_deleted.is_(False))).all()


@router.post(
    "/",
    response_model=EventTypeRead,
    status_code=201,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def create_event_type(body: EventTypeBase, tenant_id: TenantDep, db: DbDep) -> EventType:
    _validate_permission_slip_config(body.allow_signups, body.require_permission_slip)
    event_type = EventType(tenant_id=tenant_id, **body.model_dump())
    db.add(event_type)
    db.commit()
    db.refresh(event_type)
    return event_type


@router.get(
    "/{event_type_id}",
    response_model=EventTypeRead,
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def get_event_type(event_type_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> EventType:
    return get_or_404(db, EventType, event_type_id, tenant_id, "Event type not found")


@router.patch(
    "/{event_type_id}",
    response_model=EventTypeRead,
    dependencies=[Depends(require(Permission.EVENT_WRITE))],
)
def update_event_type(
    event_type_id: uuid.UUID, body: EventTypeUpdate, tenant_id: TenantDep, db: DbDep
) -> EventType:
    event_type = get_or_404(db, EventType, event_type_id, tenant_id, "Event type not found")
    updates = body.model_dump(exclude_unset=True)
    _validate_permission_slip_config(
        updates.get("allow_signups", event_type.allow_signups),
        updates.get("require_permission_slip", event_type.require_permission_slip),
    )
    for k, v in updates.items():
        setattr(event_type, k, v)
    db.commit()
    db.refresh(event_type)
    return event_type


@router.delete(
    "/{event_type_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.EVENT_DELETE))],
)
def delete_event_type(event_type_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    event_type = get_or_404(db, EventType, event_type_id, tenant_id, "Event type not found")
    if event_type.is_system:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="System event types cannot be deleted; set is_active=false to disable",
        )
    event_type.is_deleted = True
    db.commit()
