# Backfill property BM25 trên Weaviate Cloud — runbook, chưa chạy

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/recsys-harness
- Trạng thái: dang dở
- Phạm vi: docs
- Bị thay thế bởi: `2026-09-30-backfill-bm25-cloud-kiem-nguon-db.md`

## Mục tiêu

Lịch 10 ngày, Day 1 phần C (`docs/plan/2026-09-28-lich-10-ngay-3-engine.md`): backfill property BM25 (`nameAscii`, `searchTextAscii`) cho collection `Product` trên Weaviate Cloud, để `/search` trên cloud chạy hybrid thật thay vì dense-only (`docs/plan/2026-09-28-summary-search-recsys-benchmark.md` §1.5 mục 4). Day 2 (parity cloud vs local, latency breakdown) phụ thuộc bước này.

## File thay đổi

- Không có file code. Tick và ghi chú trong lịch nằm ở entry `2026-09-29-recsys-harness-day1.md`.

## Quyết định

- **Không chạy từ máy dev.** Máy làm B/C không có quyền VM hay khoá Weaviate Cloud (`.env` chỉ trỏ Weaviate local). Quy tắc 24/09: collection Cloud chỉ do job trên VM ghi, vì `embed_products` tính phần "đổi" và "mồ côi" theo `DATABASE_URL` của máy chạy, rồi **xoá vector mồ côi** trên Cloud (`src/backend/jobs/embed_products.py`, `.env.example`, `history/2026-09-24-luong-cao-index-backend-sau-audit.md`).
- "Bật `SEARCH_HYBRID=true` trên cloud" không phải việc sửa cấu hình: giá trị mặc định đã là `true` (`core/config.py`) và `ops/` không ghi đè. Việc thật là backfill rồi xác nhận qua `diagnostics`.

## Runbook (chạy trên VM, với env của job cào: `DATABASE_URL` là DB đã sinh vector cho Cloud)

0. `curl -s "$WEAVIATE_URL/v1/.well-known/ready"` — cluster có thể là Sandbox 14 ngày (ghi nhận ~23/09).
1. `python -m src.backend.jobs.embed_products --dry-run`. Kỳ vọng `searchUnits` = số search unit của DB VM (3.183 ở snapshot 24/09), `embedded 0`, `deletedOrphans 0`, `missingLexical` ≈ `searchUnits`. **Nếu `embedded > 0` hoặc `deletedOrphans > 0` thì dừng**: DB không khớp Cloud. Lưu ý: dry-run vẫn POST hai property BM25 còn thiếu lên schema (`ensure_collection` chạy trước khi xét `--dry-run`); việc này vô hại.
2. Đặt stopwords `none` trước khi backfill (code chỉ đặt lúc tạo collection mới; preset `en` bỏ các âm tiết như "an" của Hội An): `GET /v1/schema/Product`, sửa `invertedIndexConfig.stopwords.preset` thành `none`, `PUT /v1/schema/Product`, rồi GET lại để xác nhận (`history/2026-09-25-search-hybrid-bm25-rrf.md`).
3. `python -m src.backend.jobs.embed_products --backfill-lexical` → `backfilledLexical` = `missingLexical` ở bước 1 (chỉ PATCH, không gọi Cohere).
4. Dry-run lại → `missingLexical 0`. Cloud tắt GraphQL, nên đếm bằng report của job hoặc REST `/v1/objects`.
5. Xác nhận trên backend VM: `GET /api/v1/search?q=VinWonders&limit=5` → `diagnostics.searchMode = HYBRID_CANDIDATE_SCORE`, `lexicalCandidates > 0`; thử thêm `q=Vinpeal Resort Nha Trang` (có `corrections`) và `q=KS biển tại NT` (có `normalizedQuery`).

## Kiểm tra

- Chưa chạy bước nào trên Cloud.
- Đã kiểm trên máy này: Weaviate local của compose có collection `Product` với vector `embed-multilingual-v3.0:catalog-text-v2`, stopwords preset `en` (`GET /v1/schema/Product`).

## Còn lại / rủi ro

- Cần người giữ quyền VM chạy runbook trên, rồi ghi số vào lịch (mục C Day 1) và tạo entry history mới đổi trạng thái.
- Weaviate local cũng đang dùng stopwords `en`; nếu Day 2 so parity cloud vs local thì nên đặt `none` cho cả hai.
