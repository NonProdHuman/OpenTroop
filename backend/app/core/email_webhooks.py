"""Resend email-webhook signature verification and event application (GH-80).

Resend signs webhooks with the **Standard Webhooks / svix** scheme. We verify it by
hand rather than pulling in the ``svix`` dependency — the scheme is a short HMAC and a
vendor SDK is not worth the supply-chain surface for one endpoint.

The scheme:
  - Headers ``svix-id``, ``svix-timestamp``, ``svix-signature``.
  - Signed content is exactly ``{id}.{timestamp}.{body}`` (raw request body bytes).
  - The signing key is the base64 payload of the secret after its ``whsec_`` prefix.
  - The signature is base64 ``HMAC-SHA256(key, signed_content)``.
  - ``svix-signature`` carries one or more space-separated ``v1,<sig>`` entries; a
    request is valid if *any* entry matches (constant-time compare).
  - Timestamps older/newer than a 5-minute skew are rejected (replay guard).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time
from collections.abc import Iterable
from typing import Any, cast

from sqlalchemy import CursorResult, func, update
from sqlalchemy.orm import Session

from app.models.member import Member

# Max clock skew tolerated between the ``svix-timestamp`` and our clock.
_TIMESTAMP_TOLERANCE_SECONDS = 5 * 60

# Resend event types we act on.
EVENT_BOUNCED = "email.bounced"
EVENT_COMPLAINED = "email.complained"


class WebhookVerificationError(Exception):
    """Raised when a webhook signature cannot be verified (→ 403)."""


def _signing_key(secret: str) -> bytes:
    """Decode a ``whsec_...`` secret into its raw HMAC key bytes."""
    raw = secret.removeprefix("whsec_")
    try:
        return base64.b64decode(raw)
    except (ValueError, binascii.Error) as exc:  # pragma: no cover - config error
        raise WebhookVerificationError("Malformed webhook secret") from exc


def verify_webhook_signature(
    secret: str,
    svix_id: str | None,
    svix_timestamp: str | None,
    svix_signature: str | None,
    body: bytes,
    *,
    now: float | None = None,
) -> None:
    """Verify a Standard Webhooks signature or raise :class:`WebhookVerificationError`.

    ``now`` is injectable for deterministic tests; it defaults to wall-clock time.
    """
    if not (svix_id and svix_timestamp and svix_signature):
        raise WebhookVerificationError("Missing signature headers")

    try:
        timestamp = int(svix_timestamp)
    except ValueError as exc:
        raise WebhookVerificationError("Invalid timestamp") from exc

    current = int(now if now is not None else time.time())
    if abs(current - timestamp) > _TIMESTAMP_TOLERANCE_SECONDS:
        raise WebhookVerificationError("Timestamp outside tolerance window")

    key = _signing_key(secret)
    # Signed content is the raw bytes joined by literal dots — build it in bytes so a
    # non-UTF-8 body can never desync us from what Resend signed.
    signed_content = svix_id.encode() + b"." + svix_timestamp.encode() + b"." + body
    expected = base64.b64encode(hmac.new(key, signed_content, hashlib.sha256).digest()).decode()

    # The header holds space-separated "v<version>,<b64sig>" entries; accept a match
    # on any v1 entry (constant-time compare to avoid a timing oracle).
    for entry in svix_signature.split(" "):
        version, _, candidate = entry.partition(",")
        if version == "v1" and candidate and hmac.compare_digest(candidate, expected):
            return
    raise WebhookVerificationError("No matching signature")


def _extract_recipients(payload: dict[str, object]) -> list[str]:
    """Pull the recipient address list out of a Resend event payload (``data.to``)."""
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    to = data.get("to")
    if isinstance(to, str):
        return [to]
    if isinstance(to, list):
        return [addr for addr in to if isinstance(addr, str)]
    return []


def apply_email_event(db: Session, event_type: str, payload: dict[str, object]) -> int:
    """Apply a Resend bounce/complaint event; return the number of Member rows updated.

    A hard bounce or a spam complaint is a fact about an **email address**, not about
    one troop's roster — the same person may sit in several tenants under the same
    address, and every one of those sends will fail (bounce) or draw a complaint. So
    this write is deliberately **cross-tenant**: the router passes the BYPASSRLS admin
    session (``AdminDbDep``) — the sanctioned cross-tenant path used by the platform
    control plane. No ``unscoped()`` wrapper is needed: the ORM scoping listener only
    filters SELECTs, and a webhook request resolves no tenant context to filter by.

    - ``email.bounced``   → ``email_bounced = True``.
    - ``email.complained`` → ``email_bounced = True`` **and** ``email_opt_out = True``;
      a spam complaint is a stronger, CAN-SPAM-grade opt-out signal than a bounce, so we
      also suppress future sends the member never explicitly asked to stop.

    Any other event type is a no-op (returns 0) — webhooks must never fail on types we
    don't handle.
    """
    if event_type not in (EVENT_BOUNCED, EVENT_COMPLAINED):
        return 0

    values: dict[str, bool] = {"email_bounced": True}
    if event_type == EVENT_COMPLAINED:
        values["email_opt_out"] = True

    updated = 0
    for address in _unique_normalized(_extract_recipients(payload)):
        # Case-insensitive match: mailbox addressing is not case-sensitive in practice,
        # and a bounce fact should suppress every stored spelling of the address.
        result = db.execute(
            update(Member)
            .where(func.lower(Member.email) == address, Member.is_deleted.is_(False))
            .values(**values)
        )
        # An UPDATE always yields a CursorResult carrying rowcount. Direct
        # (unquoted) cast so CodeQL sees the imports as used — see d206033.
        updated += cast(CursorResult[Any], result).rowcount or 0
    db.commit()
    return updated


def _unique_normalized(addresses: Iterable[str]) -> list[str]:
    """Lower-case, strip, drop blanks, and de-duplicate a list of addresses."""
    seen: dict[str, None] = {}
    for addr in addresses:
        normalized = addr.strip().lower()
        if normalized:
            seen.setdefault(normalized, None)
    return list(seen)


__all__ = [
    "EVENT_BOUNCED",
    "EVENT_COMPLAINED",
    "WebhookVerificationError",
    "apply_email_event",
    "verify_webhook_signature",
]
