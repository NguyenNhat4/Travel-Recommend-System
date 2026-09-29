# Sửa khởi tạo crawler monitor

- Ngày: 2026-09-29
- Tác giả: Khoa15
- Nhánh: khoa/split-crawler-workflow
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Khắc phục lỗi crawler monitor thoát với `NameError: name 'Monitor' is not defined` khi chạy trên VM.

## File thay đổi

- `src/data_collection/monitor.py` — khởi tạo `FreshMonitor` đúng các thư mục state, run và log.
- `history/2026-09-29-fix-crawler-monitor-bootstrap.md` — ghi lịch sử thay đổi.

## Quyết định

- `monitor.py` hiện chỉ định nghĩa `FreshMonitor`; hàm `main` được sửa để dùng class này và dùng cùng instance cho HTTP handler.

## Kiểm tra

- `python3 -m py_compile src/data_collection/monitor.py`: sẽ chạy sau khi sửa.
- YAML/workflow checks: đã pass trước thay đổi này.

## Còn lại / rủi ro

- Cần build/publish image crawler mới và rerun workflow để VM nhận bản sửa.
