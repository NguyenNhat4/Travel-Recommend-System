# Day 4 R (RecSys): merge M6, đủ cột handbook §12, chạy 6 arm trên bộ split mới, report v5@asof20260924

- Ngày: 2026-10-01
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent)
- Nhánh: `bench/day4-rec` (tách từ `bench_search_recomSys@a6f920b`, merge `origin/bench/m6-trip-ended@8842c3a` → `69e01a5`)
- Trạng thái: hoàn thành (phạm vi A theo quyết định người dùng; R3–R5 để ngày kế — xem Còn lại)
- Phạm vi: evaluation, docs

## Mục tiêu

Phần R (Rec) của `docs/plan/2026-10-01-chia-task-day4-search-rec.md`: tái lập engine v5 trên harness, bổ sung metric còn thiếu
để bảng đủ cột handbook §12 (Gini độ phủ, cross-category theo **chuyến mở**), chạy đủ arm trên hai split, sinh report tự động và
viết report có CI, ceiling, phân khúc, P1/P3. Phục vụ FR-REC-01..04, NFR-PERF-01, test-plan §2.5. Người dùng chốt trước khi code
(01/10): **phạm vi A** = R1, R2, R6 (phần sinh markdown), R7, R8; không làm registry thuật toán / funnel / scorer Tier 1 (R3–R5);
**đóng băng split mới** trên DB local vì DB khác split cũ; **báo cả hai biến thể** cross-category theo chuyến mở.

## File thay đổi

- Qua merge M6 (`8842c3a`, 20 file): `src/backend/app/domain/recommendation/profile.py`, `application/recommendation/use_cases.py`,
  test backend, `src/evaluation/recsys_bench/{arms,ceiling,splits}.py` + test, `docs/prd/requirements.md` (FR-REC-02),
  `docs/prd/update-archive/2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md` (đã áp dụng), spec §4.14,
  `src/evaluation/reports/eval-2026-10-02-recsys-bench-v5.md`, `history/2026-10-02-recsys-fr-rec-02-trip-ended.md` và cloud-latency.
- `src/evaluation/recsys_bench/metrics.py` — sửa: `gini` (chuyển từ sanity), `exposure_gini`, `score(..., *, open_trip=)` với
  `cross_category_open_trip` / `cross_category_open_trip_bought` + `users_open_trip*`, `paired_bootstrap` (chép từ search_bench).
- `src/evaluation/recsys_bench/sanity.py` — sửa: import `gini` từ metrics, bỏ bản cục bộ.
- `src/evaluation/recsys_bench/bench.py` — sửa: `evaluate(..., *, views=None)` tự tính / nhận `engine_view`; `open_trip_taxonomies`.
- `src/evaluation/recsys_bench/report.py` — sửa: 3 cột mới, `footnote`, `header` in `git`, `run_markdown`, `merge_run` nối `history`.
- `src/evaluation/recsys_bench/compare.py` — thêm: `compare_arms` / `compare_markdown` (Δ base − ref, CI95 bootstrap theo khách).
- `src/evaluation/recsys_bench/__main__.py` — sửa: `run` tính `views` một lần với `has_vector` (`_vector_ids`), ghi `gitDescribe`
  + `history` + `openTripAssumesAllVectors`, cảnh báo run gộp nhiều commit, in footnote; lệnh mới `compare`, `report`; `user` thêm
  `becauseDaysAgo` và `p3Check` (VP0000003); docstring.
- `src/evaluation/recsys_bench/tests/test_metrics_open_trip_gini.py` — thêm: 8 test tính tay (Gini, hai biến thể cross-cat, evaluate
  có/không views, bootstrap, compare, report/footnote/header/history, CLI `compare`/`report`).
- `src/evaluation/recsys_bench/frozen/split-llbo-asof20260924.json`, `split-temporal-asof20260924.json` — thêm: bộ split đóng băng
  trên DB local seed 09-23 (giữ bộ `asof20260922`).
- `src/evaluation/reports/eval-2026-10-01-recsys-bench-v5-asof20260924.md` — thêm: report đầy đủ.
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §1 (`compare`, `report`, khoá mới summary, cột mới), §3.1 (bộ split 0924, quy tắc
  không so chéo), §4.15 (bảng v5@asof20260924 + CI + ceiling + đọc nhanh), §5.1 (P1/P3 sau M6), §6 I-8, §7 (định nghĩa 3 cột,
  đoạn "Ceiling", việc chưa làm), dòng cập nhật.
- `docs/plan/2026-10-01-chia-task-day4-search-rec.md` — sửa: tên R, tick R1/R2/R7/R8 (R6 một phần), bảng bàn giao §5.4, §5.5.
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: tick Day 4 B + log Day 4 (R).
- `history/2026-10-01-recsys-day4-v5-full-metrics.md` — thêm: entry này.

## Quyết định

- **Mốc dữ liệu:** DB local máy này là seed 09-23 (`as_of` 2026-09-24, 7.145 event, 3.183 unit), khác bộ split đóng băng 0922 (seed
  21/09, 6.979 event) → `run --split-file` cũ sẽ `SplitMismatch`; tunnel VM 15432 đóng; seed lại không tái lập được (catalog
  2.897 vs 3.183 unit). Người dùng chốt: đóng băng bộ `asof20260924`, gọi mốc `v5@asof20260924`; **không so chữ số** với report v5
  cũ; gate R1 thay bằng `configHash` eval/prod = `b0aee886` / `81d16abd` (chứng minh cùng code), `vectorsMissing 0`, thứ tự
  random ≪ most_popular < mpd < engine, ceiling ≥ mpd — tất cả đạt.
