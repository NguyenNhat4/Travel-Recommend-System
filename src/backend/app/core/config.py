from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
_OPTIONAL_BLANK_IS_NONE = ("itinerary_service_base_url", "itinerary_data_mode", "itinerary_llm_reasoning_effort")


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
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    # false = không dựng client LLM nào; app vẫn khởi động được không cần API key và request
    # itinerary trả 503 LLM_UNAVAILABLE có kiểm soát (hop-dong-tich-hop-itinerary-assistant.md §5.9).
    itinerary_use_llm: bool = True
    # Model duy nhất của agent; bỏ trống thì mỗi provider dùng mặc định của mình (infrastructure/llm).
    itinerary_llm_model: str | None = None
    # Riêng của agent, không dùng chung llm_temperature (0.7): mọi lời gọi của agent là
    # structured output hoặc tool calling, cần quyết định ổn định.
    itinerary_llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    # Chỉ áp cho OpenAI. Model reasoning (vd gpt-6-luna) từ chối function tools trên chat completions khi
    # reasoning bật mặc định (400); đặt "none" để tool calling chạy được. Bỏ trống thì không gửi tham số.
    itinerary_llm_reasoning_effort: Literal["none", "minimal", "low", "medium", "high"] | None = None
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
    # Kết nối TRỰC TIẾP tới Postgres (không qua pgbouncer) cho khoá advisory của job đối soát. Trống = dùng database_url.
    leader_lock_database_url: str = ""
    cdp_database_url: str = "postgresql://cdp_client_login:cdp@localhost:5432/vota"
    cdp_adapter: Literal["local", "http"] = "local"

    # Future/production HTTP adapter. Ignored while CDP_ADAPTER=local.
    cdp_base_url: str = "http://localhost:8100"
    cdp_service_token: str = ""
    cdp_timeout_seconds: float = Field(default=2.0, gt=0)
    # Browse events waiting to be sent; beyond this they are dropped and logged.
    cdp_event_queue_size: int = Field(default=1000, ge=1)

    # RecSys (search / similar / recommendations). PRD FR-SRC-02 (chốt 06/10/2026): chỉ e5-small chạy local trong tiến trình,
    # 384 chiều, không dùng dịch vụ embedding ngoài. Đổi revision = chạy lại job embed.
    embed_model: Literal["intfloat/multilingual-e5-small"] = "intfloat/multilingual-e5-small"
    # Revision Hugging Face ghim (cùng bản bench đã đo); query và document phải cùng revision.
    embed_model_revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    embed_dimension: int = 384  # đọc từ env là chuỗi nên để int; `_embedding_dimension` chỉ nhận 384
    embed_device: str = "cpu"
    embed_batch_size: int = Field(default=32, ge=1, le=256)  # số text mỗi lần chạy model (job index, prewarm)
    embed_max_tokens: int = Field(default=512, ge=8, le=512)  # e5: tối đa 512 token kể cả tiền tố; dài hơn thì cắt đuôi
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: str = ""
    # Collection vector e5-small 384 chiều (env VECTOR_COLLECTION). Tên biến mới thay WEAVIATE_COLLECTION: env cũ trên VM
    # (`WEAVIATE_COLLECTION=Product`, vector Cohere) bị bỏ qua, nên collection e5 dựng sẵn trước khi deploy được (chốt 06/10).
    vector_collection: str = "ProductE5Small"
    # Chỉ dùng khi job index tạo collection mới; Weaviate Cloud của nhóm chỉ cho phép hfresh.
    weaviate_vector_index_type: Literal["hnsw", "hfresh"] = "hnsw"
    weaviate_timeout_seconds: float = Field(default=30.0, gt=0)
    # Cổng gRPC cho truy vấn top-K mỗi request; Weaviate Cloud tự dùng 443 của host grpc-<cluster>.
    weaviate_grpc_port: int = Field(default=50051, ge=1, le=65535)
    # Cosine e5 dồn ở 0,85–0,92; 0,84 hiệu chỉnh trên gold_v4 (PRD deployment-plan §2).
    search_cutoff: float = 0.84
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
    # FR-SRC-03 (05/10): lọc cứng theo địa danh suy ra từ câu (domain/search/destination.py; contract 1.14.0
    # `diagnostics.destinationFilter`, `appliedFilters`). Mặc định tắt cho tới khi bench xác nhận trên slice dest_type và các slice
    # guard. `SEARCH_DEST_FILTER_FALLBACK`: F rỗng sau khi lọc → chạy lại không lọc (FR-SRC-04).
    search_dest_filter: bool = False
    search_dest_filter_fallback: bool = True
    # Câu gõ không dấu (slice no_diacritics; contract 1.14.0 `diagnostics.queryProfile`): `relax` nới cổng vớt BM25 và (tuỳ chọn)
    # cutoff dense cho riêng câu phát hiện không dấu (≥ min_tokens token); `off` = như cũ. Giá trị nới là tạm, chưa qua dev/test.
    search_no_diacritics_mode: Literal["off", "relax"] = "off"
    search_no_diacritics_lexical_k: int = Field(default=20, ge=0)
    search_no_diacritics_lexical_cutoff: float = 0.0
    search_no_diacritics_min_coverage: float = Field(default=0.4, ge=0, le=1)
    search_no_diacritics_cutoff: float | None = None   # None = dùng SEARCH_CUTOFF
    search_no_diacritics_min_tokens: int = Field(default=3, ge=1)
    # Query plan — kiến trúc Phase A (docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md; FR-SRC-01/03; contract 1.15.0
    # `diagnostics.queryPlan`): hard constraint suy từ câu, mỗi họ một cờ, mặc định tắt cho tới khi gold v4 xác nhận. Tắt vẫn
    # parse và khai ở `queryPlan` (bench đo độ chính xác parse). Tham số request tường minh (origin, priceMin/priceMax,
    # starRatingMin, availableOnly) luôn được áp theo contract, không phụ thuộc cờ.
    search_negation_filter: bool = False   # F3: "không có / không ghi nhận X" → loại unit CÓ GHI NHẬN tiện ích X ([C2])
    search_taxonomy_filter: bool = False   # F4: câu nêu đúng một loại sản phẩm → lọc taxonomy (≥ 2 loại thì không)
    search_route_filter: bool = False      # F5: câu vé máy bay "từ A đến B" → lọc originCity / destinationCity của tuyến
    search_numeric_filter: bool = False    # F6: giá ("dưới 2 triệu") hard, sao ("4 sao") soft — suy từ câu
    # 06/10 (kiến trúc search §3, §4, §6, §7 5C, §8, §11; contract 1.16.0): mặc định tắt / trung tính — mọi giá trị mặc định cho
    # đúng kết quả 1.15.0. travelContext.guests của POST /search luôn áp (tham số request), không phụ thuộc cờ.
    search_tone_normalize: bool = False        # dời dấu thanh của câu về kiểu đa số của catalog (hoà ↔ hòa) trước embed/BM25
    search_taxonomy_strong_only: bool = False  # F4 chỉ lọc taxonomy khi cue loại MẠNH ("khách sạn"); cue yếu ("phòng") chỉ khai
    search_party_filter: bool = False          # số khách suy từ câu ("3 người") → loại unit có sức chứa ĐÃ BIẾT nhỏ hơn
    # Kênh fuzzy tên gần đúng (trigram cửa sổ, domain/search/fuzzy.py): 0 = tắt. Bật thì unit có rank fuzzy ≤ K, độ giống
    # ≥ MIN_SIM (0.6 vớt cả tên chung chung — đo 06/10) và cosine ≥ SEARCH_LEXICAL_CUTOFF được vớt vào R. Chỉ ở hybrid.
    search_fuzzy_k: int = Field(default=0, ge=0)
    search_fuzzy_candidate_k: int = Field(default=50, ge=1)   # số ứng viên kênh fuzzy đem fuse
    search_fuzzy_min_sim: float = Field(default=0.75, ge=0, le=1)
    # Trọng số RRF theo nhánh (kiến trúc §8 weighted fusion); 1.0 = RRF thường. Chỉ tune trên split dev của gold.
    search_rrf_dense_weight: float = Field(default=1.0, ge=0)
    search_rrf_lexical_weight: float = Field(default=1.0, ge=0)
    search_rrf_fuzzy_weight: float = Field(default=1.0, ge=0)
    # Ghi một dòng app.search_logs mỗi lượt /search trang đầu (câu gốc, appliedFilters.hard + confidence, productId trang trả
    # về, total, modelVersion, latencyMs, cdp_user_id khi có Bearer hợp lệ). Ghi nền qua hàng đợi có trần; lỗi không tới response.
    search_log_queries: bool = False
    # Cache vector truy vấn /search (NFR-PERF-03; contract 1.12.0 `diagnostics.embedCache`): LRU trong tiến trình, khoá =
    # câu sau chuẩn hoá + gộp khoảng trắng; sống qua các lần nạp lại catalog vì bọc quanh embedder dùng chung.
    search_embed_cache: bool = True
    search_embed_cache_size: int = Field(default=10000, ge=1)  # 10k vector float32 384 chiều ≈ 15 MB
    search_embed_cache_log_every: int = Field(default=500, ge=1)  # log hits/misses mỗi N lượt tra
    # Nạp sẵn cache lúc khởi động (sau lần nạp catalog đầu tiên, không chặn startup): file câu gold + head query của
    # app.search_logs; pacing theo số câu / phút để prewarm không chiếm hết CPU của backend.
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
    # - ready_requires_db: /health/ready thăm dò `SELECT 1` (timeout, cache vài giây) để bản sao mất đường tới DB bị loại.
    #   Chỉ readiness; liveness/autohealing KHÔNG phụ thuộc DB, kẻo DB gián đoạn làm MIG thay VM vô ích.
    ready_requires_db: bool = False
    ready_db_timeout_seconds: float = Field(default=2.0, gt=0)
    ready_db_cache_seconds: float = Field(default=5.0, ge=0)
    require_shared_backends: bool = False
    # 0 = tắt job đối soát (test); mặc định 5 phút/lần.
    booking_reconcile_interval_seconds: int = Field(default=300, ge=0)
    # Đặt trực tiếp qua đơn nháp (docs/spec/booking/dat-truc-tiep-theo-don-nhap.md): hiệu lực của một đơn nháp, và thời gian
    # Redis giữ giỏ, đơn nháp của khách chưa đăng nhập.
    booking_draft_ttl_minutes: int = Field(default=30, ge=1)
    guest_booking_ttl_days: int = Field(default=3, ge=1)
    # Redis DB index riêng cho giỏ và đơn nháp của khách chưa đăng nhập. Trống: dev/test dùng bộ nhớ một tiến trình;
    # production bắt buộc có Redis.
    booking_redis_url: str = ""

    @field_validator("stripe_secret_key")
    @classmethod
    def _test_keys_only(cls, value: str) -> str:
        # Dự án chỉ dùng Stripe test mode (PRD project-brief §4.2): khoá live không bao giờ được nạp.
        if value.startswith(("sk_live_", "rk_live_")):
            raise ValueError("STRIPE_SECRET_KEY phải là khoá test (sk_test_…); dự án không dùng Stripe live mode")
        return value

    @model_validator(mode="after")
    def _embedding_dimension(self):
        if self.embed_dimension != 384:
            raise ValueError(f"EMBED_DIMENSION của {self.embed_model} là 384, đang là {self.embed_dimension}")
        return self

    @field_validator(*_OPTIONAL_BLANK_IS_NONE, mode="before")
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


