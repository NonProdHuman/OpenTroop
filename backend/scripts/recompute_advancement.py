#!/usr/bin/env python3
"""recompute_advancement.py — scheduled auto-credit pass (GH-92 Phase 3).

The in-request triggers cover data-driven changes (attendance, badge approvals,
rank dates). Pure time-passage thresholds — tenure and position-of-responsibility
months — cross their lines with no write to trigger on, so run this periodically
(cron / Cloud Scheduler) to record those credits. The progress *view* always
computes meters live, so display is never stale even between runs.

    uv run recompute-advancement                 # all active tenants
    uv run recompute-advancement --tenant-id ID  # one tenant

Skips suspended tenants and tenants with advancement disabled. Idempotent —
existing rows (revoked included) are never re-created.
"""

from __future__ import annotations

import argparse
import uuid


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the advancement auto-credit pass")
    parser.add_argument("--tenant-id", type=uuid.UUID, default=None, help="Limit to one tenant")
    args = parser.parse_args()

    from sqlalchemy import select

    from app.core.advancement import apply_auto_credits
    from app.core.database import SessionLocal
    from app.core.tenant_context import reset_current_tenant, set_current_tenant, unscoped
    from app.models.enums import AdvancementMode, MemberType
    from app.models.member import Member
    from app.models.tenant import Tenant

    session = SessionLocal()
    total_created = 0
    try:
        with unscoped():
            stmt = select(Tenant).where(
                Tenant.is_deleted.is_(False),
                Tenant.suspended_at.is_(None),
                Tenant.advancement_mode != AdvancementMode.DISABLED,
            )
            if args.tenant_id is not None:
                stmt = stmt.where(Tenant.id == args.tenant_id)
            tenants = list(session.scalars(stmt))

        for tenant in tenants:
            token = set_current_tenant(tenant.id)
            try:
                scouts = list(
                    session.scalars(select(Member).where(Member.member_type == MemberType.SCOUT))
                )
                tenant_created = 0
                for scout in scouts:
                    tenant_created += len(apply_auto_credits(scout.id, session))
                session.commit()
            finally:
                reset_current_tenant(token)
            print(f"{tenant.slug}: {len(scouts)} scouts, {tenant_created} credits recorded")
            total_created += tenant_created
    finally:
        session.close()

    print(f"Done: {total_created} auto-credits across {len(tenants)} tenant(s)")


if __name__ == "__main__":
    main()
