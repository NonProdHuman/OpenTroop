"""Tenant-scoped settings — currently the customizable permission-slip language.

Distinct from the platform control plane (``app/routers/platform.py``), which manages
tenants from *above*. These endpoints let a troop configure its own settings from
*within* the tenant.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import DbDep, TenantDep, require
from app.core.permission_slip import DEFAULT_PERMISSION_MESSAGE, effective_permission_message
from app.models.enums import Permission
from app.models.tenant import Tenant
from app.schemas.tenant import TenantSettingsRead, TenantSettingsUpdate

router = APIRouter(prefix="/tenant/settings", tags=["tenant-settings"])


@router.get(
    "/",
    response_model=TenantSettingsRead,
    dependencies=[Depends(require(Permission.EVENT_READ))],
)
def get_settings(tenant_id: TenantDep, db: DbDep) -> TenantSettingsRead:
    # Tenant is platform-level (no tenant_id column); fetch by primary key. When the
    # row is absent (e.g. test/self-host bootstrap), fall back to the default language.
    tenant = db.get(Tenant, tenant_id)
    message = (
        effective_permission_message(tenant) if tenant is not None else DEFAULT_PERMISSION_MESSAGE
    )
    return TenantSettingsRead(permission_message=message)


@router.patch(
    "/",
    response_model=TenantSettingsRead,
    dependencies=[Depends(require(Permission.ROLE_MANAGE))],
)
def update_settings(
    body: TenantSettingsUpdate, tenant_id: TenantDep, db: DbDep
) -> TenantSettingsRead:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if "permission_message" in body.model_dump(exclude_unset=True):
        tenant.permission_message = body.permission_message
    db.commit()
    db.refresh(tenant)
    return TenantSettingsRead(permission_message=effective_permission_message(tenant))
