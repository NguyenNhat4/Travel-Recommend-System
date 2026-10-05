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
    itinerary_data_mode: Literal["fixture", "inprocess", "http", "disabled"] | None = None
    itinerary_tool_timeout_seconds: float = Field(default=10.0, gt=0)
    itinerary_llm_timeout_seconds: float = Field(default=10.0, gt=0)
    itinerary_request_timeout_seconds: float = Field(default=10.0, gt=0)
    itinerary_conversation_ttl_seconds: int = Field(default=86_400, ge=60)
    # Redis DB index riêng cho working memory của agent; production không được dùng process memory.
    itinerary_redis_url: str = ""

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
    # Chỉ job index (jobs/embed_products.py, P5 docs/plan/2026-09-29-index-cohere-song-song.md): số lô 96 text gọi
    # Cohere cùng lúc (1 = tuần tự) và trần lượt gọi mỗi phút của job (0 = không giới hạn). Mặc định cho key Trial
    # (100 lượt/phút), chừa chỗ cho Search dùng chung key; key Production thì nâng, vd. 8 và 1500. Search lúc chạy API
    # không bị giới hạn này.
    cohere_embed_concurrency: int = Field(default=4, ge=1, le=16)
    cohere_calls_per_minute: int = Field(default=90, ge=0)
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: str = ""
    weaviate_collection: str = "Product"
    # Chỉ dùng khi job index tạo collection mới; Weaviate Cloud của nhóm chỉ cho phép hfresh.
    weaviate_vector_index_type: Literal["hnsw", "hfresh"] = "hnsw"
    weaviate_timeout_seconds: float = Field(default=30.0, gt=0)
    # Cổng gRPC cho truy vấn top-K mỗi request; Weaviate Cloud tự dùng 443 của host grpc-<cluster>.
    weaviate_grpc_port: int = Field(default=50051, ge=1, le=65535)
    search_cutoff: float = 0.52  # quy tắc tạm của Search contract; phải benchmark lại với Cohere
    search_max_limit: int = 50
    search_candidate_k: int = Field(default=200, ge=1)
    recommend_candidate_k: int = 200
    # Hybrid /search (HYBRID_CANDIDATE_SCORE, spec §2.4): BM25 trên nameAscii/searchTextAscii + RRF ở app.
    search_hybrid: bool = True  # False → dense-only ANN_CANDIDATE_SCORE như trước 25/09
    search_normalize: bool = True  # bước chuẩn hoá truy vấn (viết tắt, chính tả tên riêng, điểm đến, kiểu đi); False → nguyên câu
    search_rrf_k: int = Field(default=60, ge=1)
    search_lexical_candidate_k: int = Field(default=50, ge=1)  # top-K BM25 lấy từ Weaviate mỗi request
    search_lexical_k: int = Field(default=10, ge=0)  # chỉ vớt hit BM25 có rank ≤ giá trị này
    search_lexical_cutoff: float = 0.50  # cosine tối thiểu của hit được vớt; luôn ≤ search_cutoff
    search_lexical_min_coverage: float = Field(default=0.6, ge=0, le=1)  # tên phải chứa ≥ 60% token của truy vấn
    # Cache vector truy vấn /search (NFR-PERF-03; contract 1.12.0 `diagnostics.embedCache`): LRU trong tiến trình, khoá =
    # câu sau chuẩn hoá + gộp khoảng trắng; sống qua các lần nạp lại catalog vì bọc quanh client Cohere dùng chung.
    search_embed_cache: bool = True
    search_embed_cache_size: int = Field(default=10000, ge=1)  # 10k vector float32 1024 chiều ≈ 41 MB
    search_embed_cache_log_every: int = Field(default=500, ge=1)  # log hits/misses mỗi N lượt tra
    # Nạp sẵn cache lúc khởi động (sau lần nạp catalog đầu tiên, không chặn startup): file câu gold + head query của
    # app.search_logs; pacing theo số câu / phút để không đụng trần Cohere (Trial 100 lượt/phút, mỗi lượt ≤ 96 câu).
    search_prewarm: bool = True
    search_prewarm_file: str = "data/search_prewarm_queries.txt"  # tương đối theo src/backend
    search_prewarm_head_queries: int = Field(default=200, ge=0)
    search_prewarm_head_days: int = Field(default=30, ge=1)
    search_prewarm_inputs_per_minute: int = Field(default=2000, ge=0)  # 0 = không ngủ giữa các lô
    search_bm25_k1: float = 1.2  # chỉ job index dùng (invertedIndexConfig của collection)
    search_bm25_b: float = 0.75
    # Chu kỳ nạp lại metadata catalog (giá, trạng thái, cửa sổ ngày) từ Postgres. Job cào chạy mỗi ngày
    # một lần nên 15 phút là đủ; mỗi lần nạp đọc lại toàn bảng và dựng lại text của mọi search unit.
    catalog_refresh_seconds: float = Field(default=900.0, gt=0)

    # --- Thanh toán Stripe (test mode, docs/prd/deployment-plan.md §2) --------------------------------
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    payment_provider: Literal["stripe", "fake"] = "stripe"  # fake: offline, không gọi mạng; cấm ở production
    booking_hold_minutes: int = Field(default=30, ge=30)  # Stripe chỉ cho phiên Checkout hết hạn sau ít nhất 30 phút
    payment_max_failed_attempts: int = Field(default=3, ge=1)
    public_web_url: str = "http://localhost:3000"
    # Chế độ nhiều bản sao sau load balancer (docs/plan/2026-10-05-ha-load-balancing.md §3b). Mặc định tắt để dev và
    # staging một VM chạy như cũ; compose HA bật cả hai.
    # - ready_requires_recsys: /health/ready trả 503 khi RecSys chưa nạp được (Weaviate rỗng/không tới được),
    #   để LB không đưa traffic vào bản sao chỉ trả kết quả rỗng.
    # - require_shared_backends: từ chối khởi động nếu Weaviate/Redis/Postgres trỏ loopback (mỗi VM một bản riêng thì
    #   phiên đăng nhập và kết quả tìm kiếm lệch nhau giữa các bản sao).
    ready_requires_recsys: bool = False
    require_shared_backends: bool = False
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


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def shared_backend_violations(settings: Settings) -> list[str]:
    """Biến kết nối dịch vụ dùng chung đang trỏ loopback (chỉ bản sao này thấy). Rỗng nếu hợp lệ hoặc không bật chế độ."""
    if not settings.require_shared_backends:
        return []
    from urllib.parse import urlparse

    bad = []
    # DATABASE_URL loopback = tunnel SSH cấu hình tay (127.0.0.1:15432) mà VM sinh từ instance template không có.
    for name, value in (("WEAVIATE_URL", settings.weaviate_url), ("AUTH_REDIS_URL", settings.auth_redis_url),
                        ("ITINERARY_REDIS_URL", settings.itinerary_redis_url),
                        ("DATABASE_URL", settings.database_url), ("CDP_DATABASE_URL", settings.cdp_database_url)):
        host = (urlparse(value).hostname or "").lower() if value else ""
        if not value or host in _LOOPBACK_HOSTS:
            bad.append(name)
    return bad


@lru_cache
def get_settings() -> Settings:
    return Settings()
