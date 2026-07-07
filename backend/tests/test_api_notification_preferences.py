"""Self-service notification preferences + tenant digest cadence API (GH-218)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import AnnouncementEmailMode, MemberType
from app.models.member import Member
from app.models.tenant import Tenant
from tests.conftest import _ADMIN_MEMBER_IDS, TENANT_A


def test_get_preferences_defaults(client: TestClient) -> None:
    r = client.get("/members/me/notification-preferences")
    assert r.status_code == 200
    body = r.json()
    assert body["announcement_email_mode"] == "every"
    assert body["email_opt_out"] is False
    assert body["email_bounced"] is False


def test_patch_preferences_updates_self_only(client: TestClient, db_session: Session) -> None:
    # A second member in the same tenant that must remain untouched.
    other = Member(
        tenant_id=TENANT_A,
        first_name="Other",
        last_name="Member",
        member_type=MemberType.ADULT,
        email="other@x.test",
    )
    db_session.add(other)
    db_session.commit()

    r = client.patch(
        "/members/me/notification-preferences",
        json={"announcement_email_mode": "digest"},
    )
    assert r.status_code == 200
    assert r.json()["announcement_email_mode"] == "digest"

    # Persisted on the caller's own member row...
    admin = db_session.get(Member, _ADMIN_MEMBER_IDS[TENANT_A])
    assert admin is not None
    assert admin.announcement_email_mode == AnnouncementEmailMode.DIGEST
    # ...and only there.
    db_session.refresh(other)
    assert other.announcement_email_mode == AnnouncementEmailMode.EVERY


def test_patch_preferences_none(client: TestClient) -> None:
    r = client.patch(
        "/members/me/notification-preferences",
        json={"announcement_email_mode": "none"},
    )
    assert r.status_code == 200
    assert r.json()["announcement_email_mode"] == "none"


def test_preferences_require_membership(claim_client: TestClient) -> None:
    # A signed-in user with no Member row in the tenant cannot read/edit prefs.
    r = claim_client.get(
        "/members/me/notification-preferences",
        headers={"X-Tenant-ID": str(TENANT_A)},
    )
    assert r.status_code == 403


# --- Tenant digest cadence (admin settings) ----------------------------------


def test_settings_expose_digest_defaults(client: TestClient) -> None:
    r = client.get("/tenant/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["digest_day"] == 6
    assert body["digest_hour_utc"] == 16


def test_patch_digest_cadence(client: TestClient, db_session: Session) -> None:
    db_session.add(Tenant(id=TENANT_A, name="Troop A", slug="troopa"))
    db_session.commit()

    r = client.patch("/tenant/settings", json={"digest_day": 2, "digest_hour_utc": 9})
    assert r.status_code == 200
    body = r.json()
    assert body["digest_day"] == 2
    assert body["digest_hour_utc"] == 9

    tenant = db_session.get(Tenant, TENANT_A)
    assert tenant is not None
    assert tenant.digest_day == 2
    assert tenant.digest_hour_utc == 9


def test_patch_digest_cadence_validates_range(client: TestClient, db_session: Session) -> None:
    db_session.add(Tenant(id=TENANT_A, name="Troop A", slug="troopa"))
    db_session.commit()

    assert client.patch("/tenant/settings", json={"digest_day": 7}).status_code == 422
    assert client.patch("/tenant/settings", json={"digest_hour_utc": 24}).status_code == 422
