# Add p99 recommender rank runtime

- Ngày: 2026-09-22
- Tác giả: người yêu cầu / Codex
- Nhánh: codex/recsys-10-architectures
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Bổ sung p99 thời gian xếp hạng vào bộ metric benchmark để quan sát tail latency cùng với p95.

## File thay đổi

- `src/evaluation/benchmark.py` — sửa: trả `p99_runtime_ms` cho benchmark, gồm cả trường hợp không có target.
- `src/evaluation/streamlit_app.py` — sửa: hiển thị p99 trong bảng và cho chọn vẽ biểu đồ.
- `src/evaluation/README.md` — sửa: mô tả cả p95 và p99.
- `src/evaluation/tests/test_temporal.py` — sửa: kiểm tra giá trị p99 từ latency mẫu.
- `history/2026-09-22-recsys-p99-runtime.md` — thêm: entry lịch sử task.

## Quyết định

- Dùng cùng mẫu latency mỗi user đã đo cho p95, lấy `numpy.percentile(..., 99)`; không bao gồm model fit hay tải embedding.
- Giữ key `p99_runtime_ms` nhất quán trong bảng kết quả, CSV và JSON.

## Kiểm tra

- Test hồi quy được chạy trước implementation và thất bại với `KeyError: 'p99_runtime_ms'` như kỳ vọng.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider src/evaluation/tests` — PASS sau khi triển khai.
- `git diff --check` — PASS.

## Còn lại / rủi ro

- p99 trên số user nhỏ dao động nhiều; đọc cùng số holdout users và các metric chất lượng.
