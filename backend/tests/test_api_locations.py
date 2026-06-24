"""API tests for /locations/ endpoints."""

from fastapi.testclient import TestClient


def _create_location(client: TestClient, **overrides: object) -> dict:
    payload = {"name": "Camp Pendleton", "city": "Oceanside", "state": "CA", **overrides}
    r = client.post("/locations/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_location(client: TestClient) -> None:
    data = _create_location(client)
    assert data["name"] == "Camp Pendleton"
    assert data["city"] == "Oceanside"
    assert data["state"] == "CA"
    assert data["country"] == "US"
    assert data["is_deleted"] is False


def test_create_location_full_fields(client: TestClient) -> None:
    data = _create_location(
        client,
        name="Meeting Hall",
        street1="123 Main St",
        street2="Suite 1",
        city="San Diego",
        state="CA",
        postal_code="92101",
        phone="619-555-0100",
        website_url="https://example.com",
        directions="Turn left at the light",
        description="Our regular meeting spot",
        distance_miles=5.2,
    )
    assert data["street1"] == "123 Main St"
    assert data["phone"] == "619-555-0100"
    assert data["distance_miles"] == 5.2


def test_list_locations(client: TestClient) -> None:
    _create_location(client, name="Location A")
    _create_location(client, name="Location B")
    r = client.get("/locations/")
    assert r.status_code == 200
    names = {loc["name"] for loc in r.json()}
    assert {"Location A", "Location B"} <= names


def test_get_location(client: TestClient) -> None:
    loc = _create_location(client)
    r = client.get(f"/locations/{loc['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Camp Pendleton"


def test_get_location_not_found(client: TestClient) -> None:
    r = client.get("/locations/00000000-0000-0000-0000-000000000099")
    assert r.status_code == 404


def test_patch_location(client: TestClient) -> None:
    loc = _create_location(client)
    r = client.patch(f"/locations/{loc['id']}", json={"name": "Updated Name", "phone": "555-1234"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Updated Name"
    assert body["phone"] == "555-1234"
    assert body["city"] == "Oceanside"  # unchanged


def test_delete_location(client: TestClient) -> None:
    loc = _create_location(client)
    assert client.delete(f"/locations/{loc['id']}").status_code == 204
    assert client.get(f"/locations/{loc['id']}").status_code == 404


def test_deleted_excluded_from_list(client: TestClient) -> None:
    loc = _create_location(client)
    client.delete(f"/locations/{loc['id']}")
    ids = [x["id"] for x in client.get("/locations/").json()]
    assert loc["id"] not in ids


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    loc = _create_location(client)
    assert other_client.get(f"/locations/{loc['id']}").status_code == 404
    assert other_client.delete(f"/locations/{loc['id']}").status_code == 404
    ids = [x["id"] for x in other_client.get("/locations/").json()]
    assert loc["id"] not in ids
