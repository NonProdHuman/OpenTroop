#!/usr/bin/env python3
"""
import_twh.py — Import a TroopWebHost XML full-data export into OpenTroop.

Run from backend/:

    uv run import-twh <tenant-id> <path/to/export.xml>

The tenant must already exist (run `uv run provision-tenant` first).  The import is
additive — running it twice on the same tenant will create duplicate records
(BSA ID uniqueness will raise an IntegrityError on the second run if the same
persons are re-imported).

Records created for the given tenant:
  Patrol, Member (scouts + adults), MemberRelationship, Position +
  MemberPositionAssignment (dated leadership terms), Location, EventType,
  Event, EventParticipant, MemberRankProgress, MemberRequirementCompletion,
  MemberMeritBadge (advancement needs the global catalog: `uv run seed-advancement`
  first; run `uv run recompute-advancement` afterwards for auto-credit thresholds)
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("tenant_id", help="UUID of the target tenant")
    parser.add_argument("xml_file", type=Path, help="Path to the TWH full-data XML export")
    parser.add_argument(
        "--timezone",
        "-tz",
        default="UTC",
        help=(
            "IANA timezone the TWH export's local times are in "
            "(e.g. America/New_York). Times are converted to UTC on import. "
            "Default: UTC"
        ),
    )
    args = parser.parse_args()

    try:
        tenant_id = uuid.UUID(args.tenant_id)
    except ValueError:
        sys.exit(f"Error: {args.tenant_id!r} is not a valid UUID")

    if not args.xml_file.exists():
        sys.exit(f"Error: file not found: {args.xml_file}")

    # Import here so the module can be discovered by mypy without a live DB.
    from app.core.database import SessionLocal
    from app.importers.twh import TwhImporter, resolve_source_tz
    from app.models import Base  # noqa: F401 — registers all tables

    try:
        source_tz = resolve_source_tz(args.timezone)
    except ValueError as exc:
        sys.exit(f"Error: {exc}")

    print(f"Parsing {args.xml_file} ...")
    root = ET.parse(args.xml_file).getroot()  # noqa: S314 — admin-supplied file, not web input

    print(f"Importing into tenant {tenant_id} (source timezone: {args.timezone}) ...")
    session = SessionLocal()
    try:
        result = TwhImporter(session, tenant_id, source_tz=source_tz).run(root)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print()
    print("Import complete:")
    print(f"  Patrols       {result.patrols:>6}")
    print(f"  Members       {result.members:>6}")
    print(f"  Relationships {result.relationships:>6}")
    print(f"  Positions     {result.positions:>6}")
    print(f"  Position terms{result.position_assignments:>6}")
    print(f"  Locations     {result.locations:>6}")
    print(f"  Event types   {result.event_types:>6}")
    print(f"  Events        {result.events:>6}")
    print(f"  Participants  {result.participants:>6}")
    print(f"  Rank progress {result.rank_progress:>6}")
    print(f"  Req. sign-offs{result.requirement_completions:>6}")
    print(f"  Merit badges  {result.merit_badges:>6}")
    print(f"  Skipped       {result.skipped:>6}")
    if result.warnings:
        print()
        print(f"Warnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  ⚠  {w}")


if __name__ == "__main__":
    main()
