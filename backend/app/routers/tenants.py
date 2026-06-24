from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbDep, PlatformAdminDep
from app.core.invite import create_invite_token
from app.models.enums import MemberType
from app.models.event_type import EventType
from app.models.member import Member
from app.models.role import MemberRoleAssignment, Role
from app.models.tenant import Tenant
from app.schemas.tenant import TenantProvision, TenantProvisioned

_DEFAULT_EVENT_TYPES: list[dict[str, object]] = [
    {"name": "Meeting", "color": "#4A90D9", "allow_signups": False},
    {
        "name": "Campout",
        "color": "#2ECC71",
        "tracks_camping_nights": True,
        "tracks_mileage": True,
        "require_permission_slip": True,
    },
    {"name": "Hike", "color": "#F39C12", "tracks_mileage": True, "require_permission_slip": True},
    {
        "name": "Service Project",
        "color": "#E74C3C",
        "tracks_service_hours": True,
        "require_permission_slip": True,
    },
    {"name": "Court of Honor", "color": "#9B59B6"},
    {"name": "Fundraiser", "color": "#1ABC9C"},
]

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("/", response_model=TenantProvisioned, status_code=201)
def provision_tenant(
    body: TenantProvision, _admin: PlatformAdminDep, db: DbDep
) -> TenantProvisioned:
    """Provision a new tenant and invite its founding admin (platform admins only).

    Tenant creation is a control-plane operation, not self-service. Atomically
    creates the Tenant, an *unclaimed* founding admin Member (``user_id`` null),
    the 'administrators' role (is_admin=True), the MemberRoleAssignment linking
    that member to the role, and the six default event types. The provisioning
    platform admin does not become a member of the new tenant.

    Returns the tenant plus a 7-day invite token the founder uses to claim the
    founding admin Member via POST /auth/claim. Returns 409 if the slug is taken.
    """
    if db.scalar(select(Tenant).where(Tenant.slug == body.slug, Tenant.is_deleted.is_(False))):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tenant with this slug already exists",
        )

    tenant = Tenant(name=body.name, slug=body.slug)
    db.add(tenant)
    db.flush()

    founder = Member(
        tenant_id=tenant.id,
        user_id=None,  # unclaimed until the founder accepts the invite
        first_name=body.founder_first_name,
        last_name=body.founder_last_name,
        email=body.founder_email,
        member_type=MemberType.ADULT,
    )
    db.add(founder)
    db.flush()

    admin_role = Role(
        tenant_id=tenant.id,
        name="Administrators",
        slug="administrators",
        is_admin=True,
        is_system=True,
    )
    db.add(admin_role)
    db.flush()

    db.add(MemberRoleAssignment(tenant_id=tenant.id, member_id=founder.id, role_id=admin_role.id))

    for defaults in _DEFAULT_EVENT_TYPES:
        db.add(EventType(tenant_id=tenant.id, is_system=True, **defaults))

    token, expires_at = create_invite_token(founder.id, tenant.id)

    db.commit()
    db.refresh(tenant)
    return TenantProvisioned(
        id=tenant.id,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        is_deleted=tenant.is_deleted,
        name=tenant.name,
        slug=tenant.slug,
        founder_member_id=founder.id,
        invite_token=token,
        invite_expires_at=expires_at,
    )
