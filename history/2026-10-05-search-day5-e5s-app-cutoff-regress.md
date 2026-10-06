# Search Day 5: `/search` production với e5-small, cutoff, dev/test, regression gọn, F1, báo cáo tuần Search

- Ngày: 2026-10-05
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành (Gate P chưa làm — cần quyền VM)
- Phạm vi: evaluation, docs
- Phục vụ: FR-SRC-01..04, FR-SRC-02, AC-SRC-01, NFR-PERF-01; lịch 10 ngày Day 5–6, plan Day 4–5 §2.3 việc 5, 8, 10

## Mục tiêu

Nhóm chốt e5-small / 384 thay Cohere v3 (05/10). Người dùng yêu cầu làm tiếp các việc Search Day 5: chạy 3 arm APP bằng e5-small, chia gold
dev/test, `baseline_v1` + `sb regress`, F1 smoke, phần Search của báo cáo tuần. Người dùng chốt: không chạy S0–S9; chỉ đo cutoff cho e5 (S7)
trên dev, báo trên test; Gate P ghi là bị chặn.

## File thay đổi

- `src/evaluation/search_bench/app_adapter.py` — sửa: cổng APP nhận model khác Cohere v3 (`app_collection`, `model_vectors`; collection
  `ProductBench__<model>`, `modelVersion` theo meta vector, số chiều theo vector; `ProductBench` giữ nguyên cho Cohere v3); thêm guard
  `wait_bm25_settled` / `bm25_snapshot` gọi trong `load_collection` (chờ BM25 ổn định sau khi nạp).
- `src/evaluation/search_bench/__main__.py` — sửa: `sb run` mở một `AppContext` cho mỗi model của arm APP, kiểm embedder đúng model của
  collection; `sb app-load --model`; thêm `sb gold devtest`; thêm nhóm `sb regress baseline|check` (`--split dev|test`).
- `src/evaluation/search_bench/devtest.py` — thêm (viết dở từ trước, nay hoàn thiện và nối CLI): chia dev/test phân tầng theo slice.
- `src/evaluation/search_bench/regress.py` — thêm (viết dở từ trước, nay nối CLI): baseline_v1 + check.
- `src/evaluation/search_bench/config/sbench.yaml` — sửa (viết dở từ trước): `regression.baseline_file`, `regression.regress_v1`.
- `src/evaluation/search_bench/arms/APP.e5s.{dense,dense_nocut,hybrid,hybrid_nocut,hybrid_norm,hybrid_norm_nocut}.yaml` — thêm: 6 arm APP
  e5-small, khối `app` giống bản Cohere.
- `src/evaluation/search_bench/gold/splits/devtest@gold_v3.json` — thêm: dev 66 / test 65, seed 42.
- `src/evaluation/search_bench/regression/baseline_v1.json` — thêm: `APP.e5s.hybrid_norm`, run `20261005-e5s-app-r2`, gold_v3.
- `src/evaluation/search_bench/tests/test_app_adapter.py` — sửa: 6 test model khác Cohere + 3 test guard BM25.
- `src/evaluation/search_bench/gold/holes/gold_v3__D6a/` — thêm: pool gán nhãn 466 cặp / 92 câu (A 251, B 215) + 7 auto-OOC từ top-10 của
  3 arm APP e5s (`sb gold holes --tag D6a --split`); chưa gán.
- `src/evaluation/search_bench/tests/test_devtest_regress.py` — thêm: 6 test devtest + regress.
- `src/evaluation/reports/eval-2026-10-05-search-day5-e5s-app.md` — thêm: report số (ổn định, 3 arm, so cặp, slice, sweep cutoff dev/test,
  regression, F1, lệnh tái sinh, script phụ lục).
- `src/evaluation/reports/report_week_3_search.md` — thêm: báo cáo tuần 3 phần Search cho nhóm + mentor (không sửa `report_week_3.md` của
  tqanh123, là báo cáo RecSys).
- `docs/spec/bench/arms.md` — sửa: 6 dòng `APP.e5s.*`, đoạn "Model khác Cohere" + cảnh báo đo ngay sau khi nạp.
- `docs/spec/bench/search-eval-local-spec.md` — sửa: ghi chú bản gọn của Part 13 (`gold devtest`, `regress baseline|check`).
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: ghi chú Day 6 việc 1 (split, baseline, cutoff đề xuất, S1–S10 không làm).
- `docs/plan/2026-10-01-chia-task-day4-search-rec.md` — sửa: tick §5.5 revision bge-m3.
- `docs/plan/2026-10-01-plan-day4-5.md` — sửa: §2.5 dòng 3 → "Một phần" (baseline + regress + split xong, `stages.yaml` không làm).
- `history/2026-10-05-search-day5-e5s-app-cutoff-regress.md` — thêm: entry này.

## Quyết định

