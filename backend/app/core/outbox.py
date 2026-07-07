"""The messaging outbox driver (GH-78): one pass = promote due scheduled sends
and drain pending emails, per tenant, with per-tenant pacing.

Runs from two places: the in-process lifespan loop (``OUTBOX_LOOP_ENABLED``)
and the ``drain-outbox`` CLI (cron / self-host belt). Both call
:func:`run_outbox_pass`, which discovers tenants with work via ``unscoped()``
and then processes each inside its own ``tenant_scope`` so RLS and the ORM
tenant filter hold exactly as they do on request paths.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.messaging import assemble_digests, drain_email_outbox, promote_due_scheduled
from app.core.notifications import get_notification_service
from app.core.tenant_context import tenant_scope, unscoped
from app.models.enums import EmailState, MessageStatus
from app.models.message import Message, MessageRecipient

logger = logging.getLogger(__name__)


def _tenants_with_work() -> set[uuid.UUID]:
    with SessionLocal() as db, unscoped():
        pending = set(
            db.scalars(
                select(MessageRecipient.tenant_id)
                .where(MessageRecipient.email_state == EmailState.PENDING)
                .distinct()
            ).all()
        )
        scheduled = set(
            db.scalars(
                select(Message.tenant_id)
                .where(Message.status == MessageStatus.SCHEDULED)
                .distinct()
            ).all()
        )
        # Tenants holding withheld digest email (GH-218). Due-ness is a per-tenant
        # cadence check inside the pass; visiting a not-yet-due tenant is a cheap no-op.
        held = set(
            db.scalars(
                select(MessageRecipient.tenant_id)
                .where(MessageRecipient.email_state == EmailState.HELD_DIGEST)
                .distinct()
            ).all()
        )
    return pending | scheduled | held


def run_outbox_pass() -> dict[str, int]:
    """One sweep across every tenant with queued work. Returns counters."""
    service = get_notification_service()
    promoted = attempted = digested = tenants = 0
    for tenant_id in _tenants_with_work():
        tenants += 1
        try:
            with SessionLocal() as db, tenant_scope(tenant_id):
                promoted += promote_due_scheduled(db, service)
                attempted += drain_email_outbox(db, service)
                digested += assemble_digests(db, service, tenant_id)
        except Exception:  # noqa: BLE001 — one tenant's failure must not stall the rest
            logger.warning("Outbox pass failed for tenant %s", tenant_id.hex, exc_info=True)
    return {
        "tenants": tenants,
        "promoted": promoted,
        "emails_attempted": attempted,
        "digests_sent": digested,
    }


async def outbox_loop() -> None:
    """The in-process driver: tick forever until cancelled (app lifespan)."""
    logger.info("Outbox loop started (tick every %ss)", settings.outbox_tick_seconds)
    while True:
        try:
            stats = await asyncio.to_thread(run_outbox_pass)
            if stats["emails_attempted"] or stats["promoted"] or stats["digests_sent"]:
                logger.info("Outbox pass: %s", stats)
        except Exception:  # noqa: BLE001 — the loop must survive anything
            logger.warning("Outbox pass crashed; continuing", exc_info=True)
        await asyncio.sleep(settings.outbox_tick_seconds)
