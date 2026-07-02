"""CORS preflight tests — credentialed origin/method/header narrowing (GH-118).

``allow_credentials=True`` means every origin the middleware reflects can drive
authenticated browser requests, so these tests pin exactly which origins, methods,
and headers are allowed. The app under test is built fresh so ``APP_DOMAIN`` can be
set before the middleware computes its origin regex.
"""

import importlib
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import app.main
from app.core.config import settings


@pytest.fixture()
def cors_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A client against an app whose CORS regex was built for opentroop.app."""
    monkeypatch.setattr(settings, "app_domain", "opentroop.app")
    monkeypatch.setattr(settings, "cors_origins", ["http://localhost:3000"])
    module = importlib.reload(app.main)
    yield TestClient(module.app)
    importlib.reload(app.main)  # restore module-level app built from real settings


def _preflight(client: TestClient, origin: str, method: str = "GET") -> dict[str, str]:
    r = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type,x-tenant-id",
        },
    )
    return {k.lower(): v for k, v in r.headers.items()}


@pytest.mark.parametrize(
    "origin",
    [
        "https://opentroop.app",
        "https://www.opentroop.app",
        "https://admin.opentroop.app",
        "https://troop123.opentroop.app",
        "http://localhost:3000",  # explicit dev origin from CORS_ORIGINS
    ],
)
def test_allowed_origins_are_reflected_with_credentials(
    cors_client: TestClient, origin: str
) -> None:
    headers = _preflight(cors_client, origin)
    assert headers.get("access-control-allow-origin") == origin
    assert headers.get("access-control-allow-credentials") == "true"


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.com",
        "https://opentroop.app.evil.com",
        "https://a.b.opentroop.app",  # nested subdomain — mirrors tenant resolution
        "http://troop123.opentroop.app",  # plain http never allowed for app domains
        "https://xopentroop.app",  # missing dot boundary
    ],
)
def test_disallowed_origins_are_not_reflected(cors_client: TestClient, origin: str) -> None:
    headers = _preflight(cors_client, origin)
    assert "access-control-allow-origin" not in headers


def test_preflight_advertises_enumerated_methods_and_headers_only(
    cors_client: TestClient,
) -> None:
    headers = _preflight(cors_client, "https://troop123.opentroop.app")
    methods = {m.strip() for m in headers["access-control-allow-methods"].split(",")}
    assert methods == {"GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"}
    allowed_headers = {
        h.strip().lower() for h in headers["access-control-allow-headers"].split(",")
    }
    # Starlette always appends the CORS-safelisted trio; the app-specific set is ours.
    safelisted = {"accept", "accept-language", "content-language"}
    assert allowed_headers - safelisted == {"authorization", "content-type", "x-tenant-id"}


def test_preflight_rejects_unlisted_request_header(cors_client: TestClient) -> None:
    r = cors_client.options(
        "/health",
        headers={
            "Origin": "https://troop123.opentroop.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-sneaky-header",
        },
    )
    # Starlette answers a disallowed preflight with 400 and no allow-origin header.
    assert r.status_code == 400
