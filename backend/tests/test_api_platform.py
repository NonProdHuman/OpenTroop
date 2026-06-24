"""API tests for the /platform control-plane: tenant + tenant-admin management."""

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.tenant import get_tenant_id
from app.models.enums import PlatformRole
from app.models.tenant import Tenant
from app.models.user import User
from tests.conftest import NEW_USER_ID


def _provision(client: TestClient, slug: str = "troop123", **overrides: object) -> dict:
    payload = {
        "name": "Troop 123",
        "slug": slug,
        "founder_first_name": "Jane",
        "founder_last_name": "Leader",
        "founder_email": "jane@example.com",
        **overrides,
    }
    r = client.post("/platform/tenants", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Tenant provisioning
# ---------------------------------------------------------------------------


def test_provision_creates_tenant(platform_admin_client: TestClient) -> None:
    data = _provision(platform_admin_client)
    assert data["name"] == "Troop 123"
    assert data["slug"] == "troop123"
    assert data["is_deleted"] is False
    assert data["suspended_at"] is None
    assert data["founder_member_id"]
    assert data["invite_token"]
    assert data["invite_expires_at"]


def test_provision_slug_conflict(platform_admin_client: TestClient) -> None:
    _provision(platform_admin_client, "troop456")
    r = platform_admin_client.post(
        "/platform/tenants",
        json={
            "name": "Other",
            "slug": "troop456",
            "founder_first_name": "X",
            "founder_last_name": "Y",
        },
    )
    assert r.status_code == 409


def test_provision_requires_platform_admin(claim_client: TestClient) -> None:
    """An ordinary signed-in user (no platform_role) cannot create tenants."""
    r = claim_client.post(
        "/platform/tenants",
        json={"name": "X", "slug": "x", "founder_first_name": "A", "founder_last_name": "B"},
    )
    assert r.status_code == 403


def test_provision_no_auth_returns_401(platform_admin_client: TestClient) -> None:
    r = platform_admin_client.post(
        "/platform/tenants",
        json={"name": "X", "slug": "x", "founder_first_name": "A", "founder_last_name": "B"},
        headers={"X-Test-User-ID": ""},  # clear the default header
    )
    assert r.status_code == 401


def test_founder_claims_then_administers(
    platform_admin_client: TestClient, claim_client: TestClient
) -> None:
    """End-to-end: platform admin provisions; founder claims the invite, then has admin access."""
    tenant = _provision(platform_admin_client, "troop789")
    tenant_id = tenant["id"]

    # Before claiming, the founder is not yet a member — tenant routes are forbidden.
    assert claim_client.get("/members/", headers={"X-Tenant-ID": tenant_id}).status_code == 403

    claimed = claim_client.post("/auth/claim", json={"token": tenant["invite_token"]})
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["id"] == tenant["founder_member_id"]
    assert claimed.json()["user_id"] == str(NEW_USER_ID)

    members = claim_client.get("/members/", headers={"X-Tenant-ID": tenant_id}).json()
    assert len(members) == 1
    assert members[0]["first_name"] == "Jane"
    assert members[0]["user_id"] == str(NEW_USER_ID)


# ---------------------------------------------------------------------------
# Tenant listing / detail / suspension
# ---------------------------------------------------------------------------


def test_list_and_get_tenants(platform_admin_client: TestClient) -> None:
    a = _provision(platform_admin_client, "troop-a", name="Troop A")
    b = _provision(platform_admin_client, "troop-b", name="Troop B")

    listing = platform_admin_client.get("/platform/tenants")
    assert listing.status_code == 200
    ids = {t["id"] for t in listing.json()}
    assert {a["id"], b["id"]} <= ids

    detail = platform_admin_client.get(f"/platform/tenants/{a['id']}")
    assert detail.status_code == 200
    assert detail.json()["slug"] == "troop-a"

    missing = platform_admin_client.get(f"/platform/tenants/{uuid.uuid4()}")
    assert missing.status_code == 404


def test_list_tenants_requires_platform_admin(claim_client: TestClient) -> None:
    assert claim_client.get("/platform/tenants").status_code == 403


def test_suspend_and_unsuspend(platform_admin_client: TestClient) -> None:
    tenant = _provision(platform_admin_client, "troop-susp")
    tid = tenant["id"]

    suspended = platform_admin_client.post(f"/platform/tenants/{tid}/suspend")
    assert suspended.status_code == 200
    assert suspended.json()["suspended_at"] is not None

    # Idempotent — suspending again keeps the same timestamp.
    first_ts = suspended.json()["suspended_at"]
    again = platform_admin_client.post(f"/platform/tenants/{tid}/suspend")
    assert again.json()["suspended_at"] == first_ts

    lifted = platform_admin_client.post(f"/platform/tenants/{tid}/unsuspend")
    assert lifted.status_code == 200
    assert lifted.json()["suspended_at"] is None


def test_get_tenant_id_rejects_suspended(db_session: Session) -> None:
    """A suspended tenant blocks tenant-scoped resolution with 403."""
    tenant = Tenant(name="Susp", slug="susp")
    db_session.add(tenant)
    db_session.commit()

    req = Request({"type": "http", "headers": []})

    # Active → resolves to its id.
    assert asyncio.run(get_tenant_id(req, db_session, x_tenant_id=str(tenant.id))) == tenant.id

    # Suspended → 403.
    tenant.suspended_at = datetime.now(UTC)
    db_session.commit()
    try:
        asyncio.run(get_tenant_id(req, db_session, x_tenant_id=str(tenant.id)))
        raise AssertionError("expected HTTPException")
    except HTTPException as exc:
        assert exc.status_code == 403


# ---------------------------------------------------------------------------
# Tenant administrators
# ---------------------------------------------------------------------------


def test_list_admins_shows_founder(platform_admin_client: TestClient) -> None:
    tenant = _provision(platform_admin_client, "troop-admins")
    admins = platform_admin_client.get(f"/platform/tenants/{tenant['id']}/admins")
    assert admins.status_code == 200
    body = admins.json()
    assert len(body) == 1
    assert body[0]["member_id"] == tenant["founder_member_id"]
    assert body[0]["first_name"] == "Jane"
    assert body[0]["claimed"] is False


def test_invite_and_revoke_admin(
    platform_admin_client: TestClient, claim_client: TestClient
) -> None:
    tenant = _provision(platform_admin_client, "troop-invite")
    tid = tenant["id"]

    # Invite a second admin.
    invited = platform_admin_client.post(
        f"/platform/tenants/{tid}/admins",
        json={"first_name": "Sam", "last_name": "Helper", "email": "sam@example.com"},
    )
    assert invited.status_code == 201, invited.text
    new_admin_id = invited.json()["member_id"]
    assert invited.json()["token"]

    admins = platform_admin_client.get(f"/platform/tenants/{tid}/admins").json()
    assert {a["member_id"] for a in admins} == {tenant["founder_member_id"], new_admin_id}

    # The invited admin can claim and act.
    claimed = claim_client.post("/auth/claim", json={"token": invited.json()["token"]})
    assert claimed.status_code == 200

    # Revoke the founder (two admins exist, so this is allowed).
    revoke = platform_admin_client.delete(
        f"/platform/tenants/{tid}/admins/{tenant['founder_member_id']}"
    )
    assert revoke.status_code == 204
    remaining = platform_admin_client.get(f"/platform/tenants/{tid}/admins").json()
    assert [a["member_id"] for a in remaining] == [new_admin_id]


def test_cannot_revoke_last_admin(platform_admin_client: TestClient) -> None:
    tenant = _provision(platform_admin_client, "troop-last")
    r = platform_admin_client.delete(
        f"/platform/tenants/{tenant['id']}/admins/{tenant['founder_member_id']}"
    )
    assert r.status_code == 409


def test_revoke_non_admin_returns_404(platform_admin_client: TestClient) -> None:
    tenant = _provision(platform_admin_client, "troop-404")
    r = platform_admin_client.delete(f"/platform/tenants/{tenant['id']}/admins/{uuid.uuid4()}")
    assert r.status_code == 404


def test_admin_endpoints_require_platform_admin(
    platform_admin_client: TestClient, claim_client: TestClient
) -> None:
    tenant = _provision(platform_admin_client, "troop-gate")
    assert claim_client.get(f"/platform/tenants/{tenant['id']}/admins").status_code == 403


# ---------------------------------------------------------------------------
# Platform administrators (the global tier)
# ---------------------------------------------------------------------------


def _make_user(db: Session, email: str, role: PlatformRole | None = None) -> User:
    user = User(id=uuid.uuid4(), email=email, display_name=email, platform_role=role)
    db.add(user)
    db.commit()
    return user


def test_list_platform_admins(platform_admin_client: TestClient, db_session: Session) -> None:
    _make_user(db_session, "boss@test.com", PlatformRole.SUPERADMIN)
    _make_user(db_session, "nobody@test.com", None)  # not an admin

    r = platform_admin_client.get("/platform/admins")
    assert r.status_code == 200
    emails = {a["email"] for a in r.json()}
    assert "boss@test.com" in emails
    assert "nobody@test.com" not in emails


def test_grant_platform_admin(platform_admin_client: TestClient, db_session: Session) -> None:
    _make_user(db_session, "grantme@test.com", None)
    r = platform_admin_client.post(
        "/platform/admins", json={"email": "grantme@test.com", "role": "support"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["platform_role"] == "support"
    assert r.json()["email"] == "grantme@test.com"


def test_grant_unknown_email_returns_404(platform_admin_client: TestClient) -> None:
    r = platform_admin_client.post(
        "/platform/admins", json={"email": "ghost@test.com", "role": "superadmin"}
    )
    assert r.status_code == 404


def test_grant_requires_superadmin(support_client: TestClient, db_session: Session) -> None:
    """A support-tier platform admin cannot grant platform roles."""
    _make_user(db_session, "target@test.com", None)
    r = support_client.post(
        "/platform/admins", json={"email": "target@test.com", "role": "superadmin"}
    )
    assert r.status_code == 403


def test_support_admin_can_list_but_not_mutate(
    support_client: TestClient, db_session: Session
) -> None:
    """Read access for any platform admin; mutation gated to superadmin."""
    user = _make_user(db_session, "someadmin@test.com", PlatformRole.BILLING)
    assert support_client.get("/platform/admins").status_code == 200
    assert support_client.delete(f"/platform/admins/{user.id}").status_code == 403


def test_revoke_platform_admin(platform_admin_client: TestClient, db_session: Session) -> None:
    a = _make_user(db_session, "super-a@test.com", PlatformRole.SUPERADMIN)
    _make_user(db_session, "super-b@test.com", PlatformRole.SUPERADMIN)

    # Two superadmins exist, so revoking one is allowed.
    assert platform_admin_client.delete(f"/platform/admins/{a.id}").status_code == 204
    emails = {x["email"] for x in platform_admin_client.get("/platform/admins").json()}
    assert "super-a@test.com" not in emails
    assert "super-b@test.com" in emails


def test_cannot_revoke_last_superadmin(
    platform_admin_client: TestClient, db_session: Session
) -> None:
    only = _make_user(db_session, "lonely-super@test.com", PlatformRole.SUPERADMIN)
    r = platform_admin_client.delete(f"/platform/admins/{only.id}")
    assert r.status_code == 409


def test_revoke_platform_non_admin_returns_404(
    platform_admin_client: TestClient, db_session: Session
) -> None:
    plain = _make_user(db_session, "plain@test.com", None)
    assert platform_admin_client.delete(f"/platform/admins/{plain.id}").status_code == 404
    assert platform_admin_client.delete(f"/platform/admins/{uuid.uuid4()}").status_code == 404
