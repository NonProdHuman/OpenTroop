"""Vendor-agnostic notification abstraction (see docs issue #75).

App code talks to `NotificationService`, never a vendor SDK directly. Backend
selection happens once, in `get_notification_service()`, via `EMAIL_BACKEND`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

import httpx2 as httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Raised when a backend fails to deliver an email."""


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html_body: str
    text_body: str | None = None
    reply_to: str | None = None


class EmailBackend(Protocol):
    def send(self, message: EmailMessage) -> None:
        pass


@dataclass(frozen=True)
class SMSMessage:
    to: str
    body: str


class SMSSendError(Exception):
    """Raised when a backend fails to deliver an SMS."""


class SMSBackend(Protocol):
    def send(self, message: SMSMessage) -> None:
        pass


@dataclass(frozen=True)
class PushMessage:
    """One mobile push (GH-82). ``token`` is an Expo push token in v1."""

    token: str
    title: str
    body: str
    data: dict[str, str] | None = None


class PushBackend(Protocol):
    def send_batch(self, messages: list[PushMessage]) -> list[str]:
        """Deliver best-effort; return tokens the vendor reports as dead."""


class NullPushBackend:
    """Default: push disabled (dev/self-host). Sends nothing, reports nothing."""

    def send_batch(self, messages: list[PushMessage]) -> list[str]:
        return []


class FakePushBackend:
    """In-memory backend for tests."""

    def __init__(self) -> None:
        self.sent: list[PushMessage] = []
        self.dead_tokens: list[str] = []

    def send_batch(self, messages: list[PushMessage]) -> list[str]:
        self.sent.extend(messages)
        return [t for t in self.dead_tokens if any(m.token == t for m in messages)]


class ExpoPushBackend:
    """Expo Push Service (https://docs.expo.dev/push-notifications/sending-notifications/).

    One API for iOS and Android; EAS manages APNs/FCM credentials. Chunks of
    ≤100 per request. ``DeviceNotRegistered`` tickets are returned as dead
    tokens so the caller can prune them.
    """

    CHUNK = 100

    def __init__(self, url: str) -> None:
        self.url = url

    def send_batch(self, messages: list[PushMessage]) -> list[str]:
        dead: list[str] = []
        for start in range(0, len(messages), self.CHUNK):
            chunk = messages[start : start + self.CHUNK]
            payload = [
                {
                    "to": m.token,
                    "title": m.title,
                    "body": m.body,
                    **({"data": m.data} if m.data else {}),
                }
                for m in chunk
            ]
            try:
                response = httpx.post(self.url, json=payload, timeout=10.0)
                response.raise_for_status()
                tickets = response.json().get("data", [])
            except (httpx.HTTPError, ValueError) as exc:
                # Push is best-effort by contract — log and move on.
                logger.warning("Expo push send failed: %s", exc)
                continue
            for message, ticket in zip(chunk, tickets, strict=False):
                details = ticket.get("details") or {}
                if (
                    ticket.get("status") == "error"
                    and details.get("error") == "DeviceNotRegistered"
                ):
                    dead.append(message.token)
        return dead


class FakeEmailBackend:
    """In-memory backend for tests and local dev without a real provider."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


class UnconfiguredSMSBackend:
    """Placeholder used until an SMS vendor is selected."""

    def send(self, message: SMSMessage) -> None:
        raise SMSSendError("No SMS backend is configured")


class ResendEmailBackend:
    """Sends email via the Resend HTTP API (https://resend.com/docs/api-reference)."""

    _API_URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, from_address: str) -> None:
        self._api_key = api_key
        self._from_address = from_address

    def send(self, message: EmailMessage) -> None:
        payload: dict[str, object] = {
            "from": self._from_address,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html_body,
        }
        if message.text_body is not None:
            payload["text"] = message.text_body
        if message.reply_to is not None:
            payload["reply_to"] = message.reply_to

        try:
            response = httpx.post(
                self._API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Resend email send failed: %s", exc)
            raise EmailSendError(str(exc)) from exc


@dataclass
class NotificationService:
    email_backend: EmailBackend
    sms_backend: SMSBackend = field(default_factory=UnconfiguredSMSBackend)
    push_backend: PushBackend = field(default_factory=NullPushBackend)

    def send_email(self, message: EmailMessage) -> None:
        self.email_backend.send(message)

    def send_sms(self, message: SMSMessage) -> None:
        self.sms_backend.send(message)

    def send_push(self, messages: list[PushMessage]) -> list[str]:
        """Best-effort batch push; returns dead tokens for pruning."""
        if not messages:
            return []
        return self.push_backend.send_batch(messages)


def get_email_backend() -> EmailBackend:
    backend = settings.email_backend
    if backend == "resend":
        if not settings.resend_api_key or not settings.email_from_address:
            raise RuntimeError(
                "EMAIL_BACKEND=resend requires RESEND_API_KEY and EMAIL_FROM_ADDRESS"
            )
        return ResendEmailBackend(settings.resend_api_key, settings.email_from_address)
    if backend == "fake":
        return FakeEmailBackend()
    raise RuntimeError(f"Unknown EMAIL_BACKEND: {backend!r}")


def get_push_backend() -> PushBackend:
    backend = settings.push_backend
    if backend == "expo":
        return ExpoPushBackend(settings.expo_push_url)
    if backend == "fake":
        return FakePushBackend()
    if backend == "none":
        return NullPushBackend()
    raise RuntimeError(f"Unknown PUSH_BACKEND: {backend!r}")


def get_notification_service() -> NotificationService:
    return NotificationService(email_backend=get_email_backend(), push_backend=get_push_backend())
