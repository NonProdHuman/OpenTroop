"""Settings validation: a weak APP_SECRET means forgeable claim tokens (GH-110)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(secret: str) -> Settings:
    return Settings(
        app_secret=secret,
        app_domain="opentroop.test",
        cors_origins=["http://localhost:3000"],
        _env_file=None,
    )


def test_app_secret_shorter_than_32_chars_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings("change-me-in-production")  # 23 chars — the old sample value


def test_app_secret_of_32_chars_accepted() -> None:
    assert _settings("x" * 32).app_secret == "x" * 32
