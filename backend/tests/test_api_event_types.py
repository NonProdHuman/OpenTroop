"""API tests for /event-types/ endpoints."""

from fastapi.testclient import TestClient

_DEFAULT_EVENT_TYPE_NAMES = {
    "Meeting",
    "Campout",
    "Hike",
    "Service Project",
    "Court of Honor",
    "Fundraiser",
}


def _create_event_type(client: TestClient, **overrides: object) -> dict:
    payload = {"name": "Custom Type", **overrides}
    r = client.post("/event-types/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _provision_and_claim(
    platform_admin_client: TestClient, claim_client: TestClient, slug: str, name: str
) -> str:
    """Provision a tenant (as platform admin) and have the founder claim it.

    Returns the new tenant id. After claiming, ``claim_client`` is the tenant's
    administrator and can exercise tenant-scoped routes.
    """
    r = platform_admin_client.post(
        "/platform/tenants",
        json={
            "name": name,
            "slug": slug,
            "founder_first_name": "Jane",
            "founder_last_name": "Leader",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    claim = claim_client.post("/auth/claim", json={"token": body["invite_token"]})
    assert claim.status_code == 200, claim.text
    return str(body["id"])


def test_create_event_type(client: TestClient) -> None:
    data = _create_event_type(client, name="Merit Badge Clinic", tracks_service_hours=True)
    assert data["name"] == "Merit Badge Clinic"
    assert data["tracks_service_hours"] is True
    assert data["is_system"] is False
    assert data["is_active"] is True
    assert data["is_deleted"] is False


def test_create_event_type_defaults(client: TestClient) -> None:
    data = _create_event_type(client)
    assert data["allow_signups"] is True
    assert data["require_permission_slip"] is False
    assert data["is_online"] is False
    assert data["tracks_mileage"] is False
    assert data["tracks_camping_nights"] is False


def test_list_event_types(client: TestClient) -> None:
    _create_event_type(client, name="Type A")
    _create_event_type(client, name="Type B")
    r = client.get("/event-types/")
    assert r.status_code == 200
    names = {et["name"] for et in r.json()}
    assert {"Type A", "Type B"} <= names


def test_get_event_type(client: TestClient) -> None:
    et = _create_event_type(client, name="Hike")
    r = client.get(f"/event-types/{et['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Hike"


def test_patch_event_type(client: TestClient) -> None:
    et = _create_event_type(client)
    r = client.patch(
        f"/event-types/{et['id']}",
        json={"name": "Updated", "tracks_camping_nights": True, "is_active": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Updated"
    assert body["tracks_camping_nights"] is True
    assert body["is_active"] is False


def test_delete_custom_event_type(client: TestClient) -> None:
    et = _create_event_type(client)
    assert client.delete(f"/event-types/{et['id']}").status_code == 204
    assert client.get(f"/event-types/{et['id']}").status_code == 404


def test_delete_system_event_type_rejected(client: TestClient) -> None:
    """System event types cannot be hard-deleted; disable via PATCH instead.

    is_system is set only by the seeder, never via the API. The full guard is
    exercised by test_system_type_guard_via_provisioning.
    """
    et = _create_event_type(client, name="Custom Type")
    assert et["is_system"] is False  # API-created types are never system


def test_system_type_guard_via_provisioning(
    platform_admin_client: TestClient, claim_client: TestClient
) -> None:
    """Tenant provisioning seeds 6 system EventTypes; none can be deleted."""
    tenant_id = _provision_and_claim(
        platform_admin_client, claim_client, "guard-test", "Troop Guard Test"
    )

    types_r = claim_client.get("/event-types/", headers={"X-Tenant-ID": tenant_id})
    assert types_r.status_code == 200
    system_types = [et for et in types_r.json() if et["is_system"]]
    assert len(system_types) > 0

    for et in system_types:
        del_r = claim_client.delete(f"/event-types/{et['id']}", headers={"X-Tenant-ID": tenant_id})
        assert del_r.status_code == 409


def test_provisioning_seeds_default_event_types(
    platform_admin_client: TestClient, claim_client: TestClient
) -> None:
    """POST /platform/tenants seeds 6 system EventTypes with the expected names."""
    tenant_id = _provision_and_claim(
        platform_admin_client, claim_client, "seed-test", "Troop Seed Test"
    )

    types_r = claim_client.get("/event-types/", headers={"X-Tenant-ID": tenant_id})
    assert types_r.status_code == 200
    names = {et["name"] for et in types_r.json()}
    assert names == _DEFAULT_EVENT_TYPE_NAMES


def test_campout_type_has_correct_flags(
    platform_admin_client: TestClient, claim_client: TestClient
) -> None:
    tenant_id = _provision_and_claim(
        platform_admin_client, claim_client, "flag-test", "Flag Test Troop"
    )
    types = claim_client.get("/event-types/", headers={"X-Tenant-ID": tenant_id}).json()
    campout = next(et for et in types if et["name"] == "Campout")
    assert campout["tracks_camping_nights"] is True
    assert campout["tracks_mileage"] is True
    assert campout["require_permission_slip"] is True


def test_meeting_type_no_signups(
    platform_admin_client: TestClient, claim_client: TestClient
) -> None:
    tenant_id = _provision_and_claim(
        platform_admin_client, claim_client, "meeting-test", "Meeting Test Troop"
    )
    types = claim_client.get("/event-types/", headers={"X-Tenant-ID": tenant_id}).json()
    meeting = next(et for et in types if et["name"] == "Meeting")
    assert meeting["allow_signups"] is False


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    et = _create_event_type(client, name="Private Type")
    assert other_client.get(f"/event-types/{et['id']}").status_code == 404
    ids = [x["id"] for x in other_client.get("/event-types/").json()]
    assert et["id"] not in ids
