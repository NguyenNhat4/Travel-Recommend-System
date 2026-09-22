# V-OTA backend — FastAPI, itinerary agent và RecSys

## Chạy trong Docker Compose

Chạy từ repository root:

```bash
make backend
```

Compose dựng image Backend, đợi PostgreSQL healthy và mở API tại `http://localhost:8000`. Health endpoint là `GET /health`. Dùng `make backend-logs` để theo dõi log và `make backend-stop` để dừng riêng Backend; lệnh này giữ nguyên PostgreSQL cùng volume dữ liệu.

Backend trong container kết nối PostgreSQL qua hostname `postgres` và hai role giới hạn riêng:

```text
DATABASE_URL=postgresql://vota_app_login:vota@postgres:5432/vota
CDP_DATABASE_URL=postgresql://cdp_client_login:cdp@postgres:5432/vota
```

Không dùng URL từ máy host (`localhost`) bên trong container. Nếu cần DSN khác, cấu hình `BACKEND_DATABASE_URL` và `BACKEND_CDP_DATABASE_URL` trong shell hoặc `.env` ở repository root. Các biến `OPENAI_API_KEY`, `MODEL_NAME` và cấu hình itinerary được chuyển từ môi trường Compose vào Backend.

Để dùng search/recommendation trên catalog đã seed, chạy `make demo-db` trước khi khởi động Backend. Backend không seed hoặc reset database khi container khởi động.

## Chạy trực tiếp trên máy

Khi cần reload nhanh trong lúc sửa code, dùng Uvicorn local:

```bash
python -m pip install -r src/backend/requirements.txt
make backend-local
```

Lần đầu chạy với catalog đã seed có thể tải model embedding và tạo cache; Compose giữ cache model Hugging Face và `.embcache` trong hai named volume qua các lần dừng container.

Endpoint: `GET /api/v1/search?q=&taxonomy=&destination=&limit=&offset=` (Agent tool `query` được adapter đổi thành `q`) ·
`GET /api/v1/similar/{productId}?k=` · `GET /api/v1/recommendations?k=&destination=` (JWT tùy chọn) ·
`GET /api/v1/popular?k=`

## Chỗ nào làm gì (ARCHITECTURE.md §4–5)

| Lớp | File | Nội dung |
|---|---|---|
| domain/catalog | `models.py`, `text_builder.py` | Product + vai trò (variant, is_search_unit, is_bookable); text builder theo variant |
| domain/search | `scoring.py` | FILTER → SCORE → CUTOFF → TOTAL/FACETS thuần numpy |
| domain/recommendation | `profile.py`, `popularity.py` | user vector 2 thang thời gian, MMR, because[]; điểm đến tháng/mùa |
| application | `ports.py` | `EmbedderPort`, `UnitIndex`, `VectorStorePort`, `CdpClientPort` |
| application/search | `use_cases.py` | `SearchProducts`, `SimilarProducts` |
| application/recommendation | `use_cases.py` | `RecommendForUser`, `BuildPopularity` |
| infrastructure | `embeddings/`, `vectors/in_memory_store.py`, `cdp/local_cdp_client.py` | hiện thực port; thay bằng `pgvector_store.py` / `PostgresCdpClient` sau |
| api/v1/routes | `search.py`, `recommendations.py` | chỉ HTTP, đọc use case từ `app.state` |
| `main.py` | composition root | nối infrastructure vào use case |

Quy tắc: `domain` không import FastAPI/DB/model; `application` chỉ import `ports`; chỉ `main.py` biết infrastructure.
## PostgreSQL local

`make backend` khởi động cả PostgreSQL và Backend trong cùng Docker Compose project. Trong mạng Compose, Backend dùng hostname `postgres`; các URL host-local bên dưới chỉ dành cho `make backend-local`:

```env
DATABASE_URL=postgresql://vota_app_login:vota@localhost:5432/vota
CDP_DATABASE_URL=postgresql://cdp_client_login:cdp@localhost:5432/vota
CDP_ADAPTER=local
```

- Với container, Compose đặt riêng `BACKEND_DATABASE_URL` và `BACKEND_CDP_DATABASE_URL`; giá trị mặc định dùng `postgres:5432` và vẫn giữ hai role giới hạn.
- `DATABASE_URL`: adapter catalog/app; role này chỉ được đọc `cdp.products`, không được đọc profile/event.
- `CDP_DATABASE_URL`: `LocalCdpClient`; role này chỉ được vào schema `cdp`.
- `CDP_ADAPTER=http`: đường chuyển sang `CdpHttpClient` sau này; lúc đó mới dùng `CDP_BASE_URL` và `CDP_SERVICE_TOKEN`.

Các URL này chỉ là địa chỉ PostgreSQL local; chúng không tạo database hay dữ liệu mới. Loader/seed dùng `SEED_DATABASE_URL` riêng và Backend không được dùng quyền đó.

Chạy test đọc seed thật (không ghi DB):

```bash
RUN_POSTGRES_INTEGRATION=1 python -m pytest -q src/backend/tests
```

## LLM của itinerary agent

`main.py` dựng **một** client LLM trong `lifespan` (`infrastructure/llm/build_chat_model`) và tiêm vào graph
qua `app.state.itinerary_llm`. Các node chỉ tự dựng client khi không được tiêm — đường CLI và test.

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
