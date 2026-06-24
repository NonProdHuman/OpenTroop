"""API tests for POST /tenants/ — platform-admin tenant provisioning + founder invite."""

from fastapi.testclient import TestClient

from tests.conftest import NEW_USER_ID


def _provision(client: TestClient, slug: str = "troop123", **overrides: object) -> dict:
    payload = {
        "name": "Troop 123",
        "slug": slug,
        "founder_first_name": "Jane",
        "founder_last_name": "Leader",
        "founder_email": "jane@example.com",
        **overrides,
    }
    r = client.post("/tenants/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_provision_creates_tenant(platform_admin_client: TestClient) -> None:
    data = _provision(platform_admin_client)
    assert data["name"] == "Troop 123"
    assert data["slug"] == "troop123"
    assert data["is_deleted"] is False
    # The founder is invited, not auto-claimed.
    assert data["founder_member_id"]
    assert data["invite_token"]
    assert data["invite_expires_at"]


def test_provision_slug_conflict(platform_admin_client: TestClient) -> None:
    _provision(platform_admin_client, "troop456")
    r = platform_admin_client.post(
        "/tenants/",
        json={
            "name": "Other",
            "slug": "troop456",
            "founder_first_name": "X",
            "founder_last_name": "Y",
        },
    )
    assert r.status_code == 409


def test_provision_requires_platform_admin(claim_client: TestClient) -> None:
    """An ordinary signed-in user (no platform_role) cannot create tenants."""
    r = claim_client.post(
        "/tenants/",
        json={"name": "X", "slug": "x", "founder_first_name": "A", "founder_last_name": "B"},
    )
    assert r.status_code == 403


def test_provision_no_auth_returns_401(platform_admin_client: TestClient) -> None:
    """Requests without the X-Test-User-ID header are treated as unauthenticated."""
    r = platform_admin_client.post(
        "/tenants/",
        json={"name": "X", "slug": "x", "founder_first_name": "A", "founder_last_name": "B"},
        headers={"X-Test-User-ID": ""},  # clear the default header
    )
    assert r.status_code == 401


def test_founder_claims_then_administers(
    platform_admin_client: TestClient, claim_client: TestClient
) -> None:
    """End-to-end: platform admin provisions; founder claims the invite, then has admin access."""
    tenant = _provision(platform_admin_client, "troop789")
    tenant_id = tenant["id"]

    # Before claiming, the founder is not yet a member — tenant routes are forbidden.
    assert claim_client.get("/members/", headers={"X-Tenant-ID": tenant_id}).status_code == 403

    # Founder claims their account with the returned invite token.
    claimed = claim_client.post("/auth/claim", json={"token": tenant["invite_token"]})
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["id"] == tenant["founder_member_id"]
    assert claimed.json()["user_id"] == str(NEW_USER_ID)

    # Now linked, the founder holds the administrators role and can read the roster.
    members = claim_client.get("/members/", headers={"X-Tenant-ID": tenant_id}).json()
    assert len(members) == 1
    assert members[0]["first_name"] == "Jane"
    assert members[0]["user_id"] == str(NEW_USER_ID)
