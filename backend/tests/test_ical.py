"""Unit tests for the iCal feed builder."""

import uuid
from datetime import UTC, datetime

from app.core.ical import member_calendar_ics
from app.models.enums import MemberType, RsvpStatus
from app.models.event import Event, EventParticipant
from app.models.member import Member

_TENANT = uuid.UUID("10000000-0000-0000-0000-000000000001")


def _member(session) -> Member:
    m = Member(tenant_id=_TENANT, first_name="Sam", last_name="Scout", member_type=MemberType.SCOUT)
    session.add(m)
    session.flush()
    return m


def _event(session, name: str, *, all_day: bool = False) -> Event:
    e = Event(
        tenant_id=_TENANT,
        name=name,
        event_type_id=uuid.uuid4(),
        all_day=all_day,
        scheduled_start=datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
        scheduled_end=datetime(2026, 7, 1, 11, 0, tzinfo=UTC),
    )
    session.add(e)
    session.flush()
    return e


def test_feed_contains_visible_event(db_session) -> None:
    member = _member(db_session)
    _event(db_session, "Troop Meeting")
    ics = member_calendar_ics(member, db_session, calendar_name="My Calendar")

    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.strip().endswith("END:VCALENDAR")
    assert "SUMMARY:Troop Meeting" in ics
    assert "X-WR-CALNAME:My Calendar" in ics


def test_feed_excludes_declined_event(db_session) -> None:
    member = _member(db_session)
    keep = _event(db_session, "Keep Me")
    skip = _event(db_session, "Skip Me")
    db_session.add(
        EventParticipant(
            tenant_id=_TENANT,
            event_id=skip.id,
            member_id=member.id,
            rsvp_status=RsvpStatus.DECLINED,
        )
    )
    db_session.flush()

    ics = member_calendar_ics(member, db_session, calendar_name="Cal")
    assert "Keep Me" in ics
    assert "Skip Me" not in ics
    assert f"UID:{keep.id}@opentroop" in ics


def test_all_day_event_uses_date_value(db_session) -> None:
    member = _member(db_session)
    _event(db_session, "Campout", all_day=True)
    ics = member_calendar_ics(member, db_session, calendar_name="Cal")
    assert "DTSTART;VALUE=DATE:20260701" in ics


def test_text_escaping(db_session) -> None:
    member = _member(db_session)
    _event(db_session, "Hike; bring water, food")
    ics = member_calendar_ics(member, db_session, calendar_name="Cal")
    assert "SUMMARY:Hike\\; bring water\\, food" in ics
