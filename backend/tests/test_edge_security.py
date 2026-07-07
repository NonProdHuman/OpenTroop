"""Edge-security belts (GH-116 / GH-117).

Covers the four controls added for the security-architecture findings:

1. Origin shared secret — requests lacking the Worker-injected ``X-Origin-Auth``
   are rejected when ``ORIGIN_SHARED_SECRET`` is set (direct *.run.app bypass).
2. ``ALLOW_TENANT_ID_HEADER=false`` — the ``X-Tenant-ID`` fallback is disabled in
   SaaS production so tenant UUIDs are not a probing oracle (subdomain only).
3. App-layer rate limiting — per-tenant and per-IP fixed-window buckets.
4. Cloudflare Access belt on ``/platform/*`` — an independent staff assertion is
   required in addition to ``PlatformAdminDep`` when configured.

All controls are inert by default; each test enables one via monkeypatched settings.
"""

import asyncio
import time
import uuid
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import cf_access
from app.core.config import settings
from app.core.edge_security import _FixedWindowLimiter, rate_limiter
from app.core.tenant import get_tenant_id
from app.models.tenant import Tenant
from tests.conftest import TENANT_A
from tests.test_tenant_resolution import _request

APP_DOMAIN = "opentroop.test"

SECRET = "edge-secret-0123456789abcdef0123456789abcdef"  # noqa: S105 — test-only value  # gitleaks:allow


# ---------------------------------------------------------------------------
# 1. Origin shared secret (OriginAuthMiddleware)
# ---------------------------------------------------------------------------


def test_origin_auth_disabled_by_default(client: TestClient) -> None:
    assert client.get("/groups/").status_code == 200


def test_origin_auth_missing_header_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "origin_shared_secret", SECRET)
    r = client.get("/groups/")
    assert r.status_code == 403
    assert r.json()["detail"] == "Origin verification failed"


def test_origin_auth_wrong_secret_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "origin_shared_secret", SECRET)
    r = client.get("/groups/", headers={"X-Origin-Auth": "wrong-" + SECRET})
    assert r.status_code == 403


def test_origin_auth_correct_secret_passes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "origin_shared_secret", SECRET)
    r = client.get("/groups/", headers={"X-Origin-Auth": SECRET})
    assert r.status_code == 200


