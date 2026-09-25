# V-OTA backend — FastAPI: search · similar · recommendations · itinerary agent

Chạy từ **repo root**: code import theo dạng `src.backend.app…`.

Setup và lệnh chạy: [README gốc](../../README.md). Phần dưới chỉ mô tả chi tiết riêng của backend.

## Kết nối trong Docker Compose

Backend trong container (`make backend`) kết nối PostgreSQL qua hostname `postgres` và hai role giới hạn riêng:

```text
DATABASE_URL=postgresql://vota_app_login:vota@postgres:5432/vota
CDP_DATABASE_URL=postgresql://cdp_client_login:cdp@postgres:5432/vota
```

Không dùng URL từ máy host (`localhost`) bên trong container. Nếu cần DSN khác, cấu hình `BACKEND_DATABASE_URL` và `BACKEND_CDP_DATABASE_URL` trong shell hoặc `.env` ở repository root. Weaviate cũng vậy: container dùng service `weaviate` của compose (`http://weaviate:8080`, không khoá), không lấy `WEAVIATE_URL`/`WEAVIATE_API_KEY` của máy host; môi trường dùng cluster chung thì đặt `BACKEND_WEAVIATE_URL` và `BACKEND_WEAVIATE_API_KEY`. Backend không seed, reset hay tự gọi Cohere hàng loạt khi container khởi động.

## Search / Recommendation

RecSys cố định Cohere `embed-multilingual-v3.0` (1024 chiều). Job index dùng `search_document`; request tìm kiếm dùng `search_query`. `WEAVIATE_URL`, `WEAVIATE_COLLECTION`, `COHERE_API_KEY` và `SEARCH_CUTOFF` (`0.62`, còn phải benchmark lại) được đọc qua `core/config.py`. Weaviate chỉ giữ vector + `productId`/`modelVersion`/`textHash`; tên, giá, ảnh và availability luôn hydrate từ PostgreSQL. Metadata nạp lúc khởi động rồi nạp lại mỗi `CATALOG_REFRESH_SECONDS` (mặc định 900 giây); lần nạp lại lỗi thì giữ bản đang phục vụ. Search unit chưa có vector (job index chưa chạy xong) vẫn có giá mới nhưng chưa tìm được qua vector. Chưa nạp được lần nào — thiếu PostgreSQL, Weaviate, khóa Cohere, hoặc dưới một nửa search unit có vector đúng model — thì RecSys tắt và thử lại sau 30 giây, các route còn lại vẫn chạy.

Endpoint hiện có (prefix `/api/v1`): `GET|POST /search` (`q`/`query`, `taxonomy`, `destination`, `limit`, `offset`;
Agent tool `query` được adapter đổi thành `q`) · `GET /similar/{productId}?k=` · `GET /recommendations?k=&destination=`
(JWT tùy chọn, `cdp_user_id` lấy từ token; token hỏng → 401, không hạ thành khách) · `GET /destinations` ·
`POST /assistant/itineraries` · `POST /assistant/itineraries/stream` · `GET /assistant/status` ·
auth v1 `POST /auth/register|login`, `GET /auth/me` · chỉ BFF (`X-Service-Token`)
`POST /auth/session`, `/auth/session/token`, `/auth/session/revoke` · `PUT /auth/password` ·
`GET /internal/recommendations?cdp_user_id=` (`X-Service-Token`, tắt ở production). Ngoài prefix: `GET /health`,
`GET /.well-known/jwks.json`.

## Auth

Chi tiết: `docs/spec/hop-dong-tich-hop-auth.md`. JWT ký RS256; sinh khoá dev một lần bằng `make jwt-keys` (ghi vào
`secrets/`, đã gitignore). Thiếu khoá thì development tự sinh khoá tạm — token mất hiệu lực mỗi lần restart.
Đặt `AUTH_SERVICE_TOKEN` (≥ 32 ký tự, `openssl rand -hex 32`) giống hệt ở backend và BFF, nếu không web không
đăng nhập được. `AUTH_REDIS_URL` trống thì rate limit chạy trong bộ nhớ (chỉ dev). Tài khoản seed (đăng nhập qua `/login` như user
thường): 4 persona + 50 `test01..50@vota.demo`, mật khẩu `Demo@2026`. Test Postgres/Redis thật: `RUN_POSTGRES_INTEGRATION=1
RUN_REDIS_INTEGRATION=1 python -m pytest -q src/backend/tests/integration`.

## Chỗ nào làm gì (docs/prd/architecture.md §2)

