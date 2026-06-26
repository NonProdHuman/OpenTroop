"""API tests for /members/{member_id}/positions — assigning positions to members."""

from fastapi.testclient import TestClient

from tests.conftest import _ADMIN_MEMBER_IDS, TENANT_A


def _create_member(client: TestClient, first_name: str = "Alice") -> dict:
    r = client.post(
        "/members/",
        json={"first_name": first_name, "last_name": "Test", "member_type": "adult"},
    )
    assert r.status_code == 201
    return r.json()


def _create_position(client: TestClient, slug: str = "scoutmaster") -> dict:
    r = client.post("/positions/", json={"name": slug.replace("-", " ").title(), "slug": slug})
    assert r.status_code == 201
    return r.json()


def _assign(client: TestClient, member_id: str, position_id: str) -> dict:
    r = client.post(f"/members/{member_id}/positions", json={"position_id": position_id})
    assert r.status_code == 201, r.text
    return r.json()


def test_assign_position(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    data = _assign(client, m["id"], pos["id"])
    assert data["member_id"] == m["id"]
    assert data["position_id"] == pos["id"]
    # assigned_by is the acting member (the admin), recorded automatically.
    assert data["assigned_by_id"] == str(_ADMIN_MEMBER_IDS[TENANT_A])


def test_list_member_positions(client: TestClient) -> None:
    m = _create_member(client)
    p1 = _create_position(client, "scoutmaster")
    p2 = _create_position(client, "treasurer")
    _assign(client, m["id"], p1["id"])
    _assign(client, m["id"], p2["id"])
    position_ids = {a["position_id"] for a in client.get(f"/members/{m['id']}/positions").json()}
    assert {p1["id"], p2["id"]} <= position_ids


def test_assign_is_idempotent(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    first = _assign(client, m["id"], pos["id"])
    second = _assign(client, m["id"], pos["id"])
    assert first["id"] == second["id"]


def test_unassign_position(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    _assign(client, m["id"], pos["id"])
    assert client.delete(f"/members/{m['id']}/positions/{pos['id']}").status_code == 204
    assert client.get(f"/members/{m['id']}/positions").json() == []


def test_reassign_after_unassign_revives(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    first = _assign(client, m["id"], pos["id"])
    client.delete(f"/members/{m['id']}/positions/{pos['id']}")
    revived = _assign(client, m["id"], pos["id"])
    assert revived["id"] == first["id"]  # the prior row is revived, not duplicated


def test_unassign_missing_returns_404(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    assert client.delete(f"/members/{m['id']}/positions/{pos['id']}").status_code == 404


def test_assign_position_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    m = _create_member(client)
    foreign_pos = _create_position(other_client, "foreign")
    r = client.post(f"/members/{m['id']}/positions", json={"position_id": foreign_pos["id"]})
    assert r.status_code == 422


def test_assign_to_member_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    outsider = _create_member(other_client)
    pos = _create_position(client)
    r = client.post(f"/members/{outsider['id']}/positions", json={"position_id": pos["id"]})
    assert r.status_code == 404


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    _assign(client, m["id"], pos["id"])
    # other_client (TENANT_B) cannot see TENANT_A's member at all.
    assert other_client.get(f"/members/{m['id']}/positions").status_code == 404
