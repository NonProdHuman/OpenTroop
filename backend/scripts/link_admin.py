#!/usr/bin/env python3
"""
link_admin.py — Link the platform User (Clerk identity) to an admin Member.

Use this when provision-tenant was run before signing in, so the founding
member has user_id=NULL and you can't access the API.

Two modes:

  1. Create a new admin member and link it (default):

        uv run link-admin <tenant-id> --first Jeff --last Couvrette

  2. Link an existing imported member to your User and grant them admin:

        uv run link-admin <tenant-id> --member-id <uuid>

In both cases the script finds the single existing User row (created when you
signed into the web app) and sets member.user_id = user.id, then ensures a
MemberRoleAssignment exists for the Administrators role.
"""

from __future__ import annotations

import argparse
import sys
import uuid

from sqlalchemy import select


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("tenant_id", help="UUID of the target tenant")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--member-id", help="UUID of an existing member to promote to admin")
    group.add_argument("--first", help="First name for a new admin member (use with --last)")
    parser.add_argument("--last", help="Last name for a new admin member (use with --first)")
    args = parser.parse_args()

    if args.first and not args.last:
        parser.error("--first requires --last")
    if args.last and not args.first:
        parser.error("--last requires --first")

    try:
        tid = uuid.UUID(args.tenant_id)
    except ValueError:
        sys.exit(f"Error: {args.tenant_id!r} is not a valid UUID")

    from app.core.database import SessionLocal
    from app.models import Base  # noqa: F401
    from app.models.enums import MemberType
    from app.models.member import Member
    from app.models.role import MemberRoleAssignment, Role
    from app.models.tenant import Tenant
    from app.models.user import User

    session = SessionLocal()
    try:
        # Verify tenant exists
        tenant = session.scalar(select(Tenant).where(Tenant.id == tid))
        if not tenant:
            sys.exit(f"Error: tenant {tid} not found")

        # Find the platform User — there should be exactly one if you've signed in once
        users = session.scalars(select(User).where(User.is_deleted.is_(False))).all()
        if not users:
            sys.exit(
                "Error: no User rows found. Sign into the web app with Clerk first, "
                "then re-run this script."
            )
        if len(users) > 1:
            print("Multiple users found:")
            for u in users:
                print(f"  {u.id}  {u.email or '(no email)'}  {u.display_name or ''}")
            sys.exit(
                "Specify which user to link by editing this script or adding a --user-id flag."
            )
        user = users[0]
        print(f"User: {user.id}  {user.email or '(no email)'}  {user.display_name or ''}")

        # Find or create the member
        if args.member_id:
            mid = uuid.UUID(args.member_id)
            member = session.scalar(
                select(Member).where(
                    Member.id == mid,
                    Member.tenant_id == tid,
                    Member.is_deleted.is_(False),
                )
            )
            if not member:
                sys.exit(f"Error: member {mid} not found in tenant {tid}")
        else:
            first = args.first or "Admin"
            last = args.last or "User"
            # Try to find an existing unlinked member by name first
            member = session.scalar(
                select(Member).where(
                    Member.tenant_id == tid,
                    Member.first_name == first,
                    Member.last_name == last,
                    Member.is_deleted.is_(False),
                )
            )
            if member:
                print(
                    f"Found existing member: {member.first_name} {member.last_name} ({member.id})"
                )
            else:
                member = Member(
                    tenant_id=tid,
                    first_name=first,
                    last_name=last,
                    member_type=MemberType.ADULT,
                    user_id=user.id,
                )
                session.add(member)
                session.flush()
                print(f"Created member: {member.first_name} {member.last_name} ({member.id})")

        # Link user_id
        if member.user_id != user.id:
            member.user_id = user.id
            print(f"Linked user_id → {user.id}")

        # Find the Administrators role
        admin_role = session.scalar(
            select(Role).where(
                Role.tenant_id == tid,
                Role.is_admin.is_(True),
                Role.is_deleted.is_(False),
            )
        )
        if not admin_role:
            sys.exit(
                f"Error: no admin role found in tenant {tid}. "
                "Did provision-tenant run successfully?"
            )

        # Ensure the role assignment exists
        existing_assignment = session.scalar(
            select(MemberRoleAssignment).where(
                MemberRoleAssignment.tenant_id == tid,
                MemberRoleAssignment.member_id == member.id,
                MemberRoleAssignment.role_id == admin_role.id,
                MemberRoleAssignment.is_deleted.is_(False),
            )
        )
        if not existing_assignment:
            session.add(
                MemberRoleAssignment(
                    tenant_id=tid,
                    member_id=member.id,
                    role_id=admin_role.id,
                )
            )
            print(f"Granted Administrators role ({admin_role.id})")
        else:
            print("Administrators role assignment already exists")

        session.commit()
        print()
        print("Done. You can now sign in and access the API as an admin.")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
