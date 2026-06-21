import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db


def _parse_tenant_id(x_tenant_id: Annotated[str, Header()]) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Tenant-ID must be a valid UUID") from exc


TenantDep = Annotated[uuid.UUID, Depends(_parse_tenant_id)]
DbDep = Annotated[Session, Depends(get_db)]
