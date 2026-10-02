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

## Khi PostgreSQL không với tới được

Mọi adapter Postgres mở kết nối qua `infrastructure/persistence/db_connection.py` (`connect_async`), không gọi `psycopg.AsyncConnection.connect` trực tiếp. Hàm này đặt `connect_timeout` (`DB_CONNECT_TIMEOUT_SECONDS`, mặc định 3), keepalive và `tcp_user_timeout` (`DB_TCP_USER_TIMEOUT_MS`, mặc định 15000), rồi dịch lỗi kết nối sang `DatabaseUnavailableError` (`application/errors.py`). `api/errors.py` ánh xạ lỗi đó, và `psycopg.OperationalError` rớt giữa chừng (composition root truyền vào), thành `503 DATABASE_UNAVAILABLE` (`retryable: true`, `Retry-After: 5`). Hành vi: app vẫn khởi động và phục vụ được đường không cần DB; `GET /health` không đụng DB; `GET /health/ready` thêm `database: ok|down|unknown` nhưng vẫn 200; DB lên lại thì request kế tiếp tự thành công. Adapter mới phải dùng `connect_async` (không thì request treo khi DB chết). `LocalCdpClient` vẫn đổi lỗi này thành `CdpUnavailableError`.

## Search / Recommendation

RecSys cố định Cohere `embed-multilingual-v3.0` (1024 chiều). Job index dùng `search_document`; request tìm kiếm dùng `search_query`. `WEAVIATE_URL`, `WEAVIATE_COLLECTION`, `COHERE_API_KEY` và `SEARCH_CUTOFF` (`0.62`, còn phải benchmark lại) được đọc qua `core/config.py`. Job index (`python -m src.backend.jobs.embed_products`) gọi Cohere song song `COHERE_EMBED_CONCURRENCY` lô (mặc định 4; 1 = tuần tự) dưới trần `COHERE_CALLS_PER_MINUTE` lượt/phút cho cả job (mặc định 90, hợp key Trial 100 lượt/phút; 0 = không giới hạn); gặp 429 thì mọi lô cùng chờ. Chỉ luồng chính ghi Weaviate, lô nào xong ghi ngay, lỗi giữa chừng vẫn giữ phần đã ghi. `--force` nhúng lại toàn bộ (chỉ để đo, tốn quota). Search lúc chạy API không bị giới hạn này. Weaviate chỉ giữ vector + `productId`/`modelVersion`/`textHash`; tên, giá, ảnh và availability luôn hydrate từ PostgreSQL. Metadata nạp lúc khởi động rồi nạp lại mỗi `CATALOG_REFRESH_SECONDS` (mặc định 900 giây); lần nạp lại lỗi thì giữ bản đang phục vụ. Search unit chưa có vector (job index chưa chạy xong) vẫn có giá mới nhưng chưa tìm được qua vector. Vector **truy vấn** được cache trong tiến trình (`application/search/query_cache.py`, LRU `SEARCH_EMBED_CACHE_SIZE`, khoá = câu sau chuẩn hoá; `diagnostics.embedCache` hit/miss, contract 1.12.0) và nạp sẵn ở nền sau lần nạp catalog đầu (`SEARCH_PREWARM`, file `data/search_prewarm_queries.txt` + head query `app.search_logs`); `python -m src.backend.jobs.prewarm_query_cache --base-url URL` làm nóng một backend đang chạy qua HTTP. Job index có `--lexical-only`: chỉ ghi property BM25 còn thiếu và từ chối khi catalog lệch index (không embed, không xoá). Chưa nạp được lần nào — thiếu PostgreSQL, Weaviate, khóa Cohere, hoặc dưới một nửa search unit có vector đúng model — thì RecSys tắt và thử lại sau 30 giây, các route còn lại vẫn chạy.

