"""Tests for authentication utilities: tenant resolution and user identity."""

import pytest
from sqlalchemy.orm import Session

from app.core.auth import get_or_create_user
from app.core.tenant import _extract_subdomain
from app.models.user import User

# ---------------------------------------------------------------------------
# Subdomain extraction
# ---------------------------------------------------------------------------


def test_extract_subdomain_valid() -> None:
    assert _extract_subdomain("troop123.opentroop.app", "opentroop.app") == "troop123"


def test_extract_subdomain_with_port() -> None:
    assert _extract_subdomain("troop123.opentroop.app:8080", "opentroop.app") == "troop123"


def test_extract_subdomain_apex_returns_none() -> None:
    assert _extract_subdomain("opentroop.app", "opentroop.app") is None


def test_extract_subdomain_unrelated_domain_returns_none() -> None:
    assert _extract_subdomain("other.com", "opentroop.app") is None


def test_extract_subdomain_nested_rejected() -> None:
    # Nested subdomain must not resolve — prevents Host-header spoofing.
    assert _extract_subdomain("a.troop123.opentroop.app", "opentroop.app") is None


def test_extract_subdomain_case_insensitive() -> None:
    assert _extract_subdomain("Troop123.opentroop.app", "opentroop.app") == "troop123"


# ---------------------------------------------------------------------------
# User / Identity provisioning
# ---------------------------------------------------------------------------


def test_get_or_create_user_first_login(db_session: Session) -> None:
    claims = {
        "iss": "https://accounts.google.com",
        "sub": "1234567890",
        "email": "alice@example.com",
        "name": "Alice Smith",
    }
    user = get_or_create_user(claims, db_session)
    assert isinstance(user, User)
    assert user.email == "alice@example.com"
    assert user.display_name == "Alice Smith"
    assert len(user.identities) == 1
    assert user.identities[0].provider == "google"
    assert user.identities[0].issuer == "https://accounts.google.com"
    assert user.identities[0].provider_sub == "1234567890"


def test_get_or_create_user_second_login_returns_same_user(db_session: Session) -> None:
    claims = {
        "iss": "https://accounts.google.com",
        "sub": "1234567890",
        "email": "alice@example.com",
    }
    user1 = get_or_create_user(claims, db_session)
    user2 = get_or_create_user(claims, db_session)
    assert user1.id == user2.id


def test_get_or_create_user_different_providers_create_separate_users(
    db_session: Session,
) -> None:
    google_claims = {
        "iss": "https://accounts.google.com",
        "sub": "g-001",
        "email": "bob@example.com",
    }
    apple_claims = {
        "iss": "https://appleid.apple.com",
        "sub": "a-001",
        "email": "bob@example.com",
    }
    user_g = get_or_create_user(google_claims, db_session)
    user_a = get_or_create_user(apple_claims, db_session)
    # Different (issuer, sub) pairs → different User records (no auto-link by email)
    assert user_g.id != user_a.id


def test_get_or_create_user_no_email(db_session: Session) -> None:
    claims = {"iss": "https://accounts.google.com", "sub": "anon-001"}
    user = get_or_create_user(claims, db_session)
    assert user.email is None
    assert user.display_name is None


@pytest.mark.parametrize(
    ("issuer", "expected_provider"),
    [
        ("https://accounts.google.com", "google"),
        ("https://appleid.apple.com", "apple"),
        ("https://my-app.clerk.accounts.dev", "clerk"),
        ("https://authentik.example.com", "authentik"),
        ("https://sso.example.com", "oidc"),
    ],
)
def test_provider_label_derived_from_issuer(
    db_session: Session, issuer: str, expected_provider: str
) -> None:
    claims = {"iss": issuer, "sub": f"sub-{issuer}"}
    user = get_or_create_user(claims, db_session)
    assert user.identities[0].provider == expected_provider
