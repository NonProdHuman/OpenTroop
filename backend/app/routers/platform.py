"""Platform (global) control-plane API.

This is the SaaS control plane, distinct from tenant-scoped RBAC. The role
matrix is two-tier (GH-111): every route requires a platform role
(``get_platform_admin``), and **all writes** — tenant provisioning,
suspend/unsuspend, tenant-admin invites/revocations, platform-role grants —
additionally require ``superadmin``. ``support``/``billing`` are read-only, so
they can neither escalate themselves into a tenant nor disrupt one. Every write
is audit-logged with the acting user.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.core.cf_access import require_cf_access
from app.core.deletion import export_tenant, purge_tenant
from app.core.deps import AdminDbDep, SuperadminDep, get_platform_admin
from app.core.permissions import admin_assignments
from app.core.provisioning import invite_admin_member, provision_tenant
from app.core.tenant_context import unscoped
from app.models.enums import PlatformRole
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.platform import (
    PlatformAdminGrant,
    PlatformAdminRead,
    TenantAdminInvite,
    TenantAdminInviteResult,
    TenantAdminRead,
)
from app.schemas.tenant import TenantDeleteRequest, TenantProvision, TenantProvisioned, TenantRead

# The Cloudflare Access belt (GH-117) runs first: an independent, staff-SSO-issued
# assertion is required *in addition to* the platform role, so a compromised
# tenant-plane token alone never reaches the control plane. No-op when unconfigured.
router = APIRouter(
    prefix="/platform",
    tags=["platform"],
    dependencies=[Depends(require_cf_access), Depends(get_platform_admin)],
)

# Control-plane writes are high-consequence and cross-tenant; every one is logged
# with the acting user so takeovers and mistakes are reconstructable after the fact.
audit_log = logging.getLogger("opentroop.platform.audit")


def _sanitize(value: object) -> str:
    # Target values include caller-supplied strings (emails, slugs). Escape CR/LF
    # so a crafted value cannot forge extra lines in the audit log (log injection).
    return str(value).replace("\r", "\\r").replace("\n", "\\n")


def _audit(actor: User, action: str, **target: object) -> None:
    detail = " ".join(f"{k}={_sanitize(v)}" for k, v in target.items())
    audit_log.info("%s actor=%s (%s) %s", action, actor.id, _sanitize(actor.email), detail)


def _get_tenant_or_404(db: AdminDbDep, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------


@router.post("/tenants", response_model=TenantProvisioned, status_code=201)
def create_tenant(body: TenantProvision, db: AdminDbDep, actor: SuperadminDep) -> TenantProvisioned:
    """Provision a new tenant and invite its founding admin (superadmin only).

    Atomically creates the Tenant, an *unclaimed* founding admin Member
    (``user_id`` null), the administrators role, the role assignment, and the six
    default event types. The provisioning platform admin does not become a member
    of the new tenant. Returns the tenant plus a 7-day invite token the founder
    redeems via POST /auth/claim. Returns 409 if the slug is taken.
    """
    if db.scalar(select(Tenant).where(Tenant.slug == body.slug, Tenant.is_deleted.is_(False))):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tenant with this slug already exists",
        )

    with unscoped():
        tenant, founder, token, expires_at = provision_tenant(
            db,
            name=body.name,
            slug=body.slug,
            founder_first_name=body.founder_first_name,
            founder_last_name=body.founder_last_name,
            founder_email=body.founder_email,
        )
        db.commit()
        db.refresh(tenant)
    _audit(actor, "tenant.provision", tenant=tenant.id, slug=tenant.slug, founder=founder.id)
    return TenantProvisioned(
        **TenantRead.model_validate(tenant).model_dump(),
        founder_member_id=founder.id,
        invite_token=token,
        invite_expires_at=expires_at,
    )


@router.get("/tenants", response_model=list[TenantRead])
def list_tenants(db: AdminDbDep) -> Sequence[Tenant]:
    """List all active tenants on the platform, newest first."""
    return db.scalars(
        select(Tenant).where(Tenant.is_deleted.is_(False)).order_by(Tenant.created_at.desc())
    ).all()


@router.get("/tenants/{tenant_id}", response_model=TenantRead)
def get_tenant(tenant_id: uuid.UUID, db: AdminDbDep) -> Tenant:
    return _get_tenant_or_404(db, tenant_id)


@router.post("/tenants/{tenant_id}/suspend", response_model=TenantRead)
def suspend_tenant(tenant_id: uuid.UUID, db: AdminDbDep, actor: SuperadminDep) -> Tenant:
    """Suspend a tenant — tenant-scoped requests are then rejected. Idempotent. Superadmin only."""
    tenant = _get_tenant_or_404(db, tenant_id)
    if tenant.suspended_at is None:
        tenant.suspended_at = datetime.now(UTC)
        db.commit()
        db.refresh(tenant)
    _audit(actor, "tenant.suspend", tenant=tenant.id, slug=tenant.slug)
    return tenant


@router.post("/tenants/{tenant_id}/unsuspend", response_model=TenantRead)
def unsuspend_tenant(tenant_id: uuid.UUID, db: AdminDbDep, actor: SuperadminDep) -> Tenant:
    """Lift a tenant's suspension. Idempotent. Superadmin only."""
    tenant = _get_tenant_or_404(db, tenant_id)
    if tenant.suspended_at is not None:
        tenant.suspended_at = None
        db.commit()
        db.refresh(tenant)
    _audit(actor, "tenant.unsuspend", tenant=tenant.id, slug=tenant.slug)
    return tenant