Endpoint hiện có (prefix `/api/v1`): `GET|POST /search` (`q`/`query`, `taxonomy`, `destination`, `limit`, `offset`;
ở `ITINERARY_DATA_MODE=http`, adapter đổi tham số tool `query` thành `q`) · `GET /similar/{productId}?k=` · `GET /recommendations?k=&destination=`
(JWT tùy chọn, `cdp_user_id` lấy từ token; token hỏng → 401, không hạ thành khách) · `GET /destinations` ·
`POST /assistant/itineraries` · `POST /assistant/itineraries/stream` · `GET /assistant/status` ·
`GET /assistant/conversations` · `GET /assistant/conversations/{conversationId}` (JWT bắt buộc) ·
auth v1 `POST /auth/register|login`, `GET /auth/me` · chỉ BFF (`X-Service-Token`)
`POST /auth/session`, `/auth/session/token`, `/auth/session/revoke` · `PUT /auth/password` ·
`GET /internal/recommendations?cdp_user_id=` (`X-Service-Token`, tắt ở production) · booking (JWT bắt buộc)
`GET /cart`, `POST /cart/items`, `PATCH|DELETE /cart/items/{cartItemId}`, `POST /bookings`,
`GET /bookings/{referenceCode}`, `POST /bookings/{referenceCode}/cancel` · Stripe gọi thẳng (chữ ký, không JWT)
`POST /payments/stripe/webhook`. Ngoài prefix: `GET /health`,
`GET /.well-known/jwks.json`, `GET /metrics` (Prometheus), `GET /internal/calls` (lần gọi web / agent gần nhất cho monitor;
`docs/spec/hop-dong-tich-hop-backend.md` §8.6a).

## Auth

Chi tiết: `docs/spec/hop-dong-tich-hop-auth.md`. JWT ký RS256; sinh khoá dev một lần bằng `make jwt-keys` (ghi vào
`secrets/`, đã gitignore). Thiếu khoá thì development tự sinh khoá tạm — token mất hiệu lực mỗi lần restart.
Đặt `AUTH_SERVICE_TOKEN` (≥ 32 ký tự, `openssl rand -hex 32`) giống hệt ở backend và BFF, nếu không web không
đăng nhập được. `AUTH_REDIS_URL` trống thì rate limit chạy trong bộ nhớ (chỉ dev). Tài khoản seed (đăng nhập qua `/login` như user
thường): 4 persona + 50 `test01..50@vota.demo`, mật khẩu `Demo@2026`. Test Postgres/Redis thật: `RUN_POSTGRES_INTEGRATION=1
RUN_REDIS_INTEGRATION=1 python -m pytest -q src/backend/tests/integration`.

## Booking và thanh toán Stripe (test mode)

Luồng và sơ đồ: `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md`. `POST /bookings` giữ chỗ 30 phút và trả
`payment.checkoutUrl` (trang Stripe Checkout); đơn chỉ `CONFIRMED` khi webhook có chữ ký báo đã thu tiền (hoặc job
đối soát tự hỏi Stripe). Database cần migration `0003`, `0004`, `0005` (`make db-migrate`).

Checkout ba bước (FR-BKG-08, `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md`): giỏ lưu `guests` (người lớn, trẻ em) và trả `fares`; `POST /bookings` nhận `travelers` và `itemDetails` theo từng mục, kiểm mọi luật trước khi gọi Stripe và trả `400 VALIDATION_ERROR` liệt kê hết vi phạm. Luật nằm ở `domain/booking/party_rules.py`, giá theo loại khách ở `domain/booking/fares.py`; Web chạy cùng bộ ca `src/shared/contracts/tests/booking-rules-cases.json`. Migration `0005` cần chạy trước khi khởi động Backend mới (thêm cột vào `app.cart_items`, bảng `app.booking_travelers`); chạy `python db/migrations/run.py --status` để xem đã áp chưa.

```env
STRIPE_SECRET_KEY=sk_test_...      # chỉ khoá test; sk_live_ bị từ chối khi khởi động
STRIPE_WEBHOOK_SECRET=whsec_...    # in ra bởi `stripe listen`, mỗi máy một giá trị
PAYMENT_PROVIDER=stripe            # fake: không gọi mạng (test/offline); trang thanh toán giả không mở được
BOOKING_HOLD_MINUTES=30            # >= 30 (giới hạn expires_at của Stripe)
PAYMENT_MAX_FAILED_ATTEMPTS=3
PUBLIC_WEB_URL=http://localhost:3000
BOOKING_RECONCILE_INTERVAL_SECONDS=300   # job đối soát trong tiến trình; 0 = tắt
```

