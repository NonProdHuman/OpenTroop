"""API tests for /patrols/ endpoints."""

from fastapi.testclient import TestClient


def _create_patrol(client: TestClient, name: str = "Eagle") -> dict:
    r = client.post("/patrols/", json={"name": name})
    assert r.status_code == 201
    return r.json()


def test_create_patrol(client: TestClient) -> None:
    data = _create_patrol(client)
    assert data["name"] == "Eagle"
    assert data["is_deleted"] is False
    assert "id" in data
    assert "created_at" in data


def test_list_patrols(client: TestClient) -> None:
    _create_patrol(client, "Alpha")
    _create_patrol(client, "Beta")
    r = client.get("/patrols/")
    assert r.status_code == 200
    names = {p["name"] for p in r.json()}
    assert {"Alpha", "Beta"} <= names


def test_get_patrol(client: TestClient) -> None:
    patrol = _create_patrol(client)
    r = client.get(f"/patrols/{patrol['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Eagle"


def test_patch_patrol(client: TestClient) -> None:
    patrol = _create_patrol(client)
    r = client.patch(f"/patrols/{patrol['id']}", json={"name": "Hawk"})
    assert r.status_code == 200
    assert r.json()["name"] == "Hawk"


def test_delete_patrol(client: TestClient) -> None:
    patrol = _create_patrol(client)
    r = client.delete(f"/patrols/{patrol['id']}")
    assert r.status_code == 204

    r = client.get(f"/patrols/{patrol['id']}")
    assert r.status_code == 404


def test_deleted_patrol_excluded_from_list(client: TestClient) -> None:
    patrol = _create_patrol(client, "Gone")
    client.delete(f"/patrols/{patrol['id']}")
    ids = [p["id"] for p in client.get("/patrols/").json()]
    assert patrol["id"] not in ids


def test_get_nonexistent_patrol(client: TestClient) -> None:
    r = client.get("/patrols/00000000-0000-0000-0000-000000000099")
    assert r.status_code == 404


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    patrol = _create_patrol(client)
    assert other_client.get(f"/patrols/{patrol['id']}").status_code == 404
    assert other_client.delete(f"/patrols/{patrol['id']}").status_code == 404

    other_patrols = [p["id"] for p in other_client.get("/patrols/").json()]
    assert patrol["id"] not in other_patrols
