"""API tests for /members/ endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.member import Member
from tests.conftest import NEW_USER_ID, TENANT_A


def _create_member(client: TestClient, **overrides: object) -> dict:
    payload = {
        "first_name": "Alice",
        "last_name": "Smith",
        "member_type": "scout",
        **overrides,
    }
    r = client.post("/members/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_member(client: TestClient) -> None:
    data = _create_member(client)
    assert data["first_name"] == "Alice"
    assert data["member_type"] == "scout"
    assert data["membership_status"] == "active"
    assert data["is_deleted"] is False


def test_list_members(client: TestClient) -> None:
    _create_member(client, first_name="Alice")
    _create_member(client, first_name="Bob")
    r = client.get("/members/")
    assert r.status_code == 200
    names = {m["first_name"] for m in r.json()}
    assert {"Alice", "Bob"} <= names


def test_get_member(client: TestClient) -> None:
    m = _create_member(client)
    r = client.get(f"/members/{m['id']}")
    assert r.status_code == 200
    assert r.json()["last_name"] == "Smith"


def test_patch_member(client: TestClient) -> None:
    m = _create_member(client)
    r = client.patch(f"/members/{m['id']}", json={"nickname": "Ali", "membership_status": "alumni"})
    assert r.status_code == 200
    body = r.json()
    assert body["nickname"] == "Ali"
    assert body["membership_status"] == "alumni"
    assert body["is_deleted"] is False


def test_delete_member(client: TestClient) -> None:
    m = _create_member(client)
    assert client.delete(f"/members/{m['id']}").status_code == 204
    assert client.get(f"/members/{m['id']}").status_code == 404


def test_deleted_excluded_from_list(client: TestClient) -> None:
    m = _create_member(client)
    client.delete(f"/members/{m['id']}")
    ids = [x["id"] for x in client.get("/members/").json()]
    assert m["id"] not in ids


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    m = _create_member(client)
    assert other_client.get(f"/members/{m['id']}").status_code == 404
    assert other_client.delete(f"/members/{m['id']}").status_code == 404
    ids = [x["id"] for x in other_client.get("/members/").json()]
    assert m["id"] not in ids


def test_update_member_to_adult_clears_patrol_memberships(client: TestClient) -> None:
    # Create a patrol group
    patrol = client.post("/groups/", json={"name": "Wolf", "group_type": "patrol"}).json()
    # Create a scout member
    m = _create_member(client)
    # Add scout to the patrol
    client.post(f"/groups/{patrol['id']}/members", json={"member_id": m["id"]})
    # Verify membership exists
    members = client.get(f"/groups/{patrol['id']}/members").json()
    assert m["id"] in {x["id"] for x in members}
    # Update scout member to adult
    r = client.patch(f"/members/{m['id']}", json={"member_type": "adult"})
    assert r.status_code == 200
    # Verify patrol membership has been cleared
    members_after = client.get(f"/groups/{patrol['id']}/members").json()
    assert m["id"] not in {x["id"] for x in members_after}


def test_patch_member_field_gating_basic_member_rejected(
    client: TestClient, claim_client: TestClient, db_session: Session
) -> None:
    # Create member as admin
    m_data = _create_member(client)

    # Manually link the claim_client's user_id to this member
    import uuid

    m = db_session.get(Member, uuid.UUID(m_data["id"]))
    m.user_id = NEW_USER_ID
    db_session.commit()

    # Issue requests as the basic member
    claim_client.headers["X-Tenant-ID"] = str(TENANT_A)

    # Allowed field (allergies)
    r = claim_client.patch(f"/members/{m.id}", json={"allergies": "Peanuts"})
    assert r.status_code == 200, r.text

    # Restricted field (bsa_id)
    r = claim_client.patch(f"/members/{m.id}", json={"bsa_id": "12345"})
    assert "Not authorized to edit field: bsa_id" in r.text