- **Cross-category theo chuyến mở:** báo hai biến thể (mọi khách có chuyến mở theo nguyên văn plan R2; và chỉ chuyến đã mua ≥ 1 món
  theo nghĩa handbook §12) vì chuyến chỉ view (I-3) làm biến thể 1 = 1,0 tầm thường. Chuyến mở lấy từ `ceiling.engine_view`
  (cùng luật `trip_is_open` M6, bỏ unit chưa có vector như engine). Mẫu số 0 → 0,0 / 0, không None (tránh nan khi `aggregate`).
- **Gini** = exposure top-20 trên mọi unit recommendable kể cả 0 lượt (cùng mẫu số Coverage); dùng lại `sanity.gini`, chuyển về
  `metrics.py`.
- **Không import chéo** `search_bench.metrics.paired_bootstrap` (kéo pandas và gốc package `evaluation.*`) — chép 15 dòng, ghi nguồn.
- `report.md` chỉ do lệnh `report` ghi (idempotent sau `analyze` / `compare`), `run` không ghi để file không cũ. `summary.json`
  thêm khoá ở cuối (test ràng buộc 4 khoá đầu); `history` nối khi gộp arm, `gitDescribe` là của lượt mới.
- `compare` cùng quy ước `analyze`: `--base` = arm bị xét, `--ref` = baseline; Δ = base − ref điểm phần trăm.
- `p3Check` dùng `DORMANT_AFTER_DAYS` 180 của code, không dùng 90 của contract — ghi lệch thành I-8.
- Không tạo `src/evaluation/README.md` (AGENTS §7, chưa hỏi người dùng); hướng dẫn chạy ở spec §1.
- Không commit / push (người dùng chưa yêu cầu); merge M6 tạo merge commit `69e01a5` là bước R1 bắt buộc.

## Kiểm tra

- `git merge --no-edit origin/bench/m6-trip-ended`: sạch, 20 file; sau merge `profile.py` có `trip_is_open`, `ACTIVE_TRIP_MAX_AGE_DAYS 14`,
  `ENGINE_RULES_VERSION`; FR-REC-02 bản mới; đề xuất `đã áp dụng`.
- `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q src/evaluation/recsys_bench/tests` (env DB/Weaviate local): 62 passed sau merge →
  **70 passed** sau code mới.
- `pytest src/backend/tests/unit/domain/test_recommendation_trip_open.py src/backend/tests/unit/application -k recommend`: 25 passed.
- `recsys_bench doctor`: catalog 3.183 unit / 2.384 recommendable, CDP 7.145 event as_of 2026-09-24, Weaviate OK. `sanity`: **PASS 6/6**.
- `split --kind llbo|temporal --freeze` → `frozen/split-{llbo,temporal}-asof20260924.json` (1.016 / 98 khách).
- `run` 6 arm × 2 split → `bench_out/recsys/runs/2026-10-01-{llbo,temporal}-v5/` (exit 0; `configHash b0aee886 / 81d16abd`,
  `vectorsMissing 0`): LLBO engine Recall@20 0,8484 / NDCG@10 0,5169, mpd 0,6024 / 0,3803, engine_prod 0,6191 / 0,4718, random 0,0066;
  temporal engine 0,1939 / 0,1505, mpd 0,1020 / 0,0376. Availability 1,000; coverage engine 0,565 / prod 0,207; Gini engine 0,834.
- `analyze` cả hai run: ceiling 0,988 (1004/1016) / 0,918 (90/98), đồng thuận 1,000; engine trượt-mpd trúng 20/1.016 và 1/98.
- `compare` 5 cặp (10.000 lượt): LLBO engine − mpd hit@20 +24,6 [+21,8; +27,6]; engine_prod − mpd hit@20 +1,7 [−1,1; +4,4] p 0,12;
  engine − engine_nommr −2,7 [−4,3; −1,0]; temporal engine − mpd +9,2 [+3,1; +16,3] p 0,0015.
- `user --id VP0000001`: 4/4; `user --id VP0000003`: 4/4 (`p3Check`); 0 lỗi contract, dư `sections` (I-4).
- `report --run-id … --out`: `report.md` trong hai thư mục run; số trong report `src/evaluation/reports/` chép nguyên văn từ đó.
- Không đổi contract / mock / schema → không chạy `validate_contract.py`, `db/verify.sql`.

## Còn lại / rủi ro

- **R3–R5 chưa làm** (registry `models/` + `algos_v1.yaml`, funnel chung dùng `ceiling.engine_view` + chế độ `raw`, scorer Tier 1,
  `run --algos … --mode`): người dùng chốt phạm vi A ngày 01/10; blocker đặc tả `cooc_trip` / `star_blend`
  (`TRAINING_FREE_RECSYS.md`, `serve_bench.py` không có ở bất kỳ ref nào) vẫn mở. Môi trường: `implicit 0.7.3` có wheel cp313
  win_amd64 (pip dry-run OK), `scipy` chỉ có ở `.venv-sbench`, `.venv` chưa có.
- Không tái lập được chữ số report v5 (`asof20260922`) trên máy này; bộ số mới `asof20260924` cần lead xác nhận là mốc Day 4–5.
  Hai bộ split không so chéo.
- `engine_prod` ≈ mpd ở hit@20 trên cả hai split (CI chứa 0) và coverage temporal 0,083 < 20 % — I-5 (cap 2/taxonomy) chưa xử lý,
  đổi hành vi production phải qua đề xuất PRD.
- Số LLBO `recent_activity` vẫn chịu ảnh hưởng `activeTripIsSolo` (seed); temporal 98 khách nên chênh 0,01 = 1 khách.
- Code harness lúc chạy số là working tree chưa commit (`git describe … -dirty`); engine và `configHash` không phụ thuộc phần đó.
- Việc S (search) không chạm; `/search` cloud 500 vẫn chưa có owner (chia-task §4.4).
