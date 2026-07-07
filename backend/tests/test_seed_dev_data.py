"""Tests for the seed-dev-data CLI's core seeding routine (GH-171).

Runs the full demo seed against the in-memory SQLite fixture — the same data
path the CLI uses against Postgres — so the deterministic dataset the
Playwright smoke tests rely on is verified in CI.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.groups import resolve_group_members
from app.core.tenant_context import tenant_scope
from app.models.enums import GroupType, MemberType
from app.models.event import Event
from app.models.event_audience import EventAudience
from app.models.group import Group
from app.models.location import Location
from app.models.member import Member
from app.models.rbac import MemberPositionAssignment, Position
from app.models.relationship import MemberRelationship
from scripts.seed_dev_data import (
    PATROLS,
    build_manifest,
    seed_demo_tenant,
    teardown_tenant,
)


def _count(db: Session, stmt: object) -> int:
    return db.scalar(stmt) or 0  # type: ignore[arg-type]


def test_seed_demo_tenant_populates_troop(db_session: Session) -> None:
    tenant, founder, token, expires = seed_demo_tenant(db_session)
    db_session.commit()
    tid = tenant.id

    assert tenant.slug == "demo"
    assert founder.user_id is None  # no --email → unclaimed
    assert token

    scouts = _count(
        db_session,
        select(func.count())
        .select_from(Member)
        .where(Member.tenant_id == tid, Member.member_type == MemberType.SCOUT),
    )
    adults = _count(
        db_session,
        select(func.count())
        .select_from(Member)
        .where(Member.tenant_id == tid, Member.member_type == MemberType.ADULT),
    )
    assert scouts == sum(len(names) for names in PATROLS.values()) == 20
    assert adults == 17  # 7 leaders + 8 parents + founder + read-only Demo Viewer (GH-246)

    patrols = _count(
        db_session,
        select(func.count())
        .select_from(Group)
        .where(Group.tenant_id == tid, Group.group_type == GroupType.PATROL),
    )
    assert patrols == 4

    events = _count(
        db_session, select(func.count()).select_from(Event).where(Event.tenant_id == tid)
    )
    assert events == 11

    # One audience-restricted event (the PLC meeting).
    audiences = _count(
        db_session,
        select(func.count()).select_from(EventAudience).where(EventAudience.tenant_id == tid),
    )
    assert audiences == 1

    # Each of the 8 parents links to exactly one scout by surname.
    relationships = _count(
        db_session,
        select(func.count())
        .select_from(MemberRelationship)
        .where(MemberRelationship.tenant_id == tid),
    )
    assert relationships == 8

    # Every member holds the baseline Member position (invariant from
    # docs/spec/baseline-member-access.md) — except the read-only Demo Viewer
    # (GH-246), which holds only the viewer position by design (no baseline role,
    # so it never carries photo:upload).
    member_pos = db_session.scalar(
        select(Position).where(Position.tenant_id == tid, Position.slug == "member")
    )
    assert member_pos is not None
    baseline_assignments = _count(
        db_session,
        select(func.count())
        .select_from(MemberPositionAssignment)
        .where(
            MemberPositionAssignment.tenant_id == tid,
            MemberPositionAssignment.position_id == member_pos.id,
        ),
    )
    assert baseline_assignments == scouts + adults - 1  # all but the Demo Viewer


def test_plc_group_resolves_leadership(db_session: Session) -> None:
    tenant, *_ = seed_demo_tenant(db_session)
    db_session.commit()

    plc = db_session.scalar(
        select(Group).where(Group.tenant_id == tenant.id, Group.name == "Patrol Leaders Council")
    )
    assert plc is not None
    with tenant_scope(tenant.id):
        resolved = resolve_group_members(plc.id, db_session)

    names = {
        f"{m.first_name} {m.last_name}"
        for m in db_session.scalars(select(Member).where(Member.id.in_(resolved)))
    }
    # SPL, ASPL, 4 patrol leaders, and the Scoutmaster — via the position rule.
    assert names == {
        "Aiden Brooks",
        "Ben Carter",
        "Caleb Diaz",
        "Felix Grant",
        "Kyle Lopez",
        "Peter Quinn",
        "Sarah Rivers",
    }


def test_manifest_counts_match_seeded_data(db_session: Session) -> None:
    """The e2e manifest (GH-245) is the single source of truth — its counts must
    equal what the seed actually wrote, so specs can't assert on stale numbers."""
    tenant, *_ = seed_demo_tenant(db_session)
    db_session.commit()

    manifest = build_manifest(db_session, tenant)
    counts = manifest["counts"]
    assert isinstance(counts, dict)
    assert counts["scouts"] == 20
    assert counts["adults"] == 17  # includes the read-only Demo Viewer (GH-246)
    assert counts["events"] == 11
    assert counts["locations"] == 3
    assert counts["groups"] == 6  # 4 patrols + PLC + Fundraiser Crew

    tenant_info = manifest["tenant"]
    assert isinstance(tenant_info, dict)
    assert tenant_info["slug"] == "demo"
    assert tenant_info["id"] == str(tenant.id)


def test_manifest_named_rows_exist(db_session: Session) -> None:
    """Every member / event / location / group the manifest names must actually be
    seeded — this is the drift guard: renaming a seeded row fails here, loudly."""
    tenant, *_ = seed_demo_tenant(db_session)
    db_session.commit()
    tid = tenant.id
    manifest = build_manifest(db_session, tenant)

    def exists(model: type, name: str) -> bool:
        return (
            db_session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.tenant_id == tid, model.name == name)  # type: ignore[attr-defined]
            )
            or 0
        ) > 0

    members = manifest["members"]
    events = manifest["events"]
    locations = manifest["locations"]
    groups = manifest["groups"]
    assert isinstance(members, dict)
    assert isinstance(events, dict)
    assert isinstance(locations, dict)
    assert isinstance(groups, dict)

    for full_name in set(members.values()):
        first, last = full_name.split(" ", 1)
        assert (
            db_session.scalar(
                select(func.count())
                .select_from(Member)
                .where(
                    Member.tenant_id == tid,
                    Member.first_name == first,
                    Member.last_name == last,
                )
            )
            or 0
        ) > 0, f"manifest member {full_name!r} not seeded"

    for title in set(events.values()):
        assert exists(Event, title), f"manifest event {title!r} not seeded"
    for loc_name in set(locations.values()):
        assert exists(Location, loc_name), f"manifest location {loc_name!r} not seeded"
    for group_name in set(groups.values()):
        assert exists(Group, group_name), f"manifest group {group_name!r} not seeded"


def test_teardown_then_reseed_is_clean(db_session: Session) -> None:
    tenant, *_ = seed_demo_tenant(db_session)
    db_session.commit()
    teardown_tenant(db_session, tenant.id)
    db_session.commit()

    remaining = _count(
        db_session,
        select(func.count()).select_from(Member).where(Member.tenant_id == tenant.id),
    )
    assert remaining == 0

    tenant2, *_ = seed_demo_tenant(db_session)
    db_session.commit()
    assert tenant2.slug == "demo"
    assert tenant2.id != tenant.id
    events = _count(
        db_session, select(func.count()).select_from(Event).where(Event.tenant_id == tenant2.id)
    )
    assert events == 11
