"""Inbound provider webhooks (GH-80).

Currently: Resend email bounce/complaint delivery events. This router is **not**
JWT/tenant-authenticated — the credential is the provider's HMAC webhook signature —
so every handler must verify the signature before touching the database.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.core.deps import AdminDbDep
from app.core.email_webhooks import (
    EVENT_COMPLAINED,
    WebhookVerificationError,
    apply_email_event,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/email/resend", status_code=status.HTTP_200_OK)
async def resend_email_webhook(request: Request, db: AdminDbDep) -> dict[str, object]:
    """Handle a Resend delivery event (bounce / complaint).

    Inert unless ``RESEND_WEBHOOK_SECRET`` is configured — otherwise 404, so the
    endpoint is invisible on dev/self-host deployments that don't wire it up.

    Verifies the Standard Webhooks (svix) signature over the raw body, then flips
    suppression flags on matching Member rows **across all tenants** (a bounce is an
    address-level fact — see ``apply_email_event``). Unknown event types are accepted
    as a 200 no-op; we always answer fast so the provider never enters a retry storm.
    """
    secret = settings.resend_webhook_secret
    if not secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    body = await request.body()
    try:
        verify_webhook_signature(
            secret,
            request.headers.get("svix-id"),
            request.headers.get("svix-timestamp"),
            request.headers.get("svix-signature"),
            body,
        )
    except WebhookVerificationError as exc:
        # Log at info: an unverifiable webhook is either misconfiguration or a probe,
        # not an actionable error.
        logger.info("Rejected Resend webhook: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Signature verification failed"
        ) from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        # Signed but unparseable — 400 (not 500); nothing to retry into.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body"
        ) from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    event_type = payload.get("type")
    if not isinstance(event_type, str):
        return {"status": "ignored"}

    updated = apply_email_event(db, event_type, payload)
    if updated:
        # `updated` is only nonzero for the two handled event types, so log a
        # derived literal, never the request-supplied string (py/log-injection).
        action = "complaint" if event_type == EVENT_COMPLAINED else "bounce"
        logger.info("Resend %s updated %d member row(s)", action, updated)
    return {"status": "ok", "event": event_type, "updated": updated}
