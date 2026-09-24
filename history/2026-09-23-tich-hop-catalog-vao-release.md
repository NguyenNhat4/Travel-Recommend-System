# Tích hợp catalog/data vào release và chuyển vector sang Cohere/Weaviate

- Ngày: 2026-09-23
- Tác giả: người dùng / Codex
- Nhánh: `codex/integrate-catalog-into-release`
- Trạng thái: hoàn thành
- Phạm vi: backend, data, docs

## Mục tiêu

Dùng `origin/release-mvp-v1` làm nền hoàn thiện nhất, mang hai commit catalog/data của `feat/catalog-sync-cohere` sang mà không làm mất auth/agent/refactor backend của release; giải quyết conflict, giữ baseline 11.387 sản phẩm và áp quyết định mới của team: Cohere `embed-multilingual-v3.0` + Weaviate thay pgvector.

## File thay đổi

- `AGENTS.md`, `db/verify.sql`, `docs/spec/MOCK_DATA_SPEC.md`, `src/data_collection/seed/config.py`, `src/backend/tests/integration/test_local_postgres_adapters.py` — sửa: cập nhật baseline 11.387 và snapshot 2026-09-23.
- `src/data_collection/` — thêm/sửa: mang collectors, config, scripts, tests, mapping/override, cron, monitor và pipeline automation từ source cũ; không mang Git history, secret, raw cache, browser profile, log hoặc crawl state.
- `src/data_collection/snapshots/2026-09-23/` — thêm: catalog chuẩn nén 11.387 sản phẩm, manifest/checksum và mapping combo đã duyệt.
- `docs/spec/data-collection/` — thêm/sửa: đặt schema, thống kê, hướng dẫn chạy theo thành phố, template và tài liệu bàn giao tại vị trí docs mới của release; không tạo lại `src/data_collection/docs`.
- `src/backend/app/domain/catalog/text_builder.py`, `src/backend/app/domain/catalog/__init__.py` — sửa: giữ text builder giàu thông tin, thêm phiên bản text ổn định cho `modelVersion`.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: tách `PostgresCatalogReader`; giữ adapter embed/cache cục bộ chỉ làm fallback offline.
- `src/backend/app/infrastructure/embeddings/cohere_embedder.py` — thêm: gọi Cohere Embed v2 theo batch, phân biệt `search_document`/`search_query`, kiểm 1024 chiều và chuẩn hoá vector.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — thêm: tạo/kiểm collection `Product` (`vectorizer: none`, HNSW cosine), nạp vector đã persist và hydrate catalog từ PostgreSQL.
- `src/backend/jobs/embed_products.py`, `src/backend/jobs/__init__.py` — thêm: job incremental theo `textHash`/`modelVersion`, dọn vector mồ côi và chỉ gọi Cohere cho text mới/đổi.
- `src/backend/app/core/config.py`, `src/backend/app/main.py`, `src/backend/app/application/ports/unit_index.py`, `src/backend/requirements.txt` — sửa: composition root dùng Cohere/Weaviate, model cố định 1024 chiều, cutoff tạm 0.62 và bỏ dependency tải model local.
- `src/data_collection/seed/database.py`, `src/data_collection/seed/report.py` — sửa: bỏ truy cập bảng `catalog.product_vectors` đã bị migration xóa; report trỏ sang job Weaviate.
- `Makefile`, `docker-compose.yml`, `.env.example`, `README.md`, `src/backend/README.md`, `src/data_collection/README.md` — sửa: thêm `make index-vectors`, cấu hình Cohere/Weaviate và hướng dẫn seed/index mới.
- `docs/spec/PRODUCT_SCHEMA.md`, `docs/spec/DATABASE_SCHEMA.md` — sửa: đồng bộ source-of-truth database với Weaviate, 1024 chiều và collection ngoài PostgreSQL.
- `src/backend/tests/unit/domain/test_text_builder.py`, `src/backend/tests/unit/fixtures/embed_text_cases.json` — sửa/thêm: giữ regression fixture của text builder và sửa đường dẫn fixture sau refactor release.
- `src/backend/tests/unit/infrastructure/test_cohere_embedder.py`, `src/backend/tests/unit/infrastructure/test_weaviate_store.py` — thêm: kiểm input type, batching, dimension, normalize, schema collection và fail-closed khi vector thiếu/cũ.
- `history/2026-09-23-gop-text-builder-vao-catalog-sync.md`, `history/2026-09-23-migrate-data-collection-vao-monorepo.md` — thêm từ hai commit nguồn để giữ lý do/quyết định của phần đã thực hiện trước merge.

## Quyết định

- `release-mvp-v1` là nền; không merge `feat/auth` riêng vì release đã chứa cây của nhánh đó.
- Không khôi phục `pgvector` hoặc `catalog.product_vectors`; PostgreSQL giữ catalog, Weaviate giữ vector và chỉ nối logic bằng `productId`.
- Job index tách khỏi `make demo-db` vì gọi Cohere có quota/chi phí; automation gọi `make index-vectors` sau khi promote/seed catalog.
- Runtime tạm tải vector persist từ Weaviate vào `UnitIndex` để giữ semantics exact/facet của contract hiện hành. Chuyển Search sang ANN top-K cần team Search chốt S8 trước, không tự đổi OpenAPI.
- Repo data-collection cũ không bị sửa; `src/data_collection` trong monorepo là source chính duy nhất.

## Kiểm tra

- `conda run -n vsf python -m pytest -q data_collection/tests` (chạy từ `src/`): 260 passed, 2 skipped.
- Bộ backend không phụ thuộc auth/agent: 83 passed, 2 skipped.
- Test mới Cohere/Weaviate + text builder: 26 passed.
- `PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py`: PASS (77 schema, 53 fixture hiện có và các negative check).
- Toàn bộ backend trên env `vsf` chưa chạy được: env dùng Python 3.10 trong khi code release import `enum.StrEnum` (Python 3.11+) và env thiếu package `PyJWT`; đây là giới hạn môi trường/release có sẵn, không phải lỗi của các test catalog/vector ở trên.

## Còn lại / rủi ro

- Chưa gọi Cohere thật và chưa ghi Weaviate thật vì không dùng secret/quota trong test; sau khi đặt `COHERE_API_KEY`, chạy `make index-vectors` rồi kiểm số object = 3.183.
- Search contract vẫn chờ quyết định S8 giữa exact facet và ANN HNSW; runtime hiện ưu tiên giữ contract.
- Nhánh đang ở trạng thái merge chưa commit theo yêu cầu; người dùng tự review, commit và push.
