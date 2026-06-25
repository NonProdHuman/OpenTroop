import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.permissions import resolve_permissions
from app.core.tenant import get_tenant_id
from app.models.base import TrackedBase
from app.models.enums import Permission, PlatformRole
from app.models.member import Member
from app.models.user import User

TenantDep = Annotated[uuid.UUID, Depends(get_tenant_id)]
DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_platform_admin(user: CurrentUserDep) -> User:
    """Require the caller to hold a platform (global, cross-tenant) role.

    Gates the SaaS control plane — tenant provisioning and tenant-admin
    administration — independently of any tenant-scoped permission. Raises 403
    for ordinary users (``platform_role is None``).
    """
    if user.platform_role is None:
        raise HTTPException(status_code=403, detail="Platform administrator access required")
    return user


PlatformAdminDep = Annotated[User, Depends(get_platform_admin)]


def get_superadmin(user: CurrentUserDep) -> User:
    """Require the caller to be a platform **superadmin**.

    Stricter than ``get_platform_admin``: gates the most sensitive control-plane
    actions — granting and revoking platform roles. ``support``/``billing``
    platform users are rejected (403) so they cannot escalate privileges.
    """
    if user.platform_role is not PlatformRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user


SuperadminDep = Annotated[User, Depends(get_superadmin)]


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


def require(permission: Permission) -> Callable[..., Any]:
    """Return a FastAPI dependency that enforces a permission for the calling user.

    Resolves the caller's Member record in the current tenant via user_id, then
    checks permissions through the role hierarchy. Raises 403 if the user has no
    Member row in this tenant or lacks the required permission.
    """

    async def _check(
        user: CurrentUserDep,
        tenant_id: TenantDep,
        db: DbDep,
    ) -> None:
        member = db.scalar(
            select(Member).where(
                Member.user_id == user.id,
                Member.tenant_id == tenant_id,
                Member.is_deleted.is_(False),
            )
        )
        if member is None:
            raise HTTPException(status_code=403, detail="Not a member of this tenant")
        if permission not in resolve_permissions(member.id, db):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    return _check
