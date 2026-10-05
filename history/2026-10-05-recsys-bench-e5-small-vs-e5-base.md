# Bench RecSys với vector e5-small và e5-base — chạy đủ và viết report (plan e5 Day 7–8)

- Ngày: 2026-10-05
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs
- Phục vụ: FR-REC-01..04, FR-SRC-02, NFR-PERF-01; plan `docs/plan/2026-10-05-bench-recsys-e5-small.md` Day 7 (7.1–7.8), Day 8 (8.1–8.2)

## Mục tiêu

Nhóm chốt e5-small / 384 thay Cohere v3. Đo lại bench RecSys của tqanh123 (engine v5 + baseline, gate, bảng thuật toán funnel / raw) bằng
vector e5-small và e5-base để trả lời: engine dùng e5-small có vượt baseline không; e5-small có thua e5-base không.

## File thay đổi

- `src/evaluation/reports/eval-2026-10-05-recsys-e5-small-vs-e5-base.md` — thêm: report (provenance, gate, kiểm chéo, engine + baseline,
  `compare`, so hai model, phân khúc, bảng thuật toán, ceiling, tốc độ, caveat, lệnh tái sinh, script phụ lục).
  Mục 0 giải thích cho người đọc không chuyên: cách đo (giấu món đã mua, hai split, đối thủ), ý nghĩa từng chỉ số kèm ví dụ, CI95 và
  paired bootstrap, các kiểm tra độ tin cậy, giới hạn (người dùng yêu cầu khi bàn giao).
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: tick việc Day 6 "RecSys chạy lại bằng vector e5" kèm số và đường dẫn report.
- `history/2026-10-05-recsys-bench-e5-small-vs-e5-base.md` — thêm: entry này.

## Quyết định

- Chạy sớm cả Day 7 và Day 8 trong ngày 05/10; run id và tên report dùng ngày chạy thật (`2026-10-05-…`, `eval-2026-10-05-…`) thay vì
  06/10 / 07/10 như plan.
- Cấu hình run lấy đúng Day 5 (spec recsys §4.17): pool mask, rerank none + mmr, `--max-tier 2`; gate pool engine như `make recsys-gate-run`.
- So hai model bằng script phụ lục gọi `compare.compare_arms` (không sửa `compare.py`, theo plan 6.1).
- Áp quy tắc đọc ghi trong plan trước khi chạy: engine e5-small thắng mpd với CI > 0; e5-small không thua e5-base quá 1 điểm (CI < 0) và không
  phân khúc n ≥ 20 thua quá 3 điểm → **đạt cả hai, giữ e5-small**. Không tự đổi production, không viết đề xuất PRD (ngoài phạm vi plan).

## Kiểm tra

- 16 run (`2026-10-05-{llbo,temporal}-{v5,gate,algos-funnel,algos-raw}-{e5s,e5b}`) exit 0; mọi run `frozenSha256` khớp, `vectorsMissing 0`,
  `configHash b0aee886`; 8 run algos + 4 run gate `expectFailed []`, leak 0.
- Gate G1 / G2: 1016/1016 (LLBO), 98/98 (temporal) cho cả hai model.
- Kiểm chéo 7.4: `itemknn`, `ease`, `ials-s42`, `cooc_trip`, `rp3beta` trùng ids 100 % giữa e5s và e5b (LLBO funnel, temporal funnel; LLBO raw
  với 3 scorer đầu).
- `compare` engine vs mpd: LLBO e5s Δ hit@20 +25,79 [+22,93; +28,64], NDCG@10 +12,57 [+11,19; +13,98]; temporal e5s +8,16 [+2,04; +15,31] /
  +4,55 [+1,19; +8,12].
- e5s − e5b engine: LLBO hit@20 +0,20 [−0,89; +1,28], NDCG@10 +0,37 [−0,19; +0,90]; temporal +1,02 [0,00; +3,06] / −0,39 [−0,96; +0,04].
  Phân khúc n ≥ 20 tệ nhất −0,91 (attraction LLBO).
- `analyze` 4 run v5 exit 0 (lần đầu exit 1 vì quên nạp env DB, chạy lại đúng env). `report` sinh bảng cho 8 cặp run exit 0.
- Không đổi code ở bước này; test harness vẫn 127 passed (entry `2026-10-05-recsys-bench-npy-vectors.md`).

## Còn lại / rủi ro

- Plan 8.3: gửi report cho tqanh123 và lead, chờ review — người dùng làm.
- Đề xuất PRD FR-SRC-02 (Cohere → e5-small), `baseline_v2`, index e5 lên Weaviate + parity offline = HTTP, p95 HTTP: ngoài phạm vi plan.
- Số tốc độ là offline trên máy dev, không phải NFR-PERF-01.
- Postgres bench (`wt-seed-postgres-1`, cổng 55433, volume `wt-seed_pgdata`) và worktree scratchpad vẫn còn; dọn khi không cần tái sinh số.
