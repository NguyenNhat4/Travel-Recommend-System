# Append CDP để đo lại RecSys

- Ngày: 2026-10-05
- Tác giả: người dùng / Codex
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: cdp, data, evaluation, docs

## Mục tiêu

Làm giàu CDP staging bằng dữ liệu demo bổ sung, giữ lịch sử cũ và bàn giao bộ snapshot/split mới để tqanh đo lại RecSys.

## File thay đổi

- `src/data_collection/seed/append_histories.py` — tạo artifact versioned và append transactional, idempotent.
- `src/data_collection/seed/config.py` — profile `append-v1`, các tham số nằm cùng nơi với seed.
- `src/data_collection/tests/test_append_histories.py` — kiểm checksum, namespace, rollback, idempotency và dữ liệu cũ.
- `docs/spec/MOCK_DATA_SPEC.md` — quy tắc append-v1.
- `docs/guide/recsys-append-v1-snapshot.md` — dựng DB và lệnh tqanh chạy đo.
- `src/evaluation/reports/eval-2026-10-05-cdp-append-recsys-handoff.md` — trạng thái nạp và handoff.
- `src/evaluation/recsys_bench/frozen/split-*-append-v1-asof20261005.json` — bốn split mới.
- `src/data_collection/snapshots/2026-10-05-recsys-append-v1/` — snapshot tổng hợp có checksum.

## Quyết định

- Không chạy `--history-only`; batch chỉ thêm 5.000 khách mới và 32.896 event, namespace riêng.
- Không thêm schema, app user, booking, Insider hay replica. Không dùng backup/restore vì không xóa dữ liệu cũ.
- Primary đã nạp thành công; fingerprint phần dữ liệu cũ trùng 100%. Nạp lại cùng batch là no-op.
- Các ngưỡng `db/verify.sql` của demo không áp cho batch eval; report ghi rõ ba FAIL quy mô sau append.

## Kiểm tra

- `test_append_histories.py`, `test_seed_eval_profile.py`, `test_seed_histories.py`, `src/evaluation/recsys_bench/tests`: 163 passed, 1 warning.
- Recommendation criteria: 4 passed.
- Diễn tập DB local: append, append lần hai, rollback thiếu sản phẩm và phát hiện payload đã đổi đều PASS.
- Primary: 5.000 profile, 32.896 event append; dữ liệu cũ CDP/catalog/app/booking/payment giữ nguyên.
- `db/verify.sql`: 20/23 PASS; 3 FAIL là ngưỡng demo đã biết.

## Còn lại / rủi ro

- Chưa có điểm RecSys trên snapshot append; tqanh cần chạy đủ engine/MPD/CF với vector khớp catalog và cập nhật report kết quả.
- Dữ liệu tổng hợp chỉ dùng để so sánh trong giả định generator, không đại diện khách production.
