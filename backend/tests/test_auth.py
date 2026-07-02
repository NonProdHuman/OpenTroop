"""Tests for authentication utilities: tenant resolution and user identity."""

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from sqlalchemy.orm import Session

import app.core.auth as auth_module
from app.core.auth import decode_token, get_or_create_user
from app.core.config import settings
from app.core.tenant import _extract_subdomain
from app.models.enums import MemberType, PlatformRole
from app.models.member import Member
from app.models.user import User
from tests.conftest import TENANT_A

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


def test_extract_subdomain_reserved_returns_none() -> None:
    # Platform surfaces must never be parsed as tenant slugs.
    assert _extract_subdomain("admin.opentroop.app", "opentroop.app") is None
    assert _extract_subdomain("www.opentroop.app", "opentroop.app") is None
    # Case-insensitive and port-tolerant too.
    assert _extract_subdomain("Admin.opentroop.localhost:3000", "opentroop.localhost") is None


# ---------------------------------------------------------------------------
# JWT validation (decode_token) — issuer verification + required claims (GH-112)
# ---------------------------------------------------------------------------

_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

ISSUER = "https://auth.example.com"


class _StubSigningKey:
    def __init__(self, key: Any) -> None:
        self.key = key


class _StubJwksClient:
    """Stands in for the JWKS fetch so tests can sign with a local key."""

    def get_signing_key_from_jwt(self, token: str) -> _StubSigningKey:
        return _StubSigningKey(_RSA_KEY.public_key())


def _make_token(claims: dict[str, Any]) -> str:
    return jwt.encode(claims, _RSA_KEY, algorithm="RS256")


def _standard_claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "sub": "user-123",
        "iat": now,
        "exp": now + 300,
        **overrides,
    }
    # Passing claim=None in overrides removes the claim entirely.
    return {k: v for k, v in claims.items() if v is not None}


@pytest.fixture(autouse=False)
def stub_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module, "_get_jwks_client", lambda: _StubJwksClient())