| Lớp | Thư mục | Nội dung |
|---|---|---|
| domain | `domain/<domain>/` | Business rule thuần: vai trò sản phẩm + text builder (`catalog`), FILTER → SCORE → CUTOFF (`search`), hồ sơ người dùng + MMR + phổ biến (`recommendation`), chuẩn hoá intent + ghép lịch trình (`itinerary`), mật khẩu + phiên (`auth`) |
| application | `application/ports/` | Mỗi port một file: `cdp_client.py` (`CdpClient` ghi, `CdpHistoryReader` đọc), `embedder.py`, `vector_store.py`, `unit_index.py`, `llm.py`, `itinerary_planner.py`, `itinerary_tools.py`, `auth.py` |
| application | `application/<domain>/` | Use case: `SearchProducts`, `SimilarProducts`, `RecommendForUser`, `BuildPopularity`, `PlanItinerary`, auth, booking, tracking |
| agents | `agents/` | LangGraph 10 node; `runtime_dependencies.py` hiện thực port `ItineraryPlanner`; `tools/itinerary_gateway.py` gọi Search/Recommendation qua port |
| infrastructure | `cdp/` | `LocalCdpClient` (ghi), `PostgresCdpReader` (đọc), `CdpHttpClient`, `BackgroundCdpEventRecorder` — mọi SQL vào schema `cdp` nằm ở đây |
| infrastructure | `persistence/` | `PostgresProductLookup`, conversation store, LangGraph checkpointer |
| infrastructure | `clients/` | HTTP client itinerary; fixture 50 sản phẩm cho `ITINERARY_DATA_MODE=fixture` |
| infrastructure | `llm/`, `embeddings/`, `vectors/`, `auth/` | Provider LLM (`LazyChatModel`), `CohereEmbedder`, `WeaviateVectorStore`, hash mật khẩu + JWT |
| api | `api/` | `deps.py` (Depends lấy use case), `middleware.py` (X-Request-ID, CORS), `errors.py` (Error Envelope), `v1/router.py`, `v1/schemas/` (DTO), `v1/routes/` |
| core | `core/` | `config.py` (một `Settings` duy nhất), `request_context.py` (ContextVar, không import FastAPI) |
| — | `main.py` | Composition root: nơi duy nhất nối infrastructure và agent vào use case |

Quy tắc phụ thuộc được kiểm tự động bằng `tests/architecture/test_import_rules.py`. Test đỏ nghĩa là code
vi phạm `docs/prd/architecture.md` §2; muốn đổi quy tắc thì phải có đề xuất đã chốt (AGENTS.md §8).

Test: `tests/unit/{domain,application,agents,infrastructure,api}`, `tests/contract`, `tests/integration`,
`tests/architecture`; bản giả dùng chung ở `tests/fakes/` (CDP đọc JSONL, in-memory vector store).

## PostgreSQL local

PostgreSQL chạy trong Docker và Backend kết nối qua hai DSN với hai role tách biệt. `make backend` chạy Backend trong
cùng Docker Compose project nên dùng hostname `postgres`; các URL host-local bên dưới (cũng có trong `.env.example`)
chỉ dành cho `make backend-local`:

```env
DATABASE_URL=postgresql://vota_app_login:vota@localhost:5432/vota
CDP_DATABASE_URL=postgresql://cdp_client_login:cdp@localhost:5432/vota
CDP_ADAPTER=local
```

- Với container, Compose đặt riêng `BACKEND_DATABASE_URL` và `BACKEND_CDP_DATABASE_URL`; giá trị mặc định dùng `postgres:5432` và vẫn giữ hai role giới hạn.
- `DATABASE_URL`: adapter catalog/app; role này chỉ được đọc `cdp.products`, không được đọc profile/event.
- `CDP_DATABASE_URL`: `LocalCdpClient` và `PostgresCdpReader`; role này chỉ được vào schema `cdp`.
- `CDP_ADAPTER=http`: đường chuyển sang `CdpHttpClient` sau này; lúc đó mới dùng `CDP_BASE_URL` và `CDP_SERVICE_TOKEN`.

Các URL này chỉ là địa chỉ PostgreSQL trên máy local; chúng không tạo database hay dữ liệu mới. Loader/seed dùng
`SEED_DATABASE_URL` riêng và Backend không được dùng quyền đó.

Chạy test đọc seed thật (không ghi DB):

```bash
RUN_POSTGRES_INTEGRATION=1 python -m pytest -q src/backend/tests
```

## LLM của itinerary agent

`main.py` dựng **một** client LLM trong `lifespan` (`infrastructure/llm/build_chat_model`) và tiêm vào graph
qua `app.state.itinerary_llm`. Node không tự dựng client: không được tiêm thì trả `LLM_UNAVAILABLE`
(CLI đánh giá tự gọi `build_chat_model`).

```env
ITINERARY_USE_LLM=true          # false: không dựng client nào, không cần API key
OPENAI_API_KEY=                 # thứ tự chọn provider: GEMINI -> OPENAI -> ANTHROPIC
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
ITINERARY_LLM_MODEL=            # bỏ trống: OpenAI dùng MODEL_NAME, provider khác dùng mặc định
ITINERARY_LLM_TEMPERATURE=0     # riêng của agent, không dùng chung LLM_TEMPERATURE
```

`GET /api/v1/assistant/status` trả thêm `llmMode`:

- `live` — đã dựng được client dùng chung.
- `disabled` — `ITINERARY_USE_LLM=false`.
- `unavailable` — đã bật nhưng thiếu API key hoặc thiếu SDK của provider.

Với `disabled` và `unavailable`, app vẫn khởi động và các route khác vẫn phục vụ; riêng request itinerary
trả 503 `LLM_UNAVAILABLE` có kiểm soát.

Để Agent dùng Search/Recommendation của chính Backend thay cho fixture:

```env
ITINERARY_DATA_MODE=http
ITINERARY_SERVICE_BASE_URL=http://127.0.0.1:8000
JWT_SECRET=<secret HS256 giống service Auth>
JWT_ALGORITHM=HS256
```

Tool `search_products` gọi GET `/api/v1/search` nhưng luôn bỏ Authorization. Tool
`get_recommendations` forward Bearer token; Backend chỉ lấy `cdp_user_id` từ JWT đã xác minh. Hai
response RecSys chứa đủ trường catalog để Agent hậu kiểm và không cần gọi Product Detail. Fixture vẫn
là mặc định của development/test để máy chưa seed PostgreSQL vẫn chạy được.

CLI chạy kịch bản đánh giá agent đã chuyển sang `src/evaluation/agent/cli.py`
(`python -m src.evaluation.agent.cli --help`).
