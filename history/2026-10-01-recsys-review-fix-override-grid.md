# RecSys harness — sửa theo review Phase 2–3, `run --override` (M7) và grid-search lần 1 trên temporal, đề xuất M6

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/phan-con-lai (tách từ `bench/embed-search @ 33ca23c`, gộp lại để test)
- Trạng thái: hoàn thành
- Phạm vi: evaluation (recsys_bench), docs spec/plan, docs/prd/update (đề xuất chờ chốt)

## Mục tiêu

"Phần còn lại" sau Track B Phase 0–3: (1) sửa các lỗi review đối kháng của Phase 2–3 (history
`2026-10-01-recsys-sanity-parity-http.md` ghi review đang chạy lúc commit); (2) lịch 10 ngày Day 5 B "grid-search lần 1: event
weight, half-life, dormant 90 vs 180, công thức điểm" — cần ghi đè hằng engine trong tiến trình mà không sửa production; (3) findings
4–5 (§4.11) là đổi hành vi engine → đề xuất PRD. Phục vụ FR-REC-01/02, M6, M7.

## File thay đổi

- `src/evaluation/recsys_bench/data_source.py` — sửa: `clear_event_cache` xoá cả cache `profiles-*.jsonl` (review: `sanity` không
  `--refresh` từng so event mới với profile cũ).
- `src/evaluation/recsys_bench/sanity.py` — sửa: `lifecycle_recomputed(…, index)` kiểm thêm `lifetimeOrderCount`,
  `purchasedVerticals`, `lastDestination` (khi có index); thêm kiểm tra cứng `profiles_cover_events`.
- `src/evaluation/recsys_bench/parity.py` — sửa: `make_users(…, profiles=)` phân tầng theo `cdp.profiles.lifecycleStage` (gồm khách
  0 event — 418/501 khách `new` không có event, trước đây không bao giờ được chọn); ghi `stageSource`, `zeroEventUsers`.
- `src/evaluation/recsys_bench/engine.py` — sửa: `OfflineCdpReader.all_profiles` ném `LeakageError` như `all_events`.
- `src/evaluation/recsys_bench/__main__.py` — sửa: `run --override KEY=VALUE` (hằng `profile.py` đọc lúc chạy: `MMR_LAMBDA`,
  `W_SHORT/W_POP/W_LONG`, `H_SHORT/H_LONG_DAYS`, `ACTIVE_TRIP_MAX_AGE_DAYS`, `DORMANT_AFTER_DAYS`, `MAX_REPEAT_PER_TRIP`, `W_TYPE`
  JSON; `MAX_PER_VERTICAL` không ghi đè được vì bind làm mặc định tham số), đặt trong tiến trình rồi trả lại; `summary.overrides`;
  `configHash` tự đổi vì `engine_config` đọc `vars(profile)`; `parity --make-users` dùng profile; parity.json ghi `candidateK`,
  `popularK`, ghi chú neo bảng phổ biến; nhãn `doctor`.
- `src/evaluation/recsys_bench/frozen/users60.json` — sinh lại (tầng theo profile, 14 khách 0 event).
- `src/evaluation/recsys_bench/tests/test_sanity.py`, `test_parity.py`, `test_arms_metrics.py` — sửa/thêm: assertion tautology,
  3 cột seed mới, `profiles_cover_events`, `lastDestination` theo index, `make_users` với profile, `--override` (configHash đổi, hằng
  trả lại nguyên trạng, từ chối `MAX_PER_VERTICAL` / giá trị sai kiểu).
- `docs/prd/update/2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md` — thêm: đề xuất **chờ chốt** (FR-REC-02).
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §1 `--override`; §2.1 (9 kiểm tra); §4.12 parity lần 2; thêm §4.13 grid-search lần 1.
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: tick Day 5 B grid-search lần 1; log.

## Kết quả

- Sanity sau mở rộng: **6/6 kiểm tra cứng PASS** (thêm `profiles_cover_events`: 2.000 profile, 1.582 khách có event, thiếu 0; ba cột
  seed `lifetimeOrderCount` / `purchasedVerticals` / `lastDestination` lệch 0/2.000).
- Parity lần 2 với bộ khách mới: **60/60**, trong đó 14 khách 0 event đi đường `popular` cũng trùng; HTTP local p50 93 / p95 134 ms.
- Grid-search lần 1 (temporal đóng băng `a7735af1…`, 102 khách, `--override` một yếu tố mỗi lần): Chỉ **cửa sổ trip mở** đổi kết quả: `ACTIVE_TRIP_MAX_AGE_DAYS` 60 → 30 / 14 nâng Recall@20 0,196 → 0,216 / **0,225** và NDCG@10 0,144 → 0,154 (+0,010), prod NDCG@5 +0,006 — cùng hướng với finding M6 (trip cũ còn trong 60 ngày bị coi là đang mở nên loại nhầm). `W_SHORT=0,7 / W_POP=0,15` +0,006 NDCG@10 và prod NDCG@5 +0,026; `W_SHORT=0,5 / W_POP=0,35` tệ hẳn (NDCG@10 −0,046). MMR λ 0,85 / 1,0, `H_SHORT_DAYS` 60, `DORMANT_AFTER_DAYS` 90 và `W_TYPE` 5/3/1 không đổi hoặc giảm nhẹ. Khác biệt trên 102 khách là 1–3 khách nên chỉ là hướng dò, không phải quyết định; muốn áp dụng phải qua M6 (đề xuất PRD) và chạy lại LLBO. Bảng đầy đủ: spec §4.13.

## Quyết định

- Chỉ chạy grid trên **temporal** đóng băng, không chọn tham số theo LLBO (B10, spec §3.1); LLBO là bảng cuối, giữ nguyên.
- `--override` chỉ đổi hằng trong tiến trình harness; production (`profile.py`, `core/config.py`) không đổi — muốn áp dụng phải
  qua quyết định M7 và sửa spec §4.3–4.7.
- Đề xuất M6 đặt ở `docs/prd/update/` theo AGENTS.md §8, chưa sửa engine.

## Kiểm tra

- `pytest -q src/evaluation/recsys_bench/tests` → **61 passed** (trước 59).
- `sanity --refresh` PASS; `parity --make-users` → 60 khách; `parity --base-url http://127.0.0.1:8000 --k 5 --run-id 2026-10-01-parity-http-v2` → 60/60.
- Grid: 9 run `2026-10-01-temporal-grid-*`, mỗi run `split khớp bản đóng băng`, `configHash` khác nhau.
- Gộp `bench/phan-con-lai` → `bench/embed-search`: __MERGE__.

## Còn lại / rủi ro

- Grid lần 1 là một yếu tố mỗi lần trên 102 khách — khác biệt vài phần nghìn là nhiễu; kết luận chỉ ở mức "không có nút vặn nào
  lớn ngoài category exclusion / điểm đến" cho tới khi M6 được chốt.
- `W_TYPE` 5/3/1 đổi thang vector (chuẩn hoá lại trong `build_profile`) nên gần như không đổi kết quả.
