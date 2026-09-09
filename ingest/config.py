"""Validated ingestion configuration loaded at process startup."""

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Required settings for the ingestion process."""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: AnyHttpUrl
    supabase_service_role_key: SecretStr = Field(min_length=1)
    healthchecks_ping_url: AnyHttpUrl


settings = Settings()
