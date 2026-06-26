from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration sourced from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "OpenTroop"
    database_url: str = "postgresql+psycopg://opentroop:opentroop@localhost:5432/opentroop"

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
    cors_origins: list[str] = ["http://localhost:3000"]

    # Domain used for subdomain tenant routing (e.g. troop123.opentroop.app → "opentroop.app")
    app_domain: str = "opentroop.app"

    # Secret used to sign member invite/claim tokens (HS256). Must be changed in production.
    app_secret: str = "change-me-in-production"  # noqa: S105


settings = Settings()
