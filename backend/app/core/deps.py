import uuid
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.tenant import get_tenant_id
from app.models.base import TrackedBase
from app.models.user import User

TenantDep = Annotated[uuid.UUID, Depends(get_tenant_id)]
DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


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
