"""API tests for the event photo gallery + upload pipeline (GH-145).

Runs against the in-memory `fake` storage backend — the full reserve → PUT →
confirm flow with no cloud and no live Postgres.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import storage as storage_mod
from app.core.photo_reaper import reap_photo_uploads
from app.core.storage import FakeStorage, get_storage_service
from app.models.enums import MemberType, Permission, PhotoStatus
from app.models.event_photo import EventPhoto
from app.models.member import Member
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
from app.models.tenant import Tenant

TENANT_A = uuid.UUID("10000000-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("20000000-0000-0000-0000-000000000002")
NEW_USER_ID = uuid.UUID("c0000000-0000-0000-0000-000000000001")


@pytest.fixture
def fake_storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    """Route the app at a fresh in-memory bucket for this test."""
    monkeypatch.setattr(storage_mod.settings, "storage_backend", "fake")
    monkeypatch.setattr(storage_mod, "_fake_storage", None)
    storage = get_storage_service()
    assert isinstance(storage, FakeStorage)
    return storage


def _seed_tenant(db: Session, tenant_id: uuid.UUID = TENANT_A, **kwargs: Any) -> Tenant:
    tenant = Tenant(id=tenant_id, name="Troop Test", slug=f"troop-{tenant_id.hex[:6]}", **kwargs)
    db.add(tenant)
    db.commit()
    return tenant


def _event(client: TestClient, name: str = "Campout") -> dict[str, Any]:
    et = client.post("/event-types/", json={"name": f"Type-{name}"})
    assert et.status_code == 201, et.text
    r = client.post(
        "/events/",
        json={
            "name": name,
            "event_type_id": et.json()["id"],
            "scheduled_start": "2026-07-10T09:00:00Z",
            "scheduled_end": "2026-07-12T17:00:00Z",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _initiate_body(count: int = 1, byte_length: int = 500_000) -> dict[str, Any]:
    return {
        "photos": [
            {
                "content_type": "image/jpeg",
                "byte_length": byte_length,
                "width": 2048,
                "height": 1536,
                "thumbhash": "abc123",
            }
            for _ in range(count)
        ]
    }


def _upload_and_complete(
    client: TestClient,
    fake_storage: FakeStorage,
    event_id: str,
    *,
    byte_length: int = 500_000,
    actual_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Drive the full initiate → PUT → complete flow for one photo."""
    r = client.post(f"/events/{event_id}/photos/initiate", json=_initiate_body(1, byte_length))
    assert r.status_code == 201, r.text
    upload = r.json()["uploads"][0]
    key = f"{TENANT_A}/photo/{upload['photo_id']}/display.jpg"
    fake_storage.put_object(key, actual_bytes or b"x" * byte_length, content_type="image/jpeg")
    done = client.post(f"/photos/{upload['photo_id']}/complete")
    assert done.status_code == 200, done.text
    return done.json()


# --- Upload flow -----------------------------------------------------------