def _assert_rejected(token: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    assert exc_info.value.status_code == 401


def test_decode_token_valid_with_matching_issuer(
    stub_jwks: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "auth_issuer", ISSUER)
    claims = decode_token(_make_token(_standard_claims()))
    assert claims["sub"] == "user-123"
    assert claims["iss"] == ISSUER


def test_decode_token_rejects_wrong_issuer(
    stub_jwks: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "auth_issuer", ISSUER)
    _assert_rejected(_make_token(_standard_claims(iss="https://evil.example.com")))


def test_decode_token_unset_issuer_skips_value_check(
    stub_jwks: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Deployments that don't pin AUTH_ISSUER accept any issuer value (the JWKS
    # signature is the trust anchor) — pin this permissive behavior explicitly.
    monkeypatch.setattr(settings, "auth_issuer", "")
    claims = decode_token(_make_token(_standard_claims(iss="https://other.example.com")))
    assert claims["iss"] == "https://other.example.com"


@pytest.mark.parametrize("missing", ["iss", "sub", "exp", "iat"])
def test_decode_token_rejects_missing_standard_claim(
    stub_jwks: None, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    # Even with AUTH_ISSUER unset, every standard claim must be *present*:
    # identity is keyed on (iss, sub), and exp/iat bound the token lifetime.
    monkeypatch.setattr(settings, "auth_issuer", "")
    _assert_rejected(_make_token(_standard_claims(**{missing: None})))


def test_decode_token_rejects_expired(stub_jwks: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_issuer", ISSUER)
    now = int(time.time())
    _assert_rejected(_make_token(_standard_claims(iat=now - 600, exp=now - 300)))


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
    # No first-signup-wins: the first user on an empty table is NOT auto-promoted
    # (GH-111 — launch day / DB restore must not be a race anyone can win).
    assert user.platform_role is None


def test_get_or_create_user_second_login_returns_same_user(db_session: Session) -> None:
    claims = {
        "iss": "https://accounts.google.com",
        "sub": "1234567890",
        "email": "alice@example.com",
    }
    user1 = get_or_create_user(claims, db_session)
    user2 = get_or_create_user(claims, db_session)
    assert user1.id == user2.id


def test_get_or_create_user_backfills_email_on_later_login(db_session: Session) -> None:
    # First login without email/name (e.g. JWT lacked the claims).
    bare = {"iss": "https://accounts.google.com", "sub": "late-email"}
    user = get_or_create_user(bare, db_session)
    assert user.email is None
    assert user.display_name is None

    # A later login now carries the claims → they backfill onto the existing user.
    enriched = {**bare, "email": "carol@example.com", "name": "Carol Jones"}
    same = get_or_create_user(enriched, db_session)
    assert same.id == user.id
    assert same.email == "carol@example.com"
    assert same.display_name == "Carol Jones"


def test_get_or_create_user_does_not_clobber_existing_email(db_session: Session) -> None:
    first = {"iss": "https://accounts.google.com", "sub": "stable", "email": "first@example.com"}
    user = get_or_create_user(first, db_session)
    # A later login with a different email does not overwrite the stored one.
    get_or_create_user({**first, "email": "changed@example.com"}, db_session)
    db_session.refresh(user)
    assert user.email == "first@example.com"


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


# ---------------------------------------------------------------------------
# Email-based Member auto-link — gated on a verified email claim (GH-110)
# ---------------------------------------------------------------------------


def _unclaimed_member(db: Session, email: str) -> Member:
    member = Member(
        tenant_id=TENANT_A,
        first_name="Founding",
        last_name="Admin",
        email=email,
        member_type=MemberType.ADULT,
    )
    db.add(member)
    db.commit()
    return member


def test_unverified_email_claim_does_not_autolink_member(db_session: Session) -> None:
    """An email claim without email_verified must never link an unclaimed Member.

    Tenant provisioning creates an unclaimed founding-admin Member; before GH-110
    a first login carrying the victim's (unverified) email in claims silently took
    over that admin seat.
    """
    member = _unclaimed_member(db_session, "founder@example.com")
    claims = {"iss": "https://sso.example.com", "sub": "attacker-1", "email": "founder@example.com"}
    get_or_create_user(claims, db_session)
    db_session.refresh(member)
    assert member.user_id is None


def test_truthy_but_non_boolean_email_verified_does_not_autolink(db_session: Session) -> None:
    """Only a literal ``true`` counts — strings like "true" are not verification."""
    member = _unclaimed_member(db_session, "founder2@example.com")
    claims = {
        "iss": "https://sso.example.com",
        "sub": "attacker-2",
        "email": "founder2@example.com",
        "email_verified": "true",
    }
    user = get_or_create_user(claims, db_session)
    db_session.refresh(member)
    assert member.user_id is None
    assert user.email_verified is False


def test_verified_email_claim_autolinks_member(db_session: Session) -> None:
    member = _unclaimed_member(db_session, "leader@example.com")
    claims = {
        "iss": "https://sso.example.com",
        "sub": "leader-sub",
        "email": "leader@example.com",
        "email_verified": True,
    }
    user = get_or_create_user(claims, db_session)
    db_session.refresh(member)
    assert member.user_id == user.id
    assert user.email_verified is True


def test_repeat_login_without_changes_does_not_commit(db_session: Session) -> None:
    """A steady-state login must be read-only (GH-115).

    The auto-link path used to mark the session changed unconditionally, so every
    authenticated request paid a commit. Once the profile is populated and no
    unclaimed member matches, a repeat login must not write.
    """
    claims = {
        "iss": "https://sso.example.com",
        "sub": "steady-state",
        "email": "steady@example.com",
        "name": "Steady State",
        "email_verified": True,
    }
    get_or_create_user(claims, db_session)

    commits = 0
    original_commit = db_session.commit

    def counting_commit() -> None:
        nonlocal commits
        commits += 1
        original_commit()

    db_session.commit = counting_commit  # type: ignore[method-assign]
    try:
        get_or_create_user(claims, db_session)
    finally:
        db_session.commit = original_commit  # type: ignore[method-assign]
    assert commits == 0


def test_repeat_login_still_links_newly_invited_member(db_session: Session) -> None:
    """The no-write fast path must not break late linking: a member invited after
    the user's earlier logins still links (and commits) on the next sign-in."""
    claims = {
        "iss": "https://sso.example.com",
        "sub": "late-invite",
        "email": "late-invite@example.com",
        "email_verified": True,
    }
    user = get_or_create_user(claims, db_session)
    get_or_create_user(claims, db_session)  # steady-state login, no member yet

    member = _unclaimed_member(db_session, "late-invite@example.com")
    get_or_create_user(claims, db_session)
    db_session.refresh(member)
    assert member.user_id == user.id


def test_autolink_happens_on_later_verified_login(db_session: Session) -> None:
    """A member invited after (or verified after) first login links on the next sign-in."""
    claims = {
        "iss": "https://sso.example.com",
        "sub": "late-link",
        "email": "late@example.com",
        "email_verified": True,
    }
    user = get_or_create_user(claims, db_session)
    member = _unclaimed_member(db_session, "late@example.com")

    same = get_or_create_user(claims, db_session)
    db_session.refresh(member)
    assert same.id == user.id
    assert member.user_id == user.id


def test_email_verified_upgrades_on_later_verified_login(db_session: Session) -> None:
    claims = {"iss": "https://sso.example.com", "sub": "upgrade", "email": "up@example.com"}
    user = get_or_create_user(claims, db_session)
    assert user.email_verified is False

    get_or_create_user({**claims, "email_verified": True}, db_session)
    db_session.refresh(user)
    assert user.email_verified is True


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


# ---------------------------------------------------------------------------
# Superadmin bootstrap allowlist (GH-111)
# ---------------------------------------------------------------------------


def _bootstrap_claims(**overrides: object) -> dict:
    return {
        "iss": "https://accounts.google.com",
        "sub": "bootstrap-sub",
        "email": "founder@example.com",
        "email_verified": True,
        **overrides,
    }


def test_bootstrap_email_grants_superadmin(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "bootstrap_superadmin_email", "founder@example.com")
    user = get_or_create_user(_bootstrap_claims(), db_session)
    assert user.platform_role is PlatformRole.SUPERADMIN


def test_bootstrap_email_match_is_case_insensitive(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "bootstrap_superadmin_email", "Founder@Example.COM")
    user = get_or_create_user(_bootstrap_claims(), db_session)
    assert user.platform_role is PlatformRole.SUPERADMIN


def test_bootstrap_requires_verified_email(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unverified email claim is attacker-chosen — it must never confer superadmin."""
    monkeypatch.setattr(settings, "bootstrap_superadmin_email", "founder@example.com")
    user = get_or_create_user(_bootstrap_claims(email_verified=False), db_session)
    assert user.platform_role is None


def test_bootstrap_ignores_non_matching_email(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "bootstrap_superadmin_email", "founder@example.com")
    user = get_or_create_user(_bootstrap_claims(email="stranger@example.com"), db_session)
    assert user.platform_role is None


def test_bootstrap_promotes_existing_user_on_later_verified_login(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user who signed in before the allowlist was set (or before verification)
    is promoted on their next verified sign-in."""
    monkeypatch.setattr(settings, "bootstrap_superadmin_email", "founder@example.com")
    user = get_or_create_user(_bootstrap_claims(email_verified=False), db_session)
    assert user.platform_role is None

    same = get_or_create_user(_bootstrap_claims(), db_session)
    assert same.id == user.id
    assert same.platform_role is PlatformRole.SUPERADMIN


def test_bootstrap_empty_setting_grants_nothing(db_session: Session) -> None:
    user = get_or_create_user(_bootstrap_claims(), db_session)
    assert user.platform_role is None