- Cohere chỉ đọc cache truy vấn: chạy arm Cohere với `COHERE_API_KEY` giả → 0 lượt gọi API (log: `query embed: mới 0 / cache 131`).
- Bỏ lượt chạy đầu `20261005-day5-app-e5s`: arm hybrid lệch 0,415 / 0,532 so với 0,655 / 0,680 ở hai lượt lặp (trùng nhau 100 %). Nghi BM25 của
  Weaviate chưa sẵn sàng ngay sau khi nạp collection mới; guard `wait_index_ready` chỉ chờ index vector. Chưa sửa guard (mở).
- Số hybrid Cohere của report Day 4 (`eval-2026-10-01-search-v1-3arm.md`) không tái lập: lệch 93 / 79 câu, code không đổi kể từ lượt đó → ghi
  đính chính trong report mới và báo cáo tuần, không sửa report cũ.
- Cutoff: quy tắc S7 của `arms.md`; không giá trị nào đạt cả hai điều kiện → lấy giá trị cao nhất giữ zero-result trong catalog < 2 % trên
  dev = 0,85. Chỉ đề xuất; không sửa `SEARCH_CUTOFF`, contract, backend (đổi model production cần đề xuất PRD FR-SRC-02 được chốt).
- `baseline_v1` đặt trên `APP.e5s.hybrid_norm` với cutoff YAML 0,62 (không lọc với e5); đổi cutoff / model thì đặt lại.
- F1: `/search` không có fallback BM25 → chỉ đo chất lượng BM25-only, không thêm fallback (thêm là đổi hành vi, cần PRD).
- Sweep cutoff và F1 viết dạng script ở phụ lục report (như report 02/10), không thêm lệnh `sb`.
- Rà lại Day 4–5 (người dùng yêu cầu "hoàn thiện đầy đủ"): thêm so sánh còn thiếu — xét lại mốc dense / hybrid / hybrid + normalize bằng số
  đúng, hub check 7 model, đường cong số chiều GTE (cắt vector có sẵn, Matryoshka), phân tích `cross_vertical`, revision model HF. Hub đo trên
  131 câu gold (chưa có bộ câu sinh 500 câu như spec) → chỉ đọc tương đối.
- Lỗi hybrid: tái hiện bằng thăm dò BM25 mỗi 3 s sau khi nạp (sai 10/10 câu trong ~60 s đầu) → guard trong bench. Không sửa backend /
  job index production (có thể bị cùng hiện tượng ~1 phút sau khi tạo collection mới) — chỉ ghi rủi ro.
- D6a: chỉ sinh pool; nhãn phải do người gán (như D4b, D5a).

## Kiểm tra

- `pytest evaluation/search_bench/tests` (vsf2, bỏ `test_share_dry_run_writes_launcher_outside_git_and_codes` — PermissionError có sẵn, không
  liên quan): **358 passed, 11 skipped** (trước thay đổi 346 + 6 test app adapter = 352; + 6 test devtest/regress).
- `sb gold devtest --seed 42`: dev 66 / test 65, mọi slice lệch ≤ 1.
- 6 arm APP e5s × 3 lượt; r2 = r3 100 % top-10. 3 arm APP Cohere × 2 lượt (r2, r3), r2 = r3 100 %.
- `sb compare` Cohere → e5s (r2): hybrid + normalize Δ nDCG@10 −0,36 [−4,59; +3,66] full, +0,42 [−3,74; +4,47] condensed → TIE.
- `sb regress baseline` → `regression/baseline_v1.json`; `sb --run-id 20261005-e5s-app-r3 regress check` → PASS (Δ 0, 0/131 đổi); `--split dev`
  → PASS; `--arm APP.e5s.dense` → mã 2 "arm khác nhau" như thiết kế.
- F1 smoke: 439/439 kết quả thoả filter (10 câu). BM25-only nDCG@10 0,589 so với 0,680.
- Sau guard + test mới: `pytest evaluation/search_bench/tests` **361 passed, 11 skipped** (bỏ cùng test launcher).
- Guard trên dữ liệu thật: `sb app-load --model e5-small --recreate` 1 phút 16 s; chạy ngay hybrid / hybrid_norm (run `20261005-e5s-guard`) → khác
  r2 4/131 câu mỗi arm (trước guard 68–93), nDCG@10 0,656 / 0,680.
- Hub, GTE, cross_vertical: script `hub_dims.py`, truy vấn per_query — số trong report §10–11.
- `git diff --check`: sạch.

## Còn lại / rủi ro

- Gate P (p95 `/search` cloud < 250 ms): cần quyền VM, chưa có owner; phải đo lại sau khi đổi production sang e5-small.
- `cross_vertical` −26 điểm với e5-small (10 câu): chưa phân tích từng câu — nên làm trước đề xuất PRD.
- Gán nhãn D6a (466 cặp) → `gold_v4` → `sb rescore` → đặt lại `baseline_v1`.
- Production: kiểm `/search` hybrid ngay sau khi job index tạo collection mới trên Cloud (có thể sai ~1 phút).
- `lexical_cutoff` 0,50 cũng không còn tác dụng với e5: chưa sweep.
- Đề xuất PRD FR-SRC-02: tqanh123 xem sau (người dùng chốt).
