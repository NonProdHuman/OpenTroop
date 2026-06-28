from __future__ import annotations

import logging
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.core.config import settings
from app.core.database import get_db
from app.models.user import Identity, User

logger = logging.getLogger(__name__)

_http_bearer = HTTPBearer(auto_error=False)
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.auth_jwks_uri, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


def decode_token(token: str) -> dict[str, Any]:
    """Validate a JWT against the configured JWKS. Raises HTTP 401 on any failure."""
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        # Pass audience only when configured; PyJWT skips aud verification when
        # audience=None, which is acceptable for deployments that don't use aud.
        audience: str | None = settings.auth_audience if settings.auth_audience else None
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=audience,
        )
    except jwt.exceptions.PyJWTError as exc:
        # Log only the exception class, not the message — the message may contain
        # token fragments that CodeQL (correctly) treats as sensitive log data.
        logger.debug("JWT validation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_or_create_user(claims: dict[str, Any], session: Session) -> User:
    """Look up or provision a User+Identity from validated JWT claims.

    On first login the User and Identity rows are created atomically.
    Subsequent logins with the same (issuer, sub) pair return the existing User.
    """
    issuer: str = claims["iss"]
    sub: str = claims["sub"]

    identity = session.scalar(
        select(Identity).where(
            Identity.issuer == issuer,
            Identity.provider_sub == sub,
            Identity.is_deleted.is_(False),
        )
    )
    if identity is not None:
        return identity.user

    email: str | None = claims.get("email")
    display_name: str | None = claims.get("name")

    from app.models.enums import PlatformRole

    user_count = session.scalar(select(func.count()).select_from(User))
    role = PlatformRole.SUPERADMIN if user_count == 0 else None

    user = User(id=uuid7(), email=email, display_name=display_name, platform_role=role)
    session.add(user)
    session.flush()  # populate user.id before referencing it in Identity

    if email:
        from sqlalchemy import update

        from app.models.member import Member

        session.execute(
            update(Member)
            .where(Member.email == email, Member.user_id.is_(None), Member.is_deleted.is_(False))
            .values(user_id=user.id)
        )

    identity = Identity(
        id=uuid7(),
        user_id=user.id,
        provider=_provider_label(issuer),
        issuer=issuer,
        provider_sub=sub,
        email=email,
    )
    session.add(identity)
    session.commit()
    session.refresh(user)
    return user


def _provider_label(issuer: str) -> str:
    lower = issuer.lower()
    if "google" in lower:
        return "google"
    if "apple" in lower:
        return "apple"
    if "clerk" in lower:
        return "clerk"
    if "authentik" in lower:
        return "authentik"
    return "oidc"


async def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_http_bearer)],
) -> User:
    """FastAPI dependency: validate Bearer token and return the platform User."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_token(credentials.credentials)
    return get_or_create_user(claims, db)
