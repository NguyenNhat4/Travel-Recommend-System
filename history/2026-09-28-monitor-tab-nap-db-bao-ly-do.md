# Monitor: tab Nạp DB báo rõ vì sao chưa có bảng

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Người dùng hỏi vì sao bấm tab "Nạp DB" không hiện gì. Nguyên nhân: lượt đang xem chưa có `db_load.jsonl` (lượt đang chạy
chưa tới bước nạp, hoặc lượt dừng trước bước nạp). `/api/db` trả lỗi, nhưng tab `db` không bắt lỗi như tab "Catalog cuối",
nên tab đứng ở "Đang tải…" và lỗi chỉ hiện thoáng qua trong ô thông báo chung. Chỉ sửa giao diện monitor;
không đổi PRD, contract, DDL.

## File thay đổi

- `src/data_collection/monitor_ui/index.html` — sửa: thêm `tabDb()`. Khi `/api/db` lỗi, tab in thông báo lỗi kèm lý do
  suy từ trạng thái lượt (đang chạy / chặn chất lượng / dừng trước bước nạp) và lỗi của lượt nếu có.
- `history/2026-09-28-monitor-tab-nap-db-bao-ly-do.md` — thêm: entry này.

## Quyết định

- Lý do lấy từ `S.runData` (đọc lúc mở lượt), không thêm API mới. Với lượt đang chạy, trạng thái có thể cũ vài giây;
  bấm lại tab là đủ.
- Nhánh có dữ liệu giữ nguyên `showList({kind:'db'})`.

## Kiểm tra

- Trên monitor local cổng 8765: lượt đang chạy `full-20260928T042452Z-100788` hiện "Lượt đang chạy, chưa tới bước nạp DB…";
  lượt lỗi `full-20260928T024657Z-14811` hiện "Lượt dừng trước bước nạp DB." kèm `RuntimeError: Nguồn trip-flights dừng với mã 1`.
  Console chỉ có các dòng 400 của chính `/api/db`, không có lỗi JavaScript.
- `pytest tests/test_monitor_public.py tests/test_live_monitor.py` (env `vsf`): **30 passed**.
- Chưa kiểm nhánh có bảng trên dữ liệu thật: máy chưa có lượt nào còn giữ `db_load.jsonl`.

## Còn lại / rủi ro

- Không có.
