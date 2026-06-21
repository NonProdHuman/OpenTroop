"""API tests for /role-assignments/ endpoints."""

from fastapi.testclient import TestClient


def _create_member(client: TestClient, first_name: str = "Alice") -> dict:
    r = client.post(
        "/members/",
        json={
            "first_name": first_name,
            "last_name": "Test",
            "member_type": "adult",
        },
    )
    assert r.status_code == 201
    return r.json()


def _create_role(client: TestClient, slug: str = "event_admin") -> dict:
    r = client.post("/roles/", json={"name": slug.replace("_", " ").title(), "slug": slug})
    assert r.status_code == 201
    return r.json()


def _assign(client: TestClient, member_id: str, role_id: str, **kwargs: object) -> dict:
    r = client.post(
        "/role-assignments/", json={"member_id": member_id, "role_id": role_id, **kwargs}
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_create_assignment(client: TestClient) -> None:
    m = _create_member(client)
    role = _create_role(client)
    data = _assign(client, m["id"], role["id"])
    assert data["member_id"] == m["id"]
    assert data["role_id"] == role["id"]
    assert data["assigned_by_id"] is None


def test_create_assignment_with_assigned_by(client: TestClient) -> None:
    assignee = _create_member(client, "Assignee")
    assigner = _create_member(client, "Assigner")
    role = _create_role(client)
    data = _assign(client, assignee["id"], role["id"], assigned_by_id=assigner["id"])
    assert data["assigned_by_id"] == assigner["id"]


def test_list_assignments(client: TestClient) -> None:
    m = _create_member(client)
    r1 = _create_role(client, "event_admin")
    r2 = _create_role(client, "member_admin")
    _assign(client, m["id"], r1["id"])
    _assign(client, m["id"], r2["id"])
    all_assignments = client.get("/role-assignments/").json()
    role_ids = {a["role_id"] for a in all_assignments}
    assert {r1["id"], r2["id"]} <= role_ids


def test_filter_by_member_id(client: TestClient) -> None:
    m1 = _create_member(client, "Alice")
    m2 = _create_member(client, "Bob")
    role = _create_role(client)
    _assign(client, m1["id"], role["id"])

    r = client.get(f"/role-assignments/?member_id={m1['id']}")
    assert r.status_code == 200
    assert all(a["member_id"] == m1["id"] for a in r.json())

    r2 = client.get(f"/role-assignments/?member_id={m2['id']}")
    assert r2.json() == []


def test_filter_by_role_id(client: TestClient) -> None:
    m = _create_member(client)
    role = _create_role(client, "event_admin")
    other_role = _create_role(client, "member_admin")
    _assign(client, m["id"], role["id"])

    r = client.get(f"/role-assignments/?role_id={role['id']}")
    assert all(a["role_id"] == role["id"] for a in r.json())

    r2 = client.get(f"/role-assignments/?role_id={other_role['id']}")
    assert r2.json() == []


def test_get_assignment(client: TestClient) -> None:
    m = _create_member(client)
    role = _create_role(client)
    a = _assign(client, m["id"], role["id"])
    r = client.get(f"/role-assignments/{a['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == a["id"]


def test_delete_assignment(client: TestClient) -> None:
    m = _create_member(client)
    role = _create_role(client)
    a = _assign(client, m["id"], role["id"])
    assert client.delete(f"/role-assignments/{a['id']}").status_code == 204
    assert client.get(f"/role-assignments/{a['id']}").status_code == 404


def test_member_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    outsider = _create_member(other_client)
    role = _create_role(client)
    r = client.post("/role-assignments/", json={"member_id": outsider["id"], "role_id": role["id"]})
    assert r.status_code == 422


def test_role_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    m = _create_member(client)
    role = _create_role(other_client)
    r = client.post("/role-assignments/", json={"member_id": m["id"], "role_id": role["id"]})
    assert r.status_code == 422


def test_assigned_by_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    m = _create_member(client)
    role = _create_role(client)
    outsider = _create_member(other_client)
    r = client.post(
        "/role-assignments/",
        json={"member_id": m["id"], "role_id": role["id"], "assigned_by_id": outsider["id"]},
    )
    assert r.status_code == 422


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    m = _create_member(client)
    role = _create_role(client)
    a = _assign(client, m["id"], role["id"])
    assert other_client.get(f"/role-assignments/{a['id']}").status_code == 404
    assert other_client.delete(f"/role-assignments/{a['id']}").status_code == 404
    ids = [x["id"] for x in other_client.get("/role-assignments/").json()]
    assert a["id"] not in ids
