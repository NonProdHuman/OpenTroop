"""API tests for /members/ endpoints."""

from fastapi.testclient import TestClient


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
