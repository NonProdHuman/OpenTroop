from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUserDep, DbDep
from app.models.enums import MemberType
from app.models.event_type import EventType
from app.models.member import Member
from app.models.role import MemberRoleAssignment, Role
from app.models.tenant import Tenant
from app.schemas.tenant import TenantProvision, TenantRead

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


@router.post("/", response_model=TenantRead, status_code=201)
def provision_tenant(body: TenantProvision, user: CurrentUserDep, db: DbDep) -> Tenant:
    """Create a new tenant and make the authenticated user its founding admin.

    Atomically creates the Tenant, a Member record for the founder, the
    'administrators' role (is_admin=True), and the MemberRoleAssignment
    linking the founder to that role.

    Returns 409 if the slug is already taken.
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
        user_id=user.id,
        first_name=body.founder_first_name,
        last_name=body.founder_last_name,
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

    db.commit()
    db.refresh(tenant)
    return tenant
