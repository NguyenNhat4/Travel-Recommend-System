# Cloud: đồng bộ index `Product` với catalog VM (C6) — embed 168, xoá 0

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search (không đổi file source; ghi lịch sử vận hành dữ liệu production)
- Trạng thái: hoàn thành
- Phạm vi: dữ liệu Weaviate Cloud (production), docs plan

## Mục tiêu

Plan Day 3 C6: index Cloud `Product` (3.183 object, snapshot 23/09) thiếu vector cho các search unit mới của catalog VM
(crawler chạy hằng ngày) → backend VM không tìm được chúng qua vector và parity/bench thiếu dữ liệu. Người dùng xác nhận
"embed 157 / xoá 0" (01/10) sau khi thấy dry-run; BM25 và stopwords đã đủ từ trước nên không cần backfill hay PUT schema.

## Việc đã làm (không đổi file trong repo ngoài history/plan)

- Chạy job production `src.backend.jobs.embed_products` từ worktree `feat/search-embed-cache` (`abd6428`+) với `DATABASE_URL`
  = Postgres VM qua tunnel SSH (`127.0.0.1:15432/vota`), `WEAVIATE_URL`/`WEAVIATE_API_KEY`/`COHERE_API_KEY` từ `.env`
  (chỉ đặt qua biến môi trường, không ghi file trong repo).
- Dry-run ngay trước khi ghi: `searchUnits 3304 · unchanged 3136 · embedded 168 · deletedOrphans 0 · missingLexical 0`
  (157 → 168 vì catalog VM tăng thêm 11 unit trong 2 giờ). Guard trong script: dừng nếu `deletedOrphans != 0` hoặc `embedded > 400`.
- Ghi thật: **embedded 168, deletedOrphans 0, cohereCalls 2, rateLimited 0, 31,2 s**. Dry-run sau: `unchanged 3304 · embedded 0 ·
  deletedOrphans 0`. Cloud `Product` nay = catalog VM lúc 01/10 (3.304 unit; 47 object text cũ trước đó đã được embed lại).
- Chi tiết từng sản phẩm (`c6_index_detail.jsonl`) chỉ ở scratchpad ngoài repo; file biến môi trường tạm đã xoá sau khi xong.

## Quyết định

- Không xoá gì và không PUT schema: dry-run cho thấy Cloud không có object mồ côi, BM25 3.183/3.183, stopwords `none`.
- Cho các lần sau dùng `--lexical-only` (PR2) khi chỉ cần BM25; muốn đồng bộ vector thì chạy job đầy đủ **với DATABASE_URL VM**
  (bẫy: `.env` local trỏ Postgres seed 5432 — chạy `make index-vectors` với `.env` đó sẽ xoá ~400 object Cloud).
- Catalog VM tăng liên tục → index Cloud sẽ lại lệch; việc lâu dài là job index chạy định kỳ trên VM (ops), ngoài phạm vi bench.

## Kiểm tra

- Dry-run trước/sau như trên; `sb parity --mode weaviate` chạy trước đó đã PASS 20/20 (history cùng ngày), sau đồng bộ chưa chạy lại
  (168 unit mới nằm ngoài 20 câu parity trừ khi trùng tên).

## Còn lại / rủi ro

- Người dùng nên **đổi mật khẩu SSH/DB** đã dán trong hội thoại (30/09) — không nằm trong repo nhưng đã đi qua chat.
- `/api/v1/search` trên VM vẫn 500 (bước Cohere) — chưa liên quan tới index; chờ ops.
