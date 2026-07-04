"""Event-triggered email notifications (GH-86).

Recipient resolution reuses the same primitives as the rest of the app: event
audiences resolve through :func:`resolve_group_members`, and parent expansion
walks the ``parent_of`` / ``guardian_of`` edges via
:mod:`app.core.relationships`. Sends go through :class:`NotificationService`
directly — event volumes are tens of emails, fine on-request; when the async
send queue lands (GH-78) only the transport in the routers changes.

RSVP reminders need scheduled execution, which doesn't exist yet — they are
deliberately absent here (tracked separately alongside digests).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.groups import resolve_group_members
from app.core.notifications import EmailMessage

# Deliberate reuse: relationships.py is the single home of the family-edge
# rules (see its module docstring); these helpers are internal to the app core.
from app.core.relationships import _parents_of, children_of
from app.models.enums import MemberType
from app.models.event import Event, EventParticipant
from app.models.event_audience import EventAudience
from app.models.member import Member


def _format_when(start: datetime, all_day: bool) -> str:
    if all_day:
        return start.strftime("%A, %B %d, %Y")
    return start.strftime("%A, %B %d, %Y at %I:%M %p %Z").rstrip()


def _emailable(members: list[Member]) -> list[Member]:
    """Members who can actually receive email, deduplicated by address."""
    seen: set[str] = set()
    out: list[Member] = []
    for m in members:
        if not m.email or m.email_opt_out or m.email_bounced or m.is_deleted:
            continue
        addr = m.email.lower()
        if addr in seen:
            continue
        seen.add(addr)
        out.append(m)
    return out


def _visible_member_ids(event: Event, session: Session) -> set[uuid.UUID]:
    """The members an event is visible to: its audiences, or the whole troop."""
    audience_group_ids = session.scalars(
        select(EventAudience.group_id).where(
            EventAudience.event_id == event.id,
            EventAudience.is_deleted.is_(False),
        )
    ).all()
    if audience_group_ids:
        ids: set[uuid.UUID] = set()
        for group_id in audience_group_ids:
            ids |= resolve_group_members(group_id, session)
        return ids
    return set(session.scalars(select(Member.id).where(Member.is_deleted.is_(False))).all())


def cancellation_recipients(event: Event, session: Session) -> list[Member]:
    """Everyone who could see the event, plus the parents of scouts among them."""
    ids = _visible_member_ids(event, session)
    scout_ids = set(
        session.scalars(
            select(Member.id).where(Member.id.in_(ids), Member.member_type == MemberType.SCOUT)
        ).all()
    )
    ids |= _parents_of(scout_ids, session)
    members = list(session.scalars(select(Member).where(Member.id.in_(ids))).all())
    return _emailable(members)


def permission_request_recipients(
    event: Event, session: Session
) -> dict[uuid.UUID, tuple[Member, list[Member]]]:
    """Parents to ask for permission, mapped to the scouts they must sign for.

    Covers scout participants of the event who have neither a paper slip
    (``permission_slip_submitted``) nor electronic permission recorded.
    """
    pending_scout_ids = set(
        session.scalars(
            select(EventParticipant.member_id)
            .join(Member, Member.id == EventParticipant.member_id)
            .where(
                EventParticipant.event_id == event.id,
                EventParticipant.is_deleted.is_(False),
                EventParticipant.permission_slip_submitted.is_(False),
                EventParticipant.electronic_permission.is_(False),
                Member.member_type == MemberType.SCOUT,
            )
        ).all()
    )
    if not pending_scout_ids:
        return {}

    scouts = {
        m.id: m
        for m in session.scalars(select(Member).where(Member.id.in_(pending_scout_ids))).all()
    }
    parent_ids = _parents_of(pending_scout_ids, session)
    parents = _emailable(
        list(session.scalars(select(Member).where(Member.id.in_(parent_ids))).all())
    )

    result: dict[uuid.UUID, tuple[Member, list[Member]]] = {}
    for parent in parents:
        their_pending = [scouts[c] for c in children_of(parent.id, session) if c in scouts]
        if their_pending:
            result[parent.id] = (parent, their_pending)
    return result


def build_cancellation_email(
    *, to: str, first_name: str, event_name: str, when: str, tenant_name: str
) -> EmailMessage:
    subject = f"CANCELLED: {event_name} — {tenant_name}"
    text_body = (
        f"Hi {first_name},\n\n"
        f"{event_name} ({when}) has been cancelled.\n\n"
        f"Please check the {tenant_name} calendar for the latest schedule."
    )
    html_body = (
        f"<p>Hi {first_name},</p>"
        f"<p><strong>{event_name}</strong> ({when}) has been <strong>cancelled</strong>.</p>"
        f"<p>Please check the {tenant_name} calendar for the latest schedule.</p>"
    )
    return EmailMessage(to=to, subject=subject, html_body=html_body, text_body=text_body)


def build_permission_request_email(
    *,
    to: str,
    first_name: str,
    scout_names: list[str],
    event_name: str,
    when: str,
    tenant_name: str,
) -> EmailMessage:
    scouts = ", ".join(scout_names)
    subject = f"Permission needed: {event_name} — {tenant_name}"
    text_body = (
        f"Hi {first_name},\n\n"
        f"{scouts} is signed up for {event_name} ({when}), which requires a "
        f"permission slip.\n\n"
        f"Please sign in to {tenant_name} on OpenTroop to grant electronic permission, "
        f"or send a signed paper slip with your scout."
    )
    html_body = (
        f"<p>Hi {first_name},</p>"
        f"<p><strong>{scouts}</strong> is signed up for <strong>{event_name}</strong> ({when}), "
        f"which requires a permission slip.</p>"
        f"<p>Please sign in to {tenant_name} on OpenTroop to grant electronic permission, "
        f"or send a signed paper slip with your scout.</p>"
    )
    return EmailMessage(to=to, subject=subject, html_body=html_body, text_body=text_body)


def event_when(event: Event) -> str:
    return _format_when(event.scheduled_start, event.all_day)
