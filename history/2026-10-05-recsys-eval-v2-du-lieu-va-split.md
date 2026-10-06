# RecSys eval-v2: bộ dữ liệu đánh giá đủ tín hiệu, chế độ `--history-only` cho staging, split `nexttrip` / `coldstart`

- Ngày: 2026-10-05
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành (chưa commit; chưa nạp staging — người có quyền ghi chạy)
- Phạm vi: data, evaluation, docs
- Phục vụ: FR-REC-01..04, FR-CDP-01; test-plan §2.5; ADR 2 (split "next trip", nhãn `targetInOwnHistory`)

## Mục tiêu

Người dùng muốn dữ liệu đủ để đánh giá mọi tín hiệu RecSys (CF, chuyến kế tiếp, bỏ giỏ, khách mới) cho tqanh123 tự đo, và đưa lịch sử giàu
event lên DB chung để demo. Bộ demo / enriched v1 chỉ ~270 khách quay lại, 0 lần bỏ giỏ, temporal 98 khách.

## File thay đổi

- `src/data_collection/seed/config.py` — sửa: `ABANDONED_CART_RATE` (0 ở demo), `ABANDONED_SAME_DEST_RATE`, `ABANDONED_DAYS_BEFORE`, `PROFILES["eval-v2"]`.
- `src/data_collection/seed/seed_histories.py` — sửa: `Builder.abandoned` (xem → giỏ, không mua, không gid), chèn bỏ giỏ trong `plan_generic`,
  `profile_overrides` + `generate(profile=)`, `--profile`; report thêm khách quay lại / bỏ giỏ.
- `src/data_collection/seed/database.py` — sửa: `load_history` (`--history-only`), `recompute_profiles`, `previous_seed_as_of`,
  `history_backup` / `history_restore`.
- `src/data_collection/seed/__main__.py` — sửa: `--profile`, `--history-only`, `--keep-events-since`, `--drop-missing-products`,
  `--history-backup`, `--history-restore`.
- `src/data_collection/tests/test_seed_eval_profile.py` — thêm: 7 test (demo không đổi, tất định, khách quay lại, bỏ giỏ, cap, persona, profile lạ).
- `src/evaluation/recsys_bench/splits.py` — sửa: `next_trip_split` (`as_of` = lúc bắt đầu duyệt chuyến mới), `cold_start_split`, `history_labels`;
  `PARAM_KEYS` thêm `minEvents`, `browseDays` (split cũ giữ sha).
- `src/evaluation/recsys_bench/bench.py` — sửa: `per_user` mang `targetInOwnHistory` / `targetInOwnCart` / `targetViewed`.
- `src/evaluation/recsys_bench/__main__.py` — sửa: `--kind` / `--split` nhận `nexttrip`, `coldstart`.
- `src/evaluation/recsys_bench/tests/test_splits_nexttrip_coldstart.py` — thêm: 3 test.
- `src/evaluation/recsys_bench/frozen/split-{llbo,temporal,nexttrip,coldstart}-evalv2-asof20261005.json` — thêm: 4 split đóng băng.
- `src/evaluation/reports/eval-2026-10-05-recsys-eval-v2.md` — thêm: report bàn giao (dữ liệu, split, kết quả chạy thử, lệnh cho tqanh).
- `docs/spec/MOCK_DATA_SPEC.md` — sửa: §4.1 bộ `eval-v2` + `--history-only` (bảng xử lý, diễn tập).
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §3.2 split mới + nhãn.
- `history/2026-10-05-recsys-eval-v2-du-lieu-va-split.md` — thêm: entry này.

## Quyết định

- Người dùng chốt: 5.000 khách, ≈ 40 % khách có mua quay lại, ≈ 20 % chuyến bỏ giỏ; thêm chế độ mới, mặc định không đổi (demo trùng sha
  `5fdbb170…` trước / sau); hiệu chỉnh trọng số số chuyến `(0,50; 0,25; 0,15; 0,10)` / `(0,70; 0,30)`, `ABANDONED_CART_RATE` 0,22 bằng mô phỏng.
- Giỏ của lần bỏ giỏ không mang `event_group_id` (spec chốt 21/09: chỉ purchase có gid, như app thật) — nối giỏ với chuyến là việc của harness.
- Staging: agent không ghi (không quyền, không dùng mật khẩu người dùng đưa trong chat); người dùng / người phụ trách tự chạy lệnh.
- Review (người dùng dán, 05/10) chỉ ra bản đầu `--history-only` xoá event web của tài khoản seed, hồ sơ lệch đơn giữ lại, cho qua 46 event thiếu
  sản phẩm, chưa diễn tập khôi phục → sửa cả bốn; persona P1–P4 theo phương án B1 (người dùng chốt): reset về kịch bản, giữ đơn thật.
- `nexttrip`: bản đầu đặt `as_of` = lúc mua → 98 % target có trong lịch sử (lượt xem của chính chuyến mới) → đổi sang lúc bắt đầu duyệt (7 ngày
  trước purchase), còn 28/1.493 (do lần bỏ giỏ trước).

## Kiểm tra

- `pytest data_collection/tests/test_seed_histories.py test_seed_eval_profile.py`: 26 passed; toàn bộ `data_collection/tests`: 467 passed,
  4 failed — 4 test normalise / live monitor fail y hệt trên HEAD (không liên quan).
- `pytest src/evaluation/recsys_bench/tests`: 130 passed; split cũ `split-{llbo,temporal}-asof20260924.json` verify lại trên DB bench: sha khớp.
- DB `vota_recsys_evalv2_20261005`: `verify.sql` FAIL đúng 3 dòng quy mô (5.000 profile, 32.782 event, 36 event/khách).
- Diễn tập staging (`vota_staging_sim`, seed demo `as_of` 30/09 + hoạt động web 02–04/10, 3 sản phẩm xoá): không cờ → dừng (88 event); có
  `--drop-missing-products` → giữ event web `test01`, đơn thật + event mua P1, tài khoản `VPW…`, mật khẩu đã đổi; reset event web P1; 0 profile
  lệch số đơn; `--history-restore` → hash event / profile / đơn seed trùng 100 % trước khi nạp.
- Chạy thử eval-v2 4 split (engine + baseline toàn bộ; CF 200 khách): exit 0, `vectorsMissing 0`, `expectFailed []`, leak 0; số ở report.

## Còn lại / rủi ro

- Nạp staging: người có quyền ghi chạy `--history-only --drop-missing-products --history-backup <file>` (staging thiếu 46 sản phẩm), khởi
  động lại backend. Insider không cập nhật.
- tqanh123: chạy CF đủ khách trên 4 split (mục 5 report). Engine hoà mpd ở `nexttrip` — hướng cải thiện chính.
- Không có test DB tự động cho `load_history` / `history_restore` (cần Postgres); đã diễn tập tay, ghi ở spec §4.1.
- `history/2026-10-05-recsys-web-latency.md` (đã commit trong `bb41479`) được bổ sung dòng đo từng bước cùng ngày trước đó.