@router.get("/tenants/{tenant_id}/export")
def export_tenant_data(tenant_id: uuid.UUID, db: AdminDbDep, actor: SuperadminDep) -> JSONResponse:
    """Download the tenant's full data bundle as JSON (superadmin only, GH-222).

    Every tenant-scoped table (soft-deleted rows included), the tenant row, and
    a minimal directory of linked platform users. Stamps ``last_export_at`` —
    tenant deletion requires an export taken *after* suspension, making this
    both the offboarding artifact and the accidental-delete recovery path.
    Superadmin-only because the bundle is the troop's complete PII.
    """
    tenant = _get_tenant_or_404(db, tenant_id)
    bundle = export_tenant(db, tenant)
    db.commit()
    _audit(actor, "tenant.export", tenant=tenant.id, slug=tenant.slug)
    filename = f"{tenant.slug}-export-{bundle['exported_at'][:10]}.json"
    return JSONResponse(
        bundle, headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.delete("/tenants/{tenant_id}", status_code=204)
def delete_tenant(
    tenant_id: uuid.UUID, body: TenantDeleteRequest, db: AdminDbDep, actor: SuperadminDep
) -> None:
    """Permanently delete a tenant and every row it owns (superadmin only, GH-222).

    Immediate and irreversible — the export is the recovery path, so the gate
    is strict: the tenant must be **suspended**, an export must have been taken
    **after** the suspension, and the request must echo the slug. The slug is
    freed at once (re-provisioning it works immediately). Platform User/Identity
    rows survive — they may span tenants.
    """
    tenant = _get_tenant_or_404(db, tenant_id)
    if tenant.suspended_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant must be suspended before it can be deleted",
        )
    if tenant.last_export_at is None or tenant.last_export_at < tenant.suspended_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A data export taken after suspension is required before deletion",
        )
    if body.confirm_slug != tenant.slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation slug does not match",
        )

    slug = tenant.slug
    counts = purge_tenant(db, tenant)
    db.commit()
    _audit(actor, "tenant.delete", tenant=tenant_id, slug=slug, rows=sum(counts.values()))


# ---------------------------------------------------------------------------
# Tenant administrators
# ---------------------------------------------------------------------------


@router.get("/tenants/{tenant_id}/admins", response_model=list[TenantAdminRead])
def list_tenant_admins(tenant_id: uuid.UUID, db: AdminDbDep) -> list[TenantAdminRead]:
    """List the members holding an administrator role in the tenant."""
    _get_tenant_or_404(db, tenant_id)
    admins: list[TenantAdminRead] = []
    seen: set[uuid.UUID] = set()
    with unscoped():
        for assignment in admin_assignments(tenant_id, db):
            member = db.get(Member, assignment.member_id)
            if member is None or member.is_deleted or member.id in seen:
                continue
            seen.add(member.id)
            admins.append(
                TenantAdminRead(
                    member_id=member.id,
                    first_name=member.first_name,
                    last_name=member.last_name,
                    email=member.email,
                    user_id=member.user_id,
                    claimed=member.user_id is not None,
                )
            )
    return admins


