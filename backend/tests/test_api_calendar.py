"""API tests for the iCal feed and subscription endpoints."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.tenant import Tenant

TENANT_A = uuid.UUID("10000000-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("20000000-0000-0000-0000-000000000002")


def _ensure_tenant(db: Session, tenant_id: uuid.UUID = TENANT_A) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(id=tenant_id, name=f"Troop {tenant_id}", slug=f"troop-{tenant_id.hex[:8]}")
        db.add(tenant)
        db.commit()
    return tenant


def _event_type(client: TestClient) -> dict:
    r = client.post("/event-types/", json={"name": "Meeting"})
    assert r.status_code == 201, r.text
    return r.json()


def _event(client: TestClient, event_type_id: str, name: str = "Troop Meeting") -> dict:
    r = client.post(
        "/events/",
        json={
            "name": name,
            "event_type_id": event_type_id,
            "scheduled_start": "2026-07-10T09:00:00Z",
            "scheduled_end": "2026-07-10T11:00:00Z",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _admin_member_id(client: TestClient) -> str:
    members = client.get("/members/").json()
    return next(m["id"] for m in members if m["first_name"] == "Admin")


# --- Subscription management ---------------------------------------------


def test_create_subscription_is_idempotent(client: TestClient) -> None:
    first = client.post("/calendar/subscription")
    assert first.status_code == 201
    body = first.json()
    assert body["token"]
    assert body["feed_path"] == f"/calendar/{body['token']}.ics"

    second = client.post("/calendar/subscription")
    assert second.json()["token"] == body["token"]


def test_rotate_subscription_changes_token(client: TestClient) -> None:
    token1 = client.post("/calendar/subscription").json()["token"]
    token2 = client.delete("/calendar/subscription").json()["token"]
    assert token1 != token2


# --- Feed ----------------------------------------------------------------


def test_feed_serves_ics(client: TestClient, db_session: Session) -> None:
    _ensure_tenant(db_session)
    et = _event_type(client)
    _event(client, et["id"])
    feed_path = client.post("/calendar/subscription").json()["feed_path"]

    r = client.get(feed_path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in r.text
    assert "SUMMARY:Troop Meeting" in r.text


def test_feed_excludes_declined_event(client: TestClient, db_session: Session) -> None:
    _ensure_tenant(db_session)
    et = _event_type(client)
    event = _event(client, et["id"], name="Declined Outing")
    admin_id = _admin_member_id(client)
    client.post(
        f"/events/{event['id']}/participants",
        json={"member_id": admin_id, "rsvp_status": "declined"},
    )
    feed_path = client.post("/calendar/subscription").json()["feed_path"]

    assert "Declined Outing" not in client.get(feed_path).text


def test_feed_unknown_token_404(client: TestClient, db_session: Session) -> None:
    _ensure_tenant(db_session)
    assert client.get("/calendar/nope-not-a-token.ics").status_code == 404


def test_feed_token_is_scoped_to_its_tenant(
    client: TestClient, other_client: TestClient, db_session: Session
) -> None:
    """A feed token minted in one tenant must not resolve under another tenant's context.

    Regression for the RLS bug: the feed used to look up the token with no tenant scope.
    Under Postgres RLS that unset ``app.current_tenant`` GUC meant every feed 404'd; on a
    non-RLS backend the same unscoped lookup would resolve a token across tenants. The
    route now resolves + scopes the tenant first, so tenant B's context cannot serve
    tenant A's token. Removing the scoping regresses this test to a 200.
    """
    _ensure_tenant(db_session, TENANT_A)
    _ensure_tenant(db_session, TENANT_B)

    # Mint a token for TENANT_A's admin member.
    feed_path = client.post("/calendar/subscription").json()["feed_path"]

    # Served under its own tenant, but not resolvable under TENANT_B's context.
    assert client.get(feed_path).status_code == 200
    assert other_client.get(feed_path).status_code == 404


def test_feed_404_when_tenant_suspended(client: TestClient, db_session: Session) -> None:
    tenant = _ensure_tenant(db_session)
    feed_path = client.post("/calendar/subscription").json()["feed_path"]
    assert client.get(feed_path).status_code == 200

    tenant.suspended_at = datetime.now(UTC)
    db_session.commit()
    assert client.get(feed_path).status_code == 404


def test_feed_respects_audience_scoping(client: TestClient, db_session: Session) -> None:
    """A patrol-only event appears in the member's feed only once they're in the group."""
    _ensure_tenant(db_session)
    et = _event_type(client)
    scoped = _event(client, et["id"], name="Wolf-only")
    group = client.post("/groups/", json={"name": "Wolf", "group_type": "custom"}).json()
    client.post(f"/events/{scoped['id']}/audiences", json={"group_id": group["id"]})
    feed_path = client.post("/calendar/subscription").json()["feed_path"]

    assert "Wolf-only" not in client.get(feed_path).text

    admin_id = _admin_member_id(client)
    client.post(f"/groups/{group['id']}/members", json={"member_id": admin_id})
    assert "Wolf-only" in client.get(feed_path).text
