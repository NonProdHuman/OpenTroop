"""Vendor-agnostic object storage for event photos (GH-145).

App code talks to `StorageService`, never a cloud SDK directly. The backend is
selected once, in `get_storage_service()`, via `STORAGE_BACKEND` — the same
pattern as `get_notification_service()` / `get_push_backend()`.

Photo bytes never transit the API: the client uploads straight to the object
store with a presigned PUT and downloads with a presigned GET. The server only
mints those short-lived URLs, reads an object's size back (`head`) to confirm a
quota reservation, and deletes objects when a photo is purged.

R2 and GCS-interop are both "an S3 endpoint", so a single S3-compatible driver
(`S3Storage`, boto3) covers `r2`/`s3`/`gcs` — the R2 choice is an env value, not
a code fork (ADR 0011). The in-memory `fake` backend keeps the upload/quota flow
fully testable with no cloud and no live DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

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


class S3Storage:
    """S3-compatible driver — covers Cloudflare R2, AWS S3, and GCS interop (ADR 0011).

    Presigning is a local signature computation (no network call); only ``head``
    and ``delete`` talk to the endpoint. The bucket must be private — presigned
    URLs are the *only* access path.
    """

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        presign_ttl_seconds: int,
    ) -> None:
        # boto3 is imported lazily so the (large) SDK loads only when an S3-family
        # backend is actually configured — tests and self-host `fake`/`none` skip it.
        import boto3
        from botocore.config import Config as BotoConfig

        self._bucket = bucket
        self._ttl = presign_ttl_seconds
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            # R2 requires SigV4; harmless everywhere else.
            config=BotoConfig(signature_version="s3v4"),
        )

    def presign_put(self, key: str, *, content_type: str) -> str:
        url: str = self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=self._ttl,
        )
        return url

    def presign_get(self, key: str) -> str:
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=self._ttl,
        )
        return url

    def head(self, key: str) -> ObjectInfo | None:
        from botocore.exceptions import ClientError

        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return None
            raise StorageError(f"HEAD failed for {key!r}: {code}") from exc
        return ObjectInfo(
            size_bytes=int(response["ContentLength"]),
            content_type=response.get("ContentType"),
        )

    def delete(self, key: str) -> None:
        from botocore.exceptions import ClientError

        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:  # pragma: no cover — vendor-side failure path
            code = exc.response.get("Error", {}).get("Code", "")
            raise StorageError(f"DELETE failed for {key!r}: {code}") from exc


_fake_storage: FakeStorage | None = None


def get_storage_service() -> StorageService:
    backend = settings.storage_backend
    if backend == "none":
        return NullStorage()
    if backend == "fake":
        # One process-wide instance so the simulated bucket persists across
        # requests — initiate mints a URL in one request, complete HEADs the
        # "uploaded" object in the next.
        global _fake_storage
        if _fake_storage is None:
            _fake_storage = FakeStorage()
        return _fake_storage
    if backend in ("r2", "s3", "gcs"):
        if not settings.storage_bucket:
            raise StorageNotConfigured(f"STORAGE_BACKEND={backend!r} requires STORAGE_BUCKET")
        if not settings.storage_access_key_id or not settings.storage_secret_access_key:
            raise StorageNotConfigured(
                f"STORAGE_BACKEND={backend!r} requires STORAGE_ACCESS_KEY_ID and "
                "STORAGE_SECRET_ACCESS_KEY"
            )
        return S3Storage(
            bucket=settings.storage_bucket,
            endpoint_url=settings.storage_s3_endpoint,
            region=settings.storage_region,
            access_key_id=settings.storage_access_key_id,
            secret_access_key=settings.storage_secret_access_key,
            presign_ttl_seconds=settings.storage_presign_ttl_seconds,
        )
    raise RuntimeError(f"Unknown STORAGE_BACKEND: {backend!r}")
