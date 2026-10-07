# Giữ tên collection `Product` cho vector e5-small (thay `ProductE5Small`)

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở (dựng lại collection trên Weaviate Cloud chờ sau deploy)
- Phạm vi: backend, data, docs
- Thay thế: quyết định tên collection `ProductE5Small` trong `2026-10-06-ap-dung-embedding-e5-small.md`

## Mục tiêu

Env backend và crawler trên VM được CI ghi đè từ Secret Manager mỗi lần deploy và đang đặt `WEAVIATE_COLLECTION=Product` (vector Cohere). Người dùng không muốn phụ thuộc team deploy để đổi Secret Manager. Người dùng chốt 06/10: giữ tên `Product`, dựng lại collection đó bằng vector e5-small sau khi deploy (Cohere đã bỏ hẳn nên collection Cohere cũ không còn dùng). Phục vụ FR-SRC-02.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: `weaviate_collection` mặc định `Product`.
- `src/backend/jobs/embed_products.py` — sửa: thông báo từ chối trộn model gợi ý xoá collection cũ rồi chạy lại.
- `src/data_collection/fresh_catalog.py` — sửa: chế độ local chặn collection `Product` (collection của backend local).
- `.env.example`, `src/data_collection/.env.example` — sửa: `WEAVIATE_COLLECTION=Product`.
- `docs/prd/architecture.md` (sơ đồ), `docs/prd/data-model.md` §1, `docs/prd/deployment-plan.md` §2 — sửa tên collection; `docs/spec/hop-dong-tich-hop-search-recommendation.md` S7, `src/backend/README.md` — sửa theo.
- Test: `test_local_e5_embedder.py`, `test_embed_products_job.py`, `src/data_collection/tests/test_fresh_catalog_job.py` — kỳ vọng `Product`.

## Quyết định

- Tên collection chỉ là cấu hình; PRD được sửa trong cùng thay đổi, người dùng chốt trong chat ("ok"). Không còn đường lui Cohere, nên ghi đè collection `Product` không mất gì cần giữ.
- Chốt chặn trộn model của job index giữ nguyên: job từ chối ghi vector e5 vào `Product` khi nó còn vector Cohere — phải xoá collection trước (script `rebuild_product_e5.py`, ngoài git).

## Kiểm tra

- Backend `pytest --ignore=tests/integration`: 1.627 passed, 2 skipped. `pytest src/data_collection/tests`: 489 passed, 21 skipped.
- `rebuild_product_e5.py --check` trên máy người dùng: `CLOUD_WEAVIATE_API_KEY` trong `src/data_collection/.env` đang trống → Weaviate Cloud từ chối; script đã sửa để dừng và báo thiếu khoá thay vì coi như collection chưa có. Catalog DB hiện có 3.991 search unit.

## Còn lại / rủi ro

- Thứ tự: merge vào `release-mvp-v2` (CI deploy) → chạy `rebuild_product_e5.py --apply` từ máy người dùng (xoá `Product` Cohere, embed 3.991 unit bằng e5) → backend tự nạp lại (thử lại mỗi 30 giây). Khoảng thời gian giữa deploy và lúc embed xong: Search/RecSys tắt.
- Không chạy `--apply` trước khi deploy: backend cũ (Cohere) không đọc được vector e5.
