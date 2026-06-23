import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.base import TrackedBase


def _parse_tenant_id(x_tenant_id: Annotated[str, Header()]) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Tenant-ID must be a valid UUID") from exc


TenantDep = Annotated[uuid.UUID, Depends(_parse_tenant_id)]
DbDep = Annotated[Session, Depends(get_db)]


def get_or_404[T: TrackedBase](
    db: Session, model: type[T], obj_id: uuid.UUID, tenant_id: uuid.UUID, detail: str
) -> T:
    obj = db.get(model, obj_id)
    if not obj or obj.tenant_id != tenant_id or obj.is_deleted:
        raise HTTPException(status_code=404, detail=detail)
    return obj


def require_tenant_fk[T: TrackedBase](
    db: Session, model: type[T], fk_id: uuid.UUID, tenant_id: uuid.UUID, field: str
) -> None:
    obj = db.get(model, fk_id)
    if not obj or obj.tenant_id != tenant_id or obj.is_deleted:
        raise HTTPException(status_code=422, detail=f"{field} not found in this tenant")