#: Cổng pgbouncer chạy sidecar trên mỗi VM (compose HA). Loopback ở cổng này là pooler hợp lệ, khác tunnel SSH 15432.
POOLER_SIDECAR_PORT = 6432


def shared_backend_violations(settings: Settings) -> list[str]:
    """Biến kết nối đang trỏ sai chỗ cho chế độ nhiều bản sao. Rỗng nếu hợp lệ hoặc không bật chế độ.

    - Weaviate/Redis/Postgres không được là loopback (mỗi VM một bản riêng thì lệch trạng thái), trừ pgbouncer sidecar
      ở 127.0.0.1:6432 cho DATABASE_URL/CDP_DATABASE_URL.
    - Có pooler thì khoá leader của job đối soát phải đi DSN trực tiếp tới Postgres (LEADER_LOCK_DATABASE_URL), nếu
      không khoá advisory mức session rơi vào connection của người khác và mọi bản sao đều tưởng mình là leader.
    """
    if not settings.require_shared_backends:
        return []
    from urllib.parse import urlparse

    def parsed(value: str):
        return urlparse(value) if value else None

    def loopback(value: str) -> bool:
        u = parsed(value)
        return bool(u) and (u.hostname or "").lower() in _LOOPBACK_HOSTS

    def pooler(value: str) -> bool:
        u = parsed(value)
        return loopback(value) and u.port == POOLER_SIDECAR_PORT

    bad = []
    for name, value in (("WEAVIATE_URL", settings.weaviate_url), ("AUTH_REDIS_URL", settings.auth_redis_url),
                        ("ITINERARY_REDIS_URL", settings.itinerary_redis_url)):
        if not value or loopback(value):
            bad.append(name)
    for name, value in (("DATABASE_URL", settings.database_url), ("CDP_DATABASE_URL", settings.cdp_database_url)):
        if not value or (loopback(value) and not pooler(value)):
            bad.append(name)  # loopback ngoài pooler sidecar = tunnel SSH mà VM của MIG không có
    uses_pooler = pooler(settings.database_url) or pooler(settings.cdp_database_url)
    leader = settings.leader_lock_database_url
    if uses_pooler and (not leader or loopback(leader)):
        bad.append("LEADER_LOCK_DATABASE_URL")
    return bad


@lru_cache
def get_settings() -> Settings:
    return Settings()
