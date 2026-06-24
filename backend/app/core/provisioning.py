"""Tenant provisioning helpers shared by the platform control-plane API.

Centralizes the building blocks for creating a troop and its administrators so
the ``/platform`` endpoints (and, in future, the self-host CLI) don't duplicate
the logic: default event types, the administrators role, unclaimed founding
members, and admin invitations.

All functions operate within the caller's transaction — they ``flush`` but never
``commit``; the caller owns the commit/rollback boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.invite import create_invite_token
from app.models.enums import MemberType
from app.models.event_type import EventType
from app.models.member import Member
from app.models.role import MemberRoleAssignment, Role
from app.models.tenant import Tenant

DEFAULT_EVENT_TYPES: list[dict[str, object]] = [
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


def seed_default_event_types(db: Session, tenant_id: uuid.UUID) -> None:
    """Create the six seeded, non-deletable system event types for a new tenant."""
    for defaults in DEFAULT_EVENT_TYPES:
        db.add(EventType(tenant_id=tenant_id, is_system=True, **defaults))


def ensure_administrators_role(db: Session, tenant_id: uuid.UUID) -> Role:
    """Return the tenant's administrators role, creating it if it does not exist."""
    role = db.scalar(
        select(Role).where(
            Role.tenant_id == tenant_id,
            Role.slug == "administrators",
            Role.is_deleted.is_(False),
        )
    )
    if role is None:
        role = Role(
            tenant_id=tenant_id,
            name="Administrators",
            slug="administrators",
            is_admin=True,
            is_system=True,
        )
        db.add(role)
        db.flush()
    return role


def invite_admin_member(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    first_name: str,
    last_name: str,
    email: str | None,
) -> tuple[Member, str, datetime]:
    """Create an *unclaimed* admin member and a claim token for them.

    Creates the Member (``user_id`` null), assigns the administrators role, and
    mints a 7-day invite token the invitee uses via POST /auth/claim. Returns
    ``(member, token, expires_at)``.
    """
    admin_role = ensure_administrators_role(db, tenant_id)
    member = Member(
        tenant_id=tenant_id,
        user_id=None,
        first_name=first_name,
        last_name=last_name,
        email=email,
        member_type=MemberType.ADULT,
    )
    db.add(member)
    db.flush()
    db.add(MemberRoleAssignment(tenant_id=tenant_id, member_id=member.id, role_id=admin_role.id))
    token, expires_at = create_invite_token(member.id, tenant_id)
    return member, token, expires_at


def provision_tenant(
    db: Session,
    *,
    name: str,
    slug: str,
    founder_first_name: str,
    founder_last_name: str,
    founder_email: str | None,
) -> tuple[Tenant, Member, str, datetime]:
    """Create a tenant, its founding admin invitation, and default event types.

    Returns ``(tenant, founder_member, invite_token, expires_at)``. The caller is
    responsible for checking slug uniqueness beforehand and for committing.
    """
    tenant = Tenant(name=name, slug=slug)
    db.add(tenant)
    db.flush()

    founder, token, expires_at = invite_admin_member(
        db,
        tenant.id,
        first_name=founder_first_name,
        last_name=founder_last_name,
        email=founder_email,
    )
    seed_default_event_types(db, tenant.id)
    return tenant, founder, token, expires_at
