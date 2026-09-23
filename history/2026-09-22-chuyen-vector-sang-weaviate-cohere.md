# Chuyển vector sang Weaviate + Cohere embed-multilingual-v3.0, gỡ pgvector

- Ngày: 2026-09-22
- Tác giả: mihhquan / Claude Opus 5
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs, db

## Mục tiêu

Người dùng yêu cầu cập nhật `docs/prd/architecture.md` và các file PRD liên quan vì **mỗi lần chạy `make` đều phải dựng lại database vector**. Quyết định: chuyển vector ra Weaviate (service riêng, volume riêng) và dùng Cohere `embed-multilingual-v3.0` thay cho model embedding chạy local.

Nguyên nhân gốc của cái phiền: `make demo-db` dựng lại database `vota` từ đầu, mà `catalog.product_vectors` nằm chung trong đó — nên mỗi vòng seed đều mất toàn bộ vector và phải embed lại toàn bộ catalog. Tách sang Weaviate cho vector một vòng đời độc lập với vòng seed quan hệ.

## Quyết định (người dùng chốt qua hai câu hỏi)

1. **Backend tự embed rồi tự ghi (BYOV), không dùng module `text2vec-cohere`.** Weaviate khai báo `vectorizer: none` và **không giữ `COHERE_API_KEY`**. Giữ được `in_memory_store.py` cho test offline và giữ model/version trong code app. Đánh đổi: backend phải tự đặt `input_type` (`search_document` khi nạp, `search_query` khi truy vấn) — dùng sai làm giảm chất lượng xếp hạng mà không báo lỗi, nên đã ghi cảnh báo này vào PRD và `AGENTS.md`.
2. **Gỡ hẳn `catalog.product_vectors` khỏi PRD, DDL và verify** (không chỉ đánh dấu deprecated).

Hệ quả phát sinh khi làm: bảng này là **hộ dùng duy nhất** của extension `vector`, nên gỡ luôn được `CREATE EXTENSION vector` và hạ image Postgres từ `pgvector/pgvector:pg16` xuống `postgres:16`.

## File thay đổi

**PRD (`docs/prd/`)**
- `architecture.md` — sửa: sơ đồ §1 tách subgraph `VectorStore` (Weaviate) và thêm Cohere vào External + 2 cạnh adapter; §2 thêm `embedding_client.py` vào ports và `vectors/` vào infrastructure; §4 thay 2 dòng tech stack thành PostgreSQL 16 / Weaviate / Cohere 1024 chiều; §5 thêm mục 5 mô tả luồng nạp–truy vấn, `input_type`, và ranh giới "Weaviate chỉ giữ vector + productId".
- `data-model.md` — sửa: §1 bỏ `product_vectors` khỏi sơ đồ, thêm khối Weaviate + đoạn giải thích lý do tách; §2.1 đổi entity `CATALOG_PRODUCT_VECTORS` thành `WEAVIATE_PRODUCT`; §5 viết lại mục 3 và thêm mục 4 (Weaviate ngoài vòng migration, vector mồ côi).
- `deployment-plan.md` — sửa: §1 thêm dòng "Cơ sở dữ liệu vector"; §2 thêm `COHERE_API_KEY`, `WEAVIATE_URL`, `WEAVIATE_API_KEY` và viết lại `EMBEDDING_MODEL_NAME`; §3.1 thêm lệnh khởi động Weaviate + ghi chú hai vòng đời tách rời; §5 readiness probe kiểm tra Weaviate và Cohere.
- `requirements.md` — sửa: FR-SRC-02 (model, chiều, `input_type`), NFR-PERF-03 (HNSW của Weaviate, ngân sách thời gian gọi Cohere).
- `implementation-plan.md` — sửa: Giai đoạn 2 (job embed + hybrid search của Weaviate), Giai đoạn 6 (tinh chỉnh HNSW của Weaviate).
- `project-brief.md` — sửa: sơ đồ §2.2 `pgvector` → `Cohere Embed + Weaviate`.
- `README.md` — sửa: dòng hướng dẫn Data/RecSys trỏ sang collection `Product`.
- `slides/v-ota-project-brief.html` — sửa: một dòng mô tả engine.

**Database**
- `db/vota_schema.sql`, `db/init/01_vota.sql` — xóa: bảng `catalog.product_vectors` + index HNSW + `CREATE EXTENSION IF NOT EXISTS vector`; sửa: 2 dòng comment đầu file.
- `db/migrations/0002_drop_product_vectors.sql` — thêm: migration idempotent `DROP TABLE IF EXISTS` + `DROP EXTENSION IF EXISTS` (cố ý **không** CASCADE để dừng lại nếu còn object khác dùng kiểu `vector`).
- `docker-compose.yml` — sửa: image `pgvector/pgvector:pg16` → `postgres:16`; thêm: service `weaviate` (1.27.0, `vectorizer: none`, anonymous access cho dev, cổng 8080 REST + 50051 gRPC chỉ loopback, healthcheck `/v1/.well-known/ready`) và volume `weaviate_data`.
- `db/verify.sql` — **không đổi**: đã kiểm tra, file này không tham chiếu `product_vectors` hay vector.

