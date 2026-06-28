"""API tests for /functional-roles/ and its permissions sub-resource."""

from fastapi.testclient import TestClient


def _create_role(client: TestClient, slug: str = "event-admins") -> dict:
    r = client.post(
        "/functional-roles/", json={"name": slug.replace("-", " ").title(), "slug": slug}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _administrators_role(client: TestClient) -> dict:
    """The seeded is_admin functional role (created by the admin fixture)."""
    roles = client.get("/functional-roles/").json()
    return next(r for r in roles if r["is_admin"])


def test_create_functional_role(client: TestClient) -> None:
    data = _create_role(client)
    assert data["slug"] == "event-admins"
    assert data["is_system"] is False
    assert data["is_admin"] is False  # custom roles are never is_admin


def test_list_functional_roles(client: TestClient) -> None:
    _create_role(client, "event-admins")
    _create_role(client, "member-admins")
    slugs = {r["slug"] for r in client.get("/functional-roles/").json()}
    assert {"event-admins", "member-admins"} <= slugs


def test_patch_functional_role_name(client: TestClient) -> None:
    role = _create_role(client)
    r = client.patch(f"/functional-roles/{role['id']}", json={"name": "Events Admins"})
    assert r.status_code == 200
    assert r.json()["name"] == "Events Admins"
    assert r.json()["slug"] == "event-admins"


def test_delete_functional_role(client: TestClient) -> None:
    role = _create_role(client, "temp-role")
    resp = client.delete(f"/functional-roles/{role['id']}")
    assert resp.status_code == 204
    assert client.get(f"/functional-roles/{role['id']}").status_code == 404


def test_cannot_delete_system_functional_role(client: TestClient) -> None:
    admins = _administrators_role(client)
    assert admins["is_system"] is True
    resp = client.delete(f"/functional-roles/{admins['id']}")
    assert resp.status_code == 403


def test_add_and_list_permissions(client: TestClient) -> None:
    role = _create_role(client)
    r = client.post(
        f"/functional-roles/{role['id']}/permissions", json={"permission": "event:create"}
    )
    assert r.status_code == 201
    assert r.json()["permission"] == "event:create"

    perms = client.get(f"/functional-roles/{role['id']}/permissions").json()
    assert any(p["permission"] == "event:create" for p in perms)


def test_add_permission_is_idempotent(client: TestClient) -> None:
    role = _create_role(client)
    first = client.post(
        f"/functional-roles/{role['id']}/permissions", json={"permission": "member:read"}
    ).json()
    second = client.post(
        f"/functional-roles/{role['id']}/permissions", json={"permission": "member:read"}
    ).json()
    assert first["id"] == second["id"]


def test_remove_permission(client: TestClient) -> None:
    role = _create_role(client)
    client.post(f"/functional-roles/{role['id']}/permissions", json={"permission": "member:read"})
    resp = client.delete(f"/functional-roles/{role['id']}/permissions/member:read")
    assert resp.status_code == 204
    perms = {
        p["permission"] for p in client.get(f"/functional-roles/{role['id']}/permissions").json()
    }
    assert "member:read" not in perms


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    role = _create_role(client)
    assert other_client.get(f"/functional-roles/{role['id']}").status_code == 404
    ids = [r["id"] for r in other_client.get("/functional-roles/").json()]
    assert role["id"] not in ids
