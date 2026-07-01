"""Regression test for mixed-content redirects behind the Cloud Run TLS proxy.

FastAPI's trailing-slash redirect builds an absolute ``Location`` from the request
scheme. Behind Cloud Run, uvicorn only learns the request is HTTPS if it trusts the
proxy's ``X-Forwarded-Proto`` header (enabled in the Dockerfile via
``--forwarded-allow-ips='*'``, which wraps the app in uvicorn's ProxyHeadersMiddleware
with ``trusted_hosts="*"``). Without it, the redirect emits ``http://`` and the browser
blocks the follow-up request as mixed content — surfacing as "Could not reach the
backend" with no data in the web UI.
"""

from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.main import app


def test_trailing_slash_redirect_preserves_https_when_proxy_trusted() -> None:
    """With the proxy trusted, X-Forwarded-Proto: https yields an https Location."""
    trusted = ProxyHeadersMiddleware(app, trusted_hosts="*")
    client = TestClient(trusted, base_url="http://testserver", follow_redirects=False)

    resp = client.get("/positions/", headers={"X-Forwarded-Proto": "https"})

    assert resp.status_code == 307
    assert resp.headers["location"].startswith("https://"), resp.headers["location"]


def test_untrusted_proxy_regresses_to_http() -> None:
    """Guard: the bug reproduces when the proxy header is not trusted."""
    untrusted = ProxyHeadersMiddleware(app, trusted_hosts="127.0.0.1")
    client = TestClient(untrusted, base_url="http://testserver", follow_redirects=False)

    resp = client.get("/positions/", headers={"X-Forwarded-Proto": "https"})

    assert resp.status_code == 307
    assert resp.headers["location"].startswith("http://")
