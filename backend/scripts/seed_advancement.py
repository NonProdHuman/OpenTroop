#!/usr/bin/env python3
"""seed_advancement.py — Load the global advancement catalog (GH-92).

Idempotently upserts the curated data files in ``backend/data/advancement/``
(rank requirement sets per BSA version year + the merit badge list) into the
platform-global catalog tables. Run it:

  - after migrations in a fresh environment (dev bootstrap, self-host install),
  - as a deploy step whenever the data files change (text corrections update
    rows in place; completions keep pointing at the same requirement ids).

    uv run seed-advancement            # load backend/data/advancement/
    uv run seed-advancement --dir PATH # load an alternate data directory

Catalog tables are platform-global (no tenant), so this needs a database role
that can write them — in SaaS deployments run it with the owner/migrate
credentials (same as Alembic), matching how the other seed scripts operate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the global advancement catalog")
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Data directory (defaults to backend/data/advancement/)",
    )
    args = parser.parse_args()

    from app.core.advancement_catalog import DATA_DIR, load_catalog
    from app.core.database import SessionLocal

    data_dir = args.dir or DATA_DIR
    if not data_dir.is_dir():
        print(f"error: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    session = SessionLocal()
    try:
        stats = load_catalog(session, data_dir)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"Loaded: {', '.join(stats.files) or '(no files found)'}")
    print(
        f"Ranks created: {stats.ranks} · sets created: {stats.requirement_sets} · "
        f"requirements +{stats.requirements_created} ~{stats.requirements_updated} "
        f"-{stats.requirements_removed} · badges +{stats.merit_badges_created} "
        f"~{stats.merit_badges_updated}"
    )


if __name__ == "__main__":
    main()
