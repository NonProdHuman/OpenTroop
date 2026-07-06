#!/usr/bin/env python3
"""reap_photo_uploads.py — sweep abandoned and deleted photo uploads (GH-145).

Releases the quota reservations of PENDING uploads that were never confirmed,
deletes the object bytes of soft-deleted photos, and tombstones both as PURGED
so offline mirrors drop them. Run periodically (cron / Cloud Scheduler);
idempotent and safe to run with nothing due.

    uv run reap-photo-uploads            # sweep everything due
    uv run reap-photo-uploads --dry-run  # report what would be swept, roll back
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep abandoned/deleted photo uploads")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would be swept, then roll back"
    )
    args = parser.parse_args()

    from app.core.database import SessionLocal
    from app.core.photo_reaper import reap_photo_uploads
    from app.core.storage import get_storage_service

    session = SessionLocal()
    try:
        stale, purged = reap_photo_uploads(session, get_storage_service(), dry_run=args.dry_run)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()
    finally:
        session.close()

    suffix = " (dry run — rolled back)" if args.dry_run else ""
    print(f"Reaped {stale} stale pending upload(s), purged {purged} deleted photo(s){suffix}")


if __name__ == "__main__":
    main()
