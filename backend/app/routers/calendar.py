"""Personal iCal calendar feed + subscription management.

The feed itself (``GET /calendar/{token}.ics``) is **unauthenticated by design** —
calendar apps can't do OAuth, so the unguessable per-member token *is* the
credential. The subscription endpoints that mint/rotate that token are normal
authenticated, tenant-scoped routes.
"""

import secrets

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app.core.deps import CurrentMemberDep, DbDep
from app.core.ical import member_calendar_ics
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.calendar import CalendarSubscriptionRead

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _feed_path(token: str) -> str:
    return f"/calendar/{token}.ics"


def _new_token() -> str:
    return secrets.token_urlsafe(32)


@router.get("/{token}.ics")
def get_calendar_feed(token: str, db: DbDep) -> Response:
    """Serve a member's personal iCal feed. Token-authenticated; no session.

    404s for an unknown/rotated token or a member in a suspended/deleted tenant,
    so the same response covers every "you can't see this" case.
    """
    member = db.scalar(
        select(Member).where(
            Member.calendar_token == token,
            Member.is_deleted.is_(False),
        )
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Calendar not found")

    tenant = db.get(Tenant, member.tenant_id)
    if tenant is None or tenant.is_deleted or tenant.suspended_at is not None:
        raise HTTPException(status_code=404, detail="Calendar not found")

    calendar_name = f"{tenant.name} — {member.first_name} {member.last_name}".strip()
    body = member_calendar_ics(member, db, calendar_name=calendar_name)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="opentroop.ics"'},
    )


@router.post("/subscription", response_model=CalendarSubscriptionRead, status_code=201)
def create_subscription(member: CurrentMemberDep, db: DbDep) -> CalendarSubscriptionRead:
    """Return the caller's feed token, minting one on first use (idempotent)."""
    if member.calendar_token is None:
        member.calendar_token = _new_token()
        db.commit()
    return CalendarSubscriptionRead(
        token=member.calendar_token, feed_path=_feed_path(member.calendar_token)
    )


@router.delete("/subscription", response_model=CalendarSubscriptionRead)
def rotate_subscription(member: CurrentMemberDep, db: DbDep) -> CalendarSubscriptionRead:
    """Rotate the caller's token — old subscription URLs immediately stop working."""
    member.calendar_token = _new_token()
    db.commit()
    return CalendarSubscriptionRead(
        token=member.calendar_token, feed_path=_feed_path(member.calendar_token)
    )
