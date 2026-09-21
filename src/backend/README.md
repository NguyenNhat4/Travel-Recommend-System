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

Endpoint: `GET /api/v1/search?q=&taxonomy=&destination=&limit=&offset=` ·
`GET /api/v1/similar/{productId}?k=` · `GET /api/v1/recommendations?k=&cdp_user_id=` (tạm, sẽ lấy từ JWT) ·
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
