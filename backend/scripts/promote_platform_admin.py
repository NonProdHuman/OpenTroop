#!/usr/bin/env python3
"""
promote_platform_admin.py — Grant (or revoke) a platform (global) role on a User.

Platform admins own the SaaS control plane: creating tenants and administering
tenant admins. This is the bootstrap path for the *first* platform admin in a
deployment — once one exists, further platform admins can be managed through the
API. It is also the supported self-hosted way to designate an operator.

The target User must already exist, i.e. the person must have signed in via the
web app at least once (which creates their User row). Match by email:

    uv run promote-platform-admin --email you@example.com
    uv run promote-platform-admin --email you@example.com --role support
    uv run promote-platform-admin --email you@example.com --revoke

Roles: superadmin (default), support, billing.
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--email", required=True, help="Email of an existing signed-in User")
    parser.add_argument(
        "--role",
        default="superadmin",
        choices=["superadmin", "support", "billing"],
        help="Platform role to grant (default: superadmin)",
    )
    parser.add_argument(
        "--revoke",
        action="store_true",
        help="Remove the user's platform role instead of granting one",
    )
    args = parser.parse_args()

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models import Base  # noqa: F401  (registers metadata)
    from app.models.enums import PlatformRole
    from app.models.user import User

    session = SessionLocal()
    try:
        users = session.scalars(
            select(User).where(User.email == args.email, User.is_deleted.is_(False))
        ).all()
        if not users:
            sys.exit(
                f"Error: no User with email {args.email!r}. "
                "The person must sign into the web app at least once first."
            )
        if len(users) > 1:
            ids = ", ".join(str(u.id) for u in users)
            sys.exit(f"Error: {len(users)} users share that email ({ids}); resolve manually.")

        user = users[0]
        if args.revoke:
            user.platform_role = None
            action = "revoked platform role from"
        else:
            user.platform_role = PlatformRole(args.role)
            action = f"granted {args.role!r} to"
        session.commit()

        print(f"OK: {action} {user.email} (user id: {user.id})")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
