# Đánh dấu checklist search bench: điều kiện tiên quyết + ngày 1 của Người B

- Ngày: 2026-09-24
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu tick vào `docs/spec/bench/search-eval-checklist.md` những việc đã làm xong ở ngày 1. Bằng chứng nằm ở `2026-09-23-search-bench-khung-va-catalog.md` và `2026-09-23-search-bench-embed-weaviate-ngay-1.md`.

## File thay đổi

- `docs/spec/bench/search-eval-checklist.md` — sửa: tick 12 mục, mỗi mục kèm một ghi chú ngắn (ngày, số đo).
  - "Trước ngày 1": endpoint Cohere, `COHERE_API_KEY`, `products.jsonl`, Docker + RAM, nhánh/thư mục.
  - Ngày 1 — B: 5 mục.
  - Sync cuối ngày: B demo.
  - Ngày 2 — B: `sb tokens`, đã chạy sớm và qua gate.
- `history/2026-09-24-tick-checklist-search-bench-ngay-1.md` — thêm: entry này.

## Quyết định

- Chỉ tick việc có bằng chứng chạy thật: lệnh, số đo trong hai entry lịch sử ngày 23/09. RAM 31,5 GB đo bằng `Win32_ComputerSystem`.
- **Không** tick:
  - "Mentor xác nhận bằng văn bản": chưa có.
  - Mọi mục của Người A ngày 1: draft gold do A làm; công cụ `sb catalog vocab` đã sẵn sàng.
  - "A đưa B `gold/drafts.txt`".
  - Các mục ngày 2 còn lại: embed toàn catalog, `gold pool`, chia pool.

## Kiểm tra

- `grep -c "^- \[x\]" docs/spec/bench/search-eval-checklist.md`: 12.

## Còn lại / rủi ro

- Mục collection có ghi chú `stopwords_preset: none` là khoá *đề xuất*, cần Người A / mentor xác nhận (xem `2026-09-23-search-bench-embed-weaviate-ngay-1.md`).