@router.post(
    "/tenants/{tenant_id}/admins",
    response_model=TenantAdminInviteResult,
    status_code=201,
)
def invite_tenant_admin(
    tenant_id: uuid.UUID, body: TenantAdminInvite, db: AdminDbDep, actor: SuperadminDep
) -> TenantAdminInviteResult:
    """Invite a new administrator into an existing tenant (superadmin only).

    Creates an unclaimed admin Member and returns a 7-day claim token the
    invitee redeems via POST /auth/claim. Superadmin-only: a tenant-admin seat
    grants full member PII access, so support/billing must not be able to
    invite anyone (least of all themselves) into a troop.
    """
    _get_tenant_or_404(db, tenant_id)
    with unscoped():
        member, token, expires_at = invite_admin_member(
            db,
            tenant_id,
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
        )
        db.commit()
    _audit(actor, "tenant_admin.invite", tenant=tenant_id, member=member.id, email=body.email)
    return TenantAdminInviteResult(member_id=member.id, token=token, expires_at=expires_at)


@router.delete("/tenants/{tenant_id}/admins/{member_id}", status_code=204)
def revoke_tenant_admin(
    tenant_id: uuid.UUID, member_id: uuid.UUID, db: AdminDbDep, actor: SuperadminDep
) -> None:
    """Revoke a member's administrator role(s) in the tenant (superadmin only).

    Soft-deletes the member's admin role assignment(s), preserving history.
    Returns 404 if the member is not an admin here, and 409 if they are the
    tenant's last remaining administrator (a troop must keep at least one).
    """
    with unscoped():
        assignments = admin_assignments(tenant_id, db)
        target = [a for a in assignments if a.member_id == member_id]
        if not target:
            raise HTTPException(
                status_code=404, detail="Member is not an administrator of this tenant"
            )

        remaining = {a.member_id for a in assignments} - {member_id}
        if not remaining:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot revoke the tenant's last administrator",
            )

        for assignment in target:
            assignment.is_deleted = True
        db.commit()
    _audit(actor, "tenant_admin.revoke", tenant=tenant_id, member=member_id)


# ---------------------------------------------------------------------------
# Platform administrators (the global tier itself)
# ---------------------------------------------------------------------------


def _as_admin_read(user: User) -> PlatformAdminRead:
    role = user.platform_role
    if role is None:  # callers always filter on a non-null role
        raise HTTPException(status_code=404, detail="User is not a platform administrator")
    return PlatformAdminRead(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        platform_role=role,
    )


@router.get("/admins", response_model=list[PlatformAdminRead])
def list_platform_admins(db: AdminDbDep) -> list[PlatformAdminRead]:
    """List every user holding a platform role (any platform admin may view)."""
    users = db.scalars(
        select(User)
        .where(User.platform_role.is_not(None), User.is_deleted.is_(False))
        .order_by(User.email)
    ).all()
    return [_as_admin_read(u) for u in users]


@router.post("/admins", response_model=PlatformAdminRead, status_code=201)
def grant_platform_admin(
    body: PlatformAdminGrant, db: AdminDbDep, actor: SuperadminDep
) -> PlatformAdminRead:
    """Grant a platform role to an existing user (superadmin only).

    The target user must already exist — i.e. have signed in at least once — and
    their provider must have verified the email (an unverified User.email is
    attacker-chosen at signup; matching it would let a squatter receive the role).
    Returns 404 if no user matches the email, 409 if the email is ambiguous.
    """
    users = db.scalars(
        select(User).where(
            User.email == body.email,
            User.email_verified.is_(True),
            User.is_deleted.is_(False),
        )
    ).all()
    if not users:
        raise HTTPException(
            status_code=404,
            detail="No user with that verified email — they must sign in at least once first",
        )
    if len(users) > 1:
        raise HTTPException(status_code=409, detail="Multiple users share that email")

    user = users[0]
    user.platform_role = body.role
    db.commit()
    db.refresh(user)
    _audit(actor, "platform_admin.grant", user=user.id, email=user.email, role=body.role)
    return _as_admin_read(user)


@router.delete("/admins/{user_id}", status_code=204)
def revoke_platform_admin(user_id: uuid.UUID, db: AdminDbDep, actor: SuperadminDep) -> None:
    """Revoke a user's platform role (superadmin only).

    Returns 404 if the user holds no platform role, and 409 if they are the last
    remaining superadmin (the platform must keep at least one).
    """
    user = db.get(User, user_id)
    if user is None or user.is_deleted or user.platform_role is None:
        raise HTTPException(status_code=404, detail="User is not a platform administrator")

    if user.platform_role is PlatformRole.SUPERADMIN:
        other_superadmins = db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.platform_role == PlatformRole.SUPERADMIN,
                User.is_deleted.is_(False),
                User.id != user_id,
            )
        )
        if not other_superadmins:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot revoke the last superadmin",
            )

    user.platform_role = None
    db.commit()
    _audit(actor, "platform_admin.revoke", user=user_id, email=user.email)
