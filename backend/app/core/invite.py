from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.notifications import EmailMessage

_CLAIM_DAYS = 7
_ALGORITHM = "HS256"
_TOKEN_TYPE = "member_claim"  # noqa: S105


def create_invite_token(member_id: uuid.UUID, tenant_id: uuid.UUID) -> tuple[str, datetime]:
    """Return a signed HS256 claim token and its expiry timestamp.

    The token encodes member_id, tenant_id, and a type discriminator so it
    cannot be reused for other token purposes in the same app.
    """
    expires_at = datetime.now(UTC) + timedelta(days=_CLAIM_DAYS)
    payload = {
        "sub": str(member_id),
        "tid": str(tenant_id),
        "type": _TOKEN_TYPE,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.app_secret, algorithm=_ALGORITHM)
    return token, expires_at


def decode_invite_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Validate and decode a claim token. Raises HTTP 400 on any failure."""
    try:
        payload = jwt.decode(token, settings.app_secret, algorithms=[_ALGORITHM])
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
    return uuid.UUID(payload["sub"]), uuid.UUID(payload["tid"])


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
