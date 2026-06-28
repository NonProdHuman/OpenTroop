"""Tenant provisioning helpers shared by the platform control-plane API.

Centralizes the building blocks for creating a troop and its administrators so
the ``/platform`` endpoints (and the self-host CLI) don't duplicate the logic:
default event types, the default RBAC (positions, functional roles, and their
mapping), unclaimed founding members, and admin invitations.

All functions operate within the caller's transaction — they ``flush`` but never
``commit``; the caller owns the commit/rollback boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.invite import create_invite_token
from app.core.tenant_context import unscoped
from app.models.enums import MemberType, Permission, PositionScope
from app.models.event_type import EventType
from app.models.member import Member
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
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

P = Permission

# Slug of the seeded administrators functional role and position. The founder and
# any invited admins are given the ADMINISTRATOR_POSITION_SLUG position, which maps
# to the is_admin functional role of the same slug.
ADMINISTRATORS_ROLE_SLUG = "administrators"
ADMINISTRATOR_POSITION_SLUG = "administrator"

# Default functional roles (permission buckets). ``is_admin`` short-circuits to the
# full permission set; ``permissions`` is then irrelevant. These ship is_system —
# reconfigurable per tenant but not deletable.
DEFAULT_FUNCTIONAL_ROLES: list[dict[str, object]] = [
    {"slug": ADMINISTRATORS_ROLE_SLUG, "name": "Administrators", "is_admin": True, "perms": []},
    {
        "slug": "member-admins",
        "name": "Member Admins",
        "perms": [
            P.MEMBER_READ,
            P.MEMBER_WRITE,
            P.MEMBER_READ_CONTACT,
            P.MEMBER_READ_MEDICAL,
            P.MEMBER_WRITE_MEDICAL,
            P.MEMBER_DELETE,
            P.ROLE_ASSIGN,
            P.REPORT_READ,
        ],
    },
    {
        "slug": "member-viewers",
        "name": "Member Viewers",
        "perms": [P.MEMBER_READ, P.MEMBER_READ_CONTACT],
    },
    {
        "slug": "event-admins",
        "name": "Event Admins",
        "perms": [
            P.EVENT_READ,
            P.EVENT_CREATE,
            P.EVENT_WRITE,
            P.EVENT_DELETE,
            P.EVENT_MANAGE_ATTENDANCE,
            P.REPORT_READ,
        ],
    },
    {
        "slug": "attendance-takers",
        "name": "Attendance Takers",
        "perms": [P.EVENT_READ, P.EVENT_MANAGE_ATTENDANCE],
    },
    {"slug": "event-viewers", "name": "Event Viewers", "perms": [P.EVENT_READ]},
    {
        "slug": "advancement-admins",
        "name": "Advancement Admins",
        "perms": [P.ADVANCEMENT_READ, P.ADVANCEMENT_RECORD, P.ADVANCEMENT_APPROVE],
    },
    {
        "slug": "advancement-recorders",
        "name": "Advancement Recorders",
        "perms": [P.ADVANCEMENT_READ, P.ADVANCEMENT_RECORD],
    },
    {"slug": "advancement-viewers", "name": "Advancement Viewers", "perms": [P.ADVANCEMENT_READ]},
    {
        "slug": "finance-admins",
        "name": "Finance Admins",
        "perms": [P.FINANCE_READ, P.FINANCE_WRITE, P.REPORT_READ],
    },
    {"slug": "finance-viewers", "name": "Finance Viewers", "perms": [P.FINANCE_READ]},
    {
        "slug": "troop-communicators",
        "name": "Troop Communicators",
        "perms": [P.COMMUNICATION_SEND_TROOP, P.COMMUNICATION_SEND_PATROL],
    },
    {
        "slug": "patrol-communicators",
        "name": "Patrol Communicators",
        "perms": [P.COMMUNICATION_SEND_PATROL],
    },
]

# Default positions and the functional-role slugs each maps to. ``sort_order`` keeps
# the troop's position list in a sensible (adult-leadership-first) order.
DEFAULT_POSITIONS: list[dict[str, object]] = [
    # Adult positions
    {
        "slug": ADMINISTRATOR_POSITION_SLUG,
        "name": "Administrator",
        "scope": PositionScope.ADULT,
        "roles": [ADMINISTRATORS_ROLE_SLUG],
    },
    {
        "slug": "committee-chair",
        "name": "Committee Chair",
        "scope": PositionScope.ADULT,
        "roles": ["member-admins", "event-admins", "troop-communicators"],
    },
    {
        "slug": "chartered-org-rep",
        "name": "Chartered Org Rep",
        "scope": PositionScope.ADULT,
        "roles": ["member-viewers"],
    },
    {
        "slug": "scoutmaster",
        "name": "Scoutmaster",
        "scope": PositionScope.ADULT,
        "roles": ["member-admins", "event-admins", "advancement-admins", "troop-communicators"],
    },
    {
        "slug": "assistant-scoutmaster",
        "name": "Assistant Scoutmaster",
        "scope": PositionScope.ADULT,
        "roles": ["member-viewers", "event-admins", "advancement-recorders", "troop-communicators"],
    },
    {
        "slug": "treasurer",
        "name": "Treasurer",
        "scope": PositionScope.ADULT,
        "roles": ["finance-admins"],
    },
    {
        "slug": "advancement-chair",
        "name": "Advancement Chair",
        "scope": PositionScope.ADULT,
        "roles": ["advancement-admins"],
    },
    {
        "slug": "membership-chair",
        "name": "Membership Chair",
        "scope": PositionScope.ADULT,
        "roles": ["member-admins"],
    },
    {
        "slug": "committee-member",
        "name": "Committee Member",
        "scope": PositionScope.ADULT,
        "roles": ["member-viewers", "event-viewers"],
    },
    {
        "slug": "parent-guardian",
        "name": "Parent / Guardian",
        "scope": PositionScope.ADULT,
        "roles": [],
    },
    # Scout positions
    {
        "slug": "senior-patrol-leader",
        "name": "Senior Patrol Leader",
        "scope": PositionScope.SCOUT,
        "roles": ["event-viewers", "troop-communicators"],
    },
    {
        "slug": "assistant-senior-patrol-leader",
        "name": "Assistant Senior Patrol Leader",
        "scope": PositionScope.SCOUT,
        "roles": ["event-viewers", "troop-communicators"],
    },
    {
        "slug": "patrol-leader",
        "name": "Patrol Leader",
        "scope": PositionScope.SCOUT,
        "roles": ["patrol-communicators"],
    },
    {
        "slug": "assistant-patrol-leader",
        "name": "Assistant Patrol Leader",
        "scope": PositionScope.SCOUT,
        "roles": ["patrol-communicators"],
    },
    {
        "slug": "scribe",
        "name": "Scribe",
        "scope": PositionScope.SCOUT,
        "roles": ["attendance-takers"],
    },
    {"slug": "troop-guide", "name": "Troop Guide", "scope": PositionScope.SCOUT, "roles": []},
    {"slug": "quartermaster", "name": "Quartermaster", "scope": PositionScope.SCOUT, "roles": []},
    {"slug": "historian", "name": "Historian", "scope": PositionScope.SCOUT, "roles": []},
    {"slug": "librarian", "name": "Librarian", "scope": PositionScope.SCOUT, "roles": []},
    {"slug": "bugler", "name": "Bugler", "scope": PositionScope.SCOUT, "roles": []},
    {
        "slug": "oa-representative",
        "name": "OA Representative",
        "scope": PositionScope.SCOUT,
        "roles": [],
    },
]


def seed_default_event_types(db: Session, tenant_id: uuid.UUID) -> None:
    """Create the six seeded, non-deletable system event types for a new tenant."""
    for defaults in DEFAULT_EVENT_TYPES:
        db.add(EventType(tenant_id=tenant_id, is_system=True, **defaults))


def seed_default_rbac(db: Session, tenant_id: uuid.UUID) -> None:
    """Seed the default functional roles, positions, and their mapping for a tenant.

    Idempotent: if the administrators functional role already exists, this is a
    no-op (the tenant has already been seeded). All seeded rows are is_system.
    """
    with unscoped():
        existing = db.scalar(
            select(FunctionalRole).where(
                FunctionalRole.tenant_id == tenant_id,
                FunctionalRole.slug == ADMINISTRATORS_ROLE_SLUG,
                FunctionalRole.is_deleted.is_(False),
            )
        )
        if existing is not None:
            return

        role_by_slug: dict[str, FunctionalRole] = {}
        for spec in DEFAULT_FUNCTIONAL_ROLES:
            role = FunctionalRole(
                tenant_id=tenant_id,
                name=spec["name"],
                slug=spec["slug"],
                is_admin=bool(spec.get("is_admin", False)),
                is_system=True,
            )
            db.add(role)
            db.flush()
            role_by_slug[str(spec["slug"])] = role
            for perm in spec["perms"]:  # type: ignore[attr-defined]
                db.add(
                    FunctionalRolePermission(
                        tenant_id=tenant_id, functional_role_id=role.id, permission=perm
                    )
                )

        for order, spec in enumerate(DEFAULT_POSITIONS):
            position = Position(
                tenant_id=tenant_id,
                name=spec["name"],
                slug=spec["slug"],
                applies_to=spec["scope"],
                is_system=True,
                sort_order=order,
            )
            db.add(position)
            db.flush()
            for role_slug in spec["roles"]:  # type: ignore[attr-defined]
                db.add(
                    PositionFunctionalRole(
                        tenant_id=tenant_id,
                        position_id=position.id,
                        functional_role_id=role_by_slug[role_slug].id,
                    )
                )
        db.flush()


def get_administrator_position(db: Session, tenant_id: uuid.UUID) -> Position:
    """Return the tenant's seeded Administrator position, seeding RBAC if needed."""
    with unscoped():
        position = db.scalar(
            select(Position).where(
                Position.tenant_id == tenant_id,
                Position.slug == ADMINISTRATOR_POSITION_SLUG,
                Position.is_deleted.is_(False),
            )
        )
        if position is None:
            seed_default_rbac(db, tenant_id)
            position = db.scalar(
                select(Position).where(
                    Position.tenant_id == tenant_id,
                    Position.slug == ADMINISTRATOR_POSITION_SLUG,
                    Position.is_deleted.is_(False),
                )
            )
        if position is None:  # seed_default_rbac always creates it; defensive
            raise RuntimeError("Administrator position missing after RBAC seed")
    return position


