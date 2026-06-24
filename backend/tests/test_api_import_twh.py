"""API tests for POST /import/twh."""

from pathlib import Path

from fastapi.testclient import TestClient

_FIXTURE = Path(__file__).parent / "fixtures" / "sample_twh_minimal.xml"


def _upload(client: TestClient, path: Path = _FIXTURE) -> dict:
    with open(path, "rb") as f:
        r = client.post("/import/twh", files={"file": ("export.xml", f, "application/xml")})
    return r


def test_import_returns_summary(client: TestClient) -> None:
    r = _upload(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["patrols"] == 2
    assert body["members"] == 5
    assert body["relationships"] == 2
    assert body["locations"] == 2
    assert body["event_types"] == 3
    assert body["events"] == 3
    assert body["participants"] == 3
    assert body["skipped"] >= 1


def test_import_includes_warnings(client: TestClient) -> None:
    body = _upload(client).json()
    # Unknown relationship person and unknown event type each produce a warning.
    assert len(body["warnings"]) >= 2


def test_import_is_tenant_scoped(client: TestClient, other_client: TestClient) -> None:
    """Data imported via client must not be visible via other_client."""
    _upload(client)
    r = other_client.get("/members/")
    assert r.status_code == 200
    # other_client's tenant has no imported members (only the seeded admin)
    names = {m["first_name"] for m in r.json()}
    assert "Alice" not in names


def test_import_invalid_xml_returns_422(client: TestClient) -> None:
    r = client.post(
        "/import/twh",
        files={"file": ("bad.xml", b"<not valid xml<<<", "application/xml")},
    )
    assert r.status_code == 422
    assert "Invalid XML" in r.json()["detail"]


def test_import_requires_auth(client: TestClient) -> None:
    """Endpoint must reject unauthenticated requests."""
    from app.core.auth import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)
    try:
        with open(_FIXTURE, "rb") as f:
            r = client.post(
                "/import/twh",
                files={"file": ("export.xml", f, "application/xml")},
                headers={"X-Test-User-ID": ""},  # clears the override header
            )
        assert r.status_code == 401
    finally:
        from tests.conftest import _test_current_user

        app.dependency_overrides[get_current_user] = _test_current_user
