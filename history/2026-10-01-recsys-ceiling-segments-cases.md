# RecSys harness — Track B Phase 1: ceiling, phân khúc, strict/lenient, 20 ca, arm `engine_nommr`, lệnh `analyze`

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation (recsys_bench), docs spec/plan

## Mục tiêu

Plan Day 3 Track B Phase 1 (B5 ceiling, B6 phân khúc, B7 strict/lenient, B8 20 ca, arm `engine_nommr`) trên hai run v3 đã đóng
băng (history `2026-10-01-recsys-freeze-split-config-ndcg5.md`). Trả lời: engine trượt vì bộ lọc hay vì xếp hạng; phân khúc nào
yếu; strict có đo được không. Phục vụ FR-REC-01/02, M5–M7 lịch 10 ngày.

## File thay đổi

- `src/evaluation/recsys_bench/ceiling.py` — thêm: `engine_view` (mô phỏng profile: cap lặp, trip mở, điểm đến, taxonomy bị
  loại, `bought_units`, strategy), `unreachable` (bản chính xác theo diagnostics engine / bản xấp xỉ), `ceiling`, `ceiling_markdown`.
- `src/evaluation/recsys_bench/analysis.py` — thêm: `lifecycle_at` (luật seed 180/365 ngày), `target_trip_kind`, `user_labels`,
  `segments` + markdown, `strict_lenient` + markdown, `case_reason` (ưu tiên filtered → wrong_active_trip → out_of_candidates →
  vertical_cap → pool_miss / mmr_demoted → ranked_low), `cases` (tất định, xoay vòng theo nguyên nhân) + markdown.
- `src/evaluation/recsys_bench/arms.py` — sửa: `EngineArm._ranked` dùng chung; thêm `EngineNoMmrArm` (`engine_nommr`: patch
  `use_cases.mmr_select` bằng lấy-theo-score, k = 200).
- `src/evaluation/recsys_bench/report.py` — thêm: `read_run`, `merge_run`, `RunConflict`; `write_run(merge=True)`.
- `src/evaluation/recsys_bench/__main__.py` — sửa: `run --arm engine_nommr`; `run --run-id` đã có → gộp arm; lệnh `analyze`
  (temporal chọn T theo phân vị khi run dùng phân vị); docstring module.
- `src/evaluation/recsys_bench/tests/test_ceiling.py` (4 test), `tests/test_analysis.py` (4 test) — thêm; `tests/test_arms_metrics.py`
  — thêm test `engine_nommr` (top-k engine ⊂ pool, patch không rò rỉ), gộp run, CLI `analyze` cả hai split.
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §1 lệnh mới + gộp run + `engine_nommr`; thêm §4.7 ceiling, §4.8 phân khúc,
  §4.9 strict/lenient, §4.10 20 ca + đếm, §4.11 findings 10 dòng; §7.
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: dòng backfill BM25 (C6 xong 01/10).

## Số chính (chi tiết §4.7–4.11 spec)

- Ceiling LLBO **0,990** (10 `already_bought`), temporal **0,784** (`taxonomy_excluded` 15, `destination_mismatch` 18); bản chính xác
  và xấp xỉ đồng thuận 100 %.
- `engine_nommr` LLBO Recall@20 0,863 / NDCG@10 0,548 (MMR: 0,851 / 0,524). 21/1.007 ca engine trượt-mpd trúng: `filtered` 9,
  `mmr_demoted` 6 (pool 3–17), `ranked_low` 6 (pool 22–33). Temporal 4/102.
- Temporal `cross_vertical` 0/22; `activeTripIsSolo` 0,938 (I-3, hành vi xem-rồi-mua của seed).

## Quyết định

- `destination_mismatch` / `not_available` / `not_recommendable` nằm trong `filtered` (từ ceiling) — cùng lớp "bộ lọc cứng", thứ tự
  trong plan chỉ để đọc; `wrong_active_trip` xét sau vì chỉ có nghĩa khi target tới được mask.
- `engine_nommr` là arm chẩn đoán: gộp vào run v3 (cùng `configHash`, cùng split) nhưng không vào bảng báo cáo chính.
- `vertical_cap` chỉ xét khi `--base engine_prod`; mặc định phân tích `engine` (eval) vì cap đã đo riêng (I-5).
- Nhãn lifecycle tính lại từ purchase trong train, không đọc `cdp.profiles` (tránh rò rỉ).

## Kiểm tra

- `pytest -q src/evaluation/recsys_bench/tests` → **50 passed** (trước Phase 1: 40; 10 test mới).
- `run --arm engine_nommr --run-id 2026-10-01-{llbo,temporal}-v3 --split-file …` → gộp vào run, header cùng `configHash 21577d17`.
- `analyze --run-id 2026-10-01-{llbo,temporal}-v3` → exit 0, ghi 7 file mỗi run.
- Review đối kháng (workflow 3 lens) → 3 lens / 11 agent, xác nhận và đã sửa: (1) `vertical_cap` không bao giờ tới được với `--base engine_prod` vì `returned < k` luôn đúng (prod cap 2×5 < 20) → xét cap trước, đo "hết ứng viên" trên list eval; (2) `mmr_demoted` gán cho mọi poolRank kể cả > 20 → chỉ khi poolRank ≤ k, còn lại `ranked_low`; (3) `strict_lenient` lấy cờ target-là-con từ arm đầu tiên → lấy từ split; (4) `analyze` bỏ qua `vectorsMissing` (engine bỏ event / không trả unit thiếu vector) → dừng khi ≠ 0 và ghi giả định vào `ceiling.json`; (5) `merge_run` chỉ so configHash/model/asOf → so thêm k, limitUsers, split.kind/eventsSha256/usersTest/params, vectors; run có split đóng băng thì thêm arm phải kèm `--split-file`; summary ghi `splitSha256` luôn. Kèm: f-string lồng dấu nháy (chỉ chạy 3.12) → biến trung gian; `pool_k` mặc định = `engine.candidate_k`; ghi chú lifecycle theo ngày thập phân và `closed` khi trip bị view lẻ che. Không sửa: cold_start tính là không tới được (ghi chú trong ceiling.json).

## Còn lại / rủi ro

- Phase 2 `sanity.py` (cần adapter `PostgresCdpReader.all_profiles()` ở backend — history riêng), Phase 3 parity offline = HTTP.
- Findings 4–5 là đề xuất đổi hành vi engine (category exclusion theo `usingDate`) → phải qua `docs/prd/update/` trước khi sửa (M6).
