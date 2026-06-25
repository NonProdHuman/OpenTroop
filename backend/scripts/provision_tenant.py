#!/usr/bin/env python3
"""
provision_tenant.py — Bootstrap a new tenant directly in the database.

This script is the CLI equivalent of POST /platform/tenants: it creates the Tenant
row, a founding admin Member, the Administrators role, and the six default
event types — all atomically, without requiring a Clerk JWT.

Use this for local development and self-hosted deployments. In production,
use the web onboarding flow instead (it links the founding member to a real
Clerk identity).

Recommended flow:
    1. Start the stack: ./start.sh
    2. Sign into the app with Clerk at http://localhost:3000 — this creates your User row
    3. Run this script:

        uv run provision-tenant \\
            --troop-name "Troop 123" \\
            --slug troop123 \\
            --admin-first Jeff \\
            --admin-last Smith

    4. Copy the printed Tenant ID into apps/web/.env.local as NEXT_PUBLIC_TENANT_ID
    5. Restart ./start.sh — you now have full admin access

If you run this before signing in, the founding member will have no Clerk link
and all API calls will return 403. In that case, sign in first and then run:

    uv run link-admin <tenant-id> --first <first> --last <last>
"""

from __future__ import annotations

import argparse
import sys

_DEFAULT_EVENT_TYPES: list[dict[str, object]] = [
    {"name": "Meeting", "color": "#4A90D9", "allow_signups": False},
    {
        "name": "Campout",
        "color": "#2ECC71",
        "tracks_camping_nights": True,
        "tracks_mileage": True,
        "require_permission_slip": True,
    },
    {
        "name": "Hike",
        "color": "#F39C12",
        "tracks_mileage": True,
        "require_permission_slip": True,
    },
    {
        "name": "Service Project",
        "color": "#E74C3C",
        "tracks_service_hours": True,
        "require_permission_slip": True,
    },
    {"name": "Court of Honor", "color": "#9B59B6"},
    {"name": "Fundraiser", "color": "#1ABC9C"},
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--troop-name", required=True, help='Human name, e.g. "Troop 123"')
    parser.add_argument(
        "--slug",
        required=True,
        help="URL-safe identifier, e.g. troop123 (must be unique)",
    )
    parser.add_argument("--admin-first", required=True, help="Founding admin first name")
    parser.add_argument("--admin-last", required=True, help="Founding admin last name")
    args = parser.parse_args()

    # Validate slug format
    import re

    if not re.fullmatch(r"[a-z0-9-]+", args.slug):
        sys.exit("Error: --slug must contain only lowercase letters, digits, and hyphens")

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models import Base  # noqa: F401
    from app.models.enums import MemberType
    from app.models.event_type import EventType
    from app.models.member import Member
    from app.models.role import MemberRoleAssignment, Role
    from app.models.tenant import Tenant
    from app.models.user import User

    session = SessionLocal()
    try:
        # Guard against duplicate slugs
        existing = session.scalar(
            select(Tenant).where(Tenant.slug == args.slug, Tenant.is_deleted.is_(False))
        )
        if existing:
            sys.exit(f"Error: a tenant with slug {args.slug!r} already exists (id={existing.id})")

        # Auto-link to the single existing User row (created when you sign in).
        # Clerk doesn't store email on User rows, so we can't match by email —
        # instead we rely on there being exactly one User in the DB.
        users = session.scalars(select(User).where(User.is_deleted.is_(False))).all()
        linked_user: User | None = None
        if len(users) == 1:
            linked_user = users[0]
        elif len(users) > 1:
            print(
                f"  Note: {len(users)} User rows found — cannot auto-link. "
                "Run  uv run link-admin <tenant-id> --first … --last …  after provisioning."
            )
        else:
            print(
                "  Note: no User rows found — sign into the app first so Clerk can create "
                "your User row, then run  uv run link-admin <tenant-id> --first … --last …"
            )

        tenant = Tenant(name=args.troop_name, slug=args.slug)
        session.add(tenant)
        session.flush()

        founder = Member(
            tenant_id=tenant.id,
            first_name=args.admin_first,
            last_name=args.admin_last,
            member_type=MemberType.ADULT,
            user_id=linked_user.id if linked_user else None,
        )
        session.add(founder)
        session.flush()

        admin_role = Role(
            tenant_id=tenant.id,
            name="Administrators",
            slug="administrators",
            is_admin=True,
            is_system=True,
        )
        session.add(admin_role)
        session.flush()

        session.add(
            MemberRoleAssignment(
                tenant_id=tenant.id,
                member_id=founder.id,
                role_id=admin_role.id,
            )
        )

        for defaults in _DEFAULT_EVENT_TYPES:
            session.add(EventType(tenant_id=tenant.id, is_system=True, **defaults))

        session.commit()

        print()
        print(f"Tenant created: {tenant.name!r}")
        print(f"  Tenant ID : {tenant.id}")
        print(f"  Slug      : {tenant.slug}")
        print(f"  Admin     : {founder.first_name} {founder.last_name} (member id: {founder.id})")
        if linked_user:
            print(f"  Linked to : user id {linked_user.id}  ✓ ready to use")
        else:
            print("  Linked to : (none)")
            print()
            print("  ACTION REQUIRED: sign into the app, then run:")
            print(
                f"    uv run link-admin {tenant.id} --first {args.admin_first} --last {args.admin_last}"
            )
        print()
        print("Next steps:")
        print("  1. Add to apps/web/.env.local:")
        print(f"       NEXT_PUBLIC_TENANT_ID={tenant.id}")
        print("  2. Import your TWH data:")
        print(f"       uv run import-twh {tenant.id} path/to/export.xml")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
