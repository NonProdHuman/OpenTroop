from __future__ import annotations

import logging
from typing import Annotated, Any, cast

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import select
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
        # Pass audience/issuer only when configured; PyJWT skips each verification
        # when the parameter is None, which is acceptable for deployments that
        # don't use aud or pin a single issuer. Standard claims must always be
        # present — identity is keyed on (iss, sub), so a token missing either
        # must be rejected here rather than failing later.
        audience: str | None = settings.auth_audience if settings.auth_audience else None
        issuer: str | None = settings.auth_issuer if settings.auth_issuer else None
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "iss", "sub"]},
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
    email: str | None = claims.get("email")
    display_name: str | None = claims.get("name")
    # Strict identity check: the provider must positively assert verification.
    # An email claim without it is attacker-chosen and must never drive matching.
    email_verified: bool = claims.get("email_verified") is True

    if identity is not None:
        # Backfill profile fields that were absent at first login — e.g. the Clerk JWT
        # only began including the email/name claims later. Fill only when missing so we
        # never clobber an existing value. This is what lets grant-by-email find a user
        # who signed in before email was in the token.
        user = identity.user
        changed = False
        if email and not user.email:
            user.email = email
            changed = True
        if email and email_verified and email == user.email and not user.email_verified:
            user.email_verified = True
            changed = True
        if display_name and not user.display_name:
            user.display_name = display_name
            changed = True
        if email and email_verified and _autolink_unclaimed_members(session, user, email):
            # A member invited before this user's first login (or before the email
            # was verified) links up on the next verified sign-in. Only an actual
            # link marks the session changed — unconditionally committing here made
            # every authenticated request pay a write (GH-115).
            changed = True
        if _bootstrap_superadmin(user, email, email_verified):
            changed = True
        if changed:
            session.commit()
            session.refresh(user)
        return user

    user = User(
        id=uuid7(),
        email=email,
        email_verified=bool(email) and email_verified,
        display_name=display_name,
        platform_role=None,
    )
    session.add(user)
    session.flush()  # populate user.id before referencing it in Identity

    if email and email_verified:
        _autolink_unclaimed_members(session, user, email)
    _bootstrap_superadmin(user, email, email_verified)

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


def _bootstrap_superadmin(user: User, email: str | None, email_verified: bool) -> bool:
    """Grant SUPERADMIN when the caller's *verified* email matches the bootstrap allowlist.

    This replaces the old "first signup wins" auto-promotion (GH-111): an empty
    users table must never be a race an anonymous stranger can win, and the email
    must be provider-verified — an unverified claim is attacker-chosen. Returns
    True when the role was granted.
    """
    allowlisted = settings.bootstrap_superadmin_email.strip().lower()
    if not allowlisted or user.platform_role is not None:
        return False
    if not (email and email_verified and email.lower() == allowlisted):
        return False

    from app.models.enums import PlatformRole

    user.platform_role = PlatformRole.SUPERADMIN
    logger.info("Bootstrap superadmin granted to user %s via BOOTSTRAP_SUPERADMIN_EMAIL", user.id)
    return True


def _autolink_unclaimed_members(session: Session, user: User, email: str) -> bool:
    """Link unclaimed Member rows matching a *verified* email to *user*.

    Returns True when at least one Member row was actually linked.

    Callers must have established that the OIDC provider asserted
    ``email_verified`` for *email* — tenant provisioning creates unclaimed admin
    members, so matching an unverified claim here would hand a troop's admin seat
    to anyone who can mint a token carrying the victim's address (GH-110).
    """
    from sqlalchemy import update
    from sqlalchemy.engine import CursorResult

    from app.models.member import Member

    result = session.execute(
        update(Member)
        .where(Member.email == email, Member.user_id.is_(None), Member.is_deleted.is_(False))
        .values(user_id=user.id)
    )
    # An UPDATE statement always yields a CursorResult carrying rowcount.
    return cast("CursorResult[Any]", result).rowcount > 0


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


async def get_optional_current_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_http_bearer)],
) -> User | None:
    """Like :func:`get_current_user`, but return ``None`` when *no* Bearer token is
    presented instead of raising 401.

    This is the single seam the anonymous public-demo carve-out (GH-246, ADR 0012)
    hangs off: the member-context dependencies in ``app.core.deps`` turn a ``None``
    here into a fixed, read-only Demo Viewer member — but only on the configured
    demo tenant, and only for safe methods (see ``deps._resolve_current_member``).
    Every other path treats ``None`` as unauthenticated and raises exactly as
    before, so behavior is provably inert while ``DEMO_TENANT_SLUG`` is unset. A
    malformed or expired token still raises 401 via :func:`decode_token` —
    "anonymous" means the *absence* of a credential, never a bad one.
    """
    if credentials is None:
        return None
    return get_or_create_user(decode_token(credentials.credentials), db)