def test_origin_auth_health_exempt(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Cloud Run probes and uptime checks hit the origin directly, without the Worker.
    monkeypatch.setattr(settings, "origin_shared_secret", SECRET)
    assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
# 2. ALLOW_TENANT_ID_HEADER=false (subdomain-only tenant resolution)
# ---------------------------------------------------------------------------


def _ensure_tenant(db: Session, tenant_id: uuid.UUID, slug: str) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(id=tenant_id, name=f"Troop {slug}", slug=slug)
        db.add(tenant)
        db.commit()
    return tenant


def test_tenant_header_rejected_when_disabled(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the flag off, a valid X-Tenant-ID no longer resolves a tenant (400)."""
    monkeypatch.setattr(settings, "app_domain", APP_DOMAIN)
    monkeypatch.setattr(settings, "allow_tenant_id_header", False)
    _ensure_tenant(db_session, TENANT_A, "troopa")

    req = _request({"host": "testserver"})
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_tenant_id(req, db_session, str(TENANT_A)))
    assert exc_info.value.status_code == 400


def test_subdomain_still_resolves_when_header_disabled(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_domain", APP_DOMAIN)
    monkeypatch.setattr(settings, "allow_tenant_id_header", False)
    _ensure_tenant(db_session, TENANT_A, "troopa")

    req = _request({"host": f"troopa.{APP_DOMAIN}"})
    assert asyncio.run(get_tenant_id(req, db_session, None)) == TENANT_A


def test_calendar_feed_header_fallback_disabled(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unauthenticated feed also stops honoring X-Tenant-ID when disabled."""
    monkeypatch.setattr(settings, "app_domain", APP_DOMAIN)
    _ensure_tenant(db_session, TENANT_A, "troopa")
    feed_path = client.post("/calendar/subscription").json()["feed_path"]

    # Sanity: with the flag on (default), the X-Tenant-ID the fixture sends works.
    assert client.get(feed_path).status_code == 200

    monkeypatch.setattr(settings, "allow_tenant_id_header", False)
    assert client.get(feed_path).status_code == 404
    # Subdomain resolution remains the supported path.
    r = client.get(feed_path, headers={"Host": f"troopa.{APP_DOMAIN}"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 3. App-layer rate limiting
# ---------------------------------------------------------------------------


def test_limiter_fixed_window_unit() -> None:
    limiter = _FixedWindowLimiter()
    now = 1_700_000_000.0  # deterministic; avoids real-clock window rollover flake
    assert limiter.hit("b", "k", 2, now=now) is None
    assert limiter.hit("b", "k", 2, now=now) is None
    retry = limiter.hit("b", "k", 2, now=now)
    assert retry is not None and 0 < retry <= 60
    # A different key has its own budget; a new window resets the old one.
    assert limiter.hit("b", "other", 2, now=now) is None
    assert limiter.hit("b", "k", 2, now=now + 60) is None


def test_rate_limit_tenant_bucket(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    rate_limiter.reset()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    # Use the canonical path — "/groups/" 307-redirects and the follow-up request
    # would consume a second unit of budget per call.
    for _ in range(3):
        assert client.get("/groups").status_code == 200
    r = client.get("/groups")
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    rate_limiter.reset()


def test_rate_limit_calendar_per_ip(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Token guessing on the unauthenticated feed hits the tighter per-IP bucket."""
    rate_limiter.reset()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_calendar_per_minute", 2)
    for _ in range(2):
        assert client.get("/calendar/not-a-real-token.ics").status_code == 404
    assert client.get("/calendar/not-a-real-token.ics").status_code == 429
    rate_limiter.reset()


def test_rate_limit_health_exempt(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    rate_limiter.reset()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1)
    for _ in range(5):
        assert client.get("/health").status_code == 200
    rate_limiter.reset()


def _http_scope(host: str, path: str = "/members") -> dict[str, object]:
    return {
        "type": "http",
        "path": path,
        "headers": [(b"host", host.encode())],
        "client": ("1.2.3.4", 0),
    }


def test_is_demo_request_matches_only_demo_subdomain(monkeypatch: pytest.MonkeyPatch) -> None:
    """The demo per-IP rate-limit bucket (GH-246) is chosen only for the demo tenant's
    subdomain, and only when the feature is on — inert otherwise."""
    from app.core.edge_security import _is_demo_request

    # settings.app_domain is opentroop.test in the test env.
    monkeypatch.setattr(settings, "demo_tenant_slug", "")
    assert _is_demo_request(_http_scope("demo-public.opentroop.test")) is False

    monkeypatch.setattr(settings, "demo_tenant_slug", "demo-public")
    assert _is_demo_request(_http_scope("demo-public.opentroop.test")) is True
    assert _is_demo_request(_http_scope("troop42.opentroop.test")) is False
    assert _is_demo_request(_http_scope("opentroop.test")) is False


# ---------------------------------------------------------------------------
# 4. Cloudflare Access belt on /platform/*
# ---------------------------------------------------------------------------

_ACCESS_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEAM = "testteam"
ACCESS_ISSUER = f"https://{TEAM}.cloudflareaccess.com"
ACCESS_AUD = "platform-app-aud"


class _StubSigningKey:
    def __init__(self, key: Any) -> None:
        self.key = key


class _StubJwksClient:
    def get_signing_key_from_jwt(self, token: str) -> _StubSigningKey:
        return _StubSigningKey(_ACCESS_KEY.public_key())


def _access_token(**overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "aud": ACCESS_AUD,
        "iss": ACCESS_ISSUER,
        "iat": now,
        "exp": now + 600,
        "email": "ops@example.com",
    }
    claims.update(overrides)
    return jwt.encode(claims, _ACCESS_KEY, algorithm="RS256")


@pytest.fixture
def access_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cf_access_team_domain", TEAM)
    monkeypatch.setattr(settings, "cf_access_aud", ACCESS_AUD)
    monkeypatch.setattr(cf_access, "_get_access_jwks_client", lambda team: _StubJwksClient())


def test_platform_unaffected_when_access_unconfigured(platform_admin_client: TestClient) -> None:
    assert platform_admin_client.get("/platform/tenants").status_code == 200


def test_platform_requires_access_assertion(
    platform_admin_client: TestClient, access_configured: None
) -> None:
    """A valid platform-admin token alone no longer reaches the control plane."""
    r = platform_admin_client.get("/platform/tenants")
    assert r.status_code == 401
    assert r.json()["detail"] == "Cloudflare Access assertion required"


def test_platform_rejects_garbage_assertion(
    platform_admin_client: TestClient, access_configured: None
) -> None:
    r = platform_admin_client.get(
        "/platform/tenants", headers={"Cf-Access-Jwt-Assertion": "not-a-jwt"}
    )
    assert r.status_code == 401


def test_platform_rejects_wrong_audience(
    platform_admin_client: TestClient, access_configured: None
) -> None:
    token = _access_token(aud="some-other-app")
    r = platform_admin_client.get("/platform/tenants", headers={"Cf-Access-Jwt-Assertion": token})
    assert r.status_code == 401


def test_platform_rejects_wrong_issuer(
    platform_admin_client: TestClient, access_configured: None
) -> None:
    token = _access_token(iss="https://evil.cloudflareaccess.com")
    r = platform_admin_client.get("/platform/tenants", headers={"Cf-Access-Jwt-Assertion": token})
    assert r.status_code == 401


def test_platform_rejects_expired_assertion(
    platform_admin_client: TestClient, access_configured: None
) -> None:
    now = int(time.time())
    token = _access_token(iat=now - 1200, exp=now - 600)
    r = platform_admin_client.get("/platform/tenants", headers={"Cf-Access-Jwt-Assertion": token})
    assert r.status_code == 401


def test_platform_valid_assertion_passes(
    platform_admin_client: TestClient, access_configured: None
) -> None:
    r = platform_admin_client.get(
        "/platform/tenants", headers={"Cf-Access-Jwt-Assertion": _access_token()}
    )
    assert r.status_code == 200


def test_access_belt_is_independent_of_platform_role(
    claim_client: TestClient, access_configured: None
) -> None:
    """The belt gates before the role check: no assertion → 401 even for non-admins."""
    r = claim_client.get("/platform/tenants")
    assert r.status_code == 401
