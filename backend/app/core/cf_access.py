"""Cloudflare Access belt for the platform control plane (GH-117).

The SaaS control plane (``/platform/*``) is the highest-value target: one leaked
platform-admin token is full multi-tenant compromise. This dependency adds a second,
*independent* authentication belt: when ``CF_ACCESS_TEAM_DOMAIN`` is configured, every
platform request must also carry a Cloudflare Access assertion
(``Cf-Access-Jwt-Assertion``) — a JWT Cloudflare signs only after the caller passed
the Access application's staff SSO policy. A compromised tenant-plane OIDC token
therefore no longer reaches the control plane.

Verification mirrors ``app.core.auth.decode_token``: JWKS fetched from the team's
``/cdn-cgi/access/certs`` endpoint, RS256/ES256, issuer pinned to the team domain,
audience pinned to the Access application AUD when configured. Unconfigured
(dev / tests / self-host, where there is no Cloudflare in front) the check is a no-op —
``PlatformAdminDep`` remains the only gate, exactly as before.
"""

from __future__ import annotations

import logging

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger(__name__)

_jwks_clients: dict[str, PyJWKClient] = {}


def _get_access_jwks_client(team_domain: str) -> PyJWKClient:
    client = _jwks_clients.get(team_domain)
    if client is None:
        client = PyJWKClient(
            f"https://{team_domain}.cloudflareaccess.com/cdn-cgi/access/certs",
            cache_jwk_set=True,
            lifespan=3600,
        )
        _jwks_clients[team_domain] = client
    return client


async def require_cf_access(request: Request) -> None:
    """FastAPI dependency: verify the Cloudflare Access assertion when configured."""
    team_domain = settings.cf_access_team_domain
    if not team_domain:
        return
    token = request.headers.get("cf-access-jwt-assertion")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cloudflare Access assertion required",
        )
    try:
        signing_key = _get_access_jwks_client(team_domain).get_signing_key_from_jwt(token)
        jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.cf_access_aud if settings.cf_access_aud else None,
            issuer=f"https://{team_domain}.cloudflareaccess.com",
            options={"require": ["exp", "iat", "iss"]},
        )
    except jwt.exceptions.PyJWTError as exc:
        # Log only the exception class — the message may embed token fragments.
        logger.debug("Cloudflare Access verification failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Cloudflare Access assertion",
        ) from exc
