"""Push notifications (GH-82): token registration + event-triggered sends."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.notifications import (
    FakeEmailBackend,
    FakePushBackend,
    NotificationService,
    get_notification_service,
)
from app.main import app
from app.models.member import Member
from app.models.push import PushToken
from tests.conftest import TENANT_A


@pytest.fixture()
def fake_push() -> Iterator[FakePushBackend]:
    backend = FakePushBackend()
    app.dependency_overrides[get_notification_service] = lambda: NotificationService(
        email_backend=FakeEmailBackend(), push_backend=backend
    )
    yield backend
    app.dependency_overrides.pop(get_notification_service, None)


def _event(client: TestClient) -> dict:
    et = client.post("/event-types/", json={"name": "Hike"})
    assert et.status_code == 201
    r = client.post(
        "/events/",
        json={
            "name": "Outing",
            "event_type_id": et.json()["id"],
            "scheduled_start": "2026-07-10T09:00:00Z",
            "scheduled_end": "2026-07-12T17:00:00Z",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_register_is_idempotent_and_repoints(client: TestClient, db_session: Session) -> None:
    r = client.post(
        "/notifications/push-tokens",
        json={"token": "ExponentPushToken[abc]", "platform": "ios"},
    )
    assert r.status_code == 201, r.text
    again = client.post("/notifications/push-tokens", json={"token": "ExponentPushToken[abc]"})
    assert again.status_code == 201

    rows = db_session.scalars(select(PushToken)).all()
    assert len(rows) == 1
    assert rows[0].platform is None  # last registration wins


def test_unregister_removes_from_send_path(client: TestClient, db_session: Session) -> None:
    reg = client.post("/notifications/push-tokens", json={"token": "ExponentPushToken[x]"})
    assert reg.status_code == 201
    gone = client.request(
        "DELETE", "/notifications/push-tokens", json={"token": "ExponentPushToken[x]"}
    )
    assert gone.status_code == 204
    # Soft-deleted: invisible to the scoped send query (the raw test session
    # sees the tombstone; request sessions filter it out).
    rows = db_session.scalars(select(PushToken)).all()
    assert [r.is_deleted for r in rows] == [True]


def test_cancellation_pushes_to_registered_devices(
    client: TestClient, db_session: Session, fake_push: FakePushBackend
) -> None:
    # The admin fixture member gets an email + a registered device.
    admin = db_session.scalars(select(Member)).first()
    assert admin is not None
    admin.email = "admin@example.com"
    db_session.commit()
    reg = client.post("/notifications/push-tokens", json={"token": "ExponentPushToken[dev1]"})
    assert reg.status_code == 201

    event = _event(client)
    r = client.post(f"/events/{event['id']}/cancel")
    assert r.status_code == 200, r.text

    assert [m.token for m in fake_push.sent] == ["ExponentPushToken[dev1]"]
    assert fake_push.sent[0].title == "Event cancelled"
    assert fake_push.sent[0].data == {"event_id": event["id"]}


def test_dead_tokens_are_pruned_after_send(
    client: TestClient, db_session: Session, fake_push: FakePushBackend
) -> None:
    admin = db_session.scalars(select(Member)).first()
    assert admin is not None
    admin.email = "admin@example.com"
    db_session.commit()
    reg = client.post("/notifications/push-tokens", json={"token": "ExponentPushToken[dead]"})
    assert reg.status_code == 201
    fake_push.dead_tokens = ["ExponentPushToken[dead]"]

    event = _event(client)
    r = client.post(f"/events/{event['id']}/cancel")
    assert r.status_code == 200

    assert db_session.scalars(select(PushToken)).all() == []


def test_push_is_tenant_scoped(
    client: TestClient, other_client: TestClient, db_session: Session, fake_push: FakePushBackend
) -> None:
    # A device registered in tenant B must not hear about tenant A's events.
    reg = other_client.post("/notifications/push-tokens", json={"token": "ExponentPushToken[b]"})
    assert reg.status_code == 201

    admin = db_session.scalars(select(Member).where(Member.tenant_id == TENANT_A)).first()
    assert admin is not None
    admin.email = "admin@example.com"
    db_session.commit()

    event = _event(client)
    r = client.post(f"/events/{event['id']}/cancel")
    assert r.status_code == 200
    assert [m.token for m in fake_push.sent] == []
