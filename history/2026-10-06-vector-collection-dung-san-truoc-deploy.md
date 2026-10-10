# Biến VECTOR_COLLECTION cho collection e5-small, dựng sẵn trước deploy, không đổi env VM

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành (dựng collection trên Weaviate Cloud do người dùng chạy)
- Phạm vi: backend, data, evaluation, docs
- Thay thế: `2026-10-06-giu-ten-collection-product-cho-e5.md` (giữ tên `Product` buộc phải xoá collection Cohere sau deploy, Search tắt trong lúc embed lại)

## Mục tiêu

Người dùng muốn deploy là chạy được ngay, không đổi env nào trên VM (CI ghi đè `backend.env` / `fresh-catalog.env` từ Secret Manager, đang có `WEAVIATE_COLLECTION=Product` = vector Cohere), và tự embed e5 từ máy mình lên Weaviate Cloud trước khi mở PR. Job cào trên VM chạy 02:00 nên không thể chờ bước index của nó. Phục vụ FR-SRC-02.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: trường `weaviate_collection` đổi tên `vector_collection` (env `VECTOR_COLLECTION`), mặc định `ProductE5Small`. Biến cũ `WEAVIATE_COLLECTION` không còn được đọc (alias của pydantic-settings không dùng được: `populate_by_name` làm env tên trường cũ được đọc lại — đã thử).
- `src/backend/app/main.py`, `src/backend/jobs/embed_products.py`, `src/backend/app/infrastructure/vectors/weaviate_store.py`, `src/data_collection/fresh_catalog.py`, `src/data_collection/monitor.py`, `src/evaluation/recsys_bench/__main__.py`, `src/evaluation/recsys_bench/data_source.py` — sửa: `settings.vector_collection`.
- `src/data_collection/local_crawl.sh` — sửa: xuất `VECTOR_COLLECTION` cho lượt cào thử local; chế độ local chặn cả `Product` và `ProductE5Small`.
- `docker-compose.yml`, `.env.example`, `src/data_collection/.env.example` — sửa: `VECTOR_COLLECTION=ProductE5Small`.
- `docs/prd/architecture.md`, `docs/prd/data-model.md`, `docs/prd/deployment-plan.md` §2 (dòng `VECTOR_COLLECTION`), `docs/spec/hop-dong-tich-hop-search-recommendation.md` S7, `src/backend/README.md` — sửa.
- Test: `test_local_e5_embedder.py` (thêm: env cũ `WEAVIATE_COLLECTION=Product` bị bỏ qua), `test_embed_products_job.py`, `src/data_collection/tests/test_fresh_catalog_job.py`, `test_live_monitor.py` — đổi tên trường.

## Quyết định

- Tên biến mới thay vì đổi env: đổi model là đổi không gian vector, biến cũ trỏ collection Cohere nên bỏ hẳn là đúng nghĩa; env VM không cần sửa.
- Script dựng sẵn `src/data_collection/data/vm-repair-20261006/rebuild_product_e5.py` (ngoài git): `--check` chỉ đọc; `--apply` embed vào `ProductE5Small`, không đụng `Product`.

## Kiểm tra

- Backend `pytest --ignore=tests/integration`: 1.628 passed, 2 skipped. `pytest src/data_collection/tests`: 489 passed. `pytest src/evaluation/recsys_bench/tests`: 131 passed.
- `rebuild_product_e5.py --check` (Weaviate Cloud production, chỉ đọc): `Product` 3.304 object Cohere; `ProductE5Small` chưa có; DB 3.991 search unit.

## Còn lại / rủi ro

- Người dùng chạy `--apply` trước khi mở PR; sau deploy kiểm tra RecSys nạp được `ProductE5Small`.
- Collection `Product` (Cohere) để nguyên tới khi chủ động xoá.
