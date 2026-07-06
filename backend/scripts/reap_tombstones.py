#!/usr/bin/env python3
"""reap_tombstones.py — physically delete purged-member tombstones (GH-222).

An admin purge anonymizes a member immediately; the tombstone then rides the
sync stream so offline mirrors drop the row. Once the tombstone has been
visible for the retention window (``TOMBSTONE_RETENTION_DAYS``, ≥180 per
sync-protocol Decision 5), this job hard-deletes the skeleton row and its
dependents and advances the tenant's ``purged_through_seq`` watermark — stale
sync cursors are then answered 410 and full-refetch. Run periodically
(cron / Cloud Scheduler); idempotent and safe to run with nothing due.

    uv run reap-tombstones            # reap everything past retention
    uv run reap-tombstones --dry-run  # report what would be reaped, roll back
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Hard-delete purged member tombstones")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would be reaped, then roll back"
    )
    args = parser.parse_args()

    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.core.deletion import reap_purged_members

    session = SessionLocal()
    try:
        count = reap_purged_members(session)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()
    finally:
        session.close()

    suffix = " (dry run — rolled back)" if args.dry_run else ""
    print(
        f"Reaped {count} purged member(s) past "
        f"{settings.tombstone_retention_days}-day retention{suffix}"
    )


if __name__ == "__main__":
    main()
