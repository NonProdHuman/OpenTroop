"""Personal iCal calendar feed + subscription management.

The feed itself (``GET /calendar/{token}.ics``) is **unauthenticated by design** —
calendar apps can't do OAuth, so the unguessable per-member token *is* the
credential. The subscription endpoints that mint/rotate that token are normal
authenticated, tenant-scoped routes.
"""

import hashlib
import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from app.core.deps import CurrentMemberDep, DbDep
from app.core.ical import member_calendar_ics
from app.core.tenant import scope_calendar_feed_tenant
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.calendar import CalendarSubscriptionRead

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _feed_path(token: str) -> str:
    return f"/calendar/{token}.ics"


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_calendar_token(token: str) -> str:
    """Digest a raw feed token for storage/lookup (GH-114).

    A single unsalted SHA-256 is deliberate: the token is high-entropy random data
    (not a password), so brute force is infeasible, and the digest must stay
    deterministic to serve as the indexed lookup key.
    """
    return hashlib.sha256(token.encode()).hexdigest()


@router.get("/{token}.ics")
def get_calendar_feed(
    token: str,
    db: DbDep,
    tenant_id: Annotated[uuid.UUID, Depends(scope_calendar_feed_tenant)],
) -> Response:
    """Serve a member's personal iCal feed. Token-authenticated; no session.

    ``scope_calendar_feed_tenant`` resolves the tenant (subdomain / X-Tenant-ID) and
    publishes it to the tenant context, so the token lookup below is tenant-scoped and
    survives Postgres RLS. 404s for an unknown/rotated token or a member in a
    suspended/deleted tenant, so the same response covers every "you can't see this"
    case (the suspended/deleted tenant is already rejected by the dependency).
    """
    member = db.scalar(
        select(Member).where(Member.calendar_token_hash == hash_calendar_token(token))
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Calendar not found")

    tenant = db.get(Tenant, tenant_id)
    calendar_name = (
        f"{tenant.name} — {member.first_name} {member.last_name}".strip()
        if tenant is not None
        else f"{member.first_name} {member.last_name}".strip()
    )
    body = member_calendar_ics(member, db, calendar_name=calendar_name)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="opentroop.ics"'},
    )


@router.post("/subscription", response_model=CalendarSubscriptionRead, status_code=201)
def create_subscription(member: CurrentMemberDep, db: DbDep) -> CalendarSubscriptionRead:
    """Mint the caller's feed token on first use; report status thereafter.

    Only the token's hash is stored, so the raw token appears in exactly one
    response — the one that minted it. A repeat call cannot reveal it again and
    returns ``active`` with no token; the client rotates to obtain a fresh URL.
    """
    if member.calendar_token_hash is None:
        token = _new_token()
        member.calendar_token_hash = hash_calendar_token(token)
        db.commit()
        return CalendarSubscriptionRead(active=True, token=token, feed_path=_feed_path(token))
    return CalendarSubscriptionRead(active=True)


@router.delete("/subscription", response_model=CalendarSubscriptionRead)
def rotate_subscription(member: CurrentMemberDep, db: DbDep) -> CalendarSubscriptionRead:
    """Rotate the caller's token — old subscription URLs immediately stop working."""
    token = _new_token()
    member.calendar_token_hash = hash_calendar_token(token)
    db.commit()
    return CalendarSubscriptionRead(active=True, token=token, feed_path=_feed_path(token))
