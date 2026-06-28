"""API tests for /groups/ endpoints (CRUD, membership, role rules, resolution)."""

import uuid

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import TENANT_A


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


def _admin_position_id(client: TestClient) -> str:
    positions = client.get("/positions/").json()
    return next(p["id"] for p in positions if p["slug"] == "administrator")


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


def test_list_groups_with_migration_written_lowercase_group_type(
    client: TestClient, db_session: Session
) -> None:
    """Regression: fold_patrol_into_groups migration inserts 'patrol' (lowercase) via raw
    SQL.  SAEnum(GroupType) without values_callable looked up by enum name ('PATROL') not
    value, so GET /groups/ crashed with a 500 on any tenant that had patrol data."""
    group_id = uuid.uuid4()
    db_session.execute(
        sa.text(
            "INSERT INTO groups "
            "  (id, tenant_id, name, group_type, color, description, "
            "   is_system, created_at, updated_at, is_deleted) "
            "VALUES "
            "  (:id, :tenant_id, 'Raw Patrol', 'patrol', NULL, NULL, "
            "   0, datetime('now'), datetime('now'), 0)"
        ),
        # SQLAlchemy's Uuid type stores without hyphens in SQLite — match that format.
        {"id": group_id.hex, "tenant_id": TENANT_A.hex},
    )
    db_session.commit()

    r = client.get("/groups/")
    assert r.status_code == 200, r.text
    match = next((g for g in r.json() if g["id"] == str(group_id)), None)
    assert match is not None, "raw-SQL-inserted group missing from list"
    assert match["group_type"] == "patrol"


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


# --- Dynamic position rules -----------------------------------------------


def test_position_rule_resolves_dynamic_members(client: TestClient) -> None:
    """A position rule pulls in everyone holding that position (here, the seeded admin)."""
    group = _create_group(client, "Leaders", "dynamic")
    position_id = _admin_position_id(client)

    r = client.post(f"/groups/{group['id']}/rules", json={"position_id": position_id})
    assert r.status_code == 201

    rules = client.get(f"/groups/{group['id']}/rules").json()
    assert any(rule["position_id"] == position_id for rule in rules)

    resolved = client.get(f"/groups/{group['id']}/members").json()
    assert any(m["first_name"] == "Admin" for m in resolved)


def test_remove_position_rule(client: TestClient) -> None:
    group = _create_group(client, "Leaders", "dynamic")
    position_id = _admin_position_id(client)
    client.post(f"/groups/{group['id']}/rules", json={"position_id": position_id})
    deleted = client.delete(f"/groups/{group['id']}/rules/{position_id}")
    assert deleted.status_code == 204
    resolved = client.get(f"/groups/{group['id']}/members").json()
    assert not any(m["first_name"] == "Admin" for m in resolved)


def test_add_rule_unknown_position_422(client: TestClient) -> None:
    group = _create_group(client, "Leaders", "dynamic")
    r = client.post(
        f"/groups/{group['id']}/rules",
        json={"position_id": "00000000-0000-0000-0000-000000000099"},
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


def test_adult_cannot_be_member_of_patrol(client: TestClient) -> None:
    group = _create_group(client, "Wolf", "patrol")
    adult = client.post(
        "/members/",
        json={"first_name": "Bob", "last_name": "Adult", "member_type": "adult"},
    ).json()
    r = client.post(f"/groups/{group['id']}/members", json={"member_id": adult["id"]})
    assert r.status_code == 400
    assert "Adults cannot be members of a patrol" in r.text
