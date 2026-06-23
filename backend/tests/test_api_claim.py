"""API tests for the invite/claim flow:
  POST /members/{id}/invite  — admin generates a claim token
  POST /auth/claim           — new user links their account to a Member record
"""

import jwt
from fastapi.testclient import TestClient

from app.core.config import settings
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


def test_invite_already_claimed_returns_409(client: TestClient) -> None:
    """Cannot generate an invite for a member who already has a user account."""
    # The seeded admin member already has user_id set
    from tests.conftest import _ADMIN_MEMBER_IDS

    admin_member_id = str(_ADMIN_MEMBER_IDS[TENANT_A])
    r = client.post(f"/members/{admin_member_id}/invite")
    assert r.status_code == 409


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
        {"sub": "00000000-0000-0000-0000-000000000000", "tid": str(TENANT_A), "type": "other"},
        settings.app_secret,
        algorithm="HS256",
    )
    r = claim_client.post("/auth/claim", json={"token": bad})
    assert r.status_code == 400
