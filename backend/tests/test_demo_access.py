"""Anonymous public-demo read-only carve-out (GH-246, ADR 0012).

The security-sensitive core: on the single tenant named by ``DEMO_TENANT_SLUG``, a
request carrying **no** Authorization header resolves a fixed, seeded, read-only
"Demo Viewer" member instead of 401 — and any non-GET method by that anonymous
principal is refused 403 **structurally, independent of RBAC**. These tests prove:

- feature OFF (slug unset) ⇒ anonymous requests 401 exactly as before (regression),
- feature ON ⇒ anonymous GETs work on the demo tenant (roster/events readable),
- anonymous writes ⇒ 403 even when the viewer somehow holds write permissions,
- the carve-out is single-tenant: anonymous on a NON-demo tenant ⇒ 401,
- authenticated users on the demo tenant are unaffected,
- /platform/* is unreachable and /sync/* GETs stay read-only.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.provisioning import seed_default_event_types, seed_default_rbac
from app.main import app
from app.models.enums import MemberType
from app.models.event import Event
from app.models.event_type import EventType
from app.models.member import Member
from app.models.rbac import MemberPositionAssignment, Position
from app.models.tenant import Tenant
from app.models.user import User
from tests.conftest import ADMIN_USER_ID, _set_shared_overrides

DEMO_SLUG = "demo-public"
DEMO_TENANT_ID = uuid.UUID("d3300000-0000-0000-0000-0000000000d1")
OTHER_TENANT_ID = uuid.UUID("d3300000-0000-0000-0000-0000000000d2")


def _assign(db: Session, tenant_id: uuid.UUID, member_id: uuid.UUID, slug: str) -> None:
    position = db.scalar(
        select(Position).where(Position.tenant_id == tenant_id, Position.slug == slug)
    )
    assert position is not None, f"position {slug!r} not seeded"
    db.add(
        MemberPositionAssignment(tenant_id=tenant_id, member_id=member_id, position_id=position.id)
    )
    db.flush()


@pytest.fixture
def demo_env(db_session: Session) -> None:
    """Stand up the demo tenant (RBAC + event types, a Demo Viewer, a roster member,
    a troop-wide event) plus a separate NON-demo tenant to prove scoping."""
    for tid, slug in ((DEMO_TENANT_ID, DEMO_SLUG), (OTHER_TENANT_ID, "not-demo")):
        db_session.add(Tenant(id=tid, name=slug, slug=slug))
        db_session.flush()
        seed_default_rbac(db_session, tid)
        seed_default_event_types(db_session, tid)

    # The anonymous principal: unclaimed, viewer-only.
    viewer = Member(
        tenant_id=DEMO_TENANT_ID,
        first_name="Demo",
        last_name="Viewer",
        member_type=MemberType.ADULT,
        email=settings.demo_viewer_email,
    )
    db_session.add(viewer)
    db_session.flush()
    _assign(db_session, DEMO_TENANT_ID, viewer.id, "viewer")

    # Readable content.
    db_session.add(
        Member(
            tenant_id=DEMO_TENANT_ID,
            first_name="Rex",
            last_name="Scout",
            member_type=MemberType.SCOUT,
        )
    )
    meeting_type = db_session.scalar(
        select(EventType).where(EventType.tenant_id == DEMO_TENANT_ID, EventType.name == "Meeting")
    )
    assert meeting_type is not None
    db_session.add(
        Event(
            tenant_id=DEMO_TENANT_ID,
            name="Public Demo Meeting",
            event_type_id=meeting_type.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=3),
            scheduled_end=datetime.now(UTC) + timedelta(days=3, hours=1),
        )
    )
    db_session.commit()
    return None


def _client(user_id: uuid.UUID | None = None, tenant_id: uuid.UUID = DEMO_TENANT_ID) -> TestClient:
    headers = {"X-Tenant-ID": str(tenant_id)}
    if user_id is not None:
        headers["X-Test-User-ID"] = str(user_id)
    return TestClient(app, headers=headers)


@pytest.fixture
def overrides(db_session: Session) -> Generator[None, None, None]:
    _set_shared_overrides(db_session)
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Feature OFF — regression proof that prod/self-host are unaffected.
# ---------------------------------------------------------------------------


def test_feature_off_anonymous_is_401(
    demo_env: None, overrides: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "demo_tenant_slug", "")
    assert _client().get("/members").status_code == 401


# ---------------------------------------------------------------------------
# Feature ON — anonymous reads on the demo tenant.
# ---------------------------------------------------------------------------


def test_anonymous_get_roster_and_events(
    demo_env: None, overrides: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "demo_tenant_slug", DEMO_SLUG)
    c = _client()

    members = c.get("/members")
    assert members.status_code == 200
    assert "Rex" in {m["first_name"] for m in members.json()}

    events = c.get("/events")
    assert events.status_code == 200
    assert any(e["name"] == "Public Demo Meeting" for e in events.json())


def test_anonymous_sync_get_is_readable(
    demo_env: None, overrides: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "demo_tenant_slug", DEMO_SLUG)
    assert _client().get("/sync/members").status_code == 200


# ---------------------------------------------------------------------------
# Structural read-only — writes rejected regardless of RBAC.
# ---------------------------------------------------------------------------


def test_anonymous_write_methods_are_403(
    demo_env: None, overrides: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "demo_tenant_slug", DEMO_SLUG)
    c = _client()
    body = {"first_name": "New", "last_name": "Person", "member_type": "scout"}
    victim = f"/members/{uuid.uuid4()}"

    # Every mutating verb is refused by the structural gate (before the handler runs,
    # so before any 404 for the random id) — never a 401 or a permission 403 leak.
    # Calls hoisted out of the asserts (CodeQL py/side-effect-in-assert).
    post_status = c.post("/members", json=body).status_code
    patch_status = c.patch(victim, json={"first_name": "X"}).status_code
    delete_status = c.delete(victim).status_code
    assert post_status == 403
    assert patch_status == 403
    assert delete_status == 403


def test_structural_gate_beats_a_mis_seeded_write_role(
    demo_env: None, overrides: None, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    """Even if the Demo Viewer is mistakenly given full admin, an anonymous write is
    still refused 403 — the method gate is independent of resolved permissions."""
    monkeypatch.setattr(settings, "demo_tenant_slug", DEMO_SLUG)
    viewer = db_session.scalar(
        select(Member).where(
            Member.tenant_id == DEMO_TENANT_ID,
            Member.email == settings.demo_viewer_email,
        )
    )
    assert viewer is not None
    _assign(db_session, DEMO_TENANT_ID, viewer.id, "administrator")
    db_session.commit()

    resp = _client().post(
        "/members",
        json={"first_name": "New", "last_name": "Person", "member_type": "scout"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Single-tenant scope.
# ---------------------------------------------------------------------------


def test_anonymous_on_non_demo_tenant_is_401(
    demo_env: None, overrides: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "demo_tenant_slug", DEMO_SLUG)
    assert _client(tenant_id=OTHER_TENANT_ID).get("/members").status_code == 401


def test_anonymous_cannot_reach_platform(
    demo_env: None, overrides: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "demo_tenant_slug", DEMO_SLUG)
    assert _client().get("/platform/tenants").status_code in (401, 403)


# ---------------------------------------------------------------------------
# Authenticated users on the demo tenant are unaffected.
# ---------------------------------------------------------------------------


def test_authenticated_admin_on_demo_tenant_can_write(
    demo_env: None, overrides: None, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setattr(settings, "demo_tenant_slug", DEMO_SLUG)
    # A real signed-in admin member in the demo tenant (ADMIN_USER_ID is already in
    # conftest's header→User map, so no _USERS mutation is needed).
    db_session.add(User(id=ADMIN_USER_ID, email="admin@test.com", email_verified=True))
    db_session.flush()
    admin = Member(
        tenant_id=DEMO_TENANT_ID,
        user_id=ADMIN_USER_ID,
        first_name="Real",
        last_name="Admin",
        member_type=MemberType.ADULT,
    )
    db_session.add(admin)
    db_session.flush()
    _assign(db_session, DEMO_TENANT_ID, admin.id, "administrator")
    db_session.commit()

    resp = _client(user_id=ADMIN_USER_ID).post(
        "/members",
        json={"first_name": "New", "last_name": "Scout", "member_type": "scout"},
    )
    assert resp.status_code == 201
