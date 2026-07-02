"""Tests for event cancellation + permission-request notifications (GH-86)."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.deps import get_notification_service
from app.core.notifications import FakeEmailBackend, NotificationService
from app.main import app
from app.models.enums import MemberType, RelationshipType
from app.models.member import Member, MemberRelationship
from tests.conftest import TENANT_A


@pytest.fixture()
def fake_email() -> Iterator[FakeEmailBackend]:
    backend = FakeEmailBackend()
    app.dependency_overrides[get_notification_service] = lambda: NotificationService(
        email_backend=backend
    )
    yield backend
    app.dependency_overrides.pop(get_notification_service, None)


def _member(
    db: Session,
    first_name: str,
    email: str | None,
    member_type: MemberType = MemberType.ADULT,
    **overrides: object,
) -> Member:
    member = Member(
        tenant_id=TENANT_A,
        first_name=first_name,
        last_name="Notify",
        email=email,
        member_type=member_type,
        **overrides,
    )
    db.add(member)
    db.commit()
    return member


def _link_parent(db: Session, parent: Member, child: Member) -> None:
    db.add(
        MemberRelationship(
            tenant_id=TENANT_A,
            from_member_id=parent.id,
            to_member_id=child.id,
            relationship_type=RelationshipType.PARENT_OF,
        )
    )
    db.commit()


def _event_type(client: TestClient, **overrides: object) -> dict:
    r = client.post("/event-types/", json={"name": "Campout", **overrides})
    assert r.status_code == 201, r.text
    return r.json()


def _event(client: TestClient, event_type_id: str, name: str = "Fall Campout") -> dict:
    r = client.post(
        "/events/",
        json={
            "name": name,
            "event_type_id": event_type_id,
            "scheduled_start": "2026-09-12T09:00:00Z",
            "scheduled_end": "2026-09-13T11:00:00Z",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- Cancellation ----------------------------------------------------------


def test_cancel_marks_event_and_emails_visible_members(
    client: TestClient, db_session: Session, fake_email: FakeEmailBackend
) -> None:
    scout = _member(db_session, "Scout", "scout@example.com", MemberType.SCOUT)
    parent = _member(db_session, "Parent", "parent@example.com")
    _link_parent(db_session, parent, scout)
    _member(db_session, "OptedOut", "optout@example.com", email_opt_out=True)
    _member(db_session, "NoEmail", None)

    event = _event(client, _event_type(client)["id"])
    r = client.post(f"/events/{event['id']}/cancel")
    assert r.status_code == 200, r.text
    assert r.json()["cancelled_at"] is not None

    recipients = {m.to for m in fake_email.sent}
    # Scout, parent, and the admin fixture member get the email; opted-out and
    # email-less members do not.
    assert "scout@example.com" in recipients
    assert "parent@example.com" in recipients
    assert "optout@example.com" not in recipients
    assert all(m.subject.startswith("CANCELLED: Fall Campout") for m in fake_email.sent)


def test_cancel_twice_is_conflict_and_single_send(
    client: TestClient, db_session: Session, fake_email: FakeEmailBackend
) -> None:
    _member(db_session, "Scout", "scout@example.com", MemberType.SCOUT)
    event = _event(client, _event_type(client)["id"])

    assert client.post(f"/events/{event['id']}/cancel").status_code == 200
    first_batch = len(fake_email.sent)
    assert client.post(f"/events/{event['id']}/cancel").status_code == 409
    assert len(fake_email.sent) == first_batch


def test_cancel_audience_scoped_event_only_emails_the_audience(
    client: TestClient, db_session: Session, fake_email: FakeEmailBackend
) -> None:
    in_group = _member(db_session, "Wolf", "wolf@example.com", MemberType.SCOUT)
    _member(db_session, "Outsider", "outsider@example.com", MemberType.SCOUT)

    group = client.post("/groups/", json={"name": "Wolves", "group_type": "custom"}).json()
    assert (
        client.post(
            f"/groups/{group['id']}/members", json={"member_id": str(in_group.id)}
        ).status_code
        == 201
    )
    event = _event(client, _event_type(client)["id"], name="Wolf Hike")
    assert (
        client.post(f"/events/{event['id']}/audiences", json={"group_id": group["id"]}).status_code
        == 201
    )

    assert client.post(f"/events/{event['id']}/cancel").status_code == 200
    recipients = {m.to for m in fake_email.sent}
    assert recipients == {"wolf@example.com"}


def test_cancel_unknown_event_404(client: TestClient, fake_email: FakeEmailBackend) -> None:
    assert client.post(f"/events/{uuid.uuid4()}/cancel").status_code == 404


# --- Permission requests ---------------------------------------------------


def test_notify_permissions_emails_parents_of_pending_scouts(
    client: TestClient, db_session: Session, fake_email: FakeEmailBackend
) -> None:
    scout = _member(db_session, "Alex", "alex@example.com", MemberType.SCOUT)
    signed_scout = _member(db_session, "Sam", "sam@example.com", MemberType.SCOUT)
    parent = _member(db_session, "Pat", "pat@example.com")
    _link_parent(db_session, parent, scout)
    _link_parent(db_session, parent, signed_scout)

    et = _event_type(client, require_permission_slip=True)
    event = _event(client, et["id"])
    for s in (scout, signed_scout):
        r = client.post(f"/events/{event['id']}/participants", json={"member_id": str(s.id)})
        assert r.status_code == 201, r.text
    # Sam already turned in a paper slip — Pat should only be asked about Alex.
    r = client.patch(
        f"/events/{event['id']}/participants/{signed_scout.id}",
        json={"permission_slip_submitted": True},
    )
    assert r.status_code == 200, r.text

    r = client.post(f"/events/{event['id']}/notify-permissions")
    assert r.status_code == 200, r.text
    assert r.json() == {"emails_sent": 1}
    assert len(fake_email.sent) == 1
    sent = fake_email.sent[0]
    assert sent.to == "pat@example.com"
    assert "Alex" in sent.text_body
    assert "Sam" not in sent.text_body


def test_notify_permissions_409_when_type_does_not_require_slips(
    client: TestClient, fake_email: FakeEmailBackend
) -> None:
    et = _event_type(client, require_permission_slip=False)
    event = _event(client, et["id"])
    assert client.post(f"/events/{event['id']}/notify-permissions").status_code == 409
    assert fake_email.sent == []


def test_notify_permissions_zero_when_everyone_signed(
    client: TestClient, db_session: Session, fake_email: FakeEmailBackend
) -> None:
    et = _event_type(client, require_permission_slip=True)
    event = _event(client, et["id"])
    r = client.post(f"/events/{event['id']}/notify-permissions")
    assert r.status_code == 200
    assert r.json() == {"emails_sent": 0}
    assert fake_email.sent == []
