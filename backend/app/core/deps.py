import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, get_optional_current_user
from app.core.config import settings
from app.core.database import get_admin_db, get_db
from app.core.notifications import NotificationService, get_notification_service
from app.core.permissions import resolve_permissions
from app.core.tenant import get_tenant_id
from app.core.tenant_context import reset_current_tenant, set_current_tenant
from app.models.base import TrackedBase
from app.models.enums import Permission, PlatformRole
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User


async def get_scoped_tenant_id(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
) -> AsyncGenerator[uuid.UUID, None]:
    """Resolve the request tenant and publish it to the current-tenant context.

    Layered on top of ``get_tenant_id`` so every route using ``TenantDep`` — plus
    ``require()`` and ``get_current_member`` — automatically scopes its ORM queries
    and write stamping to this tenant (see ``docs/spec/tenant-data-access.md``). The
    token is reset when the request ends, so the context never leaks across requests.
    Overriding ``get_tenant_id`` in tests still flows through here unchanged.
    """
    token = set_current_tenant(tenant_id)
    try:
        yield tenant_id
    finally:
        reset_current_tenant(token)


TenantDep = Annotated[uuid.UUID, Depends(get_scoped_tenant_id)]
DbDep = Annotated[Session, Depends(get_db)]
AdminDbDep = Annotated[Session, Depends(get_admin_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
OptionalUserDep = Annotated[User | None, Depends(get_optional_current_user)]
NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]

# HTTP methods that never mutate state. The anonymous public-demo principal is
# structurally confined to these — anything else is refused before a handler runs.
_DEMO_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})


def _demo_viewer_member(tenant_id: uuid.UUID, db: Session) -> Member | None:
    """Return the seeded anonymous Demo Viewer member, or ``None`` when not applicable.

    The public-demo carve-out (GH-246, ADR 0012) is inert unless ``DEMO_TENANT_SLUG``
    is set, and even then it applies to exactly one tenant. This keys on **both** the
    configured slug and the *resolved* tenant id: the tenant this request resolved to
    must be the demo tenant by slug. A suspended or deleted demo tenant yields
    ``None`` (falls back to the normal 401), matching the rest of tenant resolution.
    The principal is a fixed, unclaimed (``user_id`` null) member identified by
    ``DEMO_VIEWER_EMAIL`` within that tenant — never a real signed-in user.
    """
    slug = settings.demo_tenant_slug.strip()
    if not slug:
        return None
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.is_deleted or tenant.suspended_at is not None:
        return None
    if tenant.slug != slug:
        return None
    return db.scalar(
        select(Member).where(
            Member.email == settings.demo_viewer_email,
            Member.user_id.is_(None),
        )
    )


def _resolve_current_member(
    request: Request, user: User | None, tenant_id: uuid.UUID, db: Session
) -> Member:
    """Resolve the caller's ``Member`` in the current tenant for authenticated *or*
    anonymous-demo requests.

    Authenticated: the member linked to *user* in this tenant (403 if none) — exactly
    as before. Anonymous (``user is None``): the fixed Demo Viewer member, but only on
    the configured demo tenant (:func:`_demo_viewer_member`) and only for a safe HTTP
    method. Any write method by the anonymous principal is refused **403 structurally,
    independent of RBAC** — a mis-seeded viewer that somehow held write permissions
    still cannot mutate. Off the demo tenant, an anonymous request falls through to the
    same 401 the API has always returned.
    """
    if user is not None:
        # tenant_id (TenantDep) publishes the active tenant, so this query is
        # automatically scoped to it and to non-deleted rows.
        member = db.scalar(select(Member).where(Member.user_id == user.id))
        if member is None:
            raise HTTPException(status_code=403, detail="Not a member of this tenant")
        return member

    member = _demo_viewer_member(tenant_id, db)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if request.method not in _DEMO_SAFE_METHODS:
        raise HTTPException(status_code=403, detail="The demo troop is read-only")
    return member


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


def get_current_member(
    request: Request, user: OptionalUserDep, tenant_id: TenantDep, db: DbDep
) -> Member:
    """Resolve the caller's ``Member`` row in the current tenant.

    Complements ``require(...)`` (which gates by permission but doesn't expose the
    member) for handlers that need the member itself — e.g. to compute event
    visibility from the caller's group memberships. Raises 403 if the signed-in
    user has no Member in this tenant. On the configured public-demo tenant an
    anonymous (token-less) GET resolves the fixed read-only Demo Viewer instead of
    401; see :func:`_resolve_current_member`.
    """
    return _resolve_current_member(request, user, tenant_id, db)


CurrentMemberDep = Annotated[Member, Depends(get_current_member)]


def get_member_with_permissions(
    request: Request, user: OptionalUserDep, tenant_id: TenantDep, db: DbDep
) -> tuple[Member, frozenset[Permission]]:
    """Resolve the caller's ``Member`` and their effective permissions in one pass.

    Collapses what used to be three round trips on a single request — ``require()``
    (member lookup + resolve), ``CurrentMemberDep`` (a second member lookup), and an
    in-handler ``resolve_permissions`` — into one member query and one resolution.
    Use for handlers that both gate on and branch by permissions (e.g. permission-aware
    event visibility). Raises 403 if the user has no Member in the current tenant.
    Honors the anonymous public-demo principal via :func:`_resolve_current_member`.
    """
    member = _resolve_current_member(request, user, tenant_id, db)
    return member, resolve_permissions(member.id, db)


MemberContextDep = Annotated[
    tuple[Member, frozenset[Permission]], Depends(get_member_with_permissions)
]


def get_or_404[T: TrackedBase](db: Session, model: type[T], obj_id: uuid.UUID, detail: str) -> T:
    """Fetch a tenant-scoped row by id or raise 404.

    ``db.get`` runs under the automatic tenant + soft-delete scoping (see
    ``app.core.database``), so a row in another tenant or a soft-deleted row simply
    resolves to ``None`` here — no manual ``tenant_id``/``is_deleted`` re-check needed.
    """
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    return obj


def require_tenant_fk[T: TrackedBase](
    db: Session, model: type[T], fk_id: uuid.UUID, field: str
) -> None:
    """Validate that an FK target exists in the current tenant (and isn't deleted).

    Relies on the same automatic scoping as :func:`get_or_404`: a cross-tenant or
    soft-deleted target resolves to ``None``.
    """
    if db.get(model, fk_id) is None:
        raise HTTPException(status_code=422, detail=f"{field} not found in this tenant")


def require(permission: Permission) -> Callable[..., Any]:
    """Return a FastAPI dependency that enforces a permission for the calling user.

    Resolves the caller's Member record in the current tenant via user_id, then
    checks permissions through the role hierarchy. Raises 403 if the user has no
    Member row in this tenant or lacks the required permission.

    On the configured public-demo tenant a token-less GET resolves the fixed
    read-only Demo Viewer (:func:`_resolve_current_member`); any write method by
    that anonymous principal is refused 403 **there**, before this permission check,
    so a mis-seeded viewer can never mutate regardless of what roles it holds.
    """

    async def _check(
        request: Request,
        user: OptionalUserDep,
        tenant_id: TenantDep,
        db: DbDep,
    ) -> None:
        member = _resolve_current_member(request, user, tenant_id, db)
        if permission not in resolve_permissions(member.id, db):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    return _check
