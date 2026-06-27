from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration sourced from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "OpenTroop"
    database_url: str = "postgresql+psycopg://opentroop:opentroop@localhost:5432/opentroop"

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        if v and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        if v and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

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
