"""API tests for the invite/claim flow:
POST /members/{id}/invite  — admin generates a claim token
POST /auth/claim           — new user links their account to a Member record
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_notification_service
from app.core.invite import build_claim_url
from app.core.notifications import (
    EmailMessage,
    EmailSendError,
    FakeEmailBackend,
    NotificationService,
)
from app.main import app
from app.models.member import Member
from app.models.tenant import Tenant
from tests.conftest import NEW_USER_ID, TENANT_A


def _create_member(client: TestClient, **overrides: object) -> dict:
    payload = {"first_name": "Bob", "last_name": "Scout", "member_type": "scout", **overrides}
    r = client.post("/members/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _invite(client: TestClient, member_id: str) -> dict:
    r = client.post(f"/members/{member_id}/invite")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Invite endpoint
# ---------------------------------------------------------------------------


def test_invite_returns_token(client: TestClient) -> None:
    member = _create_member(client)
    data = _invite(client, member["id"])
    assert "token" in data
    assert "expires_at" in data


def test_invite_token_encodes_correct_ids(client: TestClient) -> None:
    member = _create_member(client)
    data = _invite(client, member["id"])
    payload = jwt.decode(data["token"], settings.app_secret, algorithms=["HS256"])
    assert payload["sub"] == member["id"]
    assert payload["tid"] == str(TENANT_A)
    assert payload["type"] == "member_claim"
    assert payload["jti"]  # single-use marker, persisted on the member


def test_invite_persists_jti_on_member(client: TestClient, db_session: Session) -> None:
    member = _create_member(client)
    data = _invite(client, member["id"])
    payload = jwt.decode(data["token"], settings.app_secret, algorithms=["HS256"])
    row = db_session.get(Member, uuid.UUID(member["id"]))
    assert row is not None
    assert row.invite_token_jti == payload["jti"]


def test_invite_already_claimed_returns_409(client: TestClient) -> None:
    """Cannot generate an invite for a member who already has a user account."""
    # The seeded admin member already has user_id set
    from tests.conftest import _ADMIN_MEMBER_IDS

    admin_member_id = str(_ADMIN_MEMBER_IDS[TENANT_A])
    r = client.post(f"/members/{admin_member_id}/invite")
    assert r.status_code == 409


def test_invite_without_email_does_not_send(client: TestClient) -> None:
    member = _create_member(client)
    data = _invite(client, member["id"])
    assert data["email_sent"] is False


def test_invite_sends_email_when_member_has_address(
    client: TestClient, db_session: Session
) -> None:
    db_session.add(Tenant(id=TENANT_A, name="Troop 42", slug="troop42"))
    db_session.commit()
    fake_backend = FakeEmailBackend()
    app.dependency_overrides[get_notification_service] = lambda: NotificationService(
        email_backend=fake_backend
    )

    member = _create_member(client, email="scout@example.com")
    data = _invite(client, member["id"])

    assert data["email_sent"] is True
    assert len(fake_backend.sent) == 1
    sent = fake_backend.sent[0]
    assert sent.to == "scout@example.com"
    assert build_claim_url("troop42", data["token"]) in sent.html_body


def test_invite_skips_send_for_opted_out_member(client: TestClient, db_session: Session) -> None:
    db_session.add(Tenant(id=TENANT_A, name="Troop 42", slug="troop42"))
    db_session.commit()
    fake_backend = FakeEmailBackend()
    app.dependency_overrides[get_notification_service] = lambda: NotificationService(
        email_backend=fake_backend
    )

    member = _create_member(client, email="scout@example.com")
    patch = client.patch(f"/members/{member['id']}", json={"email_opt_out": True})
    assert patch.status_code == 200

    data = _invite(client, member["id"])

    assert data["email_sent"] is False
    assert fake_backend.sent == []


def test_invite_send_failure_still_returns_token(client: TestClient, db_session: Session) -> None:
    db_session.add(Tenant(id=TENANT_A, name="Troop 42", slug="troop42"))
    db_session.commit()

    class FailingBackend:
        def send(self, message: EmailMessage) -> None:
            raise EmailSendError("boom")

    app.dependency_overrides[get_notification_service] = lambda: NotificationService(
        email_backend=FailingBackend()
    )

    member = _create_member(client, email="scout@example.com")
    data = _invite(client, member["id"])

    assert data["email_sent"] is False
    assert "token" in data


# ---------------------------------------------------------------------------
# Claim endpoint
# ---------------------------------------------------------------------------


def test_claim_links_user_to_member(client: TestClient, claim_client: TestClient) -> None:
    member = _create_member(client)
    assert member["user_id"] is None

    token = _invite(client, member["id"])["token"]
    r = claim_client.post("/auth/claim", json={"token": token})
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == member["id"]
    assert data["user_id"] == str(NEW_USER_ID)


def test_claim_idempotent(client: TestClient, claim_client: TestClient) -> None:
    """Claiming the same member twice with the same user returns 200 both times."""
    member = _create_member(client)
    token = _invite(client, member["id"])["token"]
    claim_client.post("/auth/claim", json={"token": token})
    r = claim_client.post("/auth/claim", json={"token": token})
    assert r.status_code == 200
    assert r.json()["user_id"] == str(NEW_USER_ID)


def test_claim_conflict_already_member(client: TestClient) -> None:
    """The admin user is already a member of TENANT_A — claim should 409."""
    member = _create_member(client)
    token = _invite(client, member["id"])["token"]
    # client acts as ADMIN_USER_ID, who already has a member record in TENANT_A
    r = client.post("/auth/claim", json={"token": token})
    assert r.status_code == 409


def test_claim_invalid_token(claim_client: TestClient) -> None:
    r = claim_client.post("/auth/claim", json={"token": "not-a-valid-token"})
    assert r.status_code == 400


def test_claim_wrong_token_type(claim_client: TestClient) -> None:
    """A token with a different type field must be rejected."""
    bad = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "tid": str(TENANT_A),
            "type": "other",
            "jti": "abc",
            "exp": datetime.now(UTC) + timedelta(days=1),
        },
        settings.app_secret,
        algorithm="HS256",
    )
    r = claim_client.post("/auth/claim", json={"token": bad})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Single-use / revocable tokens (GH-110)
# ---------------------------------------------------------------------------


def test_claim_token_without_jti_rejected(client: TestClient, claim_client: TestClient) -> None:
    """Legacy-style tokens (minted before single-use enforcement) are rejected."""
    member = _create_member(client)
    legacy = jwt.encode(
        {
            "sub": member["id"],
            "tid": str(TENANT_A),
            "type": "member_claim",
            "exp": datetime.now(UTC) + timedelta(days=1),
        },
        settings.app_secret,
        algorithm="HS256",
    )
    r = claim_client.post("/auth/claim", json={"token": legacy})
    assert r.status_code == 400


def test_reinvite_revokes_previous_token(client: TestClient, claim_client: TestClient) -> None:
    """Minting a new invite rotates the stored jti, so the earlier token dies."""
    member = _create_member(client)
    old_token = _invite(client, member["id"])["token"]
    new_token = _invite(client, member["id"])["token"]

    r = claim_client.post("/auth/claim", json={"token": old_token})
    assert r.status_code == 400

    r = claim_client.post("/auth/claim", json={"token": new_token})
    assert r.status_code == 200


def test_claim_clears_jti(
    client: TestClient, claim_client: TestClient, db_session: Session
) -> None:
    """A redeemed token is single-use: the stored jti is cleared on claim."""
    member = _create_member(client)
    token = _invite(client, member["id"])["token"]
    r = claim_client.post("/auth/claim", json={"token": token})
    assert r.status_code == 200

    row = db_session.get(Member, uuid.UUID(member["id"]))
    assert row is not None
    assert row.invite_token_jti is None


def test_claimed_token_cannot_be_replayed_after_unlink(
    client: TestClient, claim_client: TestClient, db_session: Session
) -> None:
    """If the link is later removed, the spent token must not work again."""
    member = _create_member(client)
    token = _invite(client, member["id"])["token"]
    assert claim_client.post("/auth/claim", json={"token": token}).status_code == 200

    # Simulate an admin unlinking the account (e.g. offboarding, created in error).
    row = db_session.get(Member, uuid.UUID(member["id"]))
    assert row is not None
    row.user_id = None
    db_session.commit()

    r = claim_client.post("/auth/claim", json={"token": token})
    assert r.status_code == 400
