# Clear stale recommender benchmark results

- Ngày: 2026-09-22
- Tác giả: người yêu cầu / Codex
- Nhánh: codex/recsys-10-architectures
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Ngăn Streamlit crash khi session còn giữ benchmark rows được tạo trước khi metric p99 được thêm.

## File thay đổi

- `src/evaluation/benchmark.py` — sửa: thêm kiểm tra phiên bản hình dạng benchmark rows có metric p99.
- `src/evaluation/streamlit_app.py` — sửa: xóa kết quả và metadata cũ, hướng dẫn chạy benchmark lại thay vì truy cập thiếu key.
- `src/evaluation/tests/test_temporal.py` — sửa: kiểm tra nhận diện row cũ thiếu p99.
- `history/2026-09-22-fix-stale-recsys-benchmark-state.md` — thêm: entry lịch sử task.

## Quyết định

- Không mặc định p99 bằng 0 cho báo cáo cũ vì latency mẫu gốc không được lưu để tính lại. Xóa snapshot cũ và yêu cầu chạy benchmark mới.
- Restart riêng Streamlit container khi nâng phiên bản app tại chỗ để giải phóng cả session state lẫn module Python đã import; giữ nguyên PostgreSQL và dữ liệu seed.

## Kiểm tra

- Test hồi quy được chạy trước implementation và thất bại vì helper chưa tồn tại như kỳ vọng.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider src/evaluation/tests` — PASS sau khi triển khai.
- `git diff --check` — PASS.
- `docker restart recsys-10-streamlit` — PASS; sau restart, p99 helper import được và Streamlit health trả HTTP 200.

## Còn lại / rủi ro

- Session đang mở sẽ cần chạy lại benchmark một lần để sinh lại các hàng có p99.
