from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Đường dẫn tuyệt đối tới .env ở gốc repo: uvicorn và CLI chạy từ nhiều thư mục khác nhau, nên
# env_file tương đối theo CWD sẽ im lặng bỏ qua cấu hình. Biến môi trường thật vẫn thắng file.
REPO_ROOT = Path(__file__).resolve().parents[4]

# Biến để trống trong .env đến đây là chuỗi rỗng, không phải None. Với các trường optional có
# `pattern` hoặc `Literal`, chuỗi rỗng làm Settings() ném ValidationError và backend không khởi
# động nổi — mà .env.example vốn để trống đúng những biến này, nên ai làm theo hướng dẫn
# "copy .env.example sang .env" đều vấp. Coi rỗng là "không đặt".
# Chỉ các trường thực sự Optional: trường `str` thường (cdp_service_token, openai_api_key) coi ""
# là "chưa cấu hình" và vẫn hợp lệ, không được đổi thành None.
_OPTIONAL_BLANK_IS_NONE = ("itinerary_service_base_url", "itinerary_data_mode")


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
    itinerary_data_mode: Literal["fixture", "http", "disabled"] | None = None
    itinerary_tool_timeout_seconds: float = Field(default=10.0, gt=0)
    itinerary_llm_timeout_seconds: float = Field(default=10.0, gt=0)
    itinerary_request_timeout_seconds: float = Field(default=10.0, gt=0)
    itinerary_conversation_ttl_seconds: int = Field(default=86_400, ge=60)

    # --- Auth (docs/spec/hop-dong-tich-hop-auth.md §19) ---------------------------------------
    # RS256; HS256 bị loại (§10.2). Đường dẫn tương đối tính từ gốc repo. Thiếu file: dev/test sinh
    # khoá tạm, production không khởi động.
    jwt_private_key_path: str = "./secrets/jwt-private.pem"
    jwt_public_key_path: str = "./secrets/jwt-public.pem"
    jwt_issuer: str = "https://api.vota.local"
    jwt_audience: str = "vota-api"
    jwt_access_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    jwt_clock_skew_seconds: int = Field(default=60, ge=0, le=60)
    refresh_ttl_seconds: int = Field(default=43_200, ge=600)
    argon2_memory_kib: int = Field(default=19_456, ge=19_456)
    argon2_time_cost: int = Field(default=2, ge=2)
    argon2_parallelism: int = Field(default=1, ge=1)
    # Trống: dev/test dùng rate limiter trong bộ nhớ; production bắt buộc có Redis.
    auth_redis_url: str = ""
    # Chỉ tin X-Forwarded-For khi peer thuộc các dải này (§9.4). Phân cách bằng dấu phẩy.
    trusted_proxies: str = "127.0.0.1/32"
    captcha_provider: Literal["noop"] = "noop"  # nhà cung cấp thật là P1, ngoài phạm vi
    # >= 32 ký tự; BFF và FastAPI trùng giá trị. Trống = nhóm /auth/session* và /internal/* luôn 401.
    auth_service_token: str = ""
    internal_api_enabled: bool = False

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

    # RecSys (search / similar / recommendations). Model và chiều đã chốt trong PRD 22/09/2026.
    embed_model: Literal["embed-multilingual-v3.0"] = "embed-multilingual-v3.0"
    embed_dimension: Literal[1024] = 1024
    cohere_api_key: str = ""
    cohere_base_url: str = "https://api.cohere.com"
    cohere_timeout_seconds: float = Field(default=30.0, gt=0)
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: str = ""
    weaviate_collection: str = "Product"
    weaviate_timeout_seconds: float = Field(default=30.0, gt=0)
    # Cổng gRPC cho truy vấn top-K mỗi request; Weaviate Cloud tự dùng 443 của host grpc-<cluster>.
    weaviate_grpc_port: int = Field(default=50051, ge=1, le=65535)
    search_cutoff: float = 0.62  # quy tắc tạm của Search contract; phải benchmark lại với Cohere
    search_max_limit: int = 50
    search_candidate_k: int = Field(default=200, ge=1)
    recommend_candidate_k: int = 200

    # Vector ở Weaviate, embedding bằng Cohere (docs/prd/architecture.md §5, deployment-plan.md §2).
    # Runtime và job index-vectors dùng các biến này; Weaviate không bao giờ nhận COHERE_API_KEY.
    cohere_api_key: str = ""
    embedding_model_name: str = "embed-multilingual-v3.0"
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: str = ""

    # --- Thanh toán Stripe (test mode, docs/prd/deployment-plan.md §2) --------------------------------
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    payment_provider: Literal["stripe", "fake"] = "stripe"  # fake: offline, không gọi mạng; cấm ở production
    booking_hold_minutes: int = Field(default=30, ge=30)  # Stripe chỉ cho phiên Checkout hết hạn sau ít nhất 30 phút
    payment_max_failed_attempts: int = Field(default=3, ge=1)
    public_web_url: str = "http://localhost:3000"
    # 0 = tắt job đối soát (test); mặc định 5 phút/lần.
    booking_reconcile_interval_seconds: int = Field(default=300, ge=0)

    @field_validator("stripe_secret_key")
    @classmethod
    def _test_keys_only(cls, value: str) -> str:
        # Dự án chỉ dùng Stripe test mode (PRD project-brief §4.2): khoá live không bao giờ được nạp.
        if value.startswith(("sk_live_", "rk_live_")):
            raise ValueError("STRIPE_SECRET_KEY phải là khoá test (sk_test_…); dự án không dùng Stripe live mode")
        return value

    @field_validator(*_OPTIONAL_BLANK_IS_NONE, mode="before")
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
