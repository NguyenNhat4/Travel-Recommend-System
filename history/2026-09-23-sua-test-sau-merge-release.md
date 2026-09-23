# Sửa test còn fail sau khi merge release-mvp-v1

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: backend, agent

## Mục tiêu

Cho toàn bộ test backend pass sau `2026-09-23-merge-release-mvp-v1-vao-feat-auth.md`, entry này ghi hai lỗi còn lại
từ release.

## File thay đổi

- `src/backend/tests/contract/test_assistant_contract.py` — sửa: `Clients` giả khai `supports_catalog = True`.
- `src/backend/tests/unit/api/test_security.py` — sửa: token trong parametrize sinh lúc chạy test (lambda), thêm `ids`.

## Quyết định

- Release thêm cờ `supports_catalog` vào adapter client thật (`FixtureItineraryClients`, `ItineraryHttpClients`) và
  composition root chỉ nối catalog khi cờ bật. Client giả của test contract có `list_destinations` nhưng thiếu cờ, nên
  agent không kiểm điểm đến và trả `NO_RESULTS` thay vì 422 `UNSUPPORTED_DESTINATION`. Sửa test giả cho khớp adapter,
  không đổi code chạy thật.
- Token JWT tạo lúc import hết hạn sau 5 phút; bộ test backend chạy khoảng 5 phút 20 giây nên case
  `cdp_user_id=''` báo `TOKEN_EXPIRED`. Sinh token lúc chạy test.

## Kiểm tra

- `CUDA_VISIBLE_DEVICES="" pytest src/backend/tests`: 168 passed, 2 skipped (integration Postgres, cần
  `RUN_POSTGRES_INTEGRATION=1` và database đã seed).
- `npm test` (src/frontend): 48 passed; `tsc --noEmit`: sạch.

## Còn lại / rủi ro

- Hai test integration Postgres chưa chạy vì máy không có Postgres đang chạy.
