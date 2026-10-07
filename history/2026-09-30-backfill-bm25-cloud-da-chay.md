# Đã backfill BM25 cho Weaviate Cloud (3.183 object) và đổi stopwords sang none

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/recsys-harness
- Trạng thái: hoàn thành
- Phạm vi: docs
- Thay thế: `2026-09-30-backfill-bm25-cloud-kiem-nguon-db.md` (trạng thái "dang dở": phần ghi chưa chạy)

## Mục tiêu

Người dùng cho phép chạy phần ghi của runbook đã sửa trong `2026-09-30-backfill-bm25-cloud-kiem-nguon-db.md`: đưa dữ liệu BM25 (`nameAscii`, `searchTextAscii`) lên collection `Product` của Weaviate Cloud để `/search` trên cloud chạy hybrid thật (lịch 10 ngày, Day 1 phần C; M4).

## File thay đổi

- `history/2026-09-30-backfill-bm25-cloud-da-chay.md` — thêm: entry này.
- `history/2026-09-30-backfill-bm25-cloud-kiem-nguon-db.md` — sửa: chỉ thêm dòng "Bị thay thế bởi".
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: tick mục backfill (Day 1 C) kèm số; thêm dòng Day 2 ở §8 Log.
- Không đổi code. Bản sao schema cloud trước khi sửa lưu ở `bench_out/cloud-product-schema-before-2026-09-30.json` (gitignore, không commit).

## Quyết định

- Nguồn DB là Postgres compose local (seed snapshot 2026-09-23, `as_of` 2026-09-24, 3.183 search unit), truyền bằng biến môi trường `DATABASE_URL`. Không dùng DB trên VM vì với DB đó job sẽ xoá 285 vector và embed lại 158 (xem entry thay thế).
- Làm đúng thứ tự: dry-run → lưu schema → đổi stopwords → backfill → dry-run lại → truy vấn BM25 trên cloud.

## Kiểm tra

- Trước khi ghi: Postgres local có 7.145 event, 3.183 search unit. `embed_products --dry-run` (Weaviate Cloud): `searchUnits 3183, embedded 0, deletedOrphans 0, missingLexical 3183`.
- `PUT /v1/schema/Product` với `invertedIndexConfig.stopwords.preset = none`: HTTP 200. So với schema đã lưu: chỉ `stopwords` đổi; khối `properties` chỉ khác thứ tự trả về, không trường nào đổi.
- `embed_products --backfill-lexical`: `backfilledLexical 3183`, `embedded 0`, `deletedOrphans 0`; mất 16 phút 9 giây (mỗi object một PATCH tới cluster `eu-central-1`).
- Dry-run lại: `missingLexical 0`.
- BM25 trực tiếp trên cloud qua `WeaviateVectorSearch.bm25`: "VinWonders" 10 hit (đầu là các sản phẩm VinWonders Nha Trang); "Hội An" 10 hit, toàn khách sạn Hội An (âm tiết "an" không còn bị bỏ như preset `en`); "Vinpearl Nha Trang" 10 hit.
- **Chưa kiểm `/search` đầu-cuối:**
  - Khoá Cohere trong `.env` là khoá trial, đã hết hạn mức 1.000 lượt/tháng (HTTP 429), nên không embed được truy vấn trên máy này.
  - Không vào được backend VM: tài khoản SSH chỉ được forward tới DB (`administratively prohibited` khi mở cổng 8000).

## Còn lại / rủi ro

- Người có quyền backend VM gọi `GET /api/v1/search?q=VinWonders` và xác nhận `diagnostics.searchMode = HYBRID_CANDIDATE_SCORE`, `lexicalCandidates > 0`. Không cần khởi động lại backend: property BM25 và stopwords có hiệu lực ngay trên collection.
- Nếu backend VM dùng chung khoá Cohere trial này thì `/search` trên cloud đang lỗi 429 cho tới khi đổi khoá Production hoặc sang tháng mới — cần kiểm ngay, ảnh hưởng cả đo latency Day 2 và quyết định embedding Day 5.
- Collection cloud vẫn lệch DB trên VM: 110 unit của VM chưa có vector, 48 unit có vector của text cũ, 285 object cloud không còn trong DB VM. Muốn khớp thì cần một lần index lại có chủ đích với DB VM (sẽ gọi Cohere 158 lần và xoá 285 object).
- Object mới do job index ghi sau này đã tự có property BM25; stopwords `none` giữ nguyên.
- Khôi phục stopwords cũ (nếu cần): PUT lại bản schema đã lưu trong `bench_out/`.
- Mật khẩu SSH và DB đã được dán vào hội thoại; nên đổi.
