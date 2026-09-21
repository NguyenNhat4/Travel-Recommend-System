from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Travel Recommendation API"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    itinerary_service_base_url: str | None = Field(default=None, pattern=r"^https?://")

    @field_validator("itinerary_service_base_url", mode="before")
    @classmethod
    def empty_itinerary_service_base_url_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    itinerary_data_mode: Literal["fixture", "http", "disabled"] | None = None
    itinerary_tool_timeout_seconds: float = Field(default=1.0, gt=0)
    itinerary_llm_timeout_seconds: float = Field(default=2.0, gt=0)
    itinerary_request_timeout_seconds: float = Field(default=5.0, gt=0)
    itinerary_conversation_ttl_seconds: int = Field(default=86_400, ge=60)

    # Local week-1 topology: one PostgreSQL instance, two roles/connections.
    # The app role cannot read cdp.events/profiles; LocalCdpClient cannot access app/catalog.
    database_url: str = "postgresql://vota_app_login:vota@localhost:5432/vota"
    cdp_database_url: str = "postgresql://cdp_client_login:cdp@localhost:5432/vota"
    cdp_adapter: Literal["local", "http"] = "local"

    # Future/production HTTP adapter. Ignored while CDP_ADAPTER=local.
    cdp_base_url: str = "http://localhost:8100"
    cdp_service_token: str = ""
    cdp_timeout_seconds: float = Field(default=2.0, gt=0)
    # Browse events waiting to be sent; beyond this they are dropped and logged.
    cdp_event_queue_size: int = Field(default=1000, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
