"""API tests for event audiences and visibility filtering."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import MemberType, Permission
from app.models.member import Member
from app.models.role import MemberRoleAssignment, Role, RolePermission

TENANT_A = uuid.UUID("10000000-0000-0000-0000-000000000001")
NEW_USER_ID = uuid.UUID("c0000000-0000-0000-0000-000000000001")


def _event_type(client: TestClient) -> dict:
    r = client.post("/event-types/", json={"name": "Hike"})
    assert r.status_code == 201, r.text
    return r.json()


def _event(client: TestClient, event_type_id: str, name: str = "Outing") -> dict:
    r = client.post(
        "/events/",
        json={
            "name": name,
            "event_type_id": event_type_id,
            "scheduled_start": "2026-07-10T09:00:00Z",
            "scheduled_end": "2026-07-12T17:00:00Z",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _group(client: TestClient, name: str = "Wolf") -> dict:
    r = client.post("/groups/", json={"name": name, "group_type": "manual"})
    assert r.status_code == 201, r.text
    return r.json()


# --- Audience CRUD --------------------------------------------------------


def test_add_list_delete_audience(client: TestClient) -> None:
    et = _event_type(client)
    event = _event(client, et["id"])
    group = _group(client)

    added = client.post(f"/events/{event['id']}/audiences", json={"group_id": group["id"]})
    assert added.status_code == 201
    assert added.json()["group_id"] == group["id"]

    listed = client.get(f"/events/{event['id']}/audiences").json()
    assert {a["group_id"] for a in listed} == {group["id"]}

    removed = client.delete(f"/events/{event['id']}/audiences/{group['id']}")
    assert removed.status_code == 204
    assert client.get(f"/events/{event['id']}/audiences").json() == []


def test_add_audience_is_idempotent(client: TestClient) -> None:
    et = _event_type(client)
    event = _event(client, et["id"])
    group = _group(client)
    first = client.post(f"/events/{event['id']}/audiences", json={"group_id": group["id"]})
    second = client.post(f"/events/{event['id']}/audiences", json={"group_id": group["id"]})
    assert first.json()["id"] == second.json()["id"]


def test_add_audience_unknown_group_422(client: TestClient) -> None:
    et = _event_type(client)
    event = _event(client, et["id"])
    r = client.post(
        f"/events/{event['id']}/audiences",
        json={"group_id": "00000000-0000-0000-0000-000000000099"},
    )
    assert r.status_code == 422


def test_manager_sees_scoped_event(client: TestClient) -> None:
    """The seeded admin holds event:write, so the visibility filter is bypassed."""
    et = _event_type(client)
    scoped = _event(client, et["id"], name="Wolf-only")
    group = _group(client)
    client.post(f"/events/{scoped['id']}/audiences", json={"group_id": group["id"]})

    ids = {e["id"] for e in client.get("/events/").json()}
    assert scoped["id"] in ids


# --- Visibility as a non-manager member -----------------------------------


def _seed_reader(db: Session) -> Member:
    """Create a member linked to NEW_USER_ID holding only event:read in TENANT_A."""
    role = Role(tenant_id=TENANT_A, name="Reader", slug="reader")
    db.add(role)
    db.flush()
    db.add(RolePermission(tenant_id=TENANT_A, role_id=role.id, permission=Permission.EVENT_READ))
    reader = Member(
        tenant_id=TENANT_A,
        user_id=NEW_USER_ID,
        first_name="Reader",
        last_name="One",
        member_type=MemberType.ADULT,
    )
    db.add(reader)
    db.flush()
    db.add(MemberRoleAssignment(tenant_id=TENANT_A, member_id=reader.id, role_id=role.id))
    db.commit()
    return reader


def test_non_manager_visibility_filter(
    client: TestClient, claim_client: TestClient, db_session: Session
) -> None:
    et = _event_type(client)
    troop = _event(client, et["id"], name="Troop-wide")
    scoped = _event(client, et["id"], name="Wolf-only")
    group = _group(client)
    client.post(f"/events/{scoped['id']}/audiences", json={"group_id": group["id"]})

    reader = _seed_reader(db_session)
    headers = {"X-Tenant-ID": str(TENANT_A)}

    # Not in the audience group: troop-wide visible, scoped hidden (list + 404 on detail).
    ids = {e["id"] for e in claim_client.get("/events/", headers=headers).json()}
    assert troop["id"] in ids
    assert scoped["id"] not in ids
    assert claim_client.get(f"/events/{scoped['id']}", headers=headers).status_code == 404

    # Add the reader to the audience group → the scoped event becomes visible.
    joined = client.post(f"/groups/{group['id']}/members", json={"member_id": str(reader.id)})
    assert joined.status_code == 201

    ids2 = {e["id"] for e in claim_client.get("/events/", headers=headers).json()}
    assert {troop["id"], scoped["id"]} <= ids2
    assert claim_client.get(f"/events/{scoped['id']}", headers=headers).status_code == 200
