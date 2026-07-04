#!/usr/bin/env python3
"""
seed_dev_data.py — Provision a deterministic demo tenant for the dev verification loop.

Stands up a realistic troop in one command so a human (or an agent) can launch the
app against known data and click through a change end-to-end (GH-171). The dataset
is fixed — same names, same patrols, same events (dated relative to today) — so
Playwright smoke tests in apps/web/e2e can assert on it.

Usage (from backend/, with Postgres up — e.g. via ./start.sh or docker compose):

    uv run seed-dev-data --email you@example.com          # first run
    uv run seed-dev-data --email you@example.com --reset  # tear down + re-seed

--email links the founding "Demo Admin" member to your signed-in User row (sign in
through the app once first, same as provision-tenant). Without --email the founder
is left unclaimed and a claim token is printed.

What gets created (tenant slug "demo" unless --slug is given):
  - Default RBAC + event types via the normal provisioning path
  - 4 patrols (Ravens, Foxes, Hawks, Otters) x 5 scouts each
  - 15 adults: 7 leaders (SM, 2x ASM, committee) + 8 parents with parent_of links
  - Position terms: SPL, ASPL, 4 patrol leaders, scribe, adult leadership
  - "Patrol Leaders Council" (rule-based group) + "Fundraiser Crew" (manual group)
  - 3 locations; 11 events spanning T-35d .. T+30d with RSVPs, attendance on past
    events, and one PLC-only (audience-restricted) meeting
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.member import Member
    from app.models.tenant import Tenant

# ---------------------------------------------------------------------------
# Fixed dataset — names are stable so e2e tests can assert on them.
# ---------------------------------------------------------------------------

PATROLS: dict[str, list[str]] = {
    "Ravens": ["Aiden Brooks", "Ben Carter", "Caleb Diaz", "Dylan Evans", "Ethan Ford"],
    "Foxes": ["Felix Grant", "Gavin Hayes", "Henry Irwin", "Isaac James", "Jonah Kim"],
    "Hawks": ["Kyle Lopez", "Liam Moore", "Mason Nolan", "Noah Ortiz", "Owen Price"],
    "Otters": ["Peter Quinn", "Ryan Silva", "Sam Turner", "Tyler Underwood", "Wyatt Vance"],
}

# name -> position slug (seeded by seed_default_rbac)
ADULT_LEADERS: dict[str, str] = {
    "Sarah Rivers": "scoutmaster",
    "Mark Chen": "assistant-scoutmaster",
    "Priya Patel": "assistant-scoutmaster",
    "David Okafor": "committee-chair",
    "Laura Bennett": "treasurer",
    "Carlos Mendez": "advancement-chair",
    "Emily Stone": "membership-chair",
}

# Parents of the first 8 scouts (surnames match their child).
PARENTS: list[str] = [
    "Anna Brooks",
    "Brian Carter",
    "Maria Diaz",
    "James Evans",
    "Karen Ford",
    "Tom Grant",
    "Lisa Hayes",
    "Paul Irwin",
]

SCOUT_POSITIONS: dict[str, str] = {
    "Aiden Brooks": "senior-patrol-leader",
    "Ben Carter": "assistant-senior-patrol-leader",
    "Caleb Diaz": "patrol-leader",  # Ravens
    "Felix Grant": "patrol-leader",  # Foxes
    "Kyle Lopez": "patrol-leader",  # Hawks
    "Peter Quinn": "patrol-leader",  # Otters
    "Gavin Hayes": "scribe",
}

LOCATIONS: list[dict[str, str]] = [
    {"name": "First Methodist Church", "street1": "100 Main St", "city": "Springfield"},
    {"name": "Camp Wapiti", "street1": "4501 Scout Camp Rd", "city": "Pine Valley"},
    {"name": "Miller's Farm", "street1": "77 Orchard Lane", "city": "Springfield"},
]


def _split(full_name: str) -> tuple[str, str]:
    first, last = full_name.split(" ", 1)
    return first, last


def _email_for(full_name: str) -> str:
    return full_name.lower().replace(" ", ".") + "@example.com"


def teardown_tenant(session: Session, tenant_id: uuid.UUID) -> None:
    """Hard-delete every row belonging to the demo tenant, then the tenant itself.

    Unlike ``reset-tenant`` (which preserves Clerk-linked members for re-imports),
    the demo tenant is fully disposable — determinism beats preservation here.
    Platform Users/Identities are never touched.
    """
    from sqlalchemy import delete

    from app.models.event import Event, EventOrganizer, EventParticipant
    from app.models.event_audience import EventAudience
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

    # FK dependency order: children first.
    for model in (
        EventParticipant,
        EventOrganizer,
        EventAudience,
        Event,
        EventType,
        GroupRule,
        GroupMember,
        Group,
        MemberRelationship,
        MemberPositionAssignment,
        PositionFunctionalRole,
        FunctionalRolePermission,
        Position,
        FunctionalRole,
        Member,
        Location,
    ):
        session.execute(delete(model).where(model.tenant_id == tenant_id))
    session.execute(delete(Tenant).where(Tenant.id == tenant_id))
    session.flush()


def seed_demo_tenant(  # noqa: C901 — linear seed routine; splitting hurts readability
    session: Session,
    *,
    slug: str = "demo",
    troop_name: str = "Demo Troop 42",
    email: str | None = None,
) -> tuple[Tenant, Member, str, datetime]:
    """Provision + populate the demo tenant on *session* (flushed, not committed).

    Returns ``(tenant, founder_member, invite_token, invite_expires_at)`` — the same
    shape as ``provision_tenant``. Kept separate from ``main()`` so the test suite
    can run the full seed against the in-memory SQLite fixture.
    """
    from sqlalchemy import select

    from app.core.provisioning import get_or_create_member_position, provision_tenant
    from app.models.enums import (
        GroupType,
        MemberType,
        RelationshipType,
        RsvpStatus,
        RuleDimension,
        RuleLogic,
    )
    from app.models.event import Event, EventOrganizer, EventParticipant
    from app.models.event_audience import EventAudience
    from app.models.event_type import EventType
    from app.models.group import Group, GroupMember, GroupRule
    from app.models.location import Location
    from app.models.member import Member
    from app.models.rbac import MemberPositionAssignment, Position
    from app.models.relationship import MemberRelationship

    today = date.today()

    def dt(day_offset: int, hour: int, minute: int = 0) -> datetime:
        return datetime.combine(today + timedelta(days=day_offset), time(hour, minute), UTC)

    # -- Tenant + founder via the normal provisioning path -----------------------
    tenant, founder, invite_token, invite_expires = provision_tenant(
        session,
        name=troop_name,
        slug=slug,
        founder_first_name="Demo",
        founder_last_name="Admin",
        founder_email=email,
    )
    tid = tenant.id
    member_position = get_or_create_member_position(session, tid)

    def add_member(
        full_name: str,
        member_type: MemberType,
        *,
        email: str | None = None,
        dob: date | None = None,
    ) -> Member:
        first, last = _split(full_name)
        m = Member(
            tenant_id=tid,
            first_name=first,
            last_name=last,
            member_type=member_type,
            email=email,
            date_of_birth=dob,
        )
        session.add(m)
        session.flush()
        session.add(
            MemberPositionAssignment(tenant_id=tid, member_id=m.id, position_id=member_position.id)
        )
        return m

    def assign(member: Member, position_slug: str, *, start_offset_days: int = -180) -> None:
        position = session.scalar(
            select(Position).where(
                Position.tenant_id == tid,
                Position.slug == position_slug,
                Position.is_deleted.is_(False),
            )
        )
        if position is None:
            raise RuntimeError(f"Seeded position {position_slug!r} not found")
        session.add(
            MemberPositionAssignment(
                tenant_id=tid,
                member_id=member.id,
                position_id=position.id,
                start_date=today + timedelta(days=start_offset_days),
            )
        )

    # -- Members: scouts in patrols, adult leaders, parents -----------------------
    scouts: dict[str, Member] = {}
    for p_index, (patrol_name, scout_names) in enumerate(PATROLS.items()):
        group = Group(tenant_id=tid, name=patrol_name, group_type=GroupType.PATROL)
        session.add(group)
        session.flush()
        for s_index, full_name in enumerate(scout_names):
            # Deterministic ages 11-17, birthdays spread across the year.
            n = p_index * 5 + s_index
            dob = date(today.year - (11 + n % 7), (n * 3) % 12 + 1, (n * 7) % 28 + 1)
            scout = add_member(full_name, MemberType.SCOUT, dob=dob)
            scouts[full_name] = scout
            session.add(GroupMember(tenant_id=tid, group_id=group.id, member_id=scout.id))

    adults: dict[str, Member] = {}
    for full_name in [*ADULT_LEADERS, *PARENTS]:
        adults[full_name] = add_member(full_name, MemberType.ADULT, email=_email_for(full_name))

    for full_name, slug_ in ADULT_LEADERS.items():
        assign(adults[full_name], slug_)
    for full_name in PARENTS:
        assign(adults[full_name], "parent-guardian")
    for full_name, slug_ in SCOUT_POSITIONS.items():
        assign(scouts[full_name], slug_)

    # Parents ↔ children: surname match against the first 8 scouts.
    all_scouts = list(scouts.values())
    for parent_name in PARENTS:
        _, parent_last = _split(parent_name)
        for scout in all_scouts:
            if scout.last_name == parent_last:
                session.add(
                    MemberRelationship(
                        tenant_id=tid,
                        from_member_id=adults[parent_name].id,
                        to_member_id=scout.id,
                        relationship_type=RelationshipType.PARENT_OF,
                    )
                )

    # -- Custom groups -------------------------------------------------------------
    plc = Group(
        tenant_id=tid,
        name="Patrol Leaders Council",
        group_type=GroupType.CUSTOM,
        rule_logic=RuleLogic.AND,
        description="SPL, ASPL, patrol leaders, and the Scoutmaster",
    )
    session.add(plc)
    session.flush()
    plc_position_ids = [
        str(p.id)
        for p in session.scalars(
            select(Position).where(
                Position.tenant_id == tid,
                Position.slug.in_(
                    [
                        "senior-patrol-leader",
                        "assistant-senior-patrol-leader",
                        "patrol-leader",
                        "scoutmaster",
                    ]
                ),
            )
        )
    ]
    session.add(
        GroupRule(
            tenant_id=tid,
            group_id=plc.id,
            dimension=RuleDimension.POSITION,
            values=plc_position_ids,
        )
    )

    crew = Group(tenant_id=tid, name="Fundraiser Crew", group_type=GroupType.CUSTOM)
    session.add(crew)
    session.flush()
    for m in [
        scouts["Isaac James"],
        scouts["Liam Moore"],
        scouts["Ryan Silva"],
        adults["Laura Bennett"],
        adults["Tom Grant"],
    ]:
        session.add(GroupMember(tenant_id=tid, group_id=crew.id, member_id=m.id))

    # -- Locations -------------------------------------------------------------------
    locations: dict[str, Location] = {}
    for loc in LOCATIONS:
        row = Location(tenant_id=tid, **loc)
        session.add(row)
        locations[loc["name"]] = row
    session.flush()

    # -- Events ------------------------------------------------------------------------
    event_types = {
        et.name: et for et in session.scalars(select(EventType).where(EventType.tenant_id == tid))
    }

    def add_event(name: str, type_name: str, start: datetime, end: datetime, **kw: object) -> Event:
        e = Event(
            tenant_id=tid,
            name=name,
            event_type_id=event_types[type_name].id,
            scheduled_start=start,
            scheduled_end=end,
            **kw,  # type: ignore[arg-type]
        )
        session.add(e)
        session.flush()
        return e

    def participate(
        event: Event,
        member: Member,
        *,
        rsvp: RsvpStatus = RsvpStatus.NO_RESPONSE,
        signed_up: bool = True,
        attended: bool | None = None,
        driver: bool = False,
        seat_count: int | None = None,
    ) -> None:
        session.add(
            EventParticipant(
                tenant_id=tid,
                event_id=event.id,
                member_id=member.id,
                signed_up=signed_up,
                rsvp_status=rsvp,
                attended=attended,
                driver=driver,
                seat_count=seat_count,
                signed_up_at=dt(-40, 12),
            )
        )

    church = locations["First Methodist Church"]
    leaders_present = [adults["Sarah Rivers"], adults["Mark Chen"]]

    # Past weekly meetings with attendance taken.
    for week, offset in enumerate((-28, -21, -14, -7)):
        meeting = add_event(
            "Troop Meeting",
            "Meeting",
            dt(offset, 23),
            dt(offset, 23) + timedelta(minutes=90),
            location_id=church.id,
            attendance_taken=True,
        )
        for i, scout in enumerate(all_scouts):
            participate(meeting, scout, attended=(i + week) % 5 != 0)
        for adult in leaders_present:
            participate(meeting, adult, attended=True)

    # Past campout, attendance taken, activity metrics recorded.
    past_campout = add_event(
        "Fall Beach Campout",
        "Campout",
        dt(-35, 16),
        dt(-33, 15),
        location_id=locations["Camp Wapiti"].id,
        attendance_taken=True,
        camping_nights=2,
        cost_youth=Decimal("25.00"),
        cost_adult=Decimal("15.00"),
    )
    for scout in all_scouts[:12]:
        participate(past_campout, scout, rsvp=RsvpStatus.GOING, attended=True)
    for adult_name, seats in (("Sarah Rivers", 6), ("Mark Chen", 4), ("Anna Brooks", 3)):
        participate(
            past_campout,
            adults[adult_name],
            rsvp=RsvpStatus.GOING,
            attended=True,
            driver=True,
            seat_count=seats,
        )
    session.add(
        EventOrganizer(tenant_id=tid, event_id=past_campout.id, member_id=adults["Sarah Rivers"].id)
    )

    # Upcoming meeting with a spread of RSVPs.
    next_meeting = add_event(
        "Troop Meeting",
        "Meeting",
        dt(7, 23),
        dt(7, 23) + timedelta(minutes=90),
        location_id=church.id,
    )
    for i, scout in enumerate(all_scouts):
        if i < 10:
            participate(next_meeting, scout, rsvp=RsvpStatus.GOING)
        elif i < 13:
            participate(next_meeting, scout, rsvp=RsvpStatus.DECLINED, signed_up=False)
        # Remaining scouts: no participant row yet (never responded).

    # Upcoming campout with signup window + limits.
    winter_campout = add_event(
        "Winter Campout",
        "Campout",
        dt(14, 17),
        dt(16, 16),
        location_id=locations["Camp Wapiti"].id,
        signup_start=today - timedelta(days=14),
        signup_deadline=today + timedelta(days=10),
        signup_limit_scouts=20,
        signup_limit_adults=8,
        cost_youth=Decimal("30.00"),
        cost_adult=Decimal("18.00"),
        description="Cabin camping at Camp Wapiti. Bring winter gear.",
    )
    for scout in all_scouts[:8]:
        participate(winter_campout, scout, rsvp=RsvpStatus.GOING)
    for adult_name, seats in (("Sarah Rivers", 6), ("Priya Patel", 4)):
        participate(
            winter_campout,
            adults[adult_name],
            rsvp=RsvpStatus.GOING,
            driver=True,
            seat_count=seats,
        )
    session.add(
        EventOrganizer(
            tenant_id=tid, event_id=winter_campout.id, member_id=adults["Sarah Rivers"].id
        )
    )

    add_event(
        "Community Service Project",
        "Service Project",
        dt(10, 14),
        dt(10, 17),
        location_id=locations["Miller's Farm"].id,
        community_service_hours=Decimal("3.00"),
        description="Trail cleanup and fence painting.",
    )
    add_event(
        "Court of Honor",
        "Court of Honor",
        dt(30, 23),
        dt(30, 23) + timedelta(hours=2),
        location_id=church.id,
    )
    add_event(
        "Day Hike — Eagle Ridge",
        "Hike",
        dt(21, 13),
        dt(21, 21),
        hiking_miles=Decimal("5.00"),
        location_notes="Trailhead parking lot, Eagle Ridge",
    )

    # PLC-only meeting: audience-restricted to the rule-based PLC group.
    plc_meeting = add_event(
        "PLC Meeting",
        "Meeting",
        dt(3, 22, 30),
        dt(3, 23, 30),
        location_id=church.id,
        description="Monthly Patrol Leaders Council planning meeting.",
    )
    session.add(EventAudience(tenant_id=tid, event_id=plc_meeting.id, group_id=plc.id))

    session.flush()
    return tenant, founder, invite_token, invite_expires


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--slug", default="demo", help="Tenant slug (default: demo)")
    parser.add_argument("--troop-name", default="Demo Troop 42", help="Tenant display name")
    parser.add_argument(
        "--email",
        default=None,
        help="Link the founding Demo Admin to the signed-in User with this verified email",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Tear down an existing demo tenant (all its rows) and re-seed from scratch",
    )
    args = parser.parse_args()

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models import Base  # noqa: F401 — registers all tables
    from app.models.tenant import Tenant

    session = SessionLocal()
    today = date.today()
    try:
        existing = session.scalar(
            select(Tenant).where(Tenant.slug == args.slug, Tenant.is_deleted.is_(False))
        )
        if existing is not None:
            if not args.reset:
                sys.exit(
                    f"Error: tenant {args.slug!r} already exists (id={existing.id}). "
                    "Re-run with --reset to tear it down and re-seed."
                )
            print(f"Tearing down existing tenant {args.slug!r} ({existing.id}) …")
            teardown_tenant(session, existing.id)

        tenant, founder, invite_token, invite_expires = seed_demo_tenant(
            session, slug=args.slug, troop_name=args.troop_name, email=args.email
        )
        session.commit()

        scout_count = sum(len(names) for names in PATROLS.values())
        adult_count = len(ADULT_LEADERS) + len(PARENTS) + 1  # + founder
        print()
        print(f"Seeded tenant {tenant.name!r}")
        print(f"  Tenant ID : {tenant.id}")
        print(f"  Slug      : {tenant.slug}")
        print(f"  Members   : {scout_count} scouts + {adult_count} adults")
        print(f"  Events    : 11 ({today - timedelta(days=35)} .. {today + timedelta(days=30)})")
        if founder.user_id is not None:
            print(f"  Admin     : Demo Admin — linked to {args.email}  ✓ ready to use")
        else:
            print("  Admin     : Demo Admin — UNCLAIMED")
            if args.email:
                print(
                    f"    No verified User row for {args.email!r} found. Sign into the app "
                    "first, then re-run with --reset, or claim with the token below."
                )
            print(f"    Claim token (valid until {invite_expires:%Y-%m-%d}): {invite_token}")
        print()
        print("Next steps:")
        print(f"  1. apps/web/.env.local → NEXT_PUBLIC_TENANT_ID={tenant.id}")
        print(f"  2. Open http://{tenant.slug}.localhost:3000 (run ./start.sh first)")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
