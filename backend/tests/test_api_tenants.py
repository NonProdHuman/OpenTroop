"""API tests for POST /tenants/ (tenant provisioning + first-admin bootstrap)."""

from fastapi.testclient import TestClient

from tests.conftest import NEW_USER_ID, TENANT_A


def _provision(client: TestClient, slug: str = "troop123", **overrides: object) -> dict:
    payload = {
        "name": "Troop 123",
        "slug": slug,
        "founder_first_name": "Jane",
        "founder_last_name": "Leader",
        **overrides,
    }
    r = client.post("/tenants/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_provision_creates_tenant(claim_client: TestClient) -> None:
    data = _provision(claim_client)
    assert data["name"] == "Troop 123"
    assert data["slug"] == "troop123"
    assert data["is_deleted"] is False


def test_provision_slug_conflict(claim_client: TestClient) -> None:
    _provision(claim_client, "troop456")
    r = claim_client.post(
        "/tenants/",
        json={"name": "Other", "slug": "troop456", "founder_first_name": "X", "founder_last_name": "Y"},
    )
    assert r.status_code == 409


def test_provision_founder_becomes_admin(claim_client: TestClient) -> None:
    """After provisioning, the founder can perform admin actions on their new tenant."""
    tenant = _provision(claim_client, "troop789")
    tenant_id = tenant["id"]

    # Send the new tenant UUID so the tenant-scoped endpoints resolve correctly.
    r = claim_client.get("/members/", headers={"X-Tenant-ID": tenant_id})
    assert r.status_code == 200
    members = r.json()
    # Only the founder's Member was created.
    assert len(members) == 1
    assert members[0]["first_name"] == "Jane"
    assert members[0]["user_id"] == str(NEW_USER_ID)


def test_provision_no_auth_returns_401(claim_client: TestClient) -> None:
    """Requests without the X-Test-User-ID header are treated as unauthenticated."""
    r = claim_client.post(
        "/tenants/",
        json={"name": "X", "slug": "x", "founder_first_name": "A", "founder_last_name": "B"},
        headers={"X-Test-User-ID": ""},  # clear the default header
    )
    assert r.status_code == 401
