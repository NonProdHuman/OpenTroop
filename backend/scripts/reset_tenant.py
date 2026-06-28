#!/usr/bin/env python3
"""
reset_tenant.py — Clear all imported data for a tenant so the TWH import
can be re-run cleanly without tearing down the whole database.

What is DELETED:
  - All EventParticipants, EventOrganizers, Events
  - All non-system EventTypes (system defaults are re-seeded on tenant creation)
  - All Locations
  - All MemberRelationships
  - All Members whose user_id IS NULL (i.e. imported members with no Clerk claim)
  - All MemberPositionAssignments for those deleted members
  - All non-system Positions / FunctionalRoles and their mappings/permissions
  - All Patrols / Groups

What is KEPT:
  - The Tenant row itself
  - Platform Users and Identities (Clerk linkage is untouched)
  - Members with user_id set (your Clerk-linked admin accounts)
  - Their Administrator position assignments
  - System positions and functional roles (is_system=True) and their permissions

After running this script you can immediately re-run:
    uv run import-twh <same-tenant-id> path/to/export.xml

Run from backend/:
    uv run reset-tenant <tenant-uuid>
"""

from __future__ import annotations

import argparse
import sys
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session


def _run(session: Session, stmt: Any) -> int:
    """Execute a DML statement and return the affected row count."""
    result: CursorResult[Any] = session.execute(stmt)  # type: ignore[assignment]
    return result.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("tenant_id", help="UUID of the tenant to clear")
    args = parser.parse_args()

    try:
        tid = uuid.UUID(args.tenant_id)
    except ValueError:
        sys.exit(f"Error: {args.tenant_id!r} is not a valid UUID")

    from app.core.database import SessionLocal
    from app.models import Base  # noqa: F401 — registers all tables
    from app.models.event import Event, EventOrganizer, EventParticipant
    from app.models.event_type import EventType
    from app.models.group import Group, GroupMember, GroupRule
    from app.models.location import Location
    from app.models.member import Member
    from app.models.rbac import (
        FunctionalRole,
        FunctionalRolePermission,
        MemberPositionAssignment,
        Position,
        PositionFunctionalRole,
    )
    from app.models.relationship import MemberRelationship
    from app.models.tenant import Tenant

    session = SessionLocal()
    try:
        tenant = session.scalar(select(Tenant).where(Tenant.id == tid))
        if tenant is None:
            sys.exit(f"Error: tenant {tid} not found")

        print(f"Resetting tenant: {tenant.name!r} ({tid})")

        # Members whose Clerk accounts are linked — keep these.
        linked_ids: list[uuid.UUID] = list(
            session.scalars(
                select(Member.id).where(Member.tenant_id == tid, Member.user_id.is_not(None))
            )
        )
        print(f"  Keeping {len(linked_ids)} Clerk-linked member(s)")

        # -- Delete in FK order --------------------------------------------------

        n = _run(session, delete(EventParticipant).where(EventParticipant.tenant_id == tid))
        print(f"  Deleted {n} event participants")

        n = _run(session, delete(EventOrganizer).where(EventOrganizer.tenant_id == tid))
        print(f"  Deleted {n} event organizers")

        n = _run(session, delete(Event).where(Event.tenant_id == tid))
        print(f"  Deleted {n} events")

        # Group membership + rules — clear before members/positions/groups (FK order).
        n = _run(session, delete(GroupMember).where(GroupMember.tenant_id == tid))
        print(f"  Deleted {n} group memberships")

        n = _run(session, delete(GroupRule).where(GroupRule.tenant_id == tid))
        print(f"  Deleted {n} group rules")

        # Position assignments — drop for members we're about to delete (non-linked).
        if linked_ids:
            n = _run(
                session,
                delete(MemberPositionAssignment).where(
                    MemberPositionAssignment.tenant_id == tid,
                    MemberPositionAssignment.member_id.not_in(linked_ids),
                ),
            )
        else:
            n = _run(
                session,
                delete(MemberPositionAssignment).where(MemberPositionAssignment.tenant_id == tid),
            )
        print(f"  Deleted {n} position assignments")

        # Non-system positions / functional roles: drop their mappings and
        # permissions first, then the rows. System (seeded) RBAC is kept.
        non_system_position_ids = list(
            session.scalars(
                select(Position.id).where(Position.tenant_id == tid, Position.is_system.is_(False))
            )
        )
        non_system_fr_ids = list(
            session.scalars(
                select(FunctionalRole.id).where(
                    FunctionalRole.tenant_id == tid, FunctionalRole.is_system.is_(False)
                )
            )
        )
        if non_system_position_ids:
            _run(
                session,
                delete(PositionFunctionalRole).where(
                    PositionFunctionalRole.tenant_id == tid,
                    PositionFunctionalRole.position_id.in_(non_system_position_ids),
                ),
            )
        if non_system_fr_ids:
            _run(
                session,
                delete(PositionFunctionalRole).where(
                    PositionFunctionalRole.tenant_id == tid,
                    PositionFunctionalRole.functional_role_id.in_(non_system_fr_ids),
                ),
            )
            _run(
                session,
                delete(FunctionalRolePermission).where(
                    FunctionalRolePermission.tenant_id == tid,
                    FunctionalRolePermission.functional_role_id.in_(non_system_fr_ids),
                ),
            )
        n = _run(
            session,
            delete(Position).where(Position.tenant_id == tid, Position.is_system.is_(False)),
        )
        print(f"  Deleted {n} positions")
        n = _run(
            session,
            delete(FunctionalRole).where(
                FunctionalRole.tenant_id == tid, FunctionalRole.is_system.is_(False)
            ),
        )
        print(f"  Deleted {n} functional roles")

        n = _run(session, delete(MemberRelationship).where(MemberRelationship.tenant_id == tid))
        print(f"  Deleted {n} member relationships")

        n = _run(
            session,
            delete(Member).where(Member.tenant_id == tid, Member.user_id.is_(None)),
        )
        print(f"  Deleted {n} members")

        n = _run(
            session,
            delete(EventType).where(EventType.tenant_id == tid, EventType.is_system.is_(False)),
        )
        print(f"  Deleted {n} event types")

        n = _run(session, delete(Location).where(Location.tenant_id == tid))
        print(f"  Deleted {n} locations")

        n = _run(session, delete(Group).where(Group.tenant_id == tid))
        print(f"  Deleted {n} groups")

        session.commit()
        print()
        print("Done. Re-run the import:")
        print(f"  uv run python import_twh.py {tid} path/to/export.xml")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
