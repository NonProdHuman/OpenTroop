"""API tests for /groups/ endpoints (CRUD, membership, dynamic rules, resolution)."""

import uuid

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import TENANT_A


def _create_group(
    client: TestClient, name: str = "PLC", group_type: str = "custom", rule_logic: str = "and"
) -> dict:
    r = client.post(
        "/groups/", json={"name": name, "group_type": group_type, "rule_logic": rule_logic}
    )
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
    assert data["rule_logic"] == "and"
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
            "   is_system, rule_logic, created_at, updated_at, is_deleted) "
            "VALUES "
            "  (:id, :tenant_id, 'Raw Patrol', 'patrol', NULL, NULL, "
            "   0, 'and', datetime('now'), datetime('now'), 0)"
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
    r = client.patch(
        f"/groups/{g['id']}", json={"name": "Renamed", "color": "#ABCDEF", "rule_logic": "or"}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert r.json()["color"] == "#ABCDEF"
    assert r.json()["rule_logic"] == "or"


def test_delete_group(client: TestClient) -> None:
    g = _create_group(client, "Gone")
    deleted = client.delete(f"/groups/{g['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/groups/{g['id']}").status_code == 404


def test_duplicate_name_rejected(client: TestClient) -> None:
    _create_group(client, "Dup")
    r = client.post("/groups/", json={"name": "Dup", "group_type": "custom"})
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


# --- Dynamic rules API -----------------------------------------------


def test_rule_crud_and_validation(client: TestClient) -> None:
    group = _create_group(client, "DynamicGroup", "custom")
    position_id = _admin_position_id(client)

    # 1. GET rules - should be empty initially
    r = client.get(f"/groups/{group['id']}/rules")
    assert r.status_code == 200
    assert r.json() == []

    # 2. PUT invalid member_type values - should fail
    r = client.put(f"/groups/{group['id']}/rules/member_type", json={"values": ["invalid_type"]})
    assert r.status_code == 400

    # 3. PUT valid member_type
    r = client.put(f"/groups/{group['id']}/rules/member_type", json={"values": ["scout"]})
    assert r.status_code == 200
    assert r.json()["dimension"] == "member_type"
    assert r.json()["values"] == ["scout"]

    # 4. PUT boolean dimension with values - should fail
    r = client.put(f"/groups/{group['id']}/rules/oa_member", json={"values": ["some_value"]})
    assert r.status_code == 400

    # 5. PUT boolean dimension with null/empty values
    r = client.put(f"/groups/{group['id']}/rules/oa_member", json={"values": []})
    assert r.status_code == 200
    assert r.json()["dimension"] == "oa_member"
    assert r.json()["values"] == []

    # 6. PUT position rule with valid position
    r = client.put(f"/groups/{group['id']}/rules/position", json={"values": [position_id]})
    assert r.status_code == 200

    # 7. PUT position rule with invalid UUID - 400
    r = client.put(f"/groups/{group['id']}/rules/position", json={"values": ["not-a-uuid"]})
    assert r.status_code == 400

    # 8. PUT position rule with unknown position UUID - 422
    r = client.put(
        f"/groups/{group['id']}/rules/position",
        json={"values": ["00000000-0000-0000-0000-000000000099"]},
    )
    assert r.status_code == 422

    # 9. PUT group self-reference - 400
    r = client.put(f"/groups/{group['id']}/rules/group_member", json={"values": [group["id"]]})
    assert r.status_code == 400

    # 10. GET rules - should return the rules we added
    rules = client.get(f"/groups/{group['id']}/rules").json()
    dimensions = {rule["dimension"] for rule in rules}
    assert {"member_type", "oa_member", "position"} <= dimensions

    # 11. DELETE rule
    r = client.delete(f"/groups/{group['id']}/rules/oa_member")
    assert r.status_code == 204

    # 12. GET rules again - oa_member should be gone
    rules = client.get(f"/groups/{group['id']}/rules").json()
    dimensions = {rule["dimension"] for rule in rules}
    assert "oa_member" not in dimensions


def test_patrol_rejects_rules(client: TestClient) -> None:
    """Patrols are manual-only — the rule editor is closed to them."""
    patrol = _create_group(client, "Wolf", "patrol")
    r = client.put(f"/groups/{patrol['id']}/rules/member_type", json={"values": ["scout"]})
    assert r.status_code == 400
    assert "Patrols cannot have dynamic rules" in r.text


def test_relationship_dimension_removed(client: TestClient) -> None:
    """The relationship dimension was replaced by include_parents — the path 422s now."""
    group = _create_group(client, "Custom", "custom")
    r = client.put(f"/groups/{group['id']}/rules/relationship", json={"values": [group["id"]]})
    assert r.status_code == 422


def test_include_parents_flag_and_resolution(client: TestClient) -> None:
    """include_parents persists through the API and pulls parents into resolved membership."""
    group = _create_group(client, "Scouts + Parents", "custom")
    assert group["include_parents"] is False
    assert group["cc_parents_on_messages"] is False

    scout = _create_member(client, "Sammy")
    parent = client.post(
        "/members/",
        json={"first_name": "Pat", "last_name": "Parent", "member_type": "adult"},
    ).json()
    client.post(
        "/relationships/",
        json={
            "from_member_id": parent["id"],
            "to_member_id": scout["id"],
            "relationship_type": "parent_of",
        },
    )
    client.post(f"/groups/{group['id']}/members", json={"member_id": scout["id"]})

    # Without the flag: just the scout.
    ids = {m["id"] for m in client.get(f"/groups/{group['id']}/members").json()}
    assert ids == {scout["id"]}

    # Enable include_parents via PATCH; parent now resolves too.
    patched = client.patch(f"/groups/{group['id']}", json={"include_parents": True})
    assert patched.status_code == 200
    assert patched.json()["include_parents"] is True
    ids = {m["id"] for m in client.get(f"/groups/{group['id']}/members").json()}
    assert ids == {scout["id"], parent["id"]}


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