def test_initiate_reserves_and_mints_urls(
    client: TestClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    _seed_tenant(db_session)
    event = _event(client)
    r = client.post(f"/events/{event['id']}/photos/initiate", json=_initiate_body(2))
    assert r.status_code == 201
    uploads = r.json()["uploads"]
    assert len(uploads) == 2
    for upload in uploads:
        assert upload["photo_id"] in upload["upload_url"]

    usage = client.get("/storage/usage").json()
    assert usage["used_bytes"] == 0
    assert usage["reserved_bytes"] == 1_000_000

    photo = db_session.get(EventPhoto, uuid.UUID(uploads[0]["photo_id"]))
    assert photo is not None
    assert photo.status == PhotoStatus.PENDING
    assert photo.reserved_bytes == 500_000


def test_complete_verifies_size_and_settles_quota(
    client: TestClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    _seed_tenant(db_session)
    event = _event(client)
    # The client claimed 500 KB but actually uploaded 400 KB — the meter must
    # record the HEAD-verified truth, not the claim.
    photo = _upload_and_complete(
        client, fake_storage, event["id"], byte_length=500_000, actual_bytes=b"x" * 400_000
    )
    assert photo["status"] == "ready"
    assert photo["byte_size"] == 400_000

    db_session.expire_all()
    tenant = db_session.get(Tenant, TENANT_A)
    assert tenant is not None and tenant.used_storage_bytes == 400_000
    usage = client.get("/storage/usage").json()
    assert usage["used_bytes"] == 400_000
    assert usage["reserved_bytes"] == 0


def test_complete_is_idempotent(
    client: TestClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    _seed_tenant(db_session)
    event = _event(client)
    photo = _upload_and_complete(client, fake_storage, event["id"])
    again = client.post(f"/photos/{photo['id']}/complete")
    assert again.status_code == 200

    db_session.expire_all()
    tenant = db_session.get(Tenant, TENANT_A)
    assert tenant is not None and tenant.used_storage_bytes == 500_000  # counted once


def test_complete_before_put_is_409(
    client: TestClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    _seed_tenant(db_session)
    event = _event(client)
    r = client.post(f"/events/{event['id']}/photos/initiate", json=_initiate_body())
    photo_id = r.json()["uploads"][0]["photo_id"]
    done = client.post(f"/photos/{photo_id}/complete")
    assert done.status_code == 409


def test_complete_oversized_object_is_413_and_releases(
    client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.routers import photos as photos_router

    monkeypatch.setattr(photos_router.settings, "photo_max_upload_bytes", 1000)
    _seed_tenant(db_session)
    event = _event(client)
    r = client.post(f"/events/{event['id']}/photos/initiate", json=_initiate_body(1, 900))
    upload = r.json()["uploads"][0]
    key = f"{TENANT_A}/photo/{upload['photo_id']}/display.jpg"
    fake_storage.put_object(key, b"x" * 5000)  # lied in the reservation

    done = client.post(f"/photos/{upload['photo_id']}/complete")
    assert done.status_code == 413
    assert fake_storage.head(key) is None  # oversized object dropped
    photo = db_session.get(EventPhoto, uuid.UUID(upload["photo_id"]))
    assert photo is not None
    assert photo.status == PhotoStatus.FAILED
    assert photo.reserved_bytes == 0


# --- Quota enforcement -----------------------------------------------------


def test_initiate_over_quota_is_413(
    client: TestClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    _seed_tenant(db_session, storage_quota_bytes=600_000)
    event = _event(client)
    ok = client.post(f"/events/{event['id']}/photos/initiate", json=_initiate_body(1, 500_000))
    assert ok.status_code == 201
    # 500 KB reserved of a 600 KB quota — another 500 KB must be refused
    # before any presigned URL is issued.
    over = client.post(f"/events/{event['id']}/photos/initiate", json=_initiate_body(1, 500_000))
    assert over.status_code == 413


def test_initiate_per_file_cap_is_413(
    client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.routers import photos as photos_router

    monkeypatch.setattr(photos_router.settings, "photo_max_upload_bytes", 1000)
    _seed_tenant(db_session)
    event = _event(client)
    r = client.post(f"/events/{event['id']}/photos/initiate", json=_initiate_body(1, 2000))
    assert r.status_code == 413


def test_initiate_batch_cap_is_422(
    client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.routers import photos as photos_router

    monkeypatch.setattr(photos_router.settings, "photo_max_batch", 2)
    _seed_tenant(db_session)
    event = _event(client)
    r = client.post(f"/events/{event['id']}/photos/initiate", json=_initiate_body(3))
    assert r.status_code == 422


def test_initiate_rejects_non_image_content_type(
    client: TestClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    _seed_tenant(db_session)
    event = _event(client)
    body = _initiate_body()
    body["photos"][0]["content_type"] = "application/pdf"
    r = client.post(f"/events/{event['id']}/photos/initiate", json=body)
    assert r.status_code == 422


# --- Gallery + visibility --------------------------------------------------


def test_list_returns_ready_photos_with_urls(
    client: TestClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    _seed_tenant(db_session)
    event = _event(client)
    photo = _upload_and_complete(client, fake_storage, event["id"])
    # A second, never-completed upload must not appear.
    client.post(f"/events/{event['id']}/photos/initiate", json=_initiate_body())

    listed = client.get(f"/events/{event['id']}/photos")
    assert listed.status_code == 200
    items = listed.json()
    assert [p["id"] for p in items] == [photo["id"]]
    assert items[0]["display_url"]
    assert items[0]["thumbhash"] == "abc123"


def _seed_photo_member(db: Session) -> Member:
    """A member linked to NEW_USER_ID holding event:read + photo perms (no manage)."""
    role = FunctionalRole(tenant_id=TENANT_A, name="Snapper", slug="snapper")
    db.add(role)
    db.flush()
    for perm in (Permission.EVENT_READ, Permission.PHOTO_READ, Permission.PHOTO_UPLOAD):
        db.add(
            FunctionalRolePermission(
                tenant_id=TENANT_A, functional_role_id=role.id, permission=perm
            )
        )
    position = Position(tenant_id=TENANT_A, name="Snapper", slug="snapper-position")
    db.add(position)
    db.flush()
    db.add(
        PositionFunctionalRole(
            tenant_id=TENANT_A, position_id=position.id, functional_role_id=role.id
        )
    )
    member = Member(
        tenant_id=TENANT_A,
        user_id=NEW_USER_ID,
        first_name="Snapper",
        last_name="One",
        member_type=MemberType.ADULT,
    )
    db.add(member)
    db.flush()
    db.add(
        MemberPositionAssignment(tenant_id=TENANT_A, member_id=member.id, position_id=position.id)
    )
    db.commit()
    return member


def test_scoped_event_gallery_hidden_from_non_audience(
    client: TestClient,
    claim_client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
) -> None:
    _seed_tenant(db_session)
    event = _event(client, name="Wolf-only")
    group = client.post("/groups/", json={"name": "Wolf", "group_type": "custom"}).json()
    client.post(f"/events/{event['id']}/audiences", json={"group_id": group["id"]})
    _upload_and_complete(client, fake_storage, event["id"])

    member = _seed_photo_member(db_session)
    headers = {"X-Tenant-ID": str(TENANT_A)}

    # Outside the audience: the gallery 404s (existence not leaked), and so
    # does an upload attempt against the hidden event.
    assert claim_client.get(f"/events/{event['id']}/photos", headers=headers).status_code == 404
    blocked = claim_client.post(
        f"/events/{event['id']}/photos/initiate", json=_initiate_body(), headers=headers
    )
    assert blocked.status_code == 404

    # In the audience: gallery and upload both open up.
    joined = client.post(f"/groups/{group['id']}/members", json={"member_id": str(member.id)})
    assert joined.status_code == 201
    assert claim_client.get(f"/events/{event['id']}/photos", headers=headers).status_code == 200
    allowed = claim_client.post(
        f"/events/{event['id']}/photos/initiate", json=_initiate_body(), headers=headers
    )
    assert allowed.status_code == 201


def test_cross_tenant_photo_is_404(
    client: TestClient,
    other_client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
) -> None:
    _seed_tenant(db_session)
    event = _event(client)
    photo = _upload_and_complete(client, fake_storage, event["id"])
    assert other_client.get(f"/photos/{photo['id']}/download").status_code == 404
    cross_delete = other_client.delete(f"/photos/{photo['id']}")
    assert cross_delete.status_code == 404


# --- Download / caption / delete ------------------------------------------


def test_download_variants(
    client: TestClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    _seed_tenant(db_session)
    event = _event(client)
    photo = _upload_and_complete(client, fake_storage, event["id"])

    display = client.get(f"/photos/{photo['id']}/download")
    assert display.status_code == 200
    assert photo["id"] in display.json()["url"]
    # No original kept by default.
    assert client.get(f"/photos/{photo['id']}/download?variant=original").status_code == 404
    assert client.get(f"/photos/{photo['id']}/download?variant=raw").status_code == 422


def test_owner_can_caption_and_delete_own_photo(
    client: TestClient,
    claim_client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
) -> None:
    _seed_tenant(db_session)
    event = _event(client)
    _seed_photo_member(db_session)
    headers = {"X-Tenant-ID": str(TENANT_A)}

    r = claim_client.post(
        f"/events/{event['id']}/photos/initiate", json=_initiate_body(), headers=headers
    )
    upload = r.json()["uploads"][0]
    key = f"{TENANT_A}/photo/{upload['photo_id']}/display.jpg"
    fake_storage.put_object(key, b"x" * 500_000)
    claim_client.post(f"/photos/{upload['photo_id']}/complete", headers=headers)

    patched = claim_client.patch(
        f"/photos/{upload['photo_id']}", json={"caption": "Summit!"}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["caption"] == "Summit!"

    deleted = claim_client.delete(f"/photos/{upload['photo_id']}", headers=headers)
    assert deleted.status_code == 204
    db_session.expire_all()
    tenant = db_session.get(Tenant, TENANT_A)
    assert tenant is not None and tenant.used_storage_bytes == 0  # meter released


def test_non_owner_without_moderate_cannot_delete(
    client: TestClient,
    claim_client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
) -> None:
    _seed_tenant(db_session)
    event = _event(client)
    admin_photo = _upload_and_complete(client, fake_storage, event["id"])
    _seed_photo_member(db_session)
    headers = {"X-Tenant-ID": str(TENANT_A)}

    blocked = claim_client.delete(f"/photos/{admin_photo['id']}", headers=headers)
    assert blocked.status_code == 403
    # The admin holds the is_admin role (⇒ photo:moderate) and may delete anyone's.
    moderated = client.delete(f"/photos/{admin_photo['id']}")
    assert moderated.status_code == 204


# --- Reaper -----------------------------------------------------------------


def test_reaper_sweeps_stale_pending_and_deleted(
    client: TestClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    _seed_tenant(db_session)
    event = _event(client)

    # A stale PENDING upload whose object landed but was never confirmed.
    r = client.post(f"/events/{event['id']}/photos/initiate", json=_initiate_body())
    stale_id = uuid.UUID(r.json()["uploads"][0]["photo_id"])
    stale_key = f"{TENANT_A}/photo/{stale_id}/display.jpg"
    fake_storage.put_object(stale_key, b"x" * 100)
    stale = db_session.get(EventPhoto, stale_id)
    assert stale is not None
    stale.created_at = datetime.now(UTC) - timedelta(hours=48)
    db_session.commit()

    # A completed photo that was then soft-deleted (bytes awaiting cleanup).
    done = _upload_and_complete(client, fake_storage, event["id"])
    client.delete(f"/photos/{done['id']}")
    done_key = f"{TENANT_A}/photo/{done['id']}/display.jpg"
    assert fake_storage.head(done_key) is not None

    swept_stale, swept_deleted = reap_photo_uploads(db_session, fake_storage)
    db_session.commit()
    assert (swept_stale, swept_deleted) == (1, 1)
    assert fake_storage.head(stale_key) is None
    assert fake_storage.head(done_key) is None

    db_session.expire_all()
    reaped = db_session.get(EventPhoto, stale_id)
    assert reaped is not None
    assert reaped.status == PhotoStatus.PURGED
    assert reaped.reserved_bytes == 0
    assert reaped.is_deleted is True

    # Idempotent: nothing left to sweep.
    rerun = reap_photo_uploads(db_session, fake_storage)
    assert rerun == (0, 0)
