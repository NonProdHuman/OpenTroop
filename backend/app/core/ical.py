"""RFC 5545 (iCalendar) feed generation for a member's personal calendar.

Produces the ``.ics`` body served at ``GET /calendar/{token}.ics``. The feed
contains exactly the events a member may see (``event_visibility``) minus the
ones they've **declined** — so a member's calendar app stays in sync with both
patrol-scoped visibility and their own RSVPs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.event_visibility import visibility_clause
from app.core.groups import member_group_ids
from app.models.enums import RsvpStatus
from app.models.event import Event, EventParticipant
from app.models.member import Member

_PRODID = "-//OpenTroop//Calendar//EN"


def _escape(value: str) -> str:
    """Escape a TEXT value per RFC 5545 §3.3.11."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold a content line to <=75 octets, continuation lines led by a space."""
    if len(line.encode("utf-8")) <= 75:
        return line
    out: list[bytes] = []
    current = b""
    for ch in line:
        encoded = ch.encode("utf-8")
        # Leave room so a continuation (leading space) stays within 75 octets.
        if len(current) + len(encoded) > 74:
            out.append(current)
            current = b" " + encoded
        else:
            current += encoded
    out.append(current)
    return "\r\n".join(chunk.decode("utf-8") for chunk in out)


def _dt(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _date(value: datetime) -> str:
    return value.strftime("%Y%m%d")


def _vevent(event: Event, dtstamp: datetime) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{event.id}@opentroop",
        f"DTSTAMP:{_dt(dtstamp)}",
    ]
    if event.all_day:
        lines.append(f"DTSTART;VALUE=DATE:{_date(event.scheduled_start)}")
        lines.append(f"DTEND;VALUE=DATE:{_date(event.scheduled_end)}")
    else:
        lines.append(f"DTSTART:{_dt(event.scheduled_start)}")
        lines.append(f"DTEND:{_dt(event.scheduled_end)}")
    lines.append(f"SUMMARY:{_escape(event.name)}")

    location = event.location.name if event.location is not None else event.location_notes
    if location:
        lines.append(f"LOCATION:{_escape(location)}")
    if event.description:
        lines.append(f"DESCRIPTION:{_escape(event.description)}")
    lines.append("END:VEVENT")
    return lines


def member_calendar_ics(member: Member, session: Session, *, calendar_name: str) -> str:
    """Build the iCalendar document for *member* — visible, non-declined events."""
    groups = member_group_ids(member.id, session)
    events = session.scalars(
        select(Event)
        .where(
            Event.tenant_id == member.tenant_id,
            Event.is_deleted.is_(False),
            visibility_clause(groups, member.tenant_id),
        )
        .order_by(Event.scheduled_start)
    ).all()

    declined = set(
        session.scalars(
            select(EventParticipant.event_id).where(
                EventParticipant.member_id == member.id,
                EventParticipant.rsvp_status == RsvpStatus.DECLINED,
                EventParticipant.is_deleted.is_(False),
            )
        ).all()
    )

    now = datetime.now(UTC)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{_PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(calendar_name)}",
    ]
    for event in events:
        if event.id in declined:
            continue
        lines.extend(_vevent(event, now))
    lines.append("END:VCALENDAR")

    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
