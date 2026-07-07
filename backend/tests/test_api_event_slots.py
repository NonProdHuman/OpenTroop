"""API tests for universal event sign-up slots (GH-152).

Covers manager slot CRUD + non-manager 403, event-visibility 404 parity, self/family
sign-up authorization with the ``event:manage_attendance`` override, ``applies_to``
enforcement, capacity boundary + duplicate + withdraw/re-join revival, capacity lowered
below the current count, and cross-tenant isolation.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.enums import MemberType, Permission, RelationshipType
from app.models.member import Member, MemberRelationship
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
from tests.conftest import NEW_USER_ID, TENANT_A

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event_type(client: TestClient, **overrides: object) -> dict:
    r = client.post("/event-types/", json={"name": "Campout", **overrides})
    assert r.status_code == 201, r.text
    return r.json()


def _event(client: TestClient, event_type_id: str, **overrides: object) -> dict:
    payload = {
        "name": "Summer Campout",
        "event_type_id": event_type_id,
        "scheduled_start": "2026-07-10T09:00:00Z",
        "scheduled_end": "2026-07-12T17:00:00Z",
        **overrides,
    }
    r = client.post("/events/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _member(
    db: Session,
    first: str,
    member_type: MemberType = MemberType.SCOUT,
    tenant_id: uuid.UUID = TENANT_A,
    **kw: object,
) -> Member:
    m = Member(
        tenant_id=tenant_id, first_name=first, last_name="Test", member_type=member_type, **kw
    )
    db.add(m)
    db.commit()
    return m


def _member_client(user_id: uuid.UUID = NEW_USER_ID, tenant_id: uuid.UUID = TENANT_A) -> TestClient:
    return TestClient(app, headers={"X-Tenant-ID": str(tenant_id), "X-Test-User-ID": str(user_id)})


def _link(
    db: Session, adult: Member, child: Member, rel: RelationshipType = RelationshipType.PARENT_OF
) -> None:
    db.add(
        MemberRelationship(
            tenant_id=TENANT_A,
            from_member_id=adult.id,
            to_member_id=child.id,
            relationship_type=rel,
        )
    )
    db.commit()


def _grant_member(db: Session, user_id: uuid.UUID, permission: Permission, name: str) -> Member:
    """Create a TENANT_A member linked to ``user_id`` holding exactly one permission."""
    role = FunctionalRole(tenant_id=TENANT_A, name=name, slug=f"{name.lower()}-role")
    db.add(role)
    db.flush()
    db.add(
        FunctionalRolePermission(
            tenant_id=TENANT_A, functional_role_id=role.id, permission=permission
        )
    )
    position = Position(tenant_id=TENANT_A, name=name, slug=f"{name.lower()}-pos")
    db.add(position)
    db.flush()
    db.add(
        PositionFunctionalRole(
            tenant_id=TENANT_A, position_id=position.id, functional_role_id=role.id
        )
    )
    member = _member(db, name, MemberType.ADULT, user_id=user_id)
    db.add(
        MemberPositionAssignment(tenant_id=TENANT_A, member_id=member.id, position_id=position.id)
    )
    db.commit()
    return member


def _slot(client: TestClient, event_id: str, **overrides: object) -> dict:
    payload = {"name": "Grubmaster", **overrides}
    r = client.post(f"/events/{event_id}/slots", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Manager slot CRUD
# ---------------------------------------------------------------------------


def test_manager_slot_crud(client: TestClient) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])

    created = _slot(client, ev["id"], capacity=4, description="cooks dinner")
    assert created["remaining"] == 4
    assert created["signups"] == []
    assert created["applies_to"] == "any"

    listed = client.get(f"/events/{ev['id']}/slots").json()
    assert [s["name"] for s in listed] == ["Grubmaster"]

    patched = client.patch(
        f"/events/{ev['id']}/slots/{created['id']}", json={"name": "Head Cook", "capacity": 2}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "Head Cook"
    assert patched.json()["remaining"] == 2

    removed = client.delete(f"/events/{ev['id']}/slots/{created['id']}")
    assert removed.status_code == 204
    assert client.get(f"/events/{ev['id']}/slots").json() == []


def test_duplicate_slot_name_conflicts(client: TestClient) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    _slot(client, ev["id"])
    dup = client.post(f"/events/{ev['id']}/slots", json={"name": "Grubmaster"})
    assert dup.status_code == 409


def test_capacity_zero_and_bad_window_rejected(client: TestClient) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    zero = client.post(f"/events/{ev['id']}/slots", json={"name": "Zero", "capacity": 0})
    assert zero.status_code == 422
    bad = client.post(
        f"/events/{ev['id']}/slots",
        json={
            "name": "Backwards",
            "starts_at": "2026-07-10T11:00:00Z",
            "ends_at": "2026-07-10T09:00:00Z",
        },
    )
    assert bad.status_code == 422


def test_ordering_by_sort_order(client: TestClient) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    _slot(client, ev["id"], name="Second", sort_order=2)
    _slot(client, ev["id"], name="First", sort_order=1)
    names = [s["name"] for s in client.get(f"/events/{ev['id']}/slots").json()]
    assert names == ["First", "Second"]


def test_non_manager_cannot_crud_slots(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    _member(db_session, "Plain", MemberType.ADULT, user_id=NEW_USER_ID)
    pc = _member_client()
    r = pc.post(f"/events/{ev['id']}/slots", json={"name": "Nope"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Visibility parity with events
# ---------------------------------------------------------------------------


def test_slots_404_on_audience_hidden_event(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    group = client.post("/groups/", json={"name": "Wolf", "group_type": "custom"}).json()
    client.post(f"/events/{ev['id']}/audiences", json={"group_id": group["id"]})
    # A plain member not in the audience group.
    _member(db_session, "Outsider", MemberType.ADULT, user_id=NEW_USER_ID)
    pc = _member_client()
    assert pc.get(f"/events/{ev['id']}/slots").status_code == 404


def test_cross_tenant_isolation(
    client: TestClient, other_client: TestClient, db_session: Session
) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    _slot(client, ev["id"])
    # TENANT_B admin cannot see TENANT_A's event or its slots.
    assert other_client.get(f"/events/{ev['id']}/slots").status_code == 404


# ---------------------------------------------------------------------------
# Sign-up authorization
# ---------------------------------------------------------------------------


def test_self_signup_creates_no_participant(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    slot = _slot(client, ev["id"])
    parent = _member(db_session, "Parent", MemberType.ADULT, user_id=NEW_USER_ID)
    pc = _member_client()

    r = pc.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(parent.id)}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["member_id"] == str(parent.id)
    assert body["signed_up_by_id"] == str(parent.id)
    assert body["member_name"] == "Parent Test"
    # Orthogonal to RSVP: no participant row is created.
    assert client.get(f"/events/{ev['id']}/participants").json() == []


def test_parent_signs_up_child_but_not_stranger(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    slot = _slot(client, ev["id"])
    parent = _member(db_session, "Parent", MemberType.ADULT, user_id=NEW_USER_ID)
    child = _member(db_session, "Child")
    stranger = _member(db_session, "Stranger")
    _link(db_session, parent, child)
    pc = _member_client()

    ok = pc.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(child.id)}
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["signed_up_by_id"] == str(parent.id)

    denied = pc.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(stranger.id)}
    )
    assert denied.status_code == 403


def test_manage_attendance_overrides_family_scope(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    slot = _slot(client, ev["id"])
    leader = _grant_member(db_session, NEW_USER_ID, Permission.EVENT_MANAGE_ATTENDANCE, "Leader")
    stranger = _member(db_session, "Stranger")
    assert leader.id != stranger.id
    pc = _member_client()
    r = pc.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(stranger.id)}
    )
    assert r.status_code == 201, r.text


def test_applies_to_adult_rejects_scout(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    slot = _slot(client, ev["id"], applies_to="adult")
    scout = _member(db_session, "Scout", MemberType.SCOUT)
    r = client.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(scout.id)}
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Capacity & withdrawal
# ---------------------------------------------------------------------------


def test_capacity_boundary_then_full(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    slot = _slot(client, ev["id"], capacity=1)
    a = _member(db_session, "Alpha")
    b = _member(db_session, "Bravo")

    first = client.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(a.id)}
    )
    assert first.status_code == 201, first.text
    full = client.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(b.id)}
    )
    assert full.status_code == 409
    assert full.json()["detail"] == "Slot is full"

    read = client.get(f"/events/{ev['id']}/slots").json()[0]
    assert read["remaining"] == 0
    assert len(read["signups"]) == 1


def test_unlimited_slot_never_full(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    slot = _slot(client, ev["id"])  # capacity null
    for i in range(5):
        m = _member(db_session, f"M{i}")
        r = client.post(
            f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(m.id)}
        )
        assert r.status_code == 201, r.text
    assert client.get(f"/events/{ev['id']}/slots").json()[0]["remaining"] is None


def test_duplicate_active_signup_conflicts(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    slot = _slot(client, ev["id"])
    m = _member(db_session, "Once")
    first = client.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(m.id)}
    )
    assert first.status_code == 201
    dup = client.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(m.id)}
    )
    assert dup.status_code == 409


def test_withdraw_then_rejoin_revives_row(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    slot = _slot(client, ev["id"], capacity=1)
    m = _member(db_session, "Rejoin")

    first = client.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(m.id)}
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    withdraw = client.delete(f"/events/{ev['id']}/slots/{slot['id']}/signups/{m.id}")
    assert withdraw.status_code == 204
    # Capacity freed after withdrawal.
    assert client.get(f"/events/{ev['id']}/slots").json()[0]["remaining"] == 1

    rejoin = client.post(
        f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(m.id)}
    )
    assert rejoin.status_code == 201, rejoin.text
    # Same row revived — no unique-constraint violation.
    assert rejoin.json()["id"] == first_id


def test_withdraw_missing_signup_404(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    slot = _slot(client, ev["id"])
    m = _member(db_session, "Never")
    r = client.delete(f"/events/{ev['id']}/slots/{slot['id']}/signups/{m.id}")
    assert r.status_code == 404


def test_lower_capacity_below_signups_keeps_them(client: TestClient, db_session: Session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    slot = _slot(client, ev["id"], capacity=3)
    for i in range(2):
        m = _member(db_session, f"C{i}")
        client.post(f"/events/{ev['id']}/slots/{slot['id']}/signups", json={"member_id": str(m.id)})
    lowered = client.patch(f"/events/{ev['id']}/slots/{slot['id']}", json={"capacity": 1})
    assert lowered.status_code == 200, lowered.text
    body = lowered.json()
    assert body["remaining"] == 0
    assert len(body["signups"]) == 2
