"""Digest batching + member preference logic (GH-218).

Covers the withheld-email lifecycle: HELD_DIGEST rows skip the normal drain,
the weekly assembly bundles a member's held messages into one email and settles
their states, cadence respects ``last_digest_at``, and the member preference
downgrades/skips an immediate send at resolve time.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.messaging import (
    MAX_EMAIL_ATTEMPTS,
    assemble_digests,
    drain_email_outbox,
    initial_email_state,
)
from app.core.notifications import (
    EmailMessage,
    EmailSendError,
    FakeEmailBackend,
    FakePushBackend,
    NotificationService,
)
from app.core.tenant_context import tenant_scope, unscoped
from app.models import Base
from app.models.enums import (
    AnnouncementEmailMode,
    EmailState,
    MemberType,
    MessageDelivery,
    MessageStatus,
)
from app.models.member import Member
from app.models.message import Message, MessageRecipient
from app.models.tenant import Tenant
from tests.conftest import TENANT_A


@pytest.fixture()
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, future=True)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _service(email_backend: FakeEmailBackend) -> NotificationService:
    return NotificationService(email_backend=email_backend, push_backend=FakePushBackend())


def _seed_tenant(db: Session, *, last_digest_at: datetime | None) -> Tenant:
    tenant = Tenant(
        id=TENANT_A,
        name="42",
        slug="troop42",
        digest_day=datetime.now(UTC).weekday(),
        digest_hour_utc=0,
        last_digest_at=last_digest_at,
    )
    db.add(tenant)
    db.flush()
    return tenant


def _seed_member(db: Session, email: str = "scout@x.test") -> Member:
    member = Member(
        tenant_id=TENANT_A,
        first_name="River",
        last_name="Scout",
        member_type=MemberType.ADULT,
        email=email,
    )
    db.add(member)
    db.flush()
    return member


def _seed_held_message(db: Session, member: Member, subject: str, body: str) -> Message:
    """A SENT digest-delivery message with one HELD_DIGEST recipient for ``member``."""
    message = Message(
        tenant_id=TENANT_A,
        subject=subject,
        body=body,
        status=MessageStatus.SENT,
        delivery=MessageDelivery.DIGEST,
        sent_at=datetime.now(UTC),
    )
    db.add(message)
    db.flush()
    db.add(
        MessageRecipient(
            tenant_id=TENANT_A,
            message_id=message.id,
            member_id=member.id,
            email_state=EmailState.HELD_DIGEST,
        )
    )
    db.flush()
    return message


# --- Resolve-time preference logic -------------------------------------------


def test_immediate_message_is_pending_for_every_mode() -> None:
    member = Member(
        tenant_id=TENANT_A,
        first_name="A",
        last_name="B",
        member_type=MemberType.ADULT,
        email="a@x.test",
        announcement_email_mode=AnnouncementEmailMode.EVERY,
    )
    state = initial_email_state(member, send_email=True, delivery=MessageDelivery.IMMEDIATE)
    assert state == EmailState.PENDING


def test_digest_preference_downgrades_immediate_to_held() -> None:
    member = Member(
        tenant_id=TENANT_A,
        first_name="A",
        last_name="B",
        member_type=MemberType.ADULT,
        email="a@x.test",
        announcement_email_mode=AnnouncementEmailMode.DIGEST,
    )
    state = initial_email_state(member, send_email=True, delivery=MessageDelivery.IMMEDIATE)
    assert state == EmailState.HELD_DIGEST


def test_none_preference_skips_with_opt_out() -> None:
    member = Member(
        tenant_id=TENANT_A,
        first_name="A",
        last_name="B",
        member_type=MemberType.ADULT,
        email="a@x.test",
        announcement_email_mode=AnnouncementEmailMode.NONE,
    )
    # ...even for a digest-delivery message: "none" silences announcements entirely.
    assert (
        initial_email_state(member, send_email=True, delivery=MessageDelivery.IMMEDIATE)
        == EmailState.SKIPPED_OPT_OUT
    )
    assert (
        initial_email_state(member, send_email=True, delivery=MessageDelivery.DIGEST)
        == EmailState.SKIPPED_OPT_OUT
    )


def test_digest_delivery_holds_even_for_every_mode() -> None:
    member = Member(
        tenant_id=TENANT_A,
        first_name="A",
        last_name="B",
        member_type=MemberType.ADULT,
        email="a@x.test",
        announcement_email_mode=AnnouncementEmailMode.EVERY,
    )
    state = initial_email_state(member, send_email=True, delivery=MessageDelivery.DIGEST)
    assert state == EmailState.HELD_DIGEST


def test_bounced_wins_over_digest_preference() -> None:
    member = Member(
        tenant_id=TENANT_A,
        first_name="A",
        last_name="B",
        member_type=MemberType.ADULT,
        email="a@x.test",
        email_bounced=True,
        announcement_email_mode=AnnouncementEmailMode.DIGEST,
    )
    assert (
        initial_email_state(member, send_email=True, delivery=MessageDelivery.IMMEDIATE)
        == EmailState.SKIPPED_BOUNCED
    )


# --- Held rows never drain in the normal pass --------------------------------


def test_held_rows_do_not_drain(session_factory: sessionmaker[Session]) -> None:
    email = FakeEmailBackend()
    with session_factory() as db, tenant_scope(TENANT_A):
        _seed_tenant(db, last_digest_at=datetime.now(UTC))  # not due
        member = _seed_member(db)
        _seed_held_message(db, member, "Held", "Not yet")
        db.commit()

        attempted = drain_email_outbox(db, _service(email))

    assert attempted == 0
    assert email.sent == []
    with session_factory() as db, unscoped():
        states = db.scalars(select(MessageRecipient.email_state)).all()
        assert states == [EmailState.HELD_DIGEST]


# --- Assembly ----------------------------------------------------------------


def test_due_tenant_bundles_messages_into_one_email(
    session_factory: sessionmaker[Session],
) -> None:
    email = FakeEmailBackend()
    with session_factory() as db, tenant_scope(TENANT_A):
        _seed_tenant(db, last_digest_at=None)  # due
        member = _seed_member(db)
        _seed_held_message(db, member, "Campout Saturday", "Bring rain gear")
        _seed_held_message(db, member, "Popcorn sale", "Order forms due Friday")
        db.commit()

        emailed = assemble_digests(db, _service(email), TENANT_A)

    assert emailed == 1
    assert len(email.sent) == 1
    sent = email.sent[0]
    assert sent.to == "scout@x.test"
    assert "42 newsletter" in sent.subject
    # One combined email carrying both held messages' subjects + bodies.
    for token in ("Campout Saturday", "Popcorn sale", "Bring rain gear", "Order forms due Friday"):
        assert token in sent.html_body
        assert token in (sent.text_body or "")

    with session_factory() as db, unscoped():
        states = db.scalars(select(MessageRecipient.email_state)).all()
        assert states == [EmailState.SENT, EmailState.SENT]
        tenant = db.get(Tenant, TENANT_A)
        assert tenant is not None
        assert tenant.last_digest_at is not None


def test_one_email_per_member(session_factory: sessionmaker[Session]) -> None:
    email = FakeEmailBackend()
    with session_factory() as db, tenant_scope(TENANT_A):
        _seed_tenant(db, last_digest_at=None)
        a = _seed_member(db, "a@x.test")
        b = _seed_member(db, "b@x.test")
        _seed_held_message(db, a, "A1", "body")
        _seed_held_message(db, a, "A2", "body")
        _seed_held_message(db, b, "B1", "body")
        db.commit()

        emailed = assemble_digests(db, _service(email), TENANT_A)

    assert emailed == 2
    assert {m.to for m in email.sent} == {"a@x.test", "b@x.test"}


def test_not_yet_due_tenant_untouched(session_factory: sessionmaker[Session]) -> None:
    email = FakeEmailBackend()
    recent = datetime.now(UTC)
    with session_factory() as db, tenant_scope(TENANT_A):
        _seed_tenant(db, last_digest_at=recent)  # already ran for the current slot
        member = _seed_member(db)
        _seed_held_message(db, member, "Held", "wait")
        db.commit()

        emailed = assemble_digests(db, _service(email), TENANT_A)

    assert emailed == 0
    assert email.sent == []
    with session_factory() as db, unscoped():
        states = db.scalars(select(MessageRecipient.email_state)).all()
        assert states == [EmailState.HELD_DIGEST]


def test_assembly_failure_backs_off_and_keeps_held(
    session_factory: sessionmaker[Session],
) -> None:
    class _Failing(FakeEmailBackend):
        def send(self, message: EmailMessage) -> None:
            raise EmailSendError("smtp down")

    with session_factory() as db, tenant_scope(TENANT_A):
        _seed_tenant(db, last_digest_at=None)
        member = _seed_member(db)
        _seed_held_message(db, member, "Held", "body")
        db.commit()

        assemble_digests(db, _service(_Failing()), TENANT_A)

    with session_factory() as db, unscoped():
        row = db.scalars(select(MessageRecipient)).one()
        assert row.email_state == EmailState.HELD_DIGEST  # retryable, not dropped
        assert row.attempts == 1
        assert row.next_attempt_at is not None
        # The slot is *not* marked done while a retry is pending.
        tenant = db.get(Tenant, TENANT_A)
        assert tenant is not None
        assert tenant.last_digest_at is None


def test_assembly_fails_terminally_after_max_attempts(
    session_factory: sessionmaker[Session],
) -> None:
    class _Failing(FakeEmailBackend):
        def send(self, message: EmailMessage) -> None:
            raise EmailSendError("smtp down")

    with session_factory() as db, tenant_scope(TENANT_A):
        _seed_tenant(db, last_digest_at=None)
        member = _seed_member(db)
        message = _seed_held_message(db, member, "Held", "body")
        # Pre-age the row to its final attempt so one more failure is terminal.
        row = db.scalars(
            select(MessageRecipient).where(MessageRecipient.message_id == message.id)
        ).one()
        row.attempts = MAX_EMAIL_ATTEMPTS - 1
        db.commit()

        assemble_digests(db, _service(_Failing()), TENANT_A)

    with session_factory() as db, unscoped():
        row = db.scalars(select(MessageRecipient)).one()
        assert row.email_state == EmailState.FAILED
        tenant = db.get(Tenant, TENANT_A)
        assert tenant is not None
        assert tenant.last_digest_at is not None  # nothing left waiting


def test_opted_out_never_reaches_digest(session_factory: sessionmaker[Session]) -> None:
    """CAN-SPAM: an opted-out member is skipped at resolve time, so nothing is held."""
    member = Member(
        tenant_id=TENANT_A,
        first_name="A",
        last_name="B",
        member_type=MemberType.ADULT,
        email="a@x.test",
        email_opt_out=True,
        announcement_email_mode=AnnouncementEmailMode.EVERY,
    )
    assert (
        initial_email_state(member, send_email=True, delivery=MessageDelivery.DIGEST)
        == EmailState.SKIPPED_OPT_OUT
    )
