# Gợi ý: đọc tối đa 500 event mỗi khách (CDP spec §6)

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành (bench HTTP chưa chạy được, xem "Còn lại")
- Phạm vi: backend, evaluation, docs
- Liên quan: `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` (giai đoạn 2, bước 4)

## Mục tiêu

`hop-dong-tich-hop-cdp.md` §6 quy định đọc tối đa 500 event mới nhất cho mỗi lần tính gợi ý. Nhưng `PostgresCdpReader.events_for_user` đọc toàn bộ lịch sử, không có `LIMIT` và không có thứ tự phụ khi trùng thời điểm. Tài khoản persona demo dùng chung bị nhiều người test nên tích luỹ `product_view` không giới hạn, kéo theo lượt `vectors()` lịch sử phình ra. Giới hạn này cũng cần cho dấu vân tay event của cache (giai đoạn 3). Phục vụ NFR-PERF-01.

## File thay đổi

- `src/backend/app/application/ports/cdp_client.py` — sửa: thêm `HISTORY_MAX_EVENTS = 500`; docstring `events_for_user` ghi thứ tự và giới hạn.
- `src/backend/app/infrastructure/cdp/postgres_cdp_reader.py` — sửa: tham số `history_limit` (mặc định 500); SQL `ORDER BY "timestamp" DESC, event_id ASC LIMIT %s`.
- `src/backend/app/application/recommendation/use_cases.py` — sửa: cắt `[:HISTORY_MAX_EVENTS]` trên đường đọc CDP (cho adapter sau này); đường `events=` không cắt.
- `src/evaluation/recsys_bench/parity.py` — sửa: `compare_user` cắt lịch sử cùng mức, để parity offline == HTTP còn đúng với khách có hơn 500 event.
- `src/backend/tests/unit/infrastructure/test_postgres_cdp_reader.py` — sửa: thêm test câu SQL (thứ tự, thứ tự phụ, `LIMIT`) và tham số.
- `src/backend/tests/unit/application/test_recommendation_history_cap.py` — thêm: đường reader tối đa 500 event; đường `events=` không cắt.
- `src/evaluation/recsys_bench/tests/test_parity.py` — sửa: thêm test khách 520 event trùng giữa production và harness.
- `docs/spec/hop-dong-tich-hop-cdp.md` — sửa: §6 quy tắc 1 ghi đã cài, kèm thứ tự phụ.
- `history/2026-10-12-recsys-doc-toi-da-500-event.md` — thêm: entry này.

## Quyết định

- **Thứ tự phụ `event_id ASC`.** Harness đọc `all_events` theo khách, thời điểm, `event_id` tăng dần, rồi `parity.events_desc` sort ổn định giảm dần theo thời điểm. Vì vậy khi trùng thời điểm thì `event_id` tăng dần: production khớp harness, kể cả ở mốc cắt 500.
- **Cắt cả ở engine** (trên đường đọc CDP), để adapter sau này (`HttpCdpClient`) không vô tình bỏ giới hạn. Đường `events=` của harness (`OfflineEngine`) không cắt, nên `configHash` và baseline_v6 không đổi.
- **Hằng đặt ở port** `cdp_client.py`, không trong `profile.py`, vì bench băm các hằng chữ hoa của `profile.py`.
- **Thay đổi có chủ đích:** xếp hạng chỉ đổi với khách có hơn 500 event.

## Kiểm tra

- `pytest -q -p no:cacheprovider` trên `test_postgres_cdp_reader.py`, `test_recommendation_history_cap.py` và `src/evaluation/recsys_bench/tests/test_parity.py`: 28 passed.
- `pytest -q -p no:cacheprovider src/backend/tests/unit/application src/backend/tests/unit/infrastructure src/evaluation/recsys_bench/tests`: 804 passed, 8 skipped.

## Còn lại / rủi ro

- **Chưa đếm được số khách có hơn 500 event.** Cache JSONL của bench (`bench_out/recsys/cache/events-a25cd720-all.jsonl`, 01/10) không có trong worktree này, và container prodcopy không còn. Sau khi deploy thì đọc `events_read == 500` trong log `recsys.recommend`.
- **Parity HTTP 60/60 chưa chạy được** (không có môi trường prodcopy). Parity trong tiến trình pass.
