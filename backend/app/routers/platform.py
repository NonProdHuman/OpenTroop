"""Platform (global) control-plane API.

Every route here is gated by ``get_platform_admin`` (the caller's
``User.platform_role`` must be set) — this is the SaaS control plane, distinct
from tenant-scoped RBAC. Operations: provision/list/suspend tenants and invite,
list, and revoke a tenant's administrators.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbDep, get_platform_admin
from app.core.provisioning import invite_admin_member, provision_tenant
from app.models.member import Member
from app.models.role import MemberRoleAssignment, Role
from app.models.tenant import Tenant
from app.schemas.platform import TenantAdminInvite, TenantAdminInviteResult, TenantAdminRead
from app.schemas.tenant import TenantProvision, TenantProvisioned, TenantRead

router = APIRouter(
    prefix="/platform",
    tags=["platform"],
    dependencies=[Depends(get_platform_admin)],
)


def _get_tenant_or_404(db: DbDep, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------


@router.post("/tenants", response_model=TenantProvisioned, status_code=201)
def create_tenant(body: TenantProvision, db: DbDep) -> TenantProvisioned:
    """Provision a new tenant and invite its founding admin.

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
    return TenantProvisioned(
        **TenantRead.model_validate(tenant).model_dump(),
        founder_member_id=founder.id,
        invite_token=token,
        invite_expires_at=expires_at,
    )


@router.get("/tenants", response_model=list[TenantRead])
def list_tenants(db: DbDep) -> Sequence[Tenant]:
    """List all active tenants on the platform, newest first."""
    return db.scalars(
        select(Tenant).where(Tenant.is_deleted.is_(False)).order_by(Tenant.created_at.desc())
    ).all()


@router.get("/tenants/{tenant_id}", response_model=TenantRead)
def get_tenant(tenant_id: uuid.UUID, db: DbDep) -> Tenant:
    return _get_tenant_or_404(db, tenant_id)


@router.post("/tenants/{tenant_id}/suspend", response_model=TenantRead)
def suspend_tenant(tenant_id: uuid.UUID, db: DbDep) -> Tenant:
    """Suspend a tenant — tenant-scoped requests are then rejected. Idempotent."""
    tenant = _get_tenant_or_404(db, tenant_id)
    if tenant.suspended_at is None:
        tenant.suspended_at = datetime.now(UTC)
        db.commit()
        db.refresh(tenant)
    return tenant


@router.post("/tenants/{tenant_id}/unsuspend", response_model=TenantRead)
def unsuspend_tenant(tenant_id: uuid.UUID, db: DbDep) -> Tenant:
    """Lift a tenant's suspension. Idempotent."""
    tenant = _get_tenant_or_404(db, tenant_id)
    if tenant.suspended_at is not None:
        tenant.suspended_at = None
        db.commit()
        db.refresh(tenant)
    return tenant


# ---------------------------------------------------------------------------
# Tenant administrators
# ---------------------------------------------------------------------------


def _admin_assignments(db: DbDep, tenant_id: uuid.UUID) -> Sequence[MemberRoleAssignment]:
    """Active assignments of the tenant's is_admin role(s) to members."""
    return db.scalars(
        select(MemberRoleAssignment)
        .join(Role, MemberRoleAssignment.role_id == Role.id)
        .where(
            MemberRoleAssignment.tenant_id == tenant_id,
            MemberRoleAssignment.is_deleted.is_(False),
            Role.is_admin.is_(True),
            Role.is_deleted.is_(False),
        )
    ).all()


@router.get("/tenants/{tenant_id}/admins", response_model=list[TenantAdminRead])
def list_tenant_admins(tenant_id: uuid.UUID, db: DbDep) -> list[TenantAdminRead]:
    """List the members holding an administrator role in the tenant."""
    _get_tenant_or_404(db, tenant_id)
    admins: list[TenantAdminRead] = []
    seen: set[uuid.UUID] = set()
    for assignment in _admin_assignments(db, tenant_id):
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
    tenant_id: uuid.UUID, body: TenantAdminInvite, db: DbDep
) -> TenantAdminInviteResult:
    """Invite a new administrator into an existing tenant.

    Creates an unclaimed admin Member and returns a 7-day claim token the
    invitee redeems via POST /auth/claim.
    """
    _get_tenant_or_404(db, tenant_id)
    member, token, expires_at = invite_admin_member(
        db,
        tenant_id,
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
    )
    db.commit()
    return TenantAdminInviteResult(member_id=member.id, token=token, expires_at=expires_at)


@router.delete("/tenants/{tenant_id}/admins/{member_id}", status_code=204)
def revoke_tenant_admin(tenant_id: uuid.UUID, member_id: uuid.UUID, db: DbDep) -> None:
    """Revoke a member's administrator role(s) in the tenant.

    Soft-deletes the member's admin role assignment(s), preserving history.
    Returns 404 if the member is not an admin here, and 409 if they are the
    tenant's last remaining administrator (a troop must keep at least one).
    """
    assignments = _admin_assignments(db, tenant_id)
    target = [a for a in assignments if a.member_id == member_id]
    if not target:
        raise HTTPException(status_code=404, detail="Member is not an administrator of this tenant")

    remaining = {a.member_id for a in assignments} - {member_id}
    if not remaining:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot revoke the tenant's last administrator",
        )

    for assignment in target:
        assignment.is_deleted = True
    db.commit()
