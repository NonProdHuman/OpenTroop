from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration sourced from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "OpenTroop"
    database_url: str = "postgresql+psycopg://opentroop:opentroop@localhost:5432/opentroop"


settings = Settings()
