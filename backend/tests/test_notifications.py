import pytest

from app.core import notifications
from app.core.notifications import (
    EmailMessage,
    EmailSendError,
    FakeEmailBackend,
    NotificationService,
    ResendEmailBackend,
    SMSMessage,
    SMSSendError,
    UnconfiguredSMSBackend,
    get_email_backend,
)


def test_notification_service_sends_email_via_backend() -> None:
    backend = FakeEmailBackend()
    service = NotificationService(email_backend=backend)
    message = EmailMessage(to="scout@example.com", subject="Welcome", html_body="<p>Hi</p>")

    service.send_email(message)

    assert backend.sent == [message]


def test_notification_service_raises_without_sms_backend() -> None:
    service = NotificationService(email_backend=FakeEmailBackend())

    with pytest.raises(SMSSendError):
        service.send_sms(SMSMessage(to="+15551234567", body="Reminder"))


def test_notification_service_uses_configured_sms_backend() -> None:
    sent: list[SMSMessage] = []

    class RecordingSMSBackend:
        def send(self, message: SMSMessage) -> None:
            sent.append(message)

    service = NotificationService(
        email_backend=FakeEmailBackend(), sms_backend=RecordingSMSBackend()
    )
    message = SMSMessage(to="+15551234567", body="Reminder")

    service.send_sms(message)

    assert sent == [message]


def test_unconfigured_sms_backend_raises() -> None:
    with pytest.raises(SMSSendError):
        UnconfiguredSMSBackend().send(SMSMessage(to="+15551234567", body="hi"))


def test_get_email_backend_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications.settings, "email_backend", "fake")

    backend = get_email_backend()

    assert isinstance(backend, FakeEmailBackend)


def test_get_email_backend_resend_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications.settings, "email_backend", "resend")
    monkeypatch.setattr(notifications.settings, "resend_api_key", "")
    monkeypatch.setattr(notifications.settings, "email_from_address", "")

    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        get_email_backend()


def test_get_email_backend_resend_builds_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications.settings, "email_backend", "resend")
    monkeypatch.setattr(notifications.settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(notifications.settings, "email_from_address", "troop@example.com")

    backend = get_email_backend()

    assert isinstance(backend, ResendEmailBackend)


def test_get_email_backend_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications.settings, "email_backend", "carrier-pigeon")

    with pytest.raises(RuntimeError, match="Unknown EMAIL_BACKEND"):
        get_email_backend()


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise notifications.httpx.HTTPStatusError(
                "error",
                request=None,
                response=self,  # type: ignore[arg-type]
            )


def test_resend_backend_posts_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(
        url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> _FakeResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse(200)

    monkeypatch.setattr(notifications.httpx, "post", fake_post)
    backend = ResendEmailBackend(api_key="re_test_key", from_address="troop@example.com")

    backend.send(
        EmailMessage(
            to="scout@example.com",
            subject="Welcome",
            html_body="<p>Hi</p>",
            text_body="Hi",
            reply_to="leader@example.com",
        )
    )

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"] == {"Authorization": "Bearer re_test_key"}
    assert captured["json"] == {
        "from": "troop@example.com",
        "to": ["scout@example.com"],
        "subject": "Welcome",
        "html": "<p>Hi</p>",
        "text": "Hi",
        "reply_to": "leader@example.com",
    }


def test_resend_backend_raises_email_send_error_on_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(
        url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> _FakeResponse:
        return _FakeResponse(500)

    monkeypatch.setattr(notifications.httpx, "post", fake_post)
    backend = ResendEmailBackend(api_key="re_test_key", from_address="troop@example.com")

    with pytest.raises(EmailSendError):
        backend.send(EmailMessage(to="scout@example.com", subject="Welcome", html_body="<p>Hi</p>"))
