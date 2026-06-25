"""API tests for /groups/ endpoints (CRUD, membership, role rules, resolution)."""

from fastapi.testclient import TestClient


def _create_group(client: TestClient, name: str = "PLC", group_type: str = "manual") -> dict:
    r = client.post("/groups/", json={"name": name, "group_type": group_type})
    assert r.status_code == 201, r.text
    return r.json()


def _create_member(client: TestClient, first_name: str = "Alice") -> dict:
    r = client.post(
        "/members/",
        json={"first_name": first_name, "last_name": "Scout", "member_type": "scout"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _admin_role_id(client: TestClient) -> str:
    roles = client.get("/roles/").json()
    return next(r["id"] for r in roles if r["slug"] == "administrators")


# --- CRUD -----------------------------------------------------------------


def test_create_group(client: TestClient) -> None:
    data = _create_group(client, "Wolf", "patrol")
    assert data["name"] == "Wolf"
    assert data["group_type"] == "patrol"
    assert data["is_system"] is False
    assert data["is_deleted"] is False


def test_list_groups(client: TestClient) -> None:
    _create_group(client, "Alpha")
    _create_group(client, "Beta")
    names = {g["name"] for g in client.get("/groups/").json()}
    assert {"Alpha", "Beta"} <= names


def test_patch_group(client: TestClient) -> None:
    g = _create_group(client)
    r = client.patch(f"/groups/{g['id']}", json={"name": "Renamed", "color": "#ABCDEF"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert r.json()["color"] == "#ABCDEF"


def test_delete_group(client: TestClient) -> None:
    g = _create_group(client, "Gone")
    deleted = client.delete(f"/groups/{g['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/groups/{g['id']}").status_code == 404


def test_duplicate_name_rejected(client: TestClient) -> None:
    _create_group(client, "Dup")
    r = client.post("/groups/", json={"name": "Dup", "group_type": "manual"})
    assert r.status_code == 409


# --- Manual membership ----------------------------------------------------


def test_add_and_resolve_manual_member(client: TestClient) -> None:
    group = _create_group(client)
    member = _create_member(client)
    r = client.post(f"/groups/{group['id']}/members", json={"member_id": member["id"]})
    assert r.status_code == 201

    resolved = client.get(f"/groups/{group['id']}/members").json()
    assert member["id"] in {m["id"] for m in resolved}


def test_add_member_is_idempotent(client: TestClient) -> None:
    group = _create_group(client)
    member = _create_member(client)
    first = client.post(f"/groups/{group['id']}/members", json={"member_id": member["id"]})
    second = client.post(f"/groups/{group['id']}/members", json={"member_id": member["id"]})
    assert first.json()["id"] == second.json()["id"]
    resolved = client.get(f"/groups/{group['id']}/members").json()
    assert len([m for m in resolved if m["id"] == member["id"]]) == 1


def test_remove_manual_member(client: TestClient) -> None:
    group = _create_group(client)
    member = _create_member(client)
    client.post(f"/groups/{group['id']}/members", json={"member_id": member["id"]})
    deleted = client.delete(f"/groups/{group['id']}/members/{member['id']}")
    assert deleted.status_code == 204
    resolved = client.get(f"/groups/{group['id']}/members").json()
    assert member["id"] not in {m["id"] for m in resolved}


def test_add_member_unknown_member_422(client: TestClient) -> None:
    group = _create_group(client)
    r = client.post(
        f"/groups/{group['id']}/members",
        json={"member_id": "00000000-0000-0000-0000-000000000099"},
    )
    assert r.status_code == 422


def test_patrol_membership_is_exclusive(client: TestClient) -> None:
    """Adding a member to a second PATROL group removes them from the first."""
    p1 = _create_group(client, "Wolf", "patrol")
    p2 = _create_group(client, "Bear", "patrol")
    member = _create_member(client)

    client.post(f"/groups/{p1['id']}/members", json={"member_id": member["id"]})
    client.post(f"/groups/{p2['id']}/members", json={"member_id": member["id"]})

    in_p1 = {m["id"] for m in client.get(f"/groups/{p1['id']}/members").json()}
    in_p2 = {m["id"] for m in client.get(f"/groups/{p2['id']}/members").json()}
    assert member["id"] not in in_p1
    assert member["id"] in in_p2


# --- Dynamic role rules ---------------------------------------------------


def test_role_rule_resolves_dynamic_members(client: TestClient) -> None:
    """A role rule pulls in everyone holding that role (here, the seeded admin)."""
    group = _create_group(client, "Leaders", "dynamic")
    role_id = _admin_role_id(client)

    r = client.post(f"/groups/{group['id']}/rules", json={"role_id": role_id})
    assert r.status_code == 201

    rules = client.get(f"/groups/{group['id']}/rules").json()
    assert any(rule["role_id"] == role_id for rule in rules)

    resolved = client.get(f"/groups/{group['id']}/members").json()
    assert any(m["first_name"] == "Admin" for m in resolved)


def test_remove_role_rule(client: TestClient) -> None:
    group = _create_group(client, "Leaders", "dynamic")
    role_id = _admin_role_id(client)
    client.post(f"/groups/{group['id']}/rules", json={"role_id": role_id})
    deleted = client.delete(f"/groups/{group['id']}/rules/{role_id}")
    assert deleted.status_code == 204
    resolved = client.get(f"/groups/{group['id']}/members").json()
    assert not any(m["first_name"] == "Admin" for m in resolved)


def test_add_rule_unknown_role_422(client: TestClient) -> None:
    group = _create_group(client, "Leaders", "dynamic")
    r = client.post(
        f"/groups/{group['id']}/rules",
        json={"role_id": "00000000-0000-0000-0000-000000000099"},
    )
    assert r.status_code == 422


# --- Tenant isolation -----------------------------------------------------


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    group = _create_group(client)
    assert other_client.get(f"/groups/{group['id']}").status_code == 404
    cross_delete = other_client.delete(f"/groups/{group['id']}")
    assert cross_delete.status_code == 404
    other_ids = {g["id"] for g in other_client.get("/groups/").json()}
    assert group["id"] not in other_ids
