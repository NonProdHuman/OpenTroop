"""API tests for /positions/ and the position↔functional-role mapping."""

from fastapi.testclient import TestClient


def _create_position(client: TestClient, slug: str = "scoutmaster", **kwargs: object) -> dict:
    body = {"name": slug.replace("-", " ").title(), "slug": slug, **kwargs}
    r = client.post("/positions/", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _create_functional_role(client: TestClient, slug: str = "event-admins") -> dict:
    r = client.post(
        "/functional-roles/", json={"name": slug.replace("-", " ").title(), "slug": slug}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _administrator_position(client: TestClient) -> dict:
    """The seeded Administrator position (created by the admin fixture)."""
    positions = client.get("/positions/").json()
    return next(p for p in positions if p["is_system"])


def test_create_position(client: TestClient) -> None:
    data = _create_position(client, "patrol-leader", applies_to="scout")
    assert data["slug"] == "patrol-leader"
    assert data["applies_to"] == "scout"
    assert data["is_system"] is False
    assert data["sort_order"] == 0


def test_list_positions_sorted(client: TestClient) -> None:
    _create_position(client, "b-pos", sort_order=2)
    _create_position(client, "a-pos", sort_order=1)
    slugs = [p["slug"] for p in client.get("/positions/").json()]
    assert "a-pos" in slugs and "b-pos" in slugs


def test_patch_position(client: TestClient) -> None:
    pos = _create_position(client)
    r = client.patch(f"/positions/{pos['id']}", json={"name": "Scout Master", "sort_order": 5})
    assert r.status_code == 200
    assert r.json()["name"] == "Scout Master"
    assert r.json()["sort_order"] == 5


def test_delete_position(client: TestClient) -> None:
    pos = _create_position(client, "temp-pos")
    resp = client.delete(f"/positions/{pos['id']}")
    assert resp.status_code == 204
    assert client.get(f"/positions/{pos['id']}").status_code == 404


def test_cannot_delete_system_position(client: TestClient) -> None:
    admin_pos = _administrator_position(client)
    resp = client.delete(f"/positions/{admin_pos['id']}")
    assert resp.status_code == 403


def test_map_functional_role_to_position(client: TestClient) -> None:
    pos = _create_position(client)
    role = _create_functional_role(client)
    r = client.post(
        f"/positions/{pos['id']}/functional-roles", json={"functional_role_id": role["id"]}
    )
    assert r.status_code == 201
    assert r.json()["functional_role_id"] == role["id"]

    links = client.get(f"/positions/{pos['id']}/functional-roles").json()
    assert any(link["functional_role_id"] == role["id"] for link in links)


def test_map_is_idempotent(client: TestClient) -> None:
    pos = _create_position(client)
    role = _create_functional_role(client)
    first = client.post(
        f"/positions/{pos['id']}/functional-roles", json={"functional_role_id": role["id"]}
    ).json()
    second = client.post(
        f"/positions/{pos['id']}/functional-roles", json={"functional_role_id": role["id"]}
    ).json()
    assert first["id"] == second["id"]


def test_detach_functional_role(client: TestClient) -> None:
    pos = _create_position(client)
    role = _create_functional_role(client)
    client.post(f"/positions/{pos['id']}/functional-roles", json={"functional_role_id": role["id"]})
    resp = client.delete(f"/positions/{pos['id']}/functional-roles/{role['id']}")
    assert resp.status_code == 204
    links = client.get(f"/positions/{pos['id']}/functional-roles").json()
    assert not any(link["functional_role_id"] == role["id"] for link in links)


def test_map_wrong_tenant_functional_role(client: TestClient, other_client: TestClient) -> None:
    pos = _create_position(client)
    foreign_role = _create_functional_role(other_client, "foreign")
    r = client.post(
        f"/positions/{pos['id']}/functional-roles",
        json={"functional_role_id": foreign_role["id"]},
    )
    assert r.status_code == 422


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    pos = _create_position(client)
    assert other_client.get(f"/positions/{pos['id']}").status_code == 404
    ids = [p["id"] for p in other_client.get("/positions/").json()]
    assert pos["id"] not in ids
