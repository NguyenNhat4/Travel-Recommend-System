# Đề xuất: monitor sơ đồ quan hệ DB, luồng dữ liệu web / agent, hoạt động realtime

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người yêu cầu: "Tôi muốn sẽ có monitor trạng thái của DB, có được sơ hồ các mỗi quan hệ của các bảng, dễ nhìn, trực quang,
data cho agent và web sẽ lấy từ đâu, có fetch được trạng thái lúc nó gọi không... tôi muốn realtime". Vượt phạm vi đề xuất tab
DB đã áp dụng → đề xuất mới, chờ chốt (AGENTS.md mục 8).

## File thay đổi

- `docs/prd/update/2026-09-30-monitor-trang-thai-db-realtime.md` — thêm: đề xuất 2 giai đoạn, `chờ chốt`.
- `history/2026-09-30-de-xuat-monitor-trang-thai-db-realtime.md` — thêm: entry này.

## Quyết định

- Kiểm code backend: catalog nạp vào bộ nhớ (`catalog_refresh_seconds` 900); các bảng backend đọc / ghi (grep SQL trong
  `src/backend/app`); `app.search_logs`, `app.recommendation_logs` không nơi nào ghi; backend chưa có `/metrics` dù PRD §5 yêu
  cầu; agent gọi công cụ backend (`agents/tools/itinerary_gateway.py`).
- Kiểm PostgreSQL: `pg_stat_user_tables` có số đọc / ghi theo bảng; `pg_stat_statements` chưa cài (không dùng).
- Tách giai đoạn 1 (chỉ monitor) và giai đoạn 2 (backend) vì giai đoạn 2 thuộc workstream Backend.

## Kiểm tra

- Chưa sửa code.

## Còn lại / rủi ro

- Chờ người yêu cầu chốt (có thể chỉ chốt giai đoạn 1). Chưa commit.
