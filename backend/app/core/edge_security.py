"""Edge-security belts for the shared SaaS origin (GH-116).

Two pure-ASGI middlewares, both inert by default so dev, tests, and self-hosted
deployments are unaffected until explicitly configured:

- :class:`OriginAuthMiddleware` — when ``ORIGIN_SHARED_SECRET`` is set, every
  request must present the same value in ``X-Origin-Auth``. The Cloudflare Worker
  injects the header on proxied traffic, so a request hitting the raw ``*.run.app``
  origin directly (bypassing the edge WAF/rate limits and the header sanitization
  that makes ``TRUST_FORWARDED_HOST=true`` sound) is rejected with 403.
- :class:`RateLimitMiddleware` — fixed-window, in-process request limits: a
  per-tenant bucket for authenticated traffic (keyed by subdomain / ``X-Tenant-ID``)
  plus tighter per-IP buckets for the unauthenticated hot paths (``/calendar/*``,
  the token-guessing surface) and the auth plane (``/auth/*``, invite-token spray).
  Per-instance only — the Cloudflare rate-limiting rules are the first belt; this
  is the app-layer backstop the edge cannot provide when it is bypassed or absent.
  Swapping the counter store for Redis/Memorystore later only touches
  :class:`_FixedWindowLimiter`.

Both middlewares read ``settings`` per request (not at mount time) so tests can
toggle them with ``monkeypatch.setattr(settings, ...)``.
"""

from __future__ import annotations

import hmac
import threading
import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.tenant import _extract_subdomain

# Never gated: Cloud Run health probes and uptime checks hit the origin directly
# (no Worker in front) and must not consume rate-limit budget.
_EXEMPT_PATHS = frozenset({"/health"})


def _header(scope: Scope, name: bytes) -> str | None:
    """Return the first value of *name* from the raw ASGI header list."""
    for key, value in scope["headers"]:
        if key == name:
            return str(value.decode("latin-1"))
    return None


class OriginAuthMiddleware:
    """Reject requests that did not traverse the trusted edge proxy (GH-116)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        secret = settings.origin_shared_secret
        if not secret or scope["path"] in _EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return
        presented = _header(scope, b"x-origin-auth") or ""
        if not hmac.compare_digest(presented.encode(), secret.encode()):
            response = JSONResponse({"detail": "Origin verification failed"}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class _FixedWindowLimiter:
    """Per-process fixed-window counters keyed by (bucket, key).

    Deliberately simple: one dict, one lock, minute-aligned windows. The map is
    swept whenever it grows past a bound so hostile key churn (e.g. spraying
    random tenant slugs) cannot grow memory without limit.
    """

    _SWEEP_THRESHOLD = 10_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[tuple[str, str], tuple[int, int]] = {}

    def hit(self, bucket: str, key: str, limit: int, now: float | None = None) -> int | None:
        """Record one request; return None if allowed, else seconds until reset."""
        ts = int(now if now is not None else time.time())
        window = ts // 60
        with self._lock:
            if len(self._windows) > self._SWEEP_THRESHOLD:
                self._windows = {k: v for k, v in self._windows.items() if v[0] == window}
            entry = self._windows.get((bucket, key))
            count = 1 if entry is None or entry[0] != window else entry[1] + 1
            self._windows[(bucket, key)] = (window, count)
            if count > limit:
                return 60 - (ts % 60)
        return None

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


rate_limiter = _FixedWindowLimiter()


def _client_ip(scope: Scope) -> str:
    """Best available client identity for per-IP buckets.

    Behind the trusted edge (``TRUST_FORWARDED_HOST=true``) Cloudflare's
    ``CF-Connecting-IP`` names the real client; otherwise it is client-forgeable,
    so the socket peer is the only honest source.
    """
    if settings.trust_forwarded_host:
        cf_ip = _header(scope, b"cf-connecting-ip")
        if cf_ip:
            return cf_ip
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


def _tenant_key(scope: Scope) -> str:
    """Rate-limit key approximating the request's tenant, cheap enough for middleware.

    Mirrors tenant resolution (subdomain first, then the ``X-Tenant-ID`` header when
    allowed) without touching the database — the *claimed* tenant is a fine limiter
    key because lying about it only moves the caller into a different bucket, and
    the per-IP fallback still bounds anonymous traffic.
    """
    host: str | None = None
    if settings.trust_forwarded_host:
        host = _header(scope, b"x-forwarded-host")
    host = host or _header(scope, b"host") or ""
    slug = _extract_subdomain(host, settings.app_domain)
    if slug:
        return f"slug:{slug}"
    if settings.allow_tenant_id_header:
        header_tid = _header(scope, b"x-tenant-id")
        if header_tid:
            return f"tid:{header_tid}"
    return f"ip:{_client_ip(scope)}"


def _is_demo_request(scope: Scope) -> bool:
    """True when this request resolves (by subdomain) to the public-demo tenant.

    Cheap, DB-free, and inert unless ``DEMO_TENANT_SLUG`` is set — it only decides
    which rate-limit bucket the request lands in, so a mismatch never changes
    correctness, just fairness. Mirrors the host handling in :func:`_tenant_key`.
    """
    demo_slug = settings.demo_tenant_slug.strip()
    if not demo_slug:
        return False
    host: str | None = None
    if settings.trust_forwarded_host:
        host = _header(scope, b"x-forwarded-host")
    host = host or _header(scope, b"host") or ""
    return _extract_subdomain(host, settings.app_domain) == demo_slug


class RateLimitMiddleware:
    """App-layer request limits per tenant and per IP (GH-116)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        if path in _EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        if path.startswith("/calendar/"):
            bucket, key, limit = (
                "calendar",
                _client_ip(scope),
                settings.rate_limit_calendar_per_minute,
            )
        elif path.startswith("/auth/"):
            bucket, key, limit = "auth", _client_ip(scope), settings.rate_limit_auth_per_minute
        elif path.startswith("/webhooks/"):
            bucket, key, limit = (
                "webhook",
                _client_ip(scope),
                settings.rate_limit_webhook_per_minute,
            )
        elif _is_demo_request(scope):
            # The public read-only demo (GH-246) shares one anonymous principal, so a
            # single tenant bucket would let one noisy visitor 429 the demo for
            # everyone. Bill it per client IP instead, like the other unauthenticated
            # hot paths (/calendar/*). Inert unless DEMO_TENANT_SLUG is set.
            bucket, key, limit = (
                "demo",
                _client_ip(scope),
                settings.rate_limit_calendar_per_minute,
            )
        else:
            bucket, key, limit = "tenant", _tenant_key(scope), settings.rate_limit_per_minute

        retry_after = rate_limiter.hit(bucket, key, limit)
        if retry_after is not None:
            response = JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
