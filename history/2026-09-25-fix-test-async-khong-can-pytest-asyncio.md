# Sửa test lưu hội thoại để không cần pytest-asyncio

- Ngày: 2026-09-25
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

CI của PR #29 (`pytest -q src/backend/tests`) fail 5 test: `async def functions are not natively supported`. Hai file test
của commit lưu hội thoại dùng `@pytest.mark.asyncio`, nhưng `src/backend/requirements.txt` không có `pytest-asyncio`
(máy local có cài sẵn nên không lộ lỗi).

## File thay đổi

- `src/backend/tests/unit/agents/test_conversation_archive.py` — sửa: 3 test chuyển từ `@pytest.mark.asyncio` sang hàm thường gọi `asyncio.run(...)`.
- `src/backend/tests/unit/infrastructure/test_conversation_store.py` — sửa: 2 test chuyển sang `asyncio.run(...)`.
- `history/2026-09-25-fix-test-async-khong-can-pytest-asyncio.md` — thêm: entry này.

## Quyết định

- Theo quy ước sẵn có của repo: các test async khác (`test_auth_redis.py`, `test_booking_postgres.py`...) gọi `asyncio.run`
  trực tiếp, `tests/conftest.py` cũng dựa vào điều đó. Không thêm `pytest-asyncio` vào requirements để khỏi đổi dependency
  của CI/CD backend.
- Không đổi logic test, chỉ đổi cách chạy coroutine.

## Kiểm tra

- `pytest -q -p no:asyncio` cho hai file trên: 5 passed (tắt plugin để giống CI).
- Chưa chạy lại toàn bộ `src/backend/tests` local; CI báo trước đó 525 passed, 19 skipped, chỉ 5 test này fail.

## Còn lại / rủi ro

Không có.
