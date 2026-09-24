# Job embed_products: nạp vector search unit lên Weaviate bằng Cohere

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: dang dở
- Phạm vi: backend, data, docs

## Mục tiêu

Người dùng cần có data để thử: catalog JSONL nằm trong Postgres Docker (đã có sẵn qua `make demo-db`), còn vector thì đẩy lên Weaviate Cloud theo PRD (FR-SRC-02, `docs/prd/architecture.md` §5). Yêu cầu giữ đơn giản: chỉ làm phần nạp dữ liệu, chưa chuyển đường truy vấn của backend. Kèm theo đó là cập nhật README (review ở cùng phiên).

## File thay đổi

- `src/backend/app/infrastructure/embeddings/cohere_embedder.py` — thêm: `CohereEmbedder` (EmbedderPort) gọi Cohere Embed API v2 bằng httpx; `search_document` khi nạp, `search_query` khi truy vấn; mỗi lần gọi tối đa 96 text; thử lại khi gặp 429.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — thêm: `WeaviateVectorStore` gọi REST `/v1` bằng httpx: `exists`, `ensure_collection` (`vectorizer: none`, HNSW, cosine, 3 thuộc tính `productId`/`modelVersion`/`textHash`), `stored` (đọc theo cursor), `upsert` (UUID do Weaviate cấp), `delete`.
- `src/backend/app/infrastructure/vectors/embed_products.py` — thêm: job. Chỉ embed những sản phẩm có `textHash` hoặc `modelVersion` đổi, xoá vector mồ côi, kiểm vector đủ 1024 chiều. Có `--dry-run` và `--limit`.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: tách `read_catalog_rows` và `search_units` ra hàm mức module để job dùng chung. Hành vi của `PostgresVectorStore` không đổi.
- `src/backend/app/core/config.py` — sửa: thêm `cohere_api_key`, `embedding_model_name`, `weaviate_url`, `weaviate_api_key` (tên biến theo `deployment-plan.md` §2).
- `src/backend/tests/unit/infrastructure/test_embed_products.py` — thêm: 9 test (input_type, chia batch, retry 429, schema BYOV, cursor, lỗi batch, logic plan).
- `Makefile` — sửa: thêm target `embed-products` (`EMBED_ARGS=...`).
- `.env.example` — sửa: thêm khối `COHERE_API_KEY`, `EMBEDDING_MODEL_NAME`, `WEAVIATE_URL`, `WEAVIATE_API_KEY`.
- `README.md` — sửa: viết lại. Sửa Python lên 3.11+ (code dùng `StrEnum`); bỏ lệnh "cài tập con" vì thiếu httpx/numpy/jsonschema/langgraph nên không chạy được; `demo-db` là 4 bước; sửa hướng dẫn đổi cổng Postgres; thêm bước `cp .env.example .env`; thêm mục Vector và mục Test; ghi rõ backend runtime chưa đọc vector từ Weaviate.
- `docs/prd/update/2026-09-23-weaviate-cloud-index-hfresh.md` — thêm: đề xuất chờ chốt (xem Quyết định).

## Quyết định

- Gọi REST bằng httpx thay vì dùng SDK `cohere` và `weaviate-client`, để không thêm dependency. httpx đã có trong `requirements.txt`.
- Job đặt ở `infrastructure/vectors/`, vì `tests/architecture` không cho file nằm ngoài các lớp đã biết. Job đọc catalog qua `DATABASE_URL` (role `vota_app`), đúng ranh giới ở AGENTS.md §6.1.
- `modelVersion = <EMBEDDING_MODEL_NAME>+text-v1`. Đổi text builder thì tăng `TEXT_BUILDER_VERSION` để job embed lại toàn bộ.
- **Weaviate Cloud của nhóm (1.39.5) từ chối HNSW** (`422 CONFIG_NOT_ALLOWED … Allowed values: hfresh`). PRD NFR-PERF-03 bắt buộc HNSW, nên đã tạo đề xuất `docs/prd/update/2026-09-23-weaviate-cloud-index-hfresh.md` và **dừng phần đẩy lên cloud**. Code giữ HNSW đúng PRD. Chưa ghi gì lên cloud.

## Kiểm tra

- `pytest src/backend/tests/unit/infrastructure/test_embed_products.py src/backend/tests/architecture`: 17 passed.
- `pytest -q src/backend/tests`: 177 passed, 2 skipped (integration Postgres).
- Chạy thật với Postgres local (10.320 sản phẩm, 2.897 search unit) và Weaviate local: `make embed-products EMBED_ARGS="--limit 5"` tạo collection (`none`/`hnsw`/`cosine`) và ghi 5 object 1024 chiều. Chạy lại `--dry-run` cho `alreadyCurrent: 5`, `toEmbed: 2892`.
- `--dry-run` với Weaviate Cloud: kết nối và xác thực được. Tạo collection thì lỗi 422 như trên.
- `make db-migrate` trên volume local: **lỗi** ở `0002_drop_product_vectors.sql` (`could not access file "$libdir/vector"`). Volume được tạo từ image `pgvector` cũ, image `postgres:16` hiện tại không có thư viện `vector` nên không DROP được bảng có cột vector. Lỗi có từ trước task này; job embed không phụ thuộc migration này.
- Không chạy `validate_contract.py`: không đổi contract hay mock.

## Còn lại / rủi ro

- Chờ chốt đề xuất hfresh, hoặc nâng gói cloud. Sau đó chạy `make embed-products` để nạp đủ 2.897 search unit. Weaviate local đang giữ 5 object thử nghiệm.
- Migration 0002 không chạy được trên volume tạo từ image pgvector. Cách xử lý: chạy migration một lần bằng image `pgvector/pgvector:pg16`, hoặc tạo lại volume (`docker compose down -v`, sẽ mất dữ liệu local). Cần người dùng chọn; có thể phải sửa `db/migrations/README.md`.
- Backend runtime vẫn dùng sentence-transformers và index trong RAM. Chuyển `/search`, `/similar`, `/recommendations` sang Weaviate (`input_type=search_query`), cùng rủi ro S8 (đếm `facets`), là việc tiếp theo.
- Chưa commit.