Nhận webhook ở local bằng Stripe CLI (cài một lần, `stripe login`):

```bash
stripe listen --forward-to localhost:8000/api/v1/payments/stripe/webhook   # chép whsec_… vào .env
```

Thẻ test: `4242 4242 4242 4242` (thành công), `4000 0000 0000 0002` (từ chối), `4000 0000 0000 9995` (không đủ số
dư), `4000 0027 6000 3184` (3DS). Test integration adapter Postgres booking: `RUN_POSTGRES_INTEGRATION=1 python -m
pytest -q src/backend/tests/integration/test_booking_postgres.py` (dùng user test `VP0000054`, tự dọn dữ liệu).

## Chỗ nào làm gì (docs/prd/architecture.md §2)

| Lớp | Thư mục | Nội dung |
|---|---|---|
| domain | `domain/<domain>/` | Business rule thuần: vai trò sản phẩm + text builder (`catalog`), FILTER → SCORE → CUTOFF (`search`), hồ sơ người dùng + MMR + phổ biến (`recommendation`), chuẩn hoá intent + ghép lịch trình (`itinerary`), mật khẩu + phiên (`auth`), máy trạng thái đơn/thanh toán + giữ chỗ + chính sách huỷ + đoàn khách, dòng giá theo loại khách và luật kiểm (`booking`: `party`, `fares`, `party_rules`) |
| application | `application/ports/` | Mỗi port một file: `cdp_client.py` (`CdpClient` ghi, `CdpHistoryReader` đọc), `embedder.py`, `vector_store.py`, `unit_index.py`, `llm.py`, `itinerary_planner.py`, `itinerary_tools.py`, `auth.py`, `payment_gateway.py`, `booking_store.py`, `cart_repository.py`, `product_catalog.py`, `product_query.py` (GET /products) |
| application | `application/<domain>/` | Use case: `SearchProducts`, `SimilarProducts`, `RecommendForUser`, `BuildPopularity`, `PlanItinerary`, auth, booking, tracking; `itinerary/engine_tools.py` (`InProcessItineraryTools`, tool itinerary gọi engine trong tiến trình); `auth/bearer.py` (resolver Bearer dùng chung cho `api/deps.py` và tool) |
| agents | `agents/` | LangGraph 10 node; `runtime_dependencies.py` hiện thực port `ItineraryPlanner`; `tools/itinerary_gateway.py` gọi Search/Recommendation (và Similar ở lượt đổi món) qua port |
| infrastructure | `cdp/` | `LocalCdpClient` (ghi), `PostgresCdpReader` (đọc), `CdpHttpClient`, `BackgroundCdpEventRecorder` — mọi SQL vào schema `cdp` nằm ở đây |
| infrastructure | `persistence/` | `PostgresProductLookup`, Redis conversation store, Postgres conversation archive, LangGraph checkpointer, giỏ/đơn/thanh toán (`postgres_booking.py`) |
| infrastructure | `clients/` | HTTP client itinerary (`ITINERARY_DATA_MODE=http`, tuỳ chọn); fixture 50 sản phẩm cho `ITINERARY_DATA_MODE=fixture` |
| infrastructure | `llm/`, `embeddings/`, `vectors/`, `auth/`, `payments/` | Provider LLM (`LazyChatModel`), `CohereEmbedder`, `WeaviateVectorStore`, hash mật khẩu + JWT, `StripePaymentGateway` (REST qua httpx, kiểm chữ ký webhook) + `FakeGateway` (`PAYMENT_PROVIDER=fake`) |
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
ITINERARY_REDIS_URL=redis://:devpass@localhost:6379/2  # working memory 24h; bắt buộc production
```

User đăng nhập được ghi thêm transcript vào `app.conversations`/`app.conversation_messages`; lỗi archive
không làm hỏng lượt chat. Khách không được lưu lâu dài. Web đọc lại lịch sử qua hai endpoint
`/assistant/conversations`; mọi truy vấn đều lọc bằng `cdp_user_id` từ JWT đã xác minh.

`GET /api/v1/assistant/status` trả thêm `llmMode`:

- `live` — đã dựng được client dùng chung.
- `disabled` — `ITINERARY_USE_LLM=false`.
- `unavailable` — đã bật nhưng thiếu API key hoặc thiếu SDK của provider.

Với `disabled` và `unavailable`, app vẫn khởi động và các route khác vẫn phục vụ; riêng request itinerary
trả 503 `LLM_UNAVAILABLE` có kiểm soát.

Nguồn dữ liệu cho tool của Agent chọn bằng `ITINERARY_DATA_MODE`; `/assistant/status` trả lại giá trị này trong `dataMode`:

| Giá trị | Adapter | Khi dùng |
|---|---|---|
| `fixture` | `infrastructure/clients/itinerary_fixture_clients.py` (50 sản phẩm) | Mặc định development/test; máy chưa seed PostgreSQL vẫn chạy được |
| `inprocess` | `application/itinerary/engine_tools.py` | Dữ liệu thật: gọi thẳng engine Search/Recommendation/Similar/catalog trên `app.state`, không qua HTTP. `make chat`/`make web` mặc định dùng mode này |
| `http` | `infrastructure/clients/itinerary_http_clients.py` | Tuỳ chọn: gọi `/search`, `/recommendations`, `/destinations`, `/products/{id}`, `/products/{id}/similar` qua `ITINERARY_SERVICE_BASE_URL` (bắt buộc ở mode này). Dùng để hoàn tác hoặc khi tách Agent thành service riêng |
| `disabled` | — | Mặc định ngoài development/test: status `not_configured`, request itinerary trả 503 `SEARCH_UNAVAILABLE` |

Chạy Agent với dữ liệu thật (cần PostgreSQL đã seed, Weaviate đã index và `COHERE_API_KEY`):

```env
ITINERARY_DATA_MODE=inprocess
ITINERARY_TOOL_TIMEOUT_SECONDS=1   # hạn mỗi lời gọi tool, áp mọi mode
```

Chờ log `startup.recsys.ready`; trước đó tool trả 503 `SEARCH_UNAVAILABLE` retryable. Tool `search_products` không
bao giờ mang danh tính người dùng. Tool `get_recommendations` xác minh Bearer của request ngay trong tiến trình qua
`application/auth/bearer.py` (cùng resolver với route): token hỏng → 401, không hạ thành khách; không có header → khách.
Tool thứ ba `get_similar_products` (`/products/{id}/similar`, `same_taxonomy`, không mang danh tính) chỉ được mời ở
lượt đổi món, với sản phẩm gốc lấy từ lịch trình lượt trước; quy tắc ở
`docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §2.5.
Engine đồng bộ chạy trên pool riêng 40 thread (`itinerary-tool`) và giữ request ID; mỗi lời gọi kết thúc trong hạn
ghi một dòng log `itinerary.tool`, lời gọi quá hạn chỉ ghi `itinerary.tool.timeout`; engine chưa sẵn sàng hoặc lỗi ghi
`itinerary.tool.unavailable` (lỗi thì kèm tên kiểu lỗi và frame traceback, không kèm thông điệp). Không dòng nào ghi
tham số hay token. Kết quả có đúng hình dạng
response của route và đủ trường catalog để Agent hậu kiểm mà không cần gọi Product Detail. Quay về cách gọi cũ:
`ITINERARY_DATA_MODE=http` và `ITINERARY_SERVICE_BASE_URL=http://127.0.0.1:8000`. Runner golden
(`src/evaluation/agent/golden.py`) luôn gọi backend qua HTTP.

CLI chạy kịch bản đánh giá agent đã chuyển sang `src/evaluation/agent/cli.py`
(`python -m src.evaluation.agent.cli --help`).
