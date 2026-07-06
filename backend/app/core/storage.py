"""Vendor-agnostic object storage for event photos (GH-145).

App code talks to `StorageService`, never a cloud SDK directly. The backend is
selected once, in `get_storage_service()`, via `STORAGE_BACKEND` — the same
pattern as `get_notification_service()` / `get_push_backend()`.

Photo bytes never transit the API: the client uploads straight to the object
store with a presigned PUT and downloads with a presigned GET. The server only
mints those short-lived URLs, reads an object's size back (`head`) to confirm a
quota reservation, and deletes objects when a photo is purged.

R2 and GCS-interop are both "an S3 endpoint", so a single S3-compatible driver
covers them; the concrete driver is wired when the storage ADR lands (see the
issue #145 spec, §1). Today the abstraction plus the in-memory `fake` backend
ship, so the upload/quota flow is fully testable with no cloud and no live DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings


class StorageError(Exception):
    """Base class for storage-layer failures."""


class StorageNotConfigured(StorageError):
    """Raised when a storage operation is attempted with no backend configured."""


@dataclass(frozen=True)
class ObjectInfo:
    """The facts about a stored object the server needs after an upload lands."""

    size_bytes: int
    content_type: str | None = None


class StorageService(Protocol):
    """The storage operations the photo pipeline needs.

    Keys are opaque, forward-slash-delimited paths namespaced per tenant, e.g.
    ``<tenant_id>/photo/<photo_id>/display.jpg`` — the tenant prefix mirrors the
    ``tenant_id`` partitioning and keeps one troop's objects isolated.
    """

    def presign_put(self, key: str, *, content_type: str) -> str:
        """A short-lived URL the client PUTs the object bytes to."""

    def presign_get(self, key: str) -> str:
        """A short-lived URL the client GETs the object bytes from."""

    def head(self, key: str) -> ObjectInfo | None:
        """The object's server-side facts, or None if it does not exist."""

    def delete(self, key: str) -> None:
        """Remove the object. A no-op if it does not exist."""


class NullStorage:
    """Default backend: no storage configured (dev/self-host without a bucket).

    Any operation raises — a troop cannot use photos until a real backend is
    wired, and failing loudly beats silently dropping uploads.
    """

    def presign_put(self, key: str, *, content_type: str) -> str:
        raise StorageNotConfigured("No STORAGE_BACKEND is configured")

    def presign_get(self, key: str) -> str:
        raise StorageNotConfigured("No STORAGE_BACKEND is configured")

    def head(self, key: str) -> ObjectInfo | None:
        raise StorageNotConfigured("No STORAGE_BACKEND is configured")

    def delete(self, key: str) -> None:
        raise StorageNotConfigured("No STORAGE_BACKEND is configured")


@dataclass
class FakeStorage:
    """In-memory backend for tests and local dev — no cloud call.

    Presigned URLs are deterministic, unguessable-enough placeholders that encode
    the key. Because there is no real object store to receive the client's PUT,
    tests simulate the upload landing with :meth:`put_object`, after which
    :meth:`head` reports its size exactly as an S3 ``HEAD`` would.
    """

    objects: dict[str, ObjectInfo] = field(default_factory=dict)

    def put_object(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        """Simulate the client's presigned PUT completing (test helper)."""
        self.objects[key] = ObjectInfo(size_bytes=len(data), content_type=content_type)

    def presign_put(self, key: str, *, content_type: str) -> str:
        return f"https://fake-storage.local/put/{key}?content_type={content_type}"

    def presign_get(self, key: str) -> str:
        return f"https://fake-storage.local/get/{key}"

    def head(self, key: str) -> ObjectInfo | None:
        return self.objects.get(key)

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


def get_storage_service() -> StorageService:
    backend = settings.storage_backend
    if backend == "none":
        return NullStorage()
    if backend == "fake":
        return FakeStorage()
    if backend in ("r2", "s3", "gcs"):
        # The S3-compatible driver lands with the storage ADR (issue #145 §1),
        # which also adds the boto3 dependency. Until then, fail with a clear
        # pointer rather than a confusing import error.
        raise StorageNotConfigured(
            f"STORAGE_BACKEND={backend!r} is not wired yet — the S3-compatible "
            "driver ships with the storage ADR (see issue #145). Use 'fake' for "
            "tests/local dev."
        )
    raise RuntimeError(f"Unknown STORAGE_BACKEND: {backend!r}")