**Tài liệu kỹ thuật khác**
- `docs/spec/DATABASE_SCHEMA.md` — sửa: header (bỏ pgvector, đếm lại bảng), câu hỏi mở #12 đánh dấu đã chốt, bảng inventory schema `catalog`, ERD, thứ tự nạp bước (5), khối DDL, vòng feedback loop.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: rủi ro S7 đánh dấu đã chốt; thêm rủi ro S8 và một khối cảnh báo trước mục "Chế độ truy xuất" (xem "Còn lại / rủi ro").
- `AGENTS.md` — sửa: §6.2 dòng vector, §6.3 (staging không cần pgvector), §6.4 gỡ mục "D và model vector" vì đã chốt.
- `src/ARCHITECTURE.md` (4 dòng), `src/backend/README.md` (1 dòng), `README.md` (1 dòng) — bỏ pgvector.

## Kiểm tra

- `docker compose config --quiet` → OK (compose hợp lệ sau khi thêm Weaviate).
- **DDL chạy thật trên `postgres:16` sạch** (container tạm, không đụng volume của người dùng): initdb không lỗi. Kết quả truy vấn: `cdp` 3 bảng + `catalog` 1 bảng + `app` 13 bảng = **17 bảng** `vota`, `catalog` **3 view**; database `insider` **5 bảng**. `product_vectors` = 0, extension `vector` = 0. → tổng 22 bảng / 4 view, đã sửa con số trong `DATABASE_SCHEMA.md`.
- **Migration 0002 chạy thật trên trạng thái CŨ**: dựng lại bảng + extension + index HNSW trên container `pgvector/pgvector:pg16`, chạy migration lần 1 → bảng=0, ext=0; chạy **lần 2** → chỉ ra NOTICE "does not exist, skipping", không lỗi. Idempotent đạt.
- Không chạy `validate_contract.py` vì không đổi file contract nào (`schemas/search.yaml` cố ý giữ nguyên — xem S8).
- Đã grep lại toàn repo: không còn `pgvector`/`vector(`/`hnsw` trong `db/` và `docs/prd/`.

## Còn lại / rủi ro

- **S8 — `EXACT_FILTER_SCORE` cần duyệt lại (chưa chốt, đã ghi vào contract Search).** `docs/spec/hop-dong-tich-hop-search-recommendation.md` chọn exact scan với lập luận "1.125 vector × 768 chiều = 3,4 MB, nằm gọn trong `shared_buffers`; HNSW là xấp xỉ và không trả đủ tập để đếm `facets`". Weaviate là HNSW-first nên tiền đề này không còn đúng. Team Search phải chọn: (a) đếm `facets` bằng SQL trên Postgres, chỉ dùng Weaviate cho top-K, hoặc (b) đổi cam kết `facets` trong contract. **Chưa sửa `src/shared/contracts/schemas/search.yaml`** — cần chốt trước.
- **Chưa nối Weaviate vào `Makefile`.** `make demo-db` vẫn chỉ `docker compose up -d --wait postgres`. Nối vào khi job `embed_products` có thật (Giai đoạn 2), vì hiện chưa có gì ghi vào Weaviate.
- **Chưa có code adapter.** `WeaviateVectorStore` và `CohereEmbedder` mới chỉ nằm trong tài liệu; `src/backend/app/infrastructure/vectors/` hiện chỉ có `in_memory_store.py`. RecSys hiện vẫn tự embed bằng `intfloat/multilingual-e5-base` và cache ra `.embcache/` (xem `history/2026-09-21-gop-recsys-vao-backend-postgres.md`) — đường này còn chạy cho tới khi adapter Weaviate xong.
- **Máy dev đang có dữ liệu** cần chạy `make db-migrate` để áp 0002. Máy dựng mới thì `db/init/` đã sạch sẵn.
- Các tài liệu tham khảo cũ vẫn nhắc pgvector, **cố ý chưa sửa** vì là tài liệu học/khảo sát chứ không phải nguồn sự thật: `docs/spec/recsys-internship-handbook-v3-vi.md`, `docs/spec/mvp-v01.md`, `docs/spec/data-collection-spec.md`, `docs/spec/thiet-ke-schema-3-service*.md`, `docs/spec/research/`, `mvp/`.
