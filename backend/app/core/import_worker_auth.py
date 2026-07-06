"""OIDC verification for the Cloud Tasks import-worker endpoint (GH-240).

When ``IMPORT_QUEUE_BACKEND=cloudtasks``, Cloud Tasks POSTs each job to
``POST /import/jobs/execute`` carrying a Google-signed OIDC token whose audience is
the worker URL and whose email is the import worker's service account. This verifies
that token so the internal endpoint can't be driven by anyone but the queue.

The endpoint is inert unless the cloudtasks backend is configured — under the default
``inprocess`` backend it rejects everything (there is no internal caller).
"""

from __future__ import annotations

import logging

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger(__name__)

# Google's OIDC signing certificates (RS256). Same shape as the app JWKS path.
_GOOGLE_CERTS_URI = "https://www.googleapis.com/oauth2/v3/certs"
_jwks_client: PyJWKClient | None = None


def _google_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(_GOOGLE_CERTS_URI, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


def verify_worker_oidc(token: str) -> None:
    """Raise 403 unless *token* is a valid Cloud Tasks OIDC token for this worker."""
    if settings.import_queue_backend != "cloudtasks" or not settings.import_worker_url:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Import worker endpoint is not enabled.",
        )
    try:
        signing_key = _google_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.import_worker_url,
            options={"require": ["exp", "iat", "aud", "email"]},
        )
    except jwt.exceptions.PyJWTError as exc:
        logger.debug("Worker OIDC validation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid worker credential",
        ) from exc

    expected = settings.import_worker_service_account
    if expected and claims.get("email") != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker credential is not authorized",
        )
