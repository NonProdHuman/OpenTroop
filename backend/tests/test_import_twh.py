"""Tests for the TroopWebHost XML importer."""

from datetime import UTC, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.importers.twh import TwhImporter, _parse_date, _parse_datetime, resolve_source_tz
from app.models.enums import (
    GroupType,
    MemberStatus,
    MemberType,
    RelationshipType,
    RsvpStatus,
    SwimClassification,
)
from app.models.event import Event, EventParticipant
from app.models.event_type import EventType
from app.models.group import Group, GroupMember
from app.models.location import Location
from app.models.member import Member
from app.models.relationship import MemberRelationship


def _patrol_of(session: Session, member: Member) -> Group | None:
    """Return the PATROL-type group a member belongs to (or None)."""
    return (
        session.query(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .filter(
            GroupMember.member_id == member.id,
            GroupMember.is_deleted.is_(False),
            Group.group_type == GroupType.PATROL,
        )
        .first()
    )


_FIXTURE = Path(__file__).parent / "fixtures" / "sample_twh_minimal.xml"
_TENANT = __import__("uuid").UUID("10000000-0000-0000-0000-000000000001")


@pytest.fixture
def result_and_session(db_session: Session):
    """Run the importer once against the minimal fixture, return (result, session)."""
    root = ET.parse(_FIXTURE).getroot()  # noqa: S314 — committed fixture, not web input
    result = TwhImporter(db_session, _TENANT).run(root)
    return result, db_session


# ---------------------------------------------------------------------------
# Helper parsing functions
# ---------------------------------------------------------------------------


def test_parse_date_twh_format() -> None:
    d = _parse_date("3/15/2010 12:00:00 AM")
    assert d is not None
    assert d.year == 2010
    assert d.month == 3
    assert d.day == 15


def test_parse_date_empty() -> None:
    assert _parse_date("") is None
    assert _parse_date("   ") is None


def test_parse_datetime_pm() -> None:
    # No source tz → interpreted as UTC (literal wall-clock preserved).
    dt = _parse_datetime("9/10/2025 7:00:00 PM")
    assert dt is not None
    assert dt.hour == 19
    assert dt.minute == 0
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timedelta(0)


def test_parse_datetime_converts_source_tz_to_utc() -> None:
    # 7PM in America/New_York during September is EDT (UTC-4) → 23:00 UTC.
    dt = _parse_datetime("9/10/2025 7:00:00 PM", ZoneInfo("America/New_York"))
    assert dt is not None
    assert dt.hour == 23
    assert dt.utcoffset() == timedelta(0)


def test_parse_datetime_empty() -> None:
    assert _parse_datetime("") is None


def test_resolve_source_tz_valid() -> None:
    assert resolve_source_tz("UTC") == ZoneInfo("UTC")
    assert resolve_source_tz("America/Chicago") == ZoneInfo("America/Chicago")


def test_resolve_source_tz_invalid() -> None:
    with pytest.raises(ValueError, match="Unknown timezone"):
        resolve_source_tz("Not/AZone")


# ---------------------------------------------------------------------------
# Patrols
# ---------------------------------------------------------------------------


def test_patrols_imported(result_and_session) -> None:
    result, session = result_and_session
    assert result.patrols == 2
    patrols = session.query(Group).filter_by(tenant_id=_TENANT, group_type=GroupType.PATROL).all()
    names = {p.name for p in patrols}
    assert names == {"Eagle Patrol", "Hawk Patrol"}


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


def test_member_count(result_and_session) -> None:
    result, session = result_and_session
    assert result.members == 5
    members = session.query(Member).filter_by(tenant_id=_TENANT).all()
    assert len(members) == 5


def test_scout_fields(result_and_session) -> None:
    _, session = result_and_session
    alice = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Alice").one()
    assert alice.last_name == "Scout"
    assert alice.middle_name == "J"
    assert alice.nickname == "Al"
    assert alice.bsa_id == "12345678"
    assert alice.member_type == MemberType.SCOUT
    assert alice.membership_status == MemberStatus.ACTIVE
    assert alice.swim_classification == SwimClassification.SWIMMER
    assert alice.date_of_birth is not None
    assert alice.date_of_birth.year == 2010
    assert alice.email == "alice@example.com"
    assert alice.phone == "555-111-2222"
    assert alice.city == "Springfield"
    assert alice.state == "IL"


def test_scout_patrol_assignment(result_and_session) -> None:
    _, session = result_and_session
    alice = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Alice").one()
    patrol = _patrol_of(session, alice)
    assert patrol is not None
    assert patrol.name == "Eagle Patrol"


def test_scout_medical_dates(result_and_session) -> None:
    _, session = result_and_session
    alice = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Alice").one()
    assert alice.medical_form_ab_date is not None
    assert alice.medical_form_ab_date.year == 2025
    assert alice.medical_form_c_date is not None
    assert alice.swim_date is not None
    assert alice.swim_date.year == 2024


def test_scout_emergency_contacts(result_and_session) -> None:
    _, session = result_and_session
    alice = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Alice").one()
    assert alice.emergency_contact_1_name == "Bob Scout"
    assert alice.emergency_contact_1_phone == "555-333-4444"
    assert alice.emergency_contact_2_name == "Carol Scout"


def test_scout_oa_fields(result_and_session) -> None:
    _, session = result_and_session
    alice = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Alice").one()
    assert alice.oa_member is True
    assert alice.oa_active is True
    assert alice.oa_election_date is not None
    assert alice.oa_election_date.month == 3
    assert alice.oa_ordeal_date is not None
    assert alice.oa_vigil_name == "Running River"


def test_non_swimmer_classification(result_and_session) -> None:
    _, session = result_and_session
    dave = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Dave").one()
    assert dave.swim_classification == SwimClassification.NONSWIMMER
    assert dave.member_type == MemberType.SCOUT
    # Patrol 2
    patrol = _patrol_of(session, dave)
    assert patrol is not None
    assert patrol.name == "Hawk Patrol"


def test_adult_member(result_and_session) -> None:
    _, session = result_and_session
    bob = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Bob").one()
    assert bob.member_type == MemberType.ADULT
    assert bob.membership_status == MemberStatus.ACTIVE
    assert _patrol_of(session, bob) is None


def test_adult_no_bsa_id(result_and_session) -> None:
    _, session = result_and_session
    eve = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Eve").one()
    assert eve.bsa_id is None
    # Unknown swim level defaults to NONSWIMMER
    assert eve.swim_classification == SwimClassification.NONSWIMMER


def test_alumni_status(result_and_session) -> None:
    _, session = result_and_session
    grace = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Grace").one()
    assert grace.membership_status == MemberStatus.ALUMNI
    assert grace.troop_membership_end_date is not None
    assert grace.troop_membership_end_date.year == 2023


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


def test_relationship_count_and_warnings(result_and_session) -> None:
    result, session = result_and_session
    rels = session.query(MemberRelationship).filter_by(tenant_id=_TENANT).all()
    assert len(rels) == 2  # third relationship references unknown person → skipped
    assert result.skipped >= 1
    assert any("999" in w for w in result.warnings)


def test_relationship_direction(result_and_session) -> None:
    _, session = result_and_session
    alice = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Alice").one()
    bob = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Bob").one()
    rel = (
        session.query(MemberRelationship)
        .filter_by(tenant_id=_TENANT, from_member_id=bob.id, to_member_id=alice.id)
        .one()
    )
    assert rel.relationship_type == RelationshipType.PARENT_OF


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


def test_location_count(result_and_session) -> None:
    result, session = result_and_session
    assert result.locations == 2  # disabled location skipped
    locs = session.query(Location).filter_by(tenant_id=_TENANT).all()
    names = {loc.name for loc in locs}
    assert "Camp Eagle" in names
    assert "Old Meeting Hall (Closed)" not in names


def test_location_fields(result_and_session) -> None:
    _, session = result_and_session
    camp = session.query(Location).filter_by(tenant_id=_TENANT, name="Camp Eagle").one()
    assert camp.street1 == "456 Forest Rd"
    assert camp.city == "Shelbyville"
    assert camp.state == "IL"
    assert camp.postal_code == "62565"
    assert camp.phone == "555-777-8888"
    assert camp.website_url == "https://campeagle.example.com"
    assert camp.directions == "Take I-55 north"
    assert camp.description == "Beautiful wilderness camp"
    assert camp.distance_miles == 25.0


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


def test_event_type_count(result_and_session) -> None:
    result, session = result_and_session
    assert result.event_types == 3
    ets = session.query(EventType).filter_by(tenant_id=_TENANT).all()
    assert len(ets) == 3


def test_meeting_event_type_flags(result_and_session) -> None:
    _, session = result_and_session
    et = session.query(EventType).filter_by(tenant_id=_TENANT, name="Meeting").one()
    assert et.is_active is True
    assert et.is_system is False
    assert et.allow_signups is False
    assert et.tracks_camping_nights is False
    assert et.tracks_service_hours is False
    assert et.tracks_mileage is False
    assert et.require_permission_slip is False
    assert et.is_online is False
    assert et.color is None


def test_campout_event_type_flags(result_and_session) -> None:
    _, session = result_and_session
    et = session.query(EventType).filter_by(tenant_id=_TENANT, name="Campout").one()
    assert et.tracks_camping_nights is True
    assert et.tracks_service_hours is True
    assert et.tracks_mileage is True
    assert et.allow_signups is True
    assert et.require_permission_slip is True
    assert et.color == "#2ECC71"


def test_disabled_event_type_imported_inactive(result_and_session) -> None:
    _, session = result_and_session
    et = session.query(EventType).filter_by(tenant_id=_TENANT, name="Old Category").one()
    assert et.is_active is False


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def test_event_count(result_and_session) -> None:
    result, session = result_and_session
    assert result.events == 3  # event 99 (unknown type) skipped
    assert result.skipped >= 1
    assert any("999" in w for w in result.warnings)


def test_meeting_event_fields(result_and_session) -> None:
    _, session = result_and_session
    ev = session.query(Event).filter_by(tenant_id=_TENANT, name="Weekly Meeting").one()
    assert ev.attendance_taken is True
    assert ev.tour_permit_submitted is None  # empty string → None
    assert ev.description == "Monthly planning meeting"
    assert ev.all_day is False
    # Default importer uses UTC, so the wall-clock hour is preserved.
    assert ev.scheduled_start.hour == 19
    assert ev.scheduled_start.month == 9


def test_import_converts_event_times_from_source_tz(db_session: Session) -> None:
    """Importing with a source timezone stores event times converted to UTC."""
    other_tenant = __import__("uuid").UUID("10000000-0000-0000-0000-0000000000ff")
    root = ET.parse(_FIXTURE).getroot()  # noqa: S314 — committed fixture, not web input
    TwhImporter(db_session, other_tenant, source_tz=ZoneInfo("America/New_York")).run(root)

    ev = session_event(db_session, other_tenant, "Weekly Meeting")
    # 7PM EDT (UTC-4 in September) → 23:00 UTC, stored timezone-aware.
    assert ev.scheduled_start.replace(tzinfo=UTC).hour == 23


def session_event(session: Session, tenant, name: str) -> Event:
    return session.query(Event).filter_by(tenant_id=tenant, name=name).one()


def test_meeting_event_location(result_and_session) -> None:
    _, session = result_and_session
    ev = session.query(Event).filter_by(tenant_id=_TENANT, name="Weekly Meeting").one()
    assert ev.location_id is not None
    loc = session.get(Location, ev.location_id)
    assert loc is not None
    assert loc.name == "Community Center"


def test_campout_event_fields(result_and_session) -> None:
    _, session = result_and_session
    ev = session.query(Event).filter_by(tenant_id=_TENANT, name="Summer Campout").one()
    assert ev.tour_permit_submitted is True
    assert ev.signup_limit_scouts == 20
    assert ev.signup_limit_adults == 5
    assert ev.cost_youth is not None
    assert float(ev.cost_youth) == 75.0
    assert ev.departure_location == "Church parking lot"
    assert ev.hiking_miles is not None
    assert float(ev.hiking_miles) == 5.0
    assert ev.signup_deadline is not None
    assert ev.signup_deadline.month == 7
    assert ev.agenda is not None


def test_all_day_event(result_and_session) -> None:
    _, session = result_and_session
    ev = session.query(Event).filter_by(tenant_id=_TENANT, name="Court of Honor").one()
    assert ev.all_day is True
    assert ev.tour_permit_submitted is False  # "N" → False


def test_linked_event_resolved(result_and_session) -> None:
    _, session = result_and_session
    meeting = session.query(Event).filter_by(tenant_id=_TENANT, name="Weekly Meeting").one()
    coh = session.query(Event).filter_by(tenant_id=_TENANT, name="Court of Honor").one()
    assert coh.linked_event_id == meeting.id


# ---------------------------------------------------------------------------
# Event participants
# ---------------------------------------------------------------------------


def test_participant_count(result_and_session) -> None:
    result, session = result_and_session
    assert result.participants == 3  # participant 99 (unknown person) skipped
    eps = session.query(EventParticipant).filter_by(tenant_id=_TENANT).all()
    assert len(eps) == 3


def test_participant_attended(result_and_session) -> None:
    _, session = result_and_session
    alice = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Alice").one()
    meeting = session.query(Event).filter_by(tenant_id=_TENANT, name="Weekly Meeting").one()
    ep = (
        session.query(EventParticipant)
        .filter_by(tenant_id=_TENANT, event_id=meeting.id, member_id=alice.id)
        .one()
    )
    assert ep.signed_up is True
    assert ep.attended is True
    assert ep.rsvp_status is RsvpStatus.GOING


def test_participant_rsvp_status_mapping(db_session: Session) -> None:
    """TWH Sign_Up_Flag maps onto rsvp_status: N→declined, ?→no_response, Y→going."""
    xml = """
    <root>
      <Event_Type><i>1</i><Event_Type_Name>Meeting</Event_Type_Name></Event_Type>
      <Person><i>10</i><Name_First>Dee</Name_First><Name_Last>Clined</Name_Last></Person>
      <Person><i>11</i><Name_First>May</Name_First><Name_Last>Be</Name_Last></Person>
      <Event>
        <i>100</i><Event_Type_ID>1</Event_Type_ID><Event_Name>Meet</Event_Name>
        <Scheduled_Start>7/1/2026 9:00:00 AM</Scheduled_Start>
        <Scheduled_End>7/1/2026 11:00:00 AM</Scheduled_End>
      </Event>
      <Event_Participant>
        <Event_ID>100</Event_ID><Person_ID>10</Person_ID><Sign_Up_Flag>N</Sign_Up_Flag>
      </Event_Participant>
      <Event_Participant>
        <Event_ID>100</Event_ID><Person_ID>11</Person_ID><Sign_Up_Flag>?</Sign_Up_Flag>
      </Event_Participant>
    </root>
    """
    root = ET.fromstring(xml)  # noqa: S314 — test-local literal, not web input
    TwhImporter(db_session, _TENANT).run(root)

    declined = db_session.query(Member).filter_by(first_name="Dee").one()
    maybe = db_session.query(Member).filter_by(first_name="May").one()
    ep_declined = db_session.query(EventParticipant).filter_by(member_id=declined.id).one()
    ep_no_response = db_session.query(EventParticipant).filter_by(member_id=maybe.id).one()

    assert ep_declined.rsvp_status is RsvpStatus.DECLINED
    assert ep_declined.signed_up is False
    assert ep_no_response.rsvp_status is RsvpStatus.NO_RESPONSE
    assert ep_no_response.signed_up is True


def test_participant_unknown_attendance(result_and_session) -> None:
    _, session = result_and_session
    alice = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Alice").one()
    campout = session.query(Event).filter_by(tenant_id=_TENANT, name="Summer Campout").one()
    ep = (
        session.query(EventParticipant)
        .filter_by(tenant_id=_TENANT, event_id=campout.id, member_id=alice.id)
        .one()
    )
    assert ep.attended is None  # '?' → None
    assert ep.permission_slip_submitted is True
    assert ep.camping_nights_override == 2
    assert ep.comment == "Needs vegetarian meal"
    assert ep.signed_up_at is not None
    assert ep.signed_up_at.month == 6


def test_participant_driver(result_and_session) -> None:
    _, session = result_and_session
    bob = session.query(Member).filter_by(tenant_id=_TENANT, first_name="Bob").one()
    campout = session.query(Event).filter_by(tenant_id=_TENANT, name="Summer Campout").one()
    ep = (
        session.query(EventParticipant)
        .filter_by(tenant_id=_TENANT, event_id=campout.id, member_id=bob.id)
        .one()
    )
    assert ep.driver is True
    assert ep.seat_count == 4
    assert ep.attended is None  # '?' → None
