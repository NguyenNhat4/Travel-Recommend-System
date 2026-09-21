from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Biến để trống trong .env đến đây là chuỗi rỗng, không phải None. Với các trường optional có
# `pattern` hoặc `Literal`, chuỗi rỗng làm Settings() ném ValidationError và backend không khởi
# động nổi — mà .env.example vốn để trống đúng những biến này, nên ai làm theo hướng dẫn
# "copy .env.example sang .env" đều vấp. Coi rỗng là "không đặt".
# Chỉ các trường thực sự Optional: trường `str` thường (cdp_service_token, openai_api_key) coi ""
# là "chưa cấu hình" và vẫn hợp lệ, không được đổi thành None.
_OPTIONAL_BLANK_IS_NONE = ("itinerary_service_base_url", "itinerary_data_mode")


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


    @field_validator(*_OPTIONAL_BLANK_IS_NONE, mode="before")
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
