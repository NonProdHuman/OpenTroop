"""Tests for the Resend email bounce/complaint webhook (GH-80)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import email_webhooks
from app.core.config import settings
from app.core.email_webhooks import (
    WebhookVerificationError,
    verify_webhook_signature,
)
from app.models.enums import MemberType
from app.models.member import Member

from .conftest import TENANT_A, TENANT_B

# A deterministic test secret: whsec_ + base64("super-secret-signing-key-000000").
_SECRET_KEY = b"super-secret-signing-key-000000"
_SECRET = "whsec_" + base64.b64encode(_SECRET_KEY).decode()


def _sign(body: bytes, *, secret: str = _SECRET, timestamp: int | None = None) -> dict[str, str]:
    """Build valid svix signature headers over *body* using the same HMAC scheme."""
    msg_id = f"msg_{uuid.uuid4().hex}"
    ts = timestamp if timestamp is not None else int(time.time())
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed_content = f"{msg_id}.{ts}.".encode() + body
    sig = base64.b64encode(hmac.new(key, signed_content, hashlib.sha256).digest()).decode()
    return {
        "svix-id": msg_id,
        "svix-timestamp": str(ts),
        "svix-signature": f"v1,{sig}",
    }


def _event_body(event_type: str, to: list[str] | str) -> bytes:
    return json.dumps({"type": event_type, "data": {"to": to}}).encode()


# --------------------------------------------------------------------------- #
# Signature verification unit tests
# --------------------------------------------------------------------------- #


def test_verify_valid_signature() -> None:
    body = b'{"type":"email.bounced"}'
    headers = _sign(body)
    # Does not raise.
    verify_webhook_signature(
        _SECRET,
        headers["svix-id"],
        headers["svix-timestamp"],
        headers["svix-signature"],
        body,
    )


def test_verify_wrong_signature() -> None:
    body = b'{"type":"email.bounced"}'
    headers = _sign(body)
    with pytest.raises(WebhookVerificationError):
        verify_webhook_signature(
            _SECRET,
            headers["svix-id"],
            headers["svix-timestamp"],
            "v1," + base64.b64encode(b"not-the-right-signature").decode(),
            body,
        )


def test_verify_tampered_body() -> None:
    body = b'{"type":"email.bounced"}'
    headers = _sign(body)
    with pytest.raises(WebhookVerificationError):
        verify_webhook_signature(
            _SECRET,
            headers["svix-id"],
            headers["svix-timestamp"],
            headers["svix-signature"],
            body + b" tampered",
        )


def test_verify_stale_timestamp() -> None:
    body = b'{"type":"email.bounced"}'
    old = int(time.time()) - 6 * 60  # outside the 5-minute window
    headers = _sign(body, timestamp=old)
    with pytest.raises(WebhookVerificationError):
        verify_webhook_signature(
            _SECRET,
            headers["svix-id"],
            headers["svix-timestamp"],
            headers["svix-signature"],
            body,
        )


def test_verify_future_timestamp() -> None:
    body = b'{"type":"email.bounced"}'
    future = int(time.time()) + 6 * 60
    headers = _sign(body, timestamp=future)
    with pytest.raises(WebhookVerificationError):
        verify_webhook_signature(
            _SECRET,
            headers["svix-id"],
            headers["svix-timestamp"],
            headers["svix-signature"],
            body,
        )


@pytest.mark.parametrize("missing", ["svix-id", "svix-timestamp", "svix-signature"])
def test_verify_missing_headers(missing: str) -> None:
    body = b'{"type":"email.bounced"}'
    headers = _sign(body)
    headers[missing] = ""  # simulate an absent header (None in the router)
    with pytest.raises(WebhookVerificationError):
        verify_webhook_signature(
            _SECRET,
            headers["svix-id"] or None,
            headers["svix-timestamp"] or None,
            headers["svix-signature"] or None,
            body,
        )


def test_verify_multiple_signature_entries() -> None:
    """A header with several space-separated entries verifies if any v1 entry matches."""
    body = b'{"type":"email.bounced"}'
    headers = _sign(body)
    combined = "v2,otherscheme " + headers["svix-signature"]
    verify_webhook_signature(
        _SECRET,
        headers["svix-id"],
        headers["svix-timestamp"],
        combined,
        body,
    )


# --------------------------------------------------------------------------- #
# Endpoint tests
# --------------------------------------------------------------------------- #


def _add_member(db: Session, tenant_id: uuid.UUID, email: str | None) -> uuid.UUID:
    member = Member(
        tenant_id=tenant_id,
        first_name="Test",
        last_name="Member",
        member_type=MemberType.ADULT,
        email=email,
    )
    db.add(member)
    db.flush()
    return member.id


@pytest.fixture
def _webhook_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "resend_webhook_secret", _SECRET)
    return _SECRET


def test_bounce_flips_flag_across_tenants(
    client: TestClient, db_session: Session, _webhook_secret: str
) -> None:
    a_id = _add_member(db_session, TENANT_A, "shared@example.com")
    b_id = _add_member(db_session, TENANT_B, "SHARED@example.com")  # case-insensitive
    other_id = _add_member(db_session, TENANT_A, "someone-else@example.com")
    db_session.commit()

    body = _event_body("email.bounced", ["shared@example.com"])
    resp = client.post("/webhooks/email/resend", content=body, headers=_sign(body))
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    db_session.expire_all()
    assert db_session.get(Member, a_id).email_bounced is True
    assert db_session.get(Member, b_id).email_bounced is True
    # A complaint flag is not set by a bounce.
    assert db_session.get(Member, a_id).email_opt_out is False
    # An unrelated address is untouched.
    assert db_session.get(Member, other_id).email_bounced is False


def test_complaint_flips_both_flags(
    client: TestClient, db_session: Session, _webhook_secret: str
) -> None:
    m_id = _add_member(db_session, TENANT_A, "spammy@example.com")
    db_session.commit()

    body = _event_body("email.complained", ["spammy@example.com"])
    resp = client.post("/webhooks/email/resend", content=body, headers=_sign(body))
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1

    db_session.expire_all()
    member = db_session.get(Member, m_id)
    assert member.email_bounced is True
    assert member.email_opt_out is True


def test_unknown_event_type_is_noop(
    client: TestClient, db_session: Session, _webhook_secret: str
) -> None:
    m_id = _add_member(db_session, TENANT_A, "delivered@example.com")
    db_session.commit()

    body = _event_body("email.delivered", ["delivered@example.com"])
    resp = client.post("/webhooks/email/resend", content=body, headers=_sign(body))
    assert resp.status_code == 200
    assert resp.json()["updated"] == 0

    db_session.expire_all()
    assert db_session.get(Member, m_id).email_bounced is False


def test_bad_signature_is_403(
    client: TestClient, db_session: Session, _webhook_secret: str
) -> None:
    body = _event_body("email.bounced", ["x@example.com"])
    headers = _sign(body)
    headers["svix-signature"] = "v1," + base64.b64encode(b"wrong").decode()
    resp = client.post("/webhooks/email/resend", content=body, headers=headers)
    assert resp.status_code == 403


def test_missing_signature_headers_is_403(client: TestClient, _webhook_secret: str) -> None:
    body = _event_body("email.bounced", ["x@example.com"])
    resp = client.post("/webhooks/email/resend", content=body)
    assert resp.status_code == 403


def test_endpoint_404_when_secret_unset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "resend_webhook_secret", "")
    body = _event_body("email.bounced", ["x@example.com"])
    resp = client.post("/webhooks/email/resend", content=body, headers=_sign(body))
    assert resp.status_code == 404


def test_apply_email_event_ignores_unknown_type(db_session: Session) -> None:
    """Unit-level guard: apply_email_event is a no-op for non-bounce/complaint types."""
    _add_member(db_session, TENANT_A, "a@example.com")
    db_session.commit()
    updated = email_webhooks.apply_email_event(
        db_session, "email.opened", {"data": {"to": ["a@example.com"]}}
    )
    assert updated == 0
