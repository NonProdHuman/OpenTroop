"""API tests for POST /import/twh."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings

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


def test_import_with_timezone_converts_event_times_to_utc(client: TestClient) -> None:
    with open(_FIXTURE, "rb") as f:
        r = client.post(
            "/import/twh",
            files={"file": ("export.xml", f, "application/xml")},
            data={"timezone": "America/New_York"},
        )
    assert r.status_code == 200, r.text

    events = client.get("/events/").json()
    meeting = next(e for e in events if e["name"] == "Weekly Meeting")
    # 7PM EDT (UTC-4 in September) → 23:00 UTC.
    assert datetime.fromisoformat(meeting["scheduled_start"]).astimezone(UTC).hour == 23


def test_import_invalid_timezone_returns_422(client: TestClient) -> None:
    with open(_FIXTURE, "rb") as f:
        r = client.post(
            "/import/twh",
            files={"file": ("export.xml", f, "application/xml")},
            data={"timezone": "Not/AZone"},
        )
    assert r.status_code == 422
    assert "Unknown timezone" in r.json()["detail"]


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


def test_import_with_gzipped_file(client: TestClient) -> None:
    import gzip

    with open(_FIXTURE, "rb") as f:
        xml_data = f.read()

    gz_data = gzip.compress(xml_data)

    r = client.post(
        "/import/twh",
        files={"file": ("export.xml.gz", gz_data, "application/gzip")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["patrols"] == 2
    assert body["members"] == 5


def test_import_with_zipped_file(client: TestClient) -> None:
    import io
    import zipfile

    with open(_FIXTURE, "rb") as f:
        xml_data = f.read()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("export.xml", xml_data)
    zip_data = zip_buffer.getvalue()

    r = client.post(
        "/import/twh",
        files={"file": ("export.zip", zip_data, "application/zip")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["patrols"] == 2
    assert body["members"] == 5


def test_import_invalid_gzip_returns_422(client: TestClient) -> None:
    r = client.post(
        "/import/twh",
        files={"file": ("bad.xml.gz", b"not valid gzip data", "application/gzip")},
    )
    assert r.status_code == 422
    assert "Invalid GZIP compression" in r.json()["detail"]


def test_import_zip_without_xml_returns_422(client: TestClient) -> None:
    import io
    import zipfile

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("readme.txt", b"this is not an xml file")
    zip_data = zip_buffer.getvalue()

    r = client.post(
        "/import/twh",
        files={"file": ("no_xml.zip", zip_data, "application/zip")},
    )
    assert r.status_code == 422
    assert "No XML file found inside ZIP archive" in r.json()["detail"]


# ---------------------------------------------------------------------------
# GH-175 Finding 2 — size caps (413) and defensive XML parsing (422)
# ---------------------------------------------------------------------------


def test_import_oversized_upload_returns_413(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "twh_import_max_upload_bytes", 1024)
    r = client.post(
        "/import/twh",
        files={"file": ("export.xml", b"x" * 2048, "application/xml")},
    )
    assert r.status_code == 413
    assert "maximum" in r.json()["detail"].lower()


def test_import_gzip_bomb_returns_413(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A few-KB gzip that expands past the decompression cap must be rejected."""
    import gzip

    monkeypatch.setattr(settings, "twh_import_max_decompressed_bytes", 64 * 1024)
    bomb = gzip.compress(b"\x00" * (1024 * 1024))  # ~1 MiB of zeros → ~1 KiB gzipped
    assert len(bomb) < 8 * 1024, "test premise: the compressed bomb itself is tiny"

    r = client.post(
        "/import/twh",
        files={"file": ("export.xml.gz", bomb, "application/gzip")},
    )
    assert r.status_code == 413


def test_import_zip_bomb_entry_returns_413(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io
    import zipfile

    monkeypatch.setattr(settings, "twh_import_max_decompressed_bytes", 64 * 1024)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("export.xml", b"\x00" * (1024 * 1024))

    r = client.post(
        "/import/twh",
        files={"file": ("export.zip", zip_buffer.getvalue(), "application/zip")},
    )
    assert r.status_code == 413


def test_import_zip_too_many_entries_returns_413(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io
    import zipfile

    monkeypatch.setattr(settings, "twh_import_max_zip_entries", 4)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(5):
            zf.writestr(f"file{i}.txt", b"x")

    r = client.post(
        "/import/twh",
        files={"file": ("many.zip", zip_buffer.getvalue(), "application/zip")},
    )
    assert r.status_code == 413
    assert "entries" in r.json()["detail"]


def test_import_invalid_zip_returns_422(client: TestClient) -> None:
    r = client.post(
        "/import/twh",
        files={"file": ("bad.zip", b"not a zip archive at all", "application/zip")},
    )
    assert r.status_code == 422
    assert "Invalid ZIP archive" in r.json()["detail"]


def test_import_xml_with_entities_returns_422(client: TestClient) -> None:
    """defusedxml must reject entity declarations (XXE / billion-laughs vector)."""
    hostile = b'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY bomb "boom">]><foo>&bomb;</foo>'
    r = client.post(
        "/import/twh",
        files={"file": ("evil.xml", hostile, "application/xml")},
    )
    assert r.status_code == 422
    assert "Invalid XML" in r.json()["detail"]
