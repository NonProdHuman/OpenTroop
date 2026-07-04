from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration sourced from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "OpenTroop"
    database_url: str = "postgresql+psycopg://opentroop:opentroop@localhost:5432/opentroop"

    @field_validator("database_url", "database_url_admin", "database_url_migrate", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        if v and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        if v and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    # Cross-tenant platform operations (opentroop_admin role, BYPASSRLS).
    # Required for the /platform control-plane routes.  Self-hosted deployments
    # may point this at the same URL as DATABASE_URL (one owner role, one DB).
    # SaaS deployments must use a distinct credential with BYPASSRLS.
    database_url_admin: str = ""

    # Alembic / DDL migrations (table owner + BYPASSRLS so data backfills under
    # FORCE see all rows).  Falls back to DATABASE_URL when empty, which is fine
    # for local dev and self-hosted deployments where the app URL is already the
    # owner.  SaaS should set this to a separate owner credential.
    database_url_migrate: str = ""

    # OIDC / JWT — point at your provider's JWKS endpoint.
    # Clerk SaaS:    https://<frontend-api>.clerk.accounts.dev/.well-known/jwks.json
    # Authentik:     https://<host>/application/o/<app>/jwks/
    auth_jwks_uri: str = ""
    auth_issuer: str = ""
    auth_audience: str = ""

    # Comma-separated list of origins allowed by CORS.
    # In production this should be your actual frontend URL(s).
    cors_origins: list[str]

    # Domain used for subdomain tenant routing (e.g. troop123.opentroop.app → "opentroop.app")
    app_domain: str = Field(min_length=1)

    # Honor the X-Forwarded-Host header for subdomain tenant resolution. The header is
    # client-controlled, so only enable this when every path to the API goes through a
    # trusted proxy that sets (or strips) it — e.g. the Cloudflare Worker in the SaaS
    # deployment. When False (default), tenant resolution uses the Host header only.
    trust_forwarded_host: bool = False

    # Bootstrap allowlist for the first platform superadmin. When set, a user whose
    # provider-verified email matches (case-insensitive) is granted SUPERADMIN on
    # sign-in. Leave empty to bootstrap exclusively via `uv run promote-platform-admin`.
    # There is deliberately no "first signup wins" fallback — on a public SaaS an
    # empty users table (launch day, DB restore) must not be a race anyone can win.
    bootstrap_superadmin_email: str = ""

    # Secret used to sign member invite/claim tokens (HS256). A guessable secret means
    # forgeable claim tokens → tenant admin takeover, so a minimum length is enforced
    # at startup. Generate one with: python3 -c "import secrets; print(secrets.token_urlsafe(48))"
    app_secret: str = Field(min_length=32)

    # TWH import upload bounds (GH-175 Finding 2). The API is shared by many tenants,
    # so one member's crafted zip/gzip bomb must not be able to exhaust its memory.
    # A real full-troop TWH export is a few MB of XML — these are generous ceilings,
    # not targets. Self-hosted deployments may tune them via environment.
    twh_import_max_upload_bytes: int = 25 * 1024 * 1024
    twh_import_max_decompressed_bytes: int = 200 * 1024 * 1024
    twh_import_max_zip_entries: int = 64

    # Email delivery backend: "fake" (default, no vendor call — for local dev/tests)
    # or "resend". See app/core/notifications.py.
    email_backend: str = "fake"
    resend_api_key: str = ""
    email_from_address: str = ""


settings = Settings()  # type: ignore[call-arg]
