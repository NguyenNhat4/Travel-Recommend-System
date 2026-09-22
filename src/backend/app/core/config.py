from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Đường dẫn tuyệt đối tới .env ở gốc repo: uvicorn và CLI chạy từ nhiều thư mục khác nhau, nên
# env_file tương đối theo CWD sẽ im lặng bỏ qua cấu hình. Biến môi trường thật vẫn thắng file.
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
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
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    # Tắt mặc định: bật tracing là việc chủ ý (composition root tự tay đẩy 4 biến này vào
    # os.environ khi true), không phải tác dụng phụ của việc nạp .env như trước đây.
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_project: str = "default"
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    # false = không dựng client LLM nào; app vẫn khởi động được không cần API key và request
    # itinerary trả 503 LLM_UNAVAILABLE có kiểm soát (hop-dong-tich-hop-itinerary-assistant.md §5.9).
    itinerary_use_llm: bool = True
    itinerary_llm_model: str | None = None
    # Riêng của agent, không dùng chung llm_temperature (0.7): mọi lời gọi của agent là
    # structured output hoặc tool calling, cần quyết định ổn định.
    itinerary_llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
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

    # JWT do Auth backend phát hành. Không có default secret; request ẩn danh vẫn hoạt động,
    # còn request mang Bearer token sẽ fail closed nếu deployment chưa cấu hình.
    jwt_secret: str = ""
    jwt_algorithm: Literal["HS256"] = "HS256"

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
