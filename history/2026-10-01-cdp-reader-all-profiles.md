# Backend: `PostgresCdpReader.all_profiles()` cho đánh giá offline (sanity của recsys_bench)

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: backend (adapter CDP đọc, port, fake test), docs spec CDP

## Mục tiêu

Plan Day 3 Track B Phase 2: `sanity.py` cần đối chiếu `cdp.profiles.lifecycle_stage` / `days_since_last_booking` seed đã ghi
với bản tính lại từ event (phát hiện seed sai hoặc DB lệch). Harness không được SQL thẳng vào `cdp.*` (AGENTS.md §6.1) nên
thêm một method đọc lô vào adapter hiện có, cùng kiểu `all_events` (29/09). Phục vụ FR-REC-01/02, test-plan §2.5.

## File thay đổi

- `src/backend/app/infrastructure/cdp/postgres_cdp_reader.py` — sửa: `_query(..., mapper=)`; thêm `_PROFILE_COLUMNS`,
  `_profile_to_cdp`, `all_profiles()` (8 cột camelCase, `ORDER BY cdp_user_id`, không `statement_timeout`).
- `src/backend/app/application/ports/cdp_client.py` — sửa: `CdpHistoryReader.all_profiles()` (docstring: chỉ đánh giá offline).
- `src/backend/tests/fakes/jsonl_cdp_reader.py` — sửa: `all_profiles()` trả `[]`.
- `src/backend/tests/unit/infrastructure/test_postgres_cdp_reader.py` — thêm 2 test (SELECT lô, map camelCase, NULL; sự cố →
  `CdpUnavailableError`).
- `docs/spec/hop-dong-tich-hop-cdp.md` — sửa: §7 thêm dòng `all_profiles()`.

## Quyết định

- Chỉ 8 cột harness cần (không opt-in, không timestamps) — tên cột opt-in còn chờ reviewer CDP (AGENTS.md §6.4).
- Không đổi hành vi request nào; `events_for_user` / `purchase_events` giữ nguyên.

## Kiểm tra

- `pytest src/backend/tests/unit/infrastructure/test_postgres_cdp_reader.py` → **181 passed** (`tests/unit/infrastructure/test_postgres_cdp_reader.py` + `tests/unit/application`); bộ đầy đủ backend → xem history `2026-10-01-recsys-sanity-parity-http.md`.

## Còn lại / rủi ro

- `HttpCdpClient` (CDP thật) sau này cần endpoint tương đương hoặc harness bỏ kiểm tra này.
