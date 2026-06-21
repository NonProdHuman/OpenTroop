"""API tests for /roles/, /roles/{id}/permissions/, and /role-memberships/ endpoints."""

from fastapi.testclient import TestClient


def _create_role(client: TestClient, slug: str = "event_admin", **kwargs: object) -> dict:
    r = client.post(
        "/roles/", json={"name": slug.replace("_", " ").title(), "slug": slug, **kwargs}
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_create_role(client: TestClient) -> None:
    data = _create_role(client)
    assert data["slug"] == "event_admin"
    assert data["is_system"] is False
    assert data["is_admin"] is False
    assert data["is_deleted"] is False


def test_list_roles(client: TestClient) -> None:
    _create_role(client, "event_admin")
    _create_role(client, "member_admin")
    slugs = {r["slug"] for r in client.get("/roles/").json()}
    assert {"event_admin", "member_admin"} <= slugs


def test_get_role(client: TestClient) -> None:
    role = _create_role(client, "event_admin")
    r = client.get(f"/roles/{role['id']}")
    assert r.status_code == 200
    assert r.json()["slug"] == "event_admin"


def test_patch_role_name(client: TestClient) -> None:
    role = _create_role(client, "event_admin")
    r = client.patch(f"/roles/{role['id']}", json={"name": "Events Administrator"})
    assert r.status_code == 200
    assert r.json()["name"] == "Events Administrator"
    assert r.json()["slug"] == "event_admin"


def test_delete_role(client: TestClient) -> None:
    role = _create_role(client, "temp_role")
    assert client.delete(f"/roles/{role['id']}").status_code == 204
    assert client.get(f"/roles/{role['id']}").status_code == 404


def test_cannot_delete_system_role(client: TestClient) -> None:
    role = _create_role(client, "administrators", is_system=True, is_admin=True)
    r = client.delete(f"/roles/{role['id']}")
    assert r.status_code == 403


def test_deleted_role_excluded_from_list(client: TestClient) -> None:
    role = _create_role(client, "gone_role")
    client.delete(f"/roles/{role['id']}")
    ids = [r["id"] for r in client.get("/roles/").json()]
    assert role["id"] not in ids


# ---------------------------------------------------------------------------
# Role permissions
# ---------------------------------------------------------------------------


def test_add_and_list_permissions(client: TestClient) -> None:
    role = _create_role(client)
    r = client.post(f"/roles/{role['id']}/permissions/", json={"permission": "event:create"})
    assert r.status_code == 201
    assert r.json()["permission"] == "event:create"

    perms = client.get(f"/roles/{role['id']}/permissions/").json()
    assert any(p["permission"] == "event:create" for p in perms)


def test_remove_permission(client: TestClient) -> None:
    role = _create_role(client)
    perm = client.post(
        f"/roles/{role['id']}/permissions/", json={"permission": "member:read"}
    ).json()
    assert client.delete(f"/roles/{role['id']}/permissions/{perm['id']}").status_code == 204
    perms = client.get(f"/roles/{role['id']}/permissions/").json()
    assert not any(p["id"] == perm["id"] for p in perms)


def test_permissions_scoped_to_role(client: TestClient) -> None:
    role_a = _create_role(client, "role_a")
    role_b = _create_role(client, "role_b")
    client.post(f"/roles/{role_a['id']}/permissions/", json={"permission": "event:create"})
    client.post(f"/roles/{role_b['id']}/permissions/", json={"permission": "member:read"})

    a_perms = {p["permission"] for p in client.get(f"/roles/{role_a['id']}/permissions/").json()}
    b_perms = {p["permission"] for p in client.get(f"/roles/{role_b['id']}/permissions/").json()}
    assert a_perms == {"event:create"}
    assert b_perms == {"member:read"}


# ---------------------------------------------------------------------------
# Role memberships
# ---------------------------------------------------------------------------


def test_create_role_membership(client: TestClient) -> None:
    group = _create_role(client, "event_admin")
    position = _create_role(client, "scoutmaster")
    r = client.post(
        "/role-memberships/",
        json={
            "group_role_id": group["id"],
            "member_role_id": position["id"],
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["group_role_id"] == group["id"]
    assert data["member_role_id"] == position["id"]


def test_list_role_memberships(client: TestClient) -> None:
    group = _create_role(client, "event_admin")
    pos1 = _create_role(client, "scoutmaster")
    pos2 = _create_role(client, "assistant_sm")
    client.post(
        "/role-memberships/", json={"group_role_id": group["id"], "member_role_id": pos1["id"]}
    )
    client.post(
        "/role-memberships/", json={"group_role_id": group["id"], "member_role_id": pos2["id"]}
    )
    memberships = client.get("/role-memberships/").json()
    member_role_ids = {m["member_role_id"] for m in memberships}
    assert {pos1["id"], pos2["id"]} <= member_role_ids


def test_delete_role_membership(client: TestClient) -> None:
    group = _create_role(client, "event_admin")
    position = _create_role(client, "scoutmaster")
    m = client.post(
        "/role-memberships/", json={"group_role_id": group["id"], "member_role_id": position["id"]}
    ).json()
    assert client.delete(f"/role-memberships/{m['id']}").status_code == 204
    assert client.get(f"/role-memberships/{m['id']}").status_code == 404


def test_role_membership_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    group = _create_role(client, "event_admin")
    position = _create_role(other_client, "scoutmaster")
    r = client.post(
        "/role-memberships/", json={"group_role_id": group["id"], "member_role_id": position["id"]}
    )
    assert r.status_code == 422


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    role = _create_role(client)
    assert other_client.get(f"/roles/{role['id']}").status_code == 404
    assert other_client.delete(f"/roles/{role['id']}").status_code == 404
    ids = [r["id"] for r in other_client.get("/roles/").json()]
    assert role["id"] not in ids
