# Search bench: ma trận ablation F1–F6 + phần kiến trúc mới (45 arm APP e5-small), guard / khối rubric / split / weak-results, rerank offline, report gold_v4 + hole

- Ngày: 2026-10-06
- Tác giả: người dùng ("chạy đủ bench mới với gold_v4, cho ra bảng benchmark có đủ F1–6 và các phương án ablation") / Claude (Opus 5.5,
  orchestrator + 2 agent bench)
- Nhánh: fix/search-gold-v4
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Đo từng phần của kiến trúc Search OTA qua đúng `SearchProducts` của backend trên gold_v4 (sau khi lấp hole): F1–F6 riêng lẻ, tổ hợp,
leave-one-out, cutoff, fuzzy, RRF trọng số, lexical-only, dấu thanh, số khách, rerank offline; báo theo khối rubric v3 / v4, split dev /
test, guard Phase A và parse accuracy. Phục vụ FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01; NFR-PERF-01.

## File thay đổi

- `src/evaluation/search_bench/metrics.py` — sửa: chú giải theo câu (`MetricsConfig.annotations`, gold thắng từng trường), `PARSE_FIELDS`
  mở rộng (must_not_taxonomies, party_total…), `plan_fields` đọc route / derivedDestinations; cột `block` (v3 / v4) + `by_block`,
  `family` + `by_family` + `family_macro_ndcg@10`; arm APP không có `queryPlan` được chấm như plan rỗng (trước bỏ 23/154 câu khỏi parse).
- `src/evaluation/search_bench/runner.py` — sửa: nạp chú giải, block, giữ extra khi rescore.
- `src/evaluation/search_bench/config.py`, `config/sbench.yaml` — sửa: `metrics.annotations`, `forbidden_overrides: null`,
  `guards_proposed` (đề xuất 06/10, chưa chốt), `weak_results` grid.
- `src/evaluation/search_bench/config/forbidden_v3.yaml` — xoá: 8 mục chuyển nguyên văn sang `config/query_annotations.yaml`.
- `src/evaluation/search_bench/__main__.py` — sửa: `compare --split dev|test|all` + bảng theo khối rubric, lệnh `guards` (`--recompute`),
  `weak-results` (topScore / margin so nền từ cache embed, không gọi model).
- `src/evaluation/search_bench/app_adapter.py` — sửa: `APP_DEFAULTS` + knob `tone_normalize`, `taxonomy_strong_only`, `party_filter`,
  `fuzzy_k` / `fuzzy_candidate_k` / `fuzzy_min_sim`, `dense_weight` / `lexical_weight` / `fuzzy_weight`, `retrieval_mode` (lexical =
  `candidate_k 0` qua đúng đường app); `extra` giữ mọi diagnostics theo câu; rerank trong `retrieve_app`; `build_app_catalog` dựng attrs
  (cờ combo, sức chứa, phòng con).
- `src/evaluation/search_bench/rerank.py` — thêm: cross-encoder `BAAI/bge-reranker-v2-m3` (transformers, CPU, cache sqlite
  `bench_out/search/cache/rerank.sqlite`).
- `src/evaluation/search_bench/arms/APP.*.yaml` — sửa 27 arm cũ (thêm knob mặc định = hành vi cũ) + thêm 24 arm:
  `APP.e5s.hybrid_norm_nocut_{tax_strong, party, tone, fuzzy, fuzzy60, wrrf, wrrf_d, lexonly, all, all_c84, all_rr, rr, f1f6, f1f6_wrrf,
  f1f6_rr}` và `_all_minus_{dest, nodia, neg, tax, route, num, party, tone, fuzzy}`.
- Test — thêm `tests/test_annotations.py`, `tests/test_blocks_guards.py`, `tests/test_rerank.py`; sửa `tests/test_app_adapter.py`,
  `tests/test_metrics_phase_a.py`.
- `src/evaluation/reports/eval-2026-10-06-search-query-plan-gold-v4.md` — thêm: report.
- `docs/spec/bench/arms.md` — sửa: hàng arm 06/10 + knob; trạng thái arm 05/10 "đã chạy".
- `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` — sửa: tick checklist §15 theo hiện thực, thêm §17 trạng thái hiện thực
  (giai đoạn → code → cờ → số bench).
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` (§8 log Day 7), `docs/plan/2026-10-01-chia-task-day4-search-rec.md` (§5.4 hàng 06/10) — sửa.

## Quyết định

- **Mốc A = `APP.e5s.hybrid_norm_nocut`** (production hybrid + normalize, cutoff −1 vì 0,62 là ngưỡng Cohere). Identity: A và
  `dense_nocut` trùng top-10 154/154 với run vòng 1 (mã trước thay đổi).
- **Ứng viên production `_f1f6`** (F1 + F2 + F3 + F4 mọi cue + F5 + F6, không cutoff / party / tone / fuzzy) tạo SAU ma trận, từ kết quả
  leave-one-out — ghi rõ trong report là cấu hình chọn theo gold.
- **Verdict**: dùng nguyên win rule của bench; report ghi lý do "không thắng" khi nDCG tăng mà trượt điều kiện recall / slice.
- **Rerank chỉ offline** (Phase D): không đưa vào backend.
- Weak-results dùng nền = trung vị cosine trên cả catalog (contract lấy trên F) — ghi caveat.

## Kiểm tra

- `pytest src/evaluation/search_bench/tests` (.venv-sbench): 54 failed / phần còn lại pass — 54 lỗi có sẵn trước đợt này, cùng tập
  (test_gold_cli 24, test_labeling_core 14, test_streamlit_app 13, test_draft_authoring 1, test_gold_fixtures 1, test_holes 1: CRLF fixture,
  sha pool, streamlit); test mới / sửa đều pass (`test_app_adapter.py` 87 passed 1 skipped, `test_rerank.py` 18, phase A + annotations +
  blocks 76).
- Run `2026-10-06-gold-v4-r2`: 45 arm exit 0, `sb sanity` PASS, Judged@10 = 1,00 mọi arm sau hole D9a–D9e; verdict 65 cặp bằng `sb compare`.
- Kết quả chính (gold chưa tag): A 0,707 · `_f1f6` **0,807 WIN** (Δrecall +4,21, p 0,001; dev WIN; test +10,6 nDCG nhưng slice
  `flight_direction` −6,0) · ALL 0,793 · `_f1f6_rr` 0,845 (chỉ offline) · guard Phase A của `_f1f6` PASS hết.

## Còn lại / rủi ro

- Người dùng chốt bật cờ (đề xuất ở report §5; F4 cần Web) và tag `gold_v5` sau khi duyệt nhãn máy; `baseline_v1` đặt lại trên gold mới
  (người dùng đã nói sẽ chọn khi chốt baseline).
- Ngưỡng guard `guards_proposed` và margin kết quả yếu 0,058 chờ chốt.
- Chưa đo HTTP / cloud; rerank online cần GPU hoặc model nhỏ hơn.
