from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

from app.core.config import settings

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
