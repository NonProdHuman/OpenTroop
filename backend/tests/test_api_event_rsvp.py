"""API tests for the RSVP + parental-permission workflow.

Covers family-scoped RSVP authorization, the permission-slip state machine (pending →
granted → revival → invalidation on message change), driver fields, headcounts, the
sign-up window, event-type validation, and tenant permission-message settings.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.models.enums import MemberType, RelationshipType
from app.models.member import Member, MemberRelationship
from app.models.tenant import Tenant
from tests.conftest import NEW_USER_ID, TENANT_A

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event_type(client: TestClient, **overrides: object) -> dict:
    payload = {"name": "Campout", "allow_signups": True, **overrides}
    r = client.post("/event-types/", json=payload)
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


def _member(db, first: str, member_type: MemberType = MemberType.SCOUT, **kw) -> Member:
    m = Member(
        tenant_id=TENANT_A, first_name=first, last_name="Test", member_type=member_type, **kw
    )
    db.add(m)
    db.commit()
    return m


def _parent_client() -> TestClient:
    """A non-manager member client (NEW_USER_ID), authenticated in TENANT_A.

    The dependency overrides are installed by the ``client`` fixture; this just adds a
    second client with a different user header (the same pattern as ``claim_client``).
    """
    return TestClient(
        app, headers={"X-Tenant-ID": str(TENANT_A), "X-Test-User-ID": str(NEW_USER_ID)}
    )


def _link(db, adult: Member, child: Member, rel=RelationshipType.PARENT_OF) -> None:
    db.add(
        MemberRelationship(
            tenant_id=TENANT_A,
            from_member_id=adult.id,
            to_member_id=child.id,
            relationship_type=rel,
        )
    )
    db.commit()


# ---------------------------------------------------------------------------
# Family-scoped RSVP authorization
# ---------------------------------------------------------------------------


def test_parent_can_rsvp_child_but_not_stranger(client: TestClient, db_session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    parent = _member(db_session, "Parent", MemberType.ADULT, user_id=NEW_USER_ID)
    child = _member(db_session, "Child")
    stranger = _member(db_session, "Stranger")
    _link(db_session, parent, child)

    pc = _parent_client()
    ok = pc.post(f"/events/{ev['id']}/participants", json={"member_id": str(child.id)})
    assert ok.status_code == 201, ok.text
    denied = pc.post(f"/events/{ev['id']}/participants", json={"member_id": str(stranger.id)})
    assert denied.status_code == 403


def test_parent_can_rsvp_self(client: TestClient, db_session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    parent = _member(db_session, "Parent", MemberType.ADULT, user_id=NEW_USER_ID)

    pc = _parent_client()
    r = pc.post(f"/events/{ev['id']}/participants", json={"member_id": str(parent.id)})
    assert r.status_code == 201, r.text


def test_manager_bypasses_family_scope(client: TestClient, db_session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    stranger = _member(db_session, "Stranger")
    # The admin client is an event manager — may RSVP anyone.
    r = client.post(f"/events/{ev['id']}/participants", json={"member_id": str(stranger.id)})
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# Driver fields & counts
# ---------------------------------------------------------------------------


def test_driver_fields_persist(client: TestClient, db_session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    adult = _member(db_session, "Driver", MemberType.ADULT)
    r = client.post(
        f"/events/{ev['id']}/participants",
        json={
            "member_id": str(adult.id),
            "rsvp_status": "declined",
            "driver": True,
            "drives_to": True,
            "drives_from": False,
            "seat_count": 5,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["driver"] is True
    assert body["drives_to"] is True
    assert body["drives_from"] is False
    assert body["seat_count"] == 5


def test_counts(client: TestClient, db_session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"])
    scout = _member(db_session, "Scout")
    adult = _member(db_session, "Adult", MemberType.ADULT)
    driver_only = _member(db_session, "DriverOnly", MemberType.ADULT)

    client.post(
        f"/events/{ev['id']}/participants",
        json={"member_id": str(scout.id), "rsvp_status": "going", "guest_count": 2},
    )
    client.post(
        f"/events/{ev['id']}/participants",
        json={"member_id": str(adult.id), "rsvp_status": "going", "driver": True},
    )
    # Driver who is NOT attending — counts only in drivers.
    client.post(
        f"/events/{ev['id']}/participants",
        json={"member_id": str(driver_only.id), "rsvp_status": "declined", "driver": True},
    )

    counts = client.get(f"/events/{ev['id']}/counts").json()
    assert counts == {"scouts": 1, "adults": 1, "drivers": 2, "guests": 2}


# ---------------------------------------------------------------------------
# Permission-slip state machine
# ---------------------------------------------------------------------------


def _permission_event(client: TestClient) -> dict:
    et = _event_type(client, require_permission_slip=True)
    return _event(client, et["id"])


def test_permission_pending_then_granted_by_parent(client: TestClient, db_session) -> None:
    ev = _permission_event(client)
    parent = _member(db_session, "Parent", MemberType.ADULT, user_id=NEW_USER_ID)
    child = _member(db_session, "Child")
    _link(db_session, parent, child)
    pc = _parent_client()

    pc.post(
        f"/events/{ev['id']}/participants",
        json={"member_id": str(child.id), "rsvp_status": "going"},
    )
    listed = client.get(f"/events/{ev['id']}/participants").json()
    assert listed[0]["permission_status"] == "pending"

    grant = pc.post(
        f"/events/{ev['id']}/participants/{child.id}/permission",
        json={"signature": "Parent Test"},
    )
    assert grant.status_code == 200, grant.text
    body = grant.json()
    assert body["permission_status"] == "granted"
    assert body["electronic_permission"] is True
    assert body["electronic_permission_signature"] == "Parent Test"
    assert body["permission_message_snapshot"]  # captured the tenant language


def test_leader_cannot_grant_permission(client: TestClient, db_session) -> None:
    ev = _permission_event(client)
    child = _member(db_session, "Child")
    client.post(
        f"/events/{ev['id']}/participants",
        json={"member_id": str(child.id), "rsvp_status": "going"},
    )
    # The admin is a manager but not the scout's parent — no manager bypass on signing.
    r = client.post(
        f"/events/{ev['id']}/participants/{child.id}/permission",
        json={"signature": "Admin"},
    )
    assert r.status_code == 403


def test_permission_requires_going(client: TestClient, db_session) -> None:
    ev = _permission_event(client)
    parent = _member(db_session, "Parent", MemberType.ADULT, user_id=NEW_USER_ID)
    child = _member(db_session, "Child")
    _link(db_session, parent, child)
    pc = _parent_client()
    pc.post(
        f"/events/{ev['id']}/participants",
        json={"member_id": str(child.id), "rsvp_status": "declined"},
    )
    r = pc.post(
        f"/events/{ev['id']}/participants/{child.id}/permission",
        json={"signature": "Parent"},
    )
    assert r.status_code == 409


def test_permission_revives_on_redecline_then_going(client: TestClient, db_session) -> None:
    ev = _permission_event(client)
    parent = _member(db_session, "Parent", MemberType.ADULT, user_id=NEW_USER_ID)
    child = _member(db_session, "Child")
    _link(db_session, parent, child)
    pc = _parent_client()
    pc.post(
        f"/events/{ev['id']}/participants",
        json={"member_id": str(child.id), "rsvp_status": "going"},
    )
    pc.post(
        f"/events/{ev['id']}/participants/{child.id}/permission",
        json={"signature": "Parent"},
    )
    # Decline → slip no longer applicable.
    declined = pc.patch(
        f"/events/{ev['id']}/participants/{child.id}", json={"rsvp_status": "declined"}
    ).json()
    assert declined["permission_status"] == "not_required"
    # Going again → revives the original signature without re-signing.
    revived = pc.patch(
        f"/events/{ev['id']}/participants/{child.id}", json={"rsvp_status": "going"}
    ).json()
    assert revived["permission_status"] == "granted"


def test_message_change_invalidates_existing_permission(client: TestClient, db_session) -> None:
    # A Tenant row is required so the settings PATCH can persist the new message.
    db_session.add(Tenant(id=TENANT_A, name="Troop A", slug="troop-a"))
    db_session.commit()

    ev = _permission_event(client)
    parent = _member(db_session, "Parent", MemberType.ADULT, user_id=NEW_USER_ID)
    child = _member(db_session, "Child")
    _link(db_session, parent, child)
    pc = _parent_client()
    pc.post(
        f"/events/{ev['id']}/participants",
        json={"member_id": str(child.id), "rsvp_status": "going"},
    )
    pc.post(
        f"/events/{ev['id']}/participants/{child.id}/permission",
        json={"signature": "Parent"},
    )
    # Troop edits the permission language → previously-signed slip reverts to pending.
    upd = client.patch("/tenant/settings/", json={"permission_message": "New language v2"})
    assert upd.status_code == 200, upd.text
    listed = client.get(f"/events/{ev['id']}/participants").json()
    assert listed[0]["permission_status"] == "pending"


# ---------------------------------------------------------------------------
# Sign-up window
# ---------------------------------------------------------------------------


def test_signup_window_blocks_member_after_deadline(client: TestClient, db_session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"], signup_deadline="2020-01-01")
    parent = _member(db_session, "Parent", MemberType.ADULT, user_id=NEW_USER_ID)
    pc = _parent_client()
    r = pc.post(f"/events/{ev['id']}/participants", json={"member_id": str(parent.id)})
    assert r.status_code == 409
    # Manager bypasses the closed window.
    ok = client.post(f"/events/{ev['id']}/participants", json={"member_id": str(parent.id)})
    assert ok.status_code == 201, ok.text


def test_signup_window_blocks_member_before_start(client: TestClient, db_session) -> None:
    et = _event_type(client)
    ev = _event(client, et["id"], signup_start="2099-01-01")
    parent = _member(db_session, "Parent", MemberType.ADULT, user_id=NEW_USER_ID)
    pc = _parent_client()
    r = pc.post(f"/events/{ev['id']}/participants", json={"member_id": str(parent.id)})
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Event-type validation & tenant settings
# ---------------------------------------------------------------------------


def test_permission_slip_requires_signups(client: TestClient) -> None:
    r = client.post(
        "/event-types/",
        json={"name": "Bad", "allow_signups": False, "require_permission_slip": True},
    )
    assert r.status_code == 422


def test_tenant_settings_default_and_update(client: TestClient, db_session) -> None:
    db_session.add(Tenant(id=TENANT_A, name="Troop A", slug="troop-a"))
    db_session.commit()
    # Defaults to the built-in language.
    default = client.get("/tenant/settings/").json()["permission_message"]
    assert default
    updated = client.patch("/tenant/settings/", json={"permission_message": "Our troop's language"})
    assert updated.status_code == 200
    assert updated.json()["permission_message"] == "Our troop's language"
    assert client.get("/tenant/settings/").json()["permission_message"] == "Our troop's language"
