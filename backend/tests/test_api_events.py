"""API tests for /events/ endpoints — Events, Organizers, and Participants."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_event_type(client: TestClient, **overrides: object) -> dict:
    payload = {"name": "Campout", "tracks_camping_nights": True, **overrides}
    r = client.post("/event-types/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _create_location(client: TestClient) -> dict:
    r = client.post("/locations/", json={"name": "Camp Oak"})
    assert r.status_code == 201, r.text
    return r.json()


def _create_member(client: TestClient, first_name: str = "Scout") -> dict:
    r = client.post(
        "/members/", json={"first_name": first_name, "last_name": "Jones", "member_type": "scout"}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_event(client: TestClient, event_type_id: str, **overrides: object) -> dict:
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


# ---------------------------------------------------------------------------
# Events — CRUD
# ---------------------------------------------------------------------------


def test_create_event(client: TestClient) -> None:
    et = _create_event_type(client)
    data = _create_event(client, et["id"])
    assert data["name"] == "Summer Campout"
    assert data["event_type_id"] == et["id"]
    assert data["attendance_taken"] is False
    assert data["is_deleted"] is False
    assert data["event_type"]["name"] == "Campout"


def _parse_iso(value: str) -> datetime:
    # Python's fromisoformat handles a trailing "Z" from 3.11 onward.
    return datetime.fromisoformat(value)


def test_create_event_normalizes_offset_to_utc(client: TestClient) -> None:
    """A non-UTC offset in the request is stored and returned as UTC."""
    et = _create_event_type(client)
    # 09:00 at -05:00 == 14:00 UTC.
    data = _create_event(
        client,
        et["id"],
        scheduled_start="2026-07-10T09:00:00-05:00",
        scheduled_end="2026-07-10T17:00:00-05:00",
    )
    start = _parse_iso(data["scheduled_start"])
    end = _parse_iso(data["scheduled_end"])
    assert start.utcoffset() == timedelta(0)
    assert start == datetime(2026, 7, 10, 14, 0, tzinfo=UTC)
    assert end == datetime(2026, 7, 10, 22, 0, tzinfo=UTC)


def test_create_event_naive_datetime_assumed_utc(client: TestClient) -> None:
    """A naive datetime (no offset) is treated as UTC and returned with a zone."""
    et = _create_event_type(client)
    data = _create_event(
        client,
        et["id"],
        scheduled_start="2026-07-10T09:00:00",
        scheduled_end="2026-07-10T17:00:00",
    )
    start = _parse_iso(data["scheduled_start"])
    assert start.utcoffset() == timedelta(0)
    assert start == datetime(2026, 7, 10, 9, 0, tzinfo=UTC)


def test_event_read_timestamps_are_utc(client: TestClient) -> None:
    """Server-managed timestamps surface as timezone-aware UTC."""
    et = _create_event_type(client)
    data = _create_event(client, et["id"])
    assert _parse_iso(data["created_at"]).utcoffset() == timedelta(0)


def test_create_event_with_location(client: TestClient) -> None:
    et = _create_event_type(client)
    loc = _create_location(client)
    data = _create_event(client, et["id"], location_id=loc["id"])
    assert data["location_id"] == loc["id"]
    assert data["location"]["name"] == "Camp Oak"


def test_create_event_with_all_optional_fields(client: TestClient) -> None:
    et = _create_event_type(client)
    data = _create_event(
        client,
        et["id"],
        departure_location="Church parking lot",
        return_location="Same location",
        camping_nights=2,
        cost_youth="25.00",
        cost_adult="30.00",
        signup_limit_scouts=20,
        signup_limit_adults=5,
        tour_permit_submitted=False,
    )
    assert data["departure_location"] == "Church parking lot"
    assert data["return_location"] == "Same location"
    assert data["camping_nights"] == 2
    assert data["tour_permit_submitted"] is False


def test_create_event_wrong_tenant_event_type(client: TestClient, other_client: TestClient) -> None:
    et = _create_event_type(other_client)
    r = client.post(
        "/events/",
        json={
            "name": "X",
            "event_type_id": et["id"],
            "scheduled_start": "2026-07-10T09:00:00Z",
            "scheduled_end": "2026-07-10T17:00:00Z",
        },
    )
    assert r.status_code == 422


def test_create_event_wrong_tenant_location(client: TestClient, other_client: TestClient) -> None:
    et = _create_event_type(client)
    loc = _create_location(other_client)
    r = client.post(
        "/events/",
        json={
            "name": "X",
            "event_type_id": et["id"],
            "location_id": loc["id"],
            "scheduled_start": "2026-07-10T09:00:00Z",
            "scheduled_end": "2026-07-10T17:00:00Z",
        },
    )
    assert r.status_code == 422


def test_list_events(client: TestClient) -> None:
    et = _create_event_type(client)
    _create_event(client, et["id"], name="Event A")
    _create_event(client, et["id"], name="Event B")
    r = client.get("/events/")
    assert r.status_code == 200
    names = {e["name"] for e in r.json()}
    assert {"Event A", "Event B"} <= names


def test_get_event(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    r = client.get(f"/events/{ev['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Summer Campout"


def test_patch_event(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    r = client.patch(
        f"/events/{ev['id']}",
        json={"name": "Winter Campout", "camping_nights": 3, "attendance_taken": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Winter Campout"
    assert body["camping_nights"] == 3
    assert body["attendance_taken"] is True


def test_delete_event(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    assert client.delete(f"/events/{ev['id']}").status_code == 204
    assert client.get(f"/events/{ev['id']}").status_code == 404


def test_deleted_excluded_from_list(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    client.delete(f"/events/{ev['id']}")
    ids = [x["id"] for x in client.get("/events/").json()]
    assert ev["id"] not in ids


def test_linked_event(client: TestClient) -> None:
    et = _create_event_type(client)
    parent = _create_event(client, et["id"], name="Planning Meeting")
    child = _create_event(client, et["id"], name="Campout", linked_event_id=parent["id"])
    assert child["linked_event_id"] == parent["id"]


def test_linked_event_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    et_a = _create_event_type(client)
    et_b = _create_event_type(other_client)
    other_ev = _create_event(other_client, et_b["id"])
    r = client.post(
        "/events/",
        json={
            "name": "X",
            "event_type_id": et_a["id"],
            "scheduled_start": "2026-07-10T09:00:00Z",
            "scheduled_end": "2026-07-10T17:00:00Z",
            "linked_event_id": other_ev["id"],
        },
    )
    assert r.status_code == 422


def test_tenant_isolation_events(client: TestClient, other_client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    assert other_client.get(f"/events/{ev['id']}").status_code == 404
    ids = [x["id"] for x in other_client.get("/events/").json()]
    assert ev["id"] not in ids


# ---------------------------------------------------------------------------
# Organizers
# ---------------------------------------------------------------------------


def test_add_and_list_organizer(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    r = client.post(f"/events/{ev['id']}/organizers", json={"member_id": member["id"]})
    assert r.status_code == 201
    assert r.json()["member_id"] == member["id"]

    listed = client.get(f"/events/{ev['id']}/organizers").json()
    assert any(o["member_id"] == member["id"] for o in listed)


def test_add_organizer_duplicate(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    client.post(f"/events/{ev['id']}/organizers", json={"member_id": member["id"]})
    r = client.post(f"/events/{ev['id']}/organizers", json={"member_id": member["id"]})
    assert r.status_code == 409


def test_add_organizer_wrong_tenant_member(client: TestClient, other_client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    other_member = _create_member(other_client)
    r = client.post(f"/events/{ev['id']}/organizers", json={"member_id": other_member["id"]})
    assert r.status_code == 422


def test_remove_organizer(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    client.post(f"/events/{ev['id']}/organizers", json={"member_id": member["id"]})
    assert client.delete(f"/events/{ev['id']}/organizers/{member['id']}").status_code == 204
    listed = client.get(f"/events/{ev['id']}/organizers").json()
    assert not any(o["member_id"] == member["id"] for o in listed)


def test_remove_organizer_not_found(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    r = client.delete(f"/events/{ev['id']}/organizers/00000000-0000-0000-0000-000000000099")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------


def test_add_and_list_participant(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    r = client.post(f"/events/{ev['id']}/participants", json={"member_id": member["id"]})
    assert r.status_code == 201
    body = r.json()
    assert body["member_id"] == member["id"]
    assert body["signed_up"] is True
    assert body["rsvp_status"] == "no_response"
    assert body["attended"] is None
    assert body["permission_slip_submitted"] is False

    listed = client.get(f"/events/{ev['id']}/participants").json()
    assert any(p["member_id"] == member["id"] for p in listed)


def test_update_participant_rsvp_status(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    client.post(f"/events/{ev['id']}/participants", json={"member_id": member["id"]})

    r = client.patch(
        f"/events/{ev['id']}/participants/{member['id']}",
        json={"rsvp_status": "declined"},
    )
    assert r.status_code == 200
    assert r.json()["rsvp_status"] == "declined"


def test_create_participant_with_rsvp_status(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    r = client.post(
        f"/events/{ev['id']}/participants",
        json={"member_id": member["id"], "rsvp_status": "going"},
    )
    assert r.status_code == 201
    assert r.json()["rsvp_status"] == "going"


def test_add_participant_duplicate(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    client.post(f"/events/{ev['id']}/participants", json={"member_id": member["id"]})
    r = client.post(f"/events/{ev['id']}/participants", json={"member_id": member["id"]})
    assert r.status_code == 409


def test_add_participant_wrong_tenant_member(client: TestClient, other_client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    other_member = _create_member(other_client)
    r = client.post(f"/events/{ev['id']}/participants", json={"member_id": other_member["id"]})
    assert r.status_code == 422


def test_update_participant_permission_slip(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    client.post(f"/events/{ev['id']}/participants", json={"member_id": member["id"]})
    r = client.patch(
        f"/events/{ev['id']}/participants/{member['id']}",
        json={"permission_slip_submitted": True},
    )
    assert r.status_code == 200
    assert r.json()["permission_slip_submitted"] is True


def test_update_participant_activity_overrides(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    client.post(f"/events/{ev['id']}/participants", json={"member_id": member["id"]})
    r = client.patch(
        f"/events/{ev['id']}/participants/{member['id']}",
        json={"camping_nights_override": 1, "hiking_miles_override": "3.5"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["camping_nights_override"] == 1
    assert float(body["hiking_miles_override"]) == 3.5


def test_update_participant_attended_blocked_without_attendance_open(
    client: TestClient,
) -> None:
    """Marking attended=True is rejected when attendance_taken is False on the event."""
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    client.post(f"/events/{ev['id']}/participants", json={"member_id": member["id"]})
    r = client.patch(
        f"/events/{ev['id']}/participants/{member['id']}",
        json={"attended": True},
    )
    assert r.status_code == 409


def test_update_participant_attended_allowed_when_attendance_open(
    client: TestClient,
) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    client.patch(f"/events/{ev['id']}", json={"attendance_taken": True})
    member = _create_member(client)
    client.post(f"/events/{ev['id']}/participants", json={"member_id": member["id"]})
    r = client.patch(
        f"/events/{ev['id']}/participants/{member['id']}",
        json={"attended": True},
    )
    assert r.status_code == 200
    assert r.json()["attended"] is True


def test_remove_participant(client: TestClient) -> None:
    et = _create_event_type(client)
    ev = _create_event(client, et["id"])
    member = _create_member(client)
    client.post(f"/events/{ev['id']}/participants", json={"member_id": member["id"]})
    assert client.delete(f"/events/{ev['id']}/participants/{member['id']}").status_code == 204
    listed = client.get(f"/events/{ev['id']}/participants").json()
    assert not any(p["member_id"] == member["id"] for p in listed)


# ---------------------------------------------------------------------------
# Member OA fields
# ---------------------------------------------------------------------------


def test_member_oa_fields_round_trip(client: TestClient) -> None:
    r = client.post(
        "/members/",
        json={
            "first_name": "Arrow",
            "last_name": "Scout",
            "member_type": "scout",
            "oa_member": True,
            "oa_active": True,
            "oa_election_date": "2024-03-15",
            "oa_ordeal_date": "2024-06-01",
            "oa_vigil_name": "Running Deer",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["oa_member"] is True
    assert body["oa_active"] is True
    assert body["oa_election_date"] == "2024-03-15"
    assert body["oa_ordeal_date"] == "2024-06-01"
    assert body["oa_vigil_name"] == "Running Deer"


def test_member_oa_defaults_false(client: TestClient) -> None:
    r = client.post(
        "/members/",
        json={"first_name": "Plain", "last_name": "Scout", "member_type": "scout"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["oa_member"] is False
    assert body["oa_active"] is False
    assert body["oa_election_date"] is None
    assert body["oa_vigil_name"] is None


def test_member_oa_patch(client: TestClient) -> None:
    r = client.post(
        "/members/",
        json={"first_name": "New", "last_name": "Member", "member_type": "scout"},
    )
    member = r.json()
    r2 = client.patch(
        f"/members/{member['id']}",
        json={"oa_member": True, "oa_call_out_date": "2025-09-20"},
    )
    assert r2.status_code == 200
    assert r2.json()["oa_member"] is True
    assert r2.json()["oa_call_out_date"] == "2025-09-20"