def invite_admin_member(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    first_name: str,
    last_name: str,
    email: str | None,
) -> tuple[Member, str, datetime]:
    """Create an *unclaimed* admin member and a claim token for them.

    Creates the Member (``user_id`` null), assigns the Administrator position, and
    mints a 7-day invite token the invitee uses via POST /auth/claim. Returns
    ``(member, token, expires_at)``.
    """
    with unscoped():
        admin_position = get_administrator_position(db, tenant_id)

        user_id = None
        if email:
            from app.models.user import User

            existing_user = db.scalar(
                select(User).where(User.email == email, User.is_deleted.is_(False))
            )
            if existing_user:
                user_id = existing_user.id

        member = Member(
            tenant_id=tenant_id,
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            member_type=MemberType.ADULT,
        )
        db.add(member)
        db.flush()
        db.add(
            MemberPositionAssignment(
                tenant_id=tenant_id, member_id=member.id, position_id=admin_position.id
            )
        )
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
    """Create a tenant, its default RBAC + event types, and its founding admin.

    Returns ``(tenant, founder_member, invite_token, expires_at)``. The caller is
    responsible for checking slug uniqueness beforehand and for committing.
    """
    tenant = Tenant(name=name, slug=slug)
    db.add(tenant)
    db.flush()

    seed_default_rbac(db, tenant.id)
    founder, token, expires_at = invite_admin_member(
        db,
        tenant.id,
        first_name=founder_first_name,
        last_name=founder_last_name,
        email=founder_email,
    )
    seed_default_event_types(db, tenant.id)
    return tenant, founder, token, expires_at
