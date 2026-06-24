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
  Patrol, Member (scouts + adults), MemberRelationship, Location,
  EventType, Event, EventParticipant
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
    args = parser.parse_args()

    try:
        tenant_id = uuid.UUID(args.tenant_id)
    except ValueError:
        sys.exit(f"Error: {args.tenant_id!r} is not a valid UUID")

    if not args.xml_file.exists():
        sys.exit(f"Error: file not found: {args.xml_file}")

    # Import here so the module can be discovered by mypy without a live DB.
    from app.core.database import SessionLocal
    from app.importers.twh import TwhImporter
    from app.models import Base  # noqa: F401 — registers all tables

    print(f"Parsing {args.xml_file} ...")
    root = ET.parse(args.xml_file).getroot()  # noqa: S314 — admin-supplied file, not web input

    print(f"Importing into tenant {tenant_id} ...")
    session = SessionLocal()
    try:
        result = TwhImporter(session, tenant_id).run(root)
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
    print(f"  Locations     {result.locations:>6}")
    print(f"  Event types   {result.event_types:>6}")
    print(f"  Events        {result.events:>6}")
    print(f"  Participants  {result.participants:>6}")
    print(f"  Skipped       {result.skipped:>6}")
    if result.warnings:
        print()
        print(f"Warnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  ⚠  {w}")


if __name__ == "__main__":
    main()
