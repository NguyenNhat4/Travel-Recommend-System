# V-OTA backend — FastAPI: search · similar · recommendations · itinerary agent

Chạy từ **repo root**: code import theo dạng `src.backend.app…`.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r src/backend/requirements.txt
docker compose up -d --wait postgres                   # hoặc make demo-db (có seed)
uvicorn src.backend.app.main:app --reload               # hoặc make backend
python -m pytest -q src/backend/tests                   # không cần Postgres; integration tự skip
```

Biến RecSys (đọc qua `core/config.py`): `EMBED_MODEL` (mặc định `intfloat/multilingual-e5-base`), `EMBED_CACHE_DIR`
(`.embcache`), `SEARCH_CUTOFF` (`0.80`, calibrate theo model). Lần chạy đầu tải model và embed toàn bộ search unit,
cache ở `.embcache/`; đổi template hoặc model thì hash đổi và phải embed lại. Thiếu database hoặc model thì RecSys tự
tắt, các route còn lại vẫn chạy.

Endpoint hiện có (prefix `/api/v1`): `GET /search?q=&taxonomy=&destination=&limit=&offset=` ·
`GET /similar/{productId}?k=` · `GET /recommendations?k=&cdp_user_id=` (tạm, sẽ lấy từ JWT) · `GET /popular?k=` ·
`POST /assistant/itineraries` · `POST /assistant/itineraries/stream` · `GET /assistant/status`. Ngoài prefix: `GET /health`.

## Chỗ nào làm gì (docs/prd/architecture.md §2)

| Lớp | Thư mục | Nội dung |
|---|---|---|
| domain | `domain/<domain>/` | Business rule thuần: vai trò sản phẩm + text builder (`catalog`), FILTER → SCORE → CUTOFF (`search`), hồ sơ người dùng + MMR + phổ biến (`recommendation`), chuẩn hoá intent + ghép lịch trình (`itinerary`), mật khẩu + phiên (`auth`) |
| application | `application/ports/` | Mỗi port một file: `cdp_client.py` (`CdpClient` ghi, `CdpHistoryReader` đọc), `embedder.py`, `vector_store.py`, `unit_index.py`, `llm.py`, `itinerary_planner.py`, `itinerary_tools.py`, `auth.py` |
| application | `application/<domain>/` | Use case: `SearchProducts`, `SimilarProducts`, `RecommendForUser`, `BuildPopularity`, `PlanItinerary`, auth, booking, tracking |
| agents | `agents/` | LangGraph 9 node; `runtime_dependencies.py` hiện thực port `ItineraryPlanner`; `tools/itinerary_gateway.py` gọi Search/Recommendation qua port |
| infrastructure | `cdp/` | `LocalCdpClient` (ghi), `PostgresCdpReader` (đọc), `CdpHttpClient`, `BackgroundCdpEventRecorder` — mọi SQL vào schema `cdp` nằm ở đây |
| infrastructure | `persistence/` | `PostgresProductLookup`, conversation store, LangGraph checkpointer |
| infrastructure | `clients/` | HTTP client itinerary; fixture 50 sản phẩm cho `ITINERARY_DATA_MODE=fixture` |
| infrastructure | `llm/`, `embeddings/`, `vectors/`, `auth/` | Provider LLM (`LazyChatModel`), embedder, vector store Postgres (sau là Weaviate), hash mật khẩu + JWT |
| api | `api/` | `deps.py` (Depends lấy use case), `middleware.py` (X-Request-ID, CORS), `errors.py` (Error Envelope), `v1/router.py`, `v1/schemas/` (DTO), `v1/routes/` |
| core | `core/` | `config.py` (một `Settings` duy nhất), `request_context.py` (ContextVar, không import FastAPI) |
| — | `main.py` | Composition root: nơi duy nhất nối infrastructure và agent vào use case |

Quy tắc phụ thuộc được kiểm tự động bằng `tests/architecture/test_import_rules.py`. Test đỏ nghĩa là code
vi phạm `docs/prd/architecture.md` §2; muốn đổi quy tắc thì phải có đề xuất đã chốt (AGENTS.md §8).

Test: `tests/unit/{domain,application,agents,infrastructure,api}`, `tests/contract`, `tests/integration`,
`tests/architecture`; bản giả dùng chung ở `tests/fakes/` (CDP đọc JSONL, in-memory vector store).

## PostgreSQL local

PostgreSQL chạy trong Docker nhưng Backend vẫn kết nối qua hai DSN với hai role tách biệt. Giá trị dev mặc định
(cũng có trong `.env.example`):

```env
DATABASE_URL=postgresql://vota_app_login:vota@localhost:5432/vota
CDP_DATABASE_URL=postgresql://cdp_client_login:cdp@localhost:5432/vota
CDP_ADAPTER=local
```

- `DATABASE_URL`: adapter catalog/app; role này chỉ được đọc `cdp.products`, không được đọc profile/event.
- `CDP_DATABASE_URL`: `LocalCdpClient` và `PostgresCdpReader`; role này chỉ được vào schema `cdp`.
- `CDP_ADAPTER=http`: đường chuyển sang `CdpHttpClient` sau này; lúc đó mới dùng `CDP_BASE_URL` và `CDP_SERVICE_TOKEN`.

Các URL này chỉ là địa chỉ PostgreSQL trên máy local; chúng không tạo database hay dữ liệu mới. Loader/seed dùng
`SEED_DATABASE_URL` riêng và Backend không được dùng quyền đó.

Chạy test đọc seed thật (không ghi DB):

```bash
RUN_POSTGRES_INTEGRATION=1 python -m pytest -q src/backend/tests
```

CLI chạy kịch bản đánh giá agent đã chuyển sang `src/evaluation/agent/cli.py`
(`python -m src.evaluation.agent.cli --help`).
