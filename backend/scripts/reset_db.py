#!/usr/bin/env python3
"""
reset_db.py — Nuclear full-database reset: drops all tables and re-applies
every Alembic migration from scratch.

This destroys ALL data: tenants, users, members, events — everything.
You will need to provision a new tenant again (POST /platform/tenants, or the
provision-tenant CLI) before importing or using the app.

Run from backend/ (requires a running Postgres, same connection as alembic.ini):
    uv run reset-db

Pass --yes to skip the confirmation prompt (useful in CI or scripts):
    uv run reset-db --yes
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_DIR = Path(__file__).parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt",
    )
    args = parser.parse_args()

    if not args.yes:
        print("WARNING: This will permanently destroy ALL data in the database.")
        answer = input("Type 'yes' to continue: ").strip().lower()
        if answer != "yes":
            print("Aborted.")
            sys.exit(0)

    # Drop the entire public schema and recreate it. This removes tables, enum
    # types, sequences, and functions in one shot — alembic downgrade leaves
    # orphaned enum types that cause CREATE TYPE errors on the next upgrade.
    print("Dropping public schema (DROP SCHEMA public CASCADE)...")
    from app.core.database import engine

    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))
        conn.commit()

    print("Re-applying all migrations (alembic upgrade head)...")
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "alembic", "upgrade", "head"],  # noqa: S607
        check=False,
        cwd=BACKEND_DIR,
    )
    if result.returncode != 0:
        sys.exit("Error: alembic upgrade failed")

    print()
    print("Done. All tables recreated. Next steps:")
    print("  1. uv run provision-tenant --troop-name … --slug … --admin-first … --admin-last …")
    print("  2. uv run import-twh <tenant-id> path/to/export.xml")


if __name__ == "__main__":
    main()
