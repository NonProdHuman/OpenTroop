"""Storage abstraction tests (GH-145, Phase 1).

Exercises the vendor-agnostic StorageService via the in-memory `fake` backend —
no cloud, no live DB. The reserve/confirm upload flow (issue #145 §7) is built on
`presign_put` → client PUT → `head` (server reads the real size back), so those
are the operations that matter here.
"""

from __future__ import annotations

import pytest

from app.core import storage as storage_mod
from app.core.storage import (
    FakeStorage,
    NullStorage,
    ObjectInfo,
    S3Storage,
    StorageNotConfigured,
    get_storage_service,
)


def test_fake_presign_put_encodes_key_and_content_type() -> None:
    svc = FakeStorage()
    url = svc.presign_put("tenant-1/photo/abc/display.jpg", content_type="image/jpeg")
    assert "tenant-1/photo/abc/display.jpg" in url
    assert "image/jpeg" in url


def test_fake_head_is_none_until_object_lands() -> None:
    svc = FakeStorage()
    key = "tenant-1/photo/abc/display.jpg"
    # Presigning does not create the object — only the client's PUT does.
    svc.presign_put(key, content_type="image/jpeg")
    assert svc.head(key) is None


def test_fake_head_reports_real_size_after_upload() -> None:
    """The confirm step trusts the server-side size, not the client's estimate."""
    svc = FakeStorage()
    key = "tenant-1/photo/abc/display.jpg"
    svc.put_object(key, b"x" * 1234, content_type="image/jpeg")
    info = svc.head(key)
    assert info == ObjectInfo(size_bytes=1234, content_type="image/jpeg")


def test_fake_get_and_delete_round_trip() -> None:
    svc = FakeStorage()
    key = "tenant-1/photo/abc/display.jpg"
    svc.put_object(key, b"bytes")
    assert key in svc.presign_get(key)
    svc.delete(key)
    assert svc.head(key) is None
    # Deleting a missing object is a no-op, not an error.
    svc.delete(key)


def test_null_storage_fails_loud_on_every_op() -> None:
    svc = NullStorage()
    with pytest.raises(StorageNotConfigured):
        svc.presign_put("k", content_type="image/jpeg")
    with pytest.raises(StorageNotConfigured):
        svc.presign_get("k")
    with pytest.raises(StorageNotConfigured):
        svc.head("k")
    with pytest.raises(StorageNotConfigured):
        svc.delete("k")


def test_selector_returns_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage_mod.settings, "storage_backend", "fake")
    assert isinstance(get_storage_service(), FakeStorage)


def test_selector_returns_null_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage_mod.settings, "storage_backend", "none")
    assert isinstance(get_storage_service(), NullStorage)


@pytest.mark.parametrize("backend", ["r2", "s3", "gcs"])
def test_selector_s3_backends_require_bucket_and_creds(
    monkeypatch: pytest.MonkeyPatch, backend: str
) -> None:
    monkeypatch.setattr(storage_mod.settings, "storage_backend", backend)
    monkeypatch.setattr(storage_mod.settings, "storage_bucket", "")
    with pytest.raises(StorageNotConfigured, match="STORAGE_BUCKET"):
        get_storage_service()
    monkeypatch.setattr(storage_mod.settings, "storage_bucket", "troop-media")
    monkeypatch.setattr(storage_mod.settings, "storage_access_key_id", "")
    with pytest.raises(StorageNotConfigured, match="STORAGE_ACCESS_KEY_ID"):
        get_storage_service()


def test_s3_driver_presigns_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Presigning is a local signature computation — no network, real URLs (ADR 0011)."""
    monkeypatch.setattr(storage_mod.settings, "storage_backend", "r2")
    monkeypatch.setattr(storage_mod.settings, "storage_bucket", "troop-media")
    monkeypatch.setattr(
        storage_mod.settings, "storage_s3_endpoint", "https://acct.r2.cloudflarestorage.com"
    )
    monkeypatch.setattr(storage_mod.settings, "storage_access_key_id", "test-key")
    monkeypatch.setattr(storage_mod.settings, "storage_secret_access_key", "test-secret")
    svc = get_storage_service()
    assert isinstance(svc, S3Storage)

    put_url = svc.presign_put("tenant-1/photo/abc/display.jpg", content_type="image/jpeg")
    assert put_url.startswith("https://acct.r2.cloudflarestorage.com/troop-media/")
    assert "tenant-1/photo/abc/display.jpg" in put_url
    assert "X-Amz-Signature=" in put_url  # SigV4, as R2 requires

    get_url = svc.presign_get("tenant-1/photo/abc/display.jpg")
    assert "X-Amz-Expires=" in get_url


def test_selector_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage_mod.settings, "storage_backend", "dropbox")
    with pytest.raises(RuntimeError, match="Unknown STORAGE_BACKEND"):
        get_storage_service()
