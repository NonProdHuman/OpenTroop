"""The outbox driver (``app/core/outbox.py``): tenant discovery, per-tenant
scoping, error isolation, and the lifespan loop's crash survival.

The business logic underneath (``drain_email_outbox`` / ``promote_due_scheduled``)
is covered in ``test_api_messages.py``; these tests cover the driver shell that
sweeps every tenant with queued work.
"""

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import outbox
from app.core.config import settings
from app.core.notifications import (
    EmailMessage,
    FakeEmailBackend,
    FakePushBackend,
    NotificationService,
)
from app.core.tenant_context import unscoped
from app.models import Base
from app.models.enums import EmailState, MemberType, MessageStatus
from app.models.member import Member
from app.models.message import Message, MessageRecipient
from tests.conftest import TENANT_A, TENANT_B

TENANT_C = uuid.UUID("30000000-0000-0000-0000-000000000003")


class _RaisingEmailBackend(FakeEmailBackend):
    """Delivers normally except to one poisoned address, where it raises an
    unexpected (non-``EmailSendError``) exception — the "provider SDK blew up"
    case that must be contained per tenant."""

    def __init__(self, poison: str) -> None:
        super().__init__()
        self.poison = poison

    def send(self, message: EmailMessage) -> None:
        if message.to == self.poison:
            raise RuntimeError("provider exploded")
        super().send(message)


@pytest.fixture()
def session_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    """In-memory SQLite factory wired into the outbox module's ``SessionLocal``.

    ``run_outbox_pass`` opens its own sessions rather than accepting one, so the
    driver is pointed at the test engine by patching the module binding.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, future=True)
    monkeypatch.setattr(outbox, "SessionLocal", factory)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _use_service(monkeypatch: pytest.MonkeyPatch, email_backend: FakeEmailBackend) -> None:
    service = NotificationService(email_backend=email_backend, push_backend=FakePushBackend())
    monkeypatch.setattr(outbox, "get_notification_service", lambda: service)


def _seed_pending_email(db: Session, tenant_id: uuid.UUID, email: str) -> Message:
    """A SENDING message with one PENDING recipient — drainable work."""
    member = Member(
        tenant_id=tenant_id,
        first_name="Recipient",
        last_name="Outbox",
        member_type=MemberType.ADULT,
        email=email,
    )
    db.add(member)
    db.flush()
    message = Message(
        tenant_id=tenant_id,
        subject="Campout",
        body="Bring rain gear!",
        status=MessageStatus.SENDING,
    )
    db.add(message)
    db.flush()
    db.add(
        MessageRecipient(
            tenant_id=tenant_id,
            message_id=message.id,
            member_id=member.id,
            email_state=EmailState.PENDING,
        )
    )
    db.commit()
    return message


def _seed_due_scheduled(db: Session, tenant_id: uuid.UUID) -> Message:
    """A SCHEDULED message whose time has passed — promotable work."""
    message = Message(
        tenant_id=tenant_id,
        subject="Scheduled",
        body="Later!",
        status=MessageStatus.SCHEDULED,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db.add(message)
    db.commit()
    return message


def test_tenants_with_work_discovers_pending_and_scheduled(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        _seed_pending_email(db, TENANT_A, "a@x.test")
        _seed_due_scheduled(db, TENANT_B)
        # Tenant C has traffic but nothing queued: recipient already sent.
        message = _seed_pending_email(db, TENANT_C, "c@x.test")
        with unscoped():
            recipient = db.scalars(
                select(MessageRecipient).where(MessageRecipient.message_id == message.id)
            ).one()
            recipient.email_state = EmailState.SENT
            message.status = MessageStatus.SENT
            db.commit()

    assert outbox._tenants_with_work() == {TENANT_A, TENANT_B}


def test_run_outbox_pass_drains_every_tenant(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    email = FakeEmailBackend()
    _use_service(monkeypatch, email)
    with session_factory() as db:
        _seed_pending_email(db, TENANT_A, "a@x.test")
        _seed_pending_email(db, TENANT_B, "b@x.test")

    stats = outbox.run_outbox_pass()

    assert stats == {"tenants": 2, "promoted": 0, "emails_attempted": 2}
    assert {m.to for m in email.sent} == {"a@x.test", "b@x.test"}
    with session_factory() as db, unscoped():
        states = db.scalars(select(MessageRecipient.email_state)).all()
        assert states == [EmailState.SENT, EmailState.SENT]
        statuses = db.scalars(select(Message.status)).all()
        assert statuses == [MessageStatus.SENT, MessageStatus.SENT]


def test_run_outbox_pass_promotes_due_scheduled(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_service(monkeypatch, FakeEmailBackend())
    with session_factory() as db:
        message = _seed_due_scheduled(db, TENANT_A)
        message_id = message.id

    stats = outbox.run_outbox_pass()

    assert stats["promoted"] == 1
    with session_factory() as db, unscoped():
        promoted = db.get(Message, message_id)
        assert promoted is not None
        assert promoted.status != MessageStatus.SCHEDULED


def test_one_tenants_failure_does_not_stall_the_rest(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    email = _RaisingEmailBackend(poison="poisoned@x.test")
    _use_service(monkeypatch, email)
    with session_factory() as db:
        _seed_pending_email(db, TENANT_A, "poisoned@x.test")
        _seed_pending_email(db, TENANT_B, "fine@x.test")

    stats = outbox.run_outbox_pass()

    # Both tenants were visited; only the healthy one's attempt counts.
    assert stats["tenants"] == 2
    assert stats["emails_attempted"] == 1
    assert [m.to for m in email.sent] == ["fine@x.test"]
    with session_factory() as db, unscoped():
        by_state = {r.email_state for r in db.scalars(select(MessageRecipient)).all()}
        # The poisoned tenant's session rolled back — its recipient stays
        # PENDING for the next pass; the healthy tenant's is SENT.
        assert by_state == {EmailState.PENDING, EmailState.SENT}


def test_outbox_loop_survives_a_crashing_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def flaky_pass() -> dict[str, int]:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("pass crashed")
        if len(calls) == 2:  # a quiet tick — nothing to log
            return {"tenants": 0, "promoted": 0, "emails_attempted": 0}
        return {"tenants": 1, "promoted": 0, "emails_attempted": 1}

    monkeypatch.setattr(outbox, "run_outbox_pass", flaky_pass)
    monkeypatch.setattr(settings, "outbox_tick_seconds", 0)

    async def run_three_ticks() -> None:
        task = asyncio.create_task(outbox.outbox_loop())
        try:
            async with asyncio.timeout(5):
                while len(calls) < 3:
                    await asyncio.sleep(0.01)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            # The loop must propagate cancellation (not swallow it) or app
            # shutdown would hang waiting on it.
            assert task.cancelled()

    asyncio.run(run_three_ticks())
    assert len(calls) >= 3  # the crash on tick 1 did not kill the loop
