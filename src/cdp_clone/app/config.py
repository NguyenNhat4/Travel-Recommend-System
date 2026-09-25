from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CDP_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "production", "test"] = "development"
    database_url: str = "postgresql+psycopg://cdp:cdp@localhost:5433/cdp"
    # Shared with Backend, seed scripts and jobs only; never shipped to the browser.
    service_token: SecretStr = Field(min_length=32)


@lru_cache
def get_settings() -> Settings:
    return Settings()
