"""Tenant resolution hardening: X-Forwarded-Host is only trusted behind a proxy.

Regression tests for GH-113 — ``X-Forwarded-Host`` is client-supplied, so honoring it
unconditionally lets an attacker choose the tenant on any deployment whose proxy does
not strip the header. It must only be used when ``TRUST_FORWARDED_HOST=true``.
"""

import asyncio
import uuid

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.tenant import _resolve_request_host, get_tenant_id
from app.models.tenant import Tenant

TENANT_A = uuid.UUID("10000000-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("20000000-0000-0000-0000-000000000002")

APP_DOMAIN = "opentroop.test"


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


def _ensure_tenant(db: Session, tenant_id: uuid.UUID, slug: str) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(id=tenant_id, name=f"Troop {slug}", slug=slug)
        db.add(tenant)
        db.commit()
    return tenant


# --- _resolve_request_host unit tests --------------------------------------


def test_forwarded_host_ignored_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trust_forwarded_host", False)
    req = _request({"host": "real.example.com", "x-forwarded-host": "evil.example.com"})
    assert _resolve_request_host(req) == "real.example.com"


def test_forwarded_host_honored_when_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trust_forwarded_host", True)
    req = _request({"host": "proxy.internal", "x-forwarded-host": "troop123.opentroop.test"})
    assert _resolve_request_host(req) == "troop123.opentroop.test"


def test_trusted_but_no_forwarded_host_falls_back_to_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trust_forwarded_host", True)
    req = _request({"host": "troop123.opentroop.test"})
    assert _resolve_request_host(req) == "troop123.opentroop.test"


def test_no_host_headers_resolves_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trust_forwarded_host", False)
    assert _resolve_request_host(_request({})) == ""


# --- get_tenant_id (the real dependency, not the test override) ------------


def test_get_tenant_id_rejects_spoofed_forwarded_host(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With trust off, a forged X-Forwarded-Host cannot select a tenant."""
    monkeypatch.setattr(settings, "app_domain", APP_DOMAIN)
    monkeypatch.setattr(settings, "trust_forwarded_host", False)
    _ensure_tenant(db_session, TENANT_A, "troopa")

    req = _request({"host": "testserver", "x-forwarded-host": f"troopa.{APP_DOMAIN}"})
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_tenant_id(req, db_session, None))
    # Header ignored + no other tenant context → 400, not a tenant match.
    assert exc_info.value.status_code == 400


def test_get_tenant_id_resolves_forwarded_host_when_trusted(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_domain", APP_DOMAIN)
    monkeypatch.setattr(settings, "trust_forwarded_host", True)
    _ensure_tenant(db_session, TENANT_A, "troopa")

    req = _request({"host": "testserver", "x-forwarded-host": f"troopa.{APP_DOMAIN}"})
    assert asyncio.run(get_tenant_id(req, db_session, None)) == TENANT_A


def test_get_tenant_id_resolves_plain_host_subdomain(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Host-header subdomain resolution works regardless of the trust setting."""
    monkeypatch.setattr(settings, "app_domain", APP_DOMAIN)
    monkeypatch.setattr(settings, "trust_forwarded_host", False)
    _ensure_tenant(db_session, TENANT_A, "troopa")

    req = _request({"host": f"troopa.{APP_DOMAIN}"})
    assert asyncio.run(get_tenant_id(req, db_session, None)) == TENANT_A


# --- Calendar feed (unauthenticated path, scope_calendar_feed_tenant) ------
#
# The iCal feed is the highest-value target: it has no JWT, so tenant resolution is
# the only belt. The `client` fixture sends X-Tenant-ID: TENANT_A by default; a
# request-level X-Tenant-ID header overrides it.


def _feed_path(client: TestClient) -> str:
    return client.post("/calendar/subscription").json()["feed_path"]


def test_feed_spoofed_forwarded_host_cannot_switch_tenant(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_domain", APP_DOMAIN)
    monkeypatch.setattr(settings, "trust_forwarded_host", False)
    _ensure_tenant(db_session, TENANT_A, "troopa")
    _ensure_tenant(db_session, TENANT_B, "troopb")
    feed_path = _feed_path(client)  # token minted in TENANT_A

    # Spoofing another tenant's subdomain has no effect: the header is ignored and
    # the X-Tenant-ID fallback (TENANT_A) still serves the feed.
    r = client.get(feed_path, headers={"X-Forwarded-Host": f"troopb.{APP_DOMAIN}"})
    assert r.status_code == 200

    # Nor can a forged header *choose* the token's tenant when the rest of the
    # request points elsewhere — before the fix this returned 200.
    r = client.get(
        feed_path,
        headers={
            "X-Forwarded-Host": f"troopa.{APP_DOMAIN}",
            "X-Tenant-ID": str(TENANT_B),
        },
    )
    assert r.status_code == 404


def test_feed_forwarded_host_wins_when_trusted(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Behind a trusted proxy the subdomain outranks X-Tenant-ID, as documented."""
    monkeypatch.setattr(settings, "app_domain", APP_DOMAIN)
    monkeypatch.setattr(settings, "trust_forwarded_host", True)
    _ensure_tenant(db_session, TENANT_A, "troopa")
    _ensure_tenant(db_session, TENANT_B, "troopb")
    feed_path = _feed_path(client)  # token minted in TENANT_A

    r = client.get(
        feed_path,
        headers={
            "X-Forwarded-Host": f"troopa.{APP_DOMAIN}",
            "X-Tenant-ID": str(TENANT_B),
        },
    )
    assert r.status_code == 200

    r = client.get(feed_path, headers={"X-Forwarded-Host": f"troopb.{APP_DOMAIN}"})
    assert r.status_code == 404
