# Sửa race trong test prewarm của RecsysRefresher (CI fail trên feat/search-embed-cache)

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/search-embed-cache
- Trạng thái: hoàn thành
- Phạm vi: backend tests

## Mục tiêu

CI của `feat/search-embed-cache` (push `abd6428`) fail 1/966: `test_prewarm_runs_once_in_background_after_the_first_publish_and_shutdown_waits_for_it`
thấy `stop.is_set() == True` lúc `fake_prewarm` chạy. Nguyên nhân: thread của `asyncio.to_thread(prewarm)` trên runner Linux được
lên lịch **sau** khi test đã gọi `refresher.stop()`; local Windows thì thread chạy trước nên pass. Code thật đúng với ca này
(prewarm thấy `stop` → trả `stopped=True` ngay, không ghi cache dở); chỉ test giả định thứ tự thread.

## File thay đổi

- `src/backend/tests/unit/api/test_recsys_refresher.py` — sửa: `fake_prewarm` đọc `stop.is_set()` **trước** khi bật
  `threading.Event` "đã vào"; test `await asyncio.to_thread(started.wait, 5)` trước khi `stop()` → thứ tự tất định; thêm
  `import threading`.

## Quyết định

- Không nới lỏng assertion (bỏ kiểm `stop`): điều test cần chứng minh là prewarm chạy sau publish đầu **và** shutdown chờ nó — giữ
  nguyên, chỉ ép thứ tự.

## Kiểm tra

- `pytest tests/unit/api/test_recsys_refresher.py` × 5 lần → 9 passed mỗi lần.
- `pytest src/backend/tests` → **928 passed, 21 skipped** (local Windows; CI Linux đếm 966 vì chạy pytest từ gốc repo, gom thêm test ngoài src/backend/tests/unit).

## Còn lại / rủi ro

- Push lại `feat/search-embed-cache`; CI chạy lại.
