# Merge origin/release-mvp-v1 vào feat/auth

- Ngày: 2026-09-24
- Tác giả: mihhquan / Claude
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: backend | data | docs

## Mục tiêu

Lấy runtime Cohere + Weaviate và catalog thật 11.387 sản phẩm (snapshot 2026-09-23) từ `release-mvp-v1` về `feat/auth`, vì `build_recsys` trên nhánh auth còn dùng SentenceTransformers + PostgresVectorStore.

## File thay đổi

- `Makefile` — sửa: giữ `jwt-keys` của auth, dùng target `index-vectors` của release; bỏ `embed-products`.
- `docker-compose.yml` — sửa: backend phụ thuộc cả redis và weaviate; giữ env auth (JWT, Redis) và env Cohere/Weaviate.
- `src/backend/app/api/deps.py`, `src/backend/app/api/v1/router.py` — sửa: giữ cả phần auth lẫn `get_index`/`catalog_router`.
- `src/backend/app/infrastructure/embeddings/cohere_embedder.py`, `vectors/weaviate_store.py`, `vectors/postgres_store.py` — sửa: lấy bản release.
- `src/backend/app/infrastructure/vectors/embed_products.py`, `tests/unit/infrastructure/test_embed_products.py` — xóa: job của nhánh auth bị thay bởi `src/backend/jobs/embed_products.py` của release.
- `README.md`, `.env.example`, `src/backend/app/core/config.py`, `src/data_collection/README.md`, `src/data_collection/seed/report.py` — sửa: đổi tham chiếu `embed-products` sang `index-vectors`, lấy số liệu snapshot 2026-09-23.
- Các file còn lại đến từ release (catalog route, jobs, Dockerfile.daily, docs/plan, docs/spec/agent...) — thêm/sửa theo merge.

## Quyết định

- Hai nhánh cùng viết CohereEmbedder/WeaviateVectorStore (add/add). Chọn bản release vì runtime `main.py` đã nối vào nó; bỏ bản của nhánh auth thay vì giữ hai bản song song.
- Không đụng PRD; đề xuất `docs/prd/update/2026-09-23-weaviate-cloud-index-hfresh.md` vẫn chờ chốt.

## Kiểm tra

- `pytest src/backend/tests`: 283 passed, 13 skipped.
- `validate_contract.py`: xem kết quả trong phiên (chạy bằng venv backend).
- Chưa chạy lại `make demo-db` với snapshot mới và chưa chạy `make index-vectors`.

## Còn lại / rủi ro

- Cần `make demo-db-reset` (catalog 11.387) và `make index-vectors` trước khi backend recsys chạy đúng.
- `docker-compose.yml` ép `WEAVIATE_URL=http://weaviate:8080` cho backend; muốn dùng Weaviate Cloud trong `.env` phải đổi dòng này.
