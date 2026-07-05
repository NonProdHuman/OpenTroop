"""Messaging (GH-146): compose, audience, queue drain, inbox, and sync streams."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.messaging import MAX_EMAIL_ATTEMPTS, drain_email_outbox, promote_due_scheduled
from app.core.notifications import (
    EmailMessage,
    EmailSendError,
    FakeEmailBackend,
    FakePushBackend,
    NotificationService,
    get_notification_service,
)
from app.core.tenant_context import tenant_scope
from app.main import app
from app.models.enums import MemberType, MessageStatus, RelationshipType
from app.models.group import Group, GroupMember
from app.models.member import Member, MemberRelationship
from app.models.message import Message, MessageRecipient
from tests.conftest import NEW_USER_ID, TENANT_A


class _Fakes:
    def __init__(self) -> None:
        self.email = FakeEmailBackend()
        self.push = FakePushBackend()
        self.service = NotificationService(email_backend=self.email, push_backend=self.push)


@pytest.fixture()
def fakes() -> Iterator[_Fakes]:
    f = _Fakes()
    app.dependency_overrides[get_notification_service] = lambda: f.service
    yield f
    app.dependency_overrides.pop(get_notification_service, None)


def _member(
    db: Session,
    first: str,
    *,
    email: str | None = None,
    member_type: MemberType = MemberType.SCOUT,
    **overrides: object,
) -> Member:
    member = Member(
        tenant_id=TENANT_A,
        first_name=first,
        last_name="Msg",
        member_type=member_type,
        email=email,
        **overrides,  # type: ignore[arg-type]
    )
    db.add(member)
    db.flush()
    return member


def _group_with(db: Session, *members: Member, name: str = "Wolves") -> Group:
    group = Group(tenant_id=TENANT_A, name=name)
    db.add(group)
    db.flush()
    for member in members:
        db.add(GroupMember(tenant_id=TENANT_A, group_id=group.id, member_id=member.id))
    db.commit()
    return group


def _compose(client: TestClient, group_ids: list[tuple[str, str]], **overrides: object) -> dict:
    payload: dict[str, object] = {
        "subject": "Campout reminder",
        "body": "Bring rain gear!",
        "group_targets": [{"group_id": gid, "audience_type": at} for gid, at in group_ids],
        **overrides,
    }
    r = client.post("/messages", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_compose_preview_counts_and_dedup(
    client: TestClient, db_session: Session, fakes: _Fakes
) -> None:
    a = _member(db_session, "A", email="a@x.test")
    b = _member(db_session, "B", email="b@x.test", email_opt_out=True)
    c = _member(db_session, "C")  # no email
    d = _member(db_session, "D", email="d@x.test", email_bounced=True)
    g1 = _group_with(db_session, a, b, c, name="G1")
    g2 = _group_with(db_session, a, d, name="G2")  # A in both groups → dedup

    created = _compose(client, [(str(g1.id), "members"), (str(g2.id), "members")])
    preview = created["preview"]
    assert preview["total"] == 4
    assert preview["email"] == 1
    assert preview["opted_out"] == 1
    assert preview["bounced"] == 1
    assert preview["no_email"] == 1


def test_compose_rejects_bad_targets(client: TestClient, db_session: Session) -> None:
    scout = _member(db_session, "S")
    group = _group_with(db_session, scout)
    r = client.post(
        "/messages",
        json={
            "subject": "x",
            "body": "y",
            "group_targets": [
                {"group_id": str(group.id), "audience_type": "members"},
                {"group_id": str(group.id), "audience_type": "members"},
            ],
        },
    )
    assert r.status_code == 422  # duplicate target
    r = client.post(
        "/messages",
        json={
            "subject": "x",
            "body": "y",
            "group_targets": [
                {"group_id": "00000000-0000-0000-0000-000000000009", "audience_type": "members"}
            ],
        },
    )
    assert r.status_code == 422  # unknown group


def test_send_writes_inbox_pushes_and_queues_email(
    client: TestClient, db_session: Session, fakes: _Fakes
) -> None:
    a = _member(db_session, "A", email="a@x.test")
    b = _member(db_session, "B", email_opt_out=True, email="b@x.test")
    group = _group_with(db_session, a, b)
    reg = client.post("/notifications/push-tokens", json={"token": "ExponentPushToken[a]"})
    assert reg.status_code == 201
    # Re-point the admin-registered token to member A for the test.
    db_session.execute(
        select(Member)  # no-op select to keep session in sync before raw update
    )
    from app.models.push import PushToken

    token_row = db_session.scalars(select(PushToken)).one()
    token_row.member_id = a.id
    db_session.commit()

    created = _compose(client, [(str(group.id), "members")])
    message_id = created["message"]["id"]
    sent = client.post(f"/messages/{message_id}/send")
    assert sent.status_code == 200, sent.text
    stats = sent.json()["stats"]
    assert stats["total"] == 2
    assert stats["email_pending"] == 1  # A queued; B skipped (opt-out)
    assert stats["email_skipped"] == 1
    assert stats["push_sent"] == 1  # A's device
    assert [p.title for p in fakes.push.sent] == ["Campout reminder"]
    assert fakes.push.sent[0].data == {"message_id": message_id}

    # Double send is a conflict.
    again = client.post(f"/messages/{message_id}/send")
    assert again.status_code == 409

    # The outbox drain delivers the pending email and finalizes the message.
    with tenant_scope(TENANT_A):
        attempted = drain_email_outbox(db_session, fakes.service)
    assert attempted == 1
    assert [e.to for e in fakes.email.sent] == ["a@x.test"]
    message = db_session.get(Message, __import__("uuid").UUID(message_id))
    assert message is not None
    assert message.status == MessageStatus.SENT
    assert message.sent_at is not None


def test_parent_expansions(client: TestClient, db_session: Session, fakes: _Fakes) -> None:
    scout = _member(db_session, "Kid")
    parent = _member(db_session, "Pat", email="pat@x.test", member_type=MemberType.ADULT)
    db_session.add(
        MemberRelationship(
            tenant_id=TENANT_A,
            from_member_id=parent.id,
            to_member_id=scout.id,
            relationship_type=RelationshipType.PARENT_OF,
        )
    )
    group = _group_with(db_session, scout)

    both = _compose(client, [(str(group.id), "members_and_parents")])
    assert both["preview"]["total"] == 2

    parents = _compose(client, [(str(group.id), "parents_only")])
    assert parents["preview"]["total"] == 1

    sent = client.post(f"/messages/{parents['message']['id']}/send")
    assert sent.status_code == 200
    recipient_ids = {
        r.member_id
        for r in db_session.scalars(
            select(MessageRecipient).where(
                MessageRecipient.message_id == __import__("uuid").UUID(parents["message"]["id"])
            )
        )
    }
    assert recipient_ids == {parent.id}


class _FailingEmail:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, message: EmailMessage) -> None:
        self.calls += 1
        raise EmailSendError("smtp down")


def test_drain_retries_with_backoff_then_dead_letters(
    client: TestClient, db_session: Session, fakes: _Fakes
) -> None:
    a = _member(db_session, "A", email="a@x.test")
    group = _group_with(db_session, a)
    created = _compose(client, [(str(group.id), "members")])
    assert client.post(f"/messages/{created['message']['id']}/send").status_code == 200

    failing = NotificationService(email_backend=_FailingEmail())  # type: ignore[arg-type]
    with tenant_scope(TENANT_A):
        drain_email_outbox(db_session, failing)
    row = db_session.scalars(select(MessageRecipient)).one()
    assert row.attempts == 1
    assert row.email_state.value == "pending"
    assert row.next_attempt_at is not None  # backed off — not retried this tick

    # Not due yet: another pass attempts nothing.
    with tenant_scope(TENANT_A):
        assert drain_email_outbox(db_session, failing) == 0

    # Force due repeatedly until the dead-letter threshold.
    for _ in range(MAX_EMAIL_ATTEMPTS - 1):
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.commit()
        with tenant_scope(TENANT_A):
            drain_email_outbox(db_session, failing)
    db_session.refresh(row)
    assert row.email_state.value == "failed"
    assert row.last_error is not None


def test_scheduled_send_promotes_when_due(
    client: TestClient, db_session: Session, fakes: _Fakes
) -> None:
    a = _member(db_session, "A", email="a@x.test")
    group = _group_with(db_session, a)
    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    created = _compose(client, [(str(group.id), "members")], scheduled_at=future)
    r = client.post(f"/messages/{created['message']['id']}/send")
    assert r.status_code == 200
    assert r.json()["message"]["status"] == "scheduled"
    assert r.json()["stats"]["total"] == 0  # nothing resolved yet

    # Time passes: the outbox loop promotes it.
    message = db_session.get(Message, __import__("uuid").UUID(created["message"]["id"]))
    assert message is not None
    message.scheduled_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    with tenant_scope(TENANT_A):
        promoted = promote_due_scheduled(db_session, fakes.service)
    assert promoted == 1
    db_session.refresh(message)
    assert message.status in (MessageStatus.SENDING, MessageStatus.SENT)


def test_inbox_flow_and_isolation(
    client: TestClient, claim_client: TestClient, db_session: Session, fakes: _Fakes
) -> None:
    me = _member(db_session, "Me", email="me@x.test", user_id=NEW_USER_ID)
    other = _member(db_session, "Other", email="o@x.test")
    group = _group_with(db_session, me, other)
    created = _compose(client, [(str(group.id), "members")])
    assert client.post(f"/messages/{created['message']['id']}/send").status_code == 200

    headers = {"X-Tenant-ID": str(TENANT_A)}
    inbox = claim_client.get("/messages/inbox", headers=headers)
    assert inbox.status_code == 200, inbox.text
    page = inbox.json()
    assert page["unread_count"] == 1
    assert [e["subject"] for e in page["items"]] == ["Campout reminder"]

    entry = page["items"][0]
    read = claim_client.post(f"/messages/inbox/{entry['recipient_id']}/read", headers=headers)
    assert read.status_code == 200
    assert claim_client.get("/messages/inbox", headers=headers).json()["unread_count"] == 0

    # Another member's entry 404s (existence not leaked).
    other_row = db_session.scalars(
        select(MessageRecipient).where(MessageRecipient.member_id == other.id)
    ).one()
    denied = claim_client.post(f"/messages/inbox/{other_row.id}/read", headers=headers)
    assert denied.status_code == 404

    # Compose requires communication:send_troop.
    forbidden = claim_client.post(
        "/messages",
        json={
            "subject": "x",
            "body": "y",
            "group_targets": [{"group_id": str(group.id), "audience_type": "members"}],
        },
        headers=headers,
    )
    assert forbidden.status_code == 403


def test_inbox_sync_streams_scoped_to_caller(
    client: TestClient, claim_client: TestClient, db_session: Session, fakes: _Fakes
) -> None:
    me = _member(db_session, "Me", user_id=NEW_USER_ID)
    other = _member(db_session, "Other")
    group = _group_with(db_session, me, other)
    created = _compose(client, [(str(group.id), "members")])
    assert client.post(f"/messages/{created['message']['id']}/send").status_code == 200

    headers = {"X-Tenant-ID": str(TENANT_A)}
    messages = claim_client.get("/sync/inbox_messages", headers=headers)
    assert messages.status_code == 200
    assert [m["id"] for m in messages.json()["items"]] == [created["message"]["id"]]

    recipients = claim_client.get("/sync/inbox_recipients", headers=headers)
    assert recipients.status_code == 200
    rows = recipients.json()["items"]
    assert len(rows) == 1
    assert rows[0]["member_id"] == str(me.id)
