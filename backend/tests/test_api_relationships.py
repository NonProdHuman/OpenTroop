"""API tests for /relationships/ endpoints."""

from fastapi.testclient import TestClient


def _create_member(client: TestClient, first_name: str = "Alice") -> dict:
    r = client.post("/members/", json={
        "first_name": first_name, "last_name": "Test", "member_type": "adult",
    })
    assert r.status_code == 201
    return r.json()


def _create_relationship(
    client: TestClient, from_id: str, to_id: str, rel_type: str = "parent_of"
) -> dict:
    r = client.post("/relationships/", json={
        "from_member_id": from_id,
        "to_member_id": to_id,
        "relationship_type": rel_type,
    })
    assert r.status_code == 201, r.text
    return r.json()


def test_create_relationship(client: TestClient) -> None:
    parent = _create_member(client, "Pat")
    scout = _create_member(client, "Sam")
    data = _create_relationship(client, parent["id"], scout["id"])
    assert data["relationship_type"] == "parent_of"
    assert data["from_member_id"] == parent["id"]
    assert data["to_member_id"] == scout["id"]


def test_list_relationships(client: TestClient) -> None:
    a = _create_member(client, "A")
    b = _create_member(client, "B")
    _create_relationship(client, a["id"], b["id"])
    r = client.get("/relationships/")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_filter_by_member_id_both_directions(client: TestClient) -> None:
    parent = _create_member(client, "Parent")
    child = _create_member(client, "Child")
    sibling = _create_member(client, "Sibling")
    _create_relationship(client, parent["id"], child["id"], "parent_of")
    _create_relationship(client, sibling["id"], child["id"], "sibling_of")

    r = client.get(f"/relationships/?member_id={child['id']}")
    assert r.status_code == 200
    rels = r.json()
    member_ids = {(x["from_member_id"], x["to_member_id"]) for x in rels}
    assert (parent["id"], child["id"]) in member_ids
    assert (sibling["id"], child["id"]) in member_ids


def test_get_relationship(client: TestClient) -> None:
    a = _create_member(client, "A")
    b = _create_member(client, "B")
    rel = _create_relationship(client, a["id"], b["id"])
    r = client.get(f"/relationships/{rel['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == rel["id"]


def test_patch_relationship(client: TestClient) -> None:
    a = _create_member(client, "A")
    b = _create_member(client, "B")
    rel = _create_relationship(client, a["id"], b["id"], "parent_of")
    r = client.patch(f"/relationships/{rel['id']}", json={"relationship_type": "guardian_of"})
    assert r.status_code == 200
    assert r.json()["relationship_type"] == "guardian_of"


def test_delete_relationship(client: TestClient) -> None:
    a = _create_member(client, "A")
    b = _create_member(client, "B")
    rel = _create_relationship(client, a["id"], b["id"])
    assert client.delete(f"/relationships/{rel['id']}").status_code == 204
    assert client.get(f"/relationships/{rel['id']}").status_code == 404


def test_from_member_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    outsider = _create_member(other_client, "Outside")
    local = _create_member(client, "Local")
    r = client.post("/relationships/", json={
        "from_member_id": outsider["id"],
        "to_member_id": local["id"],
        "relationship_type": "parent_of",
    })
    assert r.status_code == 422


def test_to_member_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    outsider = _create_member(other_client, "Outside")
    local = _create_member(client, "Local")
    r = client.post("/relationships/", json={
        "from_member_id": local["id"],
        "to_member_id": outsider["id"],
        "relationship_type": "parent_of",
    })
    assert r.status_code == 422


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    a = _create_member(client, "A")
    b = _create_member(client, "B")
    rel = _create_relationship(client, a["id"], b["id"])
    assert other_client.get(f"/relationships/{rel['id']}").status_code == 404
    assert other_client.delete(f"/relationships/{rel['id']}").status_code == 404
