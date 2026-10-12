# FakeEmbedder dùng hash ổn định, sửa test AC-REC-02 flaky

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent), sửa theo CI check fail của PR #157
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

CI của PR #157 fail ở `test_ac_rec_02_booking_prioritises_flights_and_activities_at_the_destination` (`src/backend/tests/unit/application/test_engines.py`). Test đòi ít nhất một món gợi ý có `because` không rỗng, nhưng `FakeEmbedder` băm text bằng `hash()` của Python. `hash()` của str thay đổi theo tiến trình (`PYTHONHASHSEED`), nên vector giả và cosine thay đổi giữa các lần chạy.

## File thay đổi

- `src/backend/tests/conftest.py` — sửa: seed của `FakeEmbedder._v` dùng 4 byte đầu của SHA-256 thay vì `abs(hash(t))`; thêm `import hashlib`.

## Quyết định

- Sửa ở fake, không nới assertion: vector giả phải xác định để test lặp lại được.

## Kiểm tra

- Bản gốc: test thất bại với `PYTHONHASHSEED` 13, 14, 20, 24. Trong các seed 0–5 không fail, nên lỗi chỉ xuất hiện với một số seed.
- Bản sửa: pass với các seed 0–4 và 13, 14, 20, 24.
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q src/backend/tests` (Python 3.12, không cài torch): `2814 passed, 36 skipped`.

## Còn lại / rủi ro

- `src/evaluation/search_bench/tests/test_latency_parity.py:59` có `abs(hash(q))` để tạo id giả trong bài đo latency. Chưa đổi; nếu có flaky tương tự cần xử lý riêng.
- Môi trường local không cài được torch, nên chạy suite không có torch và transformers. Test AC-REC-02 không dùng torch.
