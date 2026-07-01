"""API tests for /members/{member_id}/positions — dated position terms."""

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


def _assign(client: TestClient, member_id: str, position_id: str, **extra) -> dict:
    r = client.post(f"/members/{member_id}/positions", json={"position_id": position_id, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_assign_position(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    data = _assign(client, m["id"], pos["id"])
    assert data["member_id"] == m["id"]
    assert data["position_id"] == pos["id"]
    assert data["assigned_by_id"] == str(_ADMIN_MEMBER_IDS[TENANT_A])
    # A new term defaults to starting today, open-ended → current.
    assert data["start_date"] is not None
    assert data["end_date"] is None
    assert data["is_current"] is True


def test_list_member_positions(client: TestClient) -> None:
    m = _create_member(client)
    p1 = _create_position(client, "scoutmaster")
    p2 = _create_position(client, "treasurer")
    _assign(client, m["id"], p1["id"])
    _assign(client, m["id"], p2["id"])
    position_ids = {a["position_id"] for a in client.get(f"/members/{m['id']}/positions").json()}
    assert {p1["id"], p2["id"]} <= position_ids


def test_assign_duplicate_current_conflicts(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    _assign(client, m["id"], pos["id"])
    r = client.post(f"/members/{m['id']}/positions", json={"position_id": pos["id"]})
    assert r.status_code == 409


def test_delete_term_by_assignment_id(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    a = _assign(client, m["id"], pos["id"])
    resp = client.delete(f"/members/{m['id']}/positions/{a['id']}")
    assert resp.status_code == 204
    positions = client.get(f"/members/{m['id']}/positions").json()
    assert len(positions) == 1
    # Soft-deleted → gone from history too.
    history = client.get(f"/members/{m['id']}/positions?current=false").json()
    assert len(history) == 1


def test_delete_missing_returns_404(client: TestClient) -> None:
    m = _create_member(client)
    import uuid

    resp = client.delete(f"/members/{m['id']}/positions/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_end_term_then_history_and_reassign(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    # Start the term in the past so we can end it in the past too (end >= start).
    a = _assign(client, m["id"], pos["id"], start_date="2025-01-01")

    # End the term in the past via PATCH → no longer current.
    r = client.patch(f"/members/{m['id']}/positions/{a['id']}", json={"end_date": "2025-06-01"})
    assert r.status_code == 200
    assert r.json()["is_current"] is False

    # Default (current) list has the Member position; full history shows the ended term + Member.
    current_pos = client.get(f"/members/{m['id']}/positions").json()
    assert len(current_pos) == 1
    history = client.get(f"/members/{m['id']}/positions?current=false").json()
    assert len(history) == 2
    ended_term = next(a for a in history if a["position_id"] == pos["id"])
    assert ended_term["end_date"] == "2025-06-01"

    # The position can be re-assigned now that the prior term has ended (new row).
    b = _assign(client, m["id"], pos["id"])
    assert b["id"] != a["id"]
    assert len(client.get(f"/members/{m['id']}/positions?current=false").json()) == 3


def test_patch_end_before_start_rejected(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    a = _assign(client, m["id"], pos["id"], start_date="2025-06-01")
    r = client.patch(f"/members/{m['id']}/positions/{a['id']}", json={"end_date": "2025-01-01"})
    assert r.status_code == 422


def test_assign_position_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    m = _create_member(client)
    foreign_pos = _create_position(other_client, "foreign")
    r = client.post(f"/members/{m['id']}/positions", json={"position_id": foreign_pos["id"]})
    assert r.status_code == 404


def test_assign_to_member_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    outsider = _create_member(other_client)
    pos = _create_position(client)
    r = client.post(f"/members/{outsider['id']}/positions", json={"position_id": pos["id"]})
    assert r.status_code == 404


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    _assign(client, m["id"], pos["id"])
    assert other_client.get(f"/members/{m['id']}/positions").status_code == 404


def test_cannot_delete_default_member_assignment(client: TestClient) -> None:
    m = _create_member(client)
    positions = client.get(f"/members/{m['id']}/positions").json()
    assert len(positions) == 1
    default_assignment_id = positions[0]["id"]

    resp = client.delete(f"/members/{m['id']}/positions/{default_assignment_id}")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Default positions cannot be deleted"
