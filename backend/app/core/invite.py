from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.notifications import EmailMessage
from app.models.member import Member

_CLAIM_DAYS = 7
_ALGORITHM = "HS256"
_TOKEN_TYPE = "member_claim"  # noqa: S105


def create_invite_token(member: Member) -> tuple[str, datetime]:
    """Mint a signed HS256 claim token for *member* and return it with its expiry.

    The token encodes member_id, tenant_id, a type discriminator (so it cannot be
    reused for other token purposes in the same app), and a fresh ``jti`` that is
    also written to ``member.invite_token_jti``. The claim endpoint honors a token
    only while its jti matches the stored one, making tokens single-use (the jti
    is cleared on claim) and revocable (re-inviting overwrites it). The caller
    owns the commit.
    """
    expires_at = datetime.now(UTC) + timedelta(days=_CLAIM_DAYS)
    jti = secrets.token_hex(16)
    member.invite_token_jti = jti
    payload = {
        "sub": str(member.id),
        "tid": str(member.tenant_id),
        "type": _TOKEN_TYPE,
        "jti": jti,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.app_secret, algorithm=_ALGORITHM)
    return token, expires_at


def decode_invite_token(token: str) -> tuple[uuid.UUID, uuid.UUID, str]:
    """Validate and decode a claim token. Raises HTTP 400 on any failure.

    Returns ``(member_id, tenant_id, jti)``. Tokens without a jti are rejected —
    every token minted since single-use enforcement carries one.
    """
    try:
        payload = jwt.decode(
            token,
            settings.app_secret,
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "sub", "tid", "jti"]},
        )
    except jwt.exceptions.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite token",
        ) from exc
    if payload.get("type") != _TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token type",
        )
    return uuid.UUID(payload["sub"]), uuid.UUID(payload["tid"]), str(payload["jti"])


def build_claim_url(slug: str, token: str) -> str:
    """Build the tenant-subdomain claim link an invitee opens to redeem a token.

    Mirrors the frontend's ``getTenantUrl`` (apps/web/src/lib/domains.ts). Local
    dev's APP_DOMAIN is "localhost:<port>", which has no valid TLS cert, hence
    the http/https split.
    """
    scheme = "http" if "localhost" in settings.app_domain else "https"
    return f"{scheme}://{slug}.{settings.app_domain}/claim?token={token}"


def build_invite_email(
    *, to: str, first_name: str, tenant_name: str, claim_url: str
) -> EmailMessage:
    subject = f"You're invited to join {tenant_name} on OpenTroop"
    text_body = (
        f"Hi {first_name},\n\n"
        f"You've been invited to join {tenant_name} on OpenTroop. "
        f"Click the link below to set up your account:\n\n"
        f"{claim_url}\n\n"
        f"This link expires in {_CLAIM_DAYS} days."
    )
    html_body = (
        f"<p>Hi {first_name},</p>"
        f"<p>You've been invited to join <strong>{tenant_name}</strong> on OpenTroop. "
        f'Click the link below to set up your account:</p><p><a href="{claim_url}">{claim_url}</a></p>'
        f"<p>This link expires in {_CLAIM_DAYS} days.</p>"
    )
    return EmailMessage(to=to, subject=subject, html_body=html_body, text_body=text_body)
