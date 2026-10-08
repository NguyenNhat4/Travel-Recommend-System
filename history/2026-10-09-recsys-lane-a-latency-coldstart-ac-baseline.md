# Lane A: latency đầu-cuối TRƯỚC, coldstart, AC-REC-01/02, split prodcopy + baseline gate v2

- Ngày: 2026-10-09 (chạy từ tối 08/10)
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs
- Tiếp theo: `history/2026-10-08-de-xuat-prd-recsys-o-kham-pha-combo-cong-thuc.md`

## Mục tiêu

Lane A của `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` — những số phải có trước mọi PR, không lệch PRD:
(A1) latency đầu-cuối TRƯỚC trên backend local; (A2) coldstart + AC-REC-01/02 (ô WP4 còn trống); (A3) split prodcopy đóng
băng + baseline gate v2 vì `baseline_v1` đã NotComparable. FR-REC-01/02/04, AC-REC-01/02, NFR-PERF-01.

## File thay đổi

- `src/evaluation/recsys_bench/theme_study/load_npy_weaviate.py` — thêm: nạp `.npy` vào collection Weaviate mới đúng định
  dạng object của `jobs/embed_products.py` (không torch, không re-embed).
- `src/evaluation/recsys_bench/theme_study/eval_profile.py` — sửa: split `coldstart`; truyền `idx` vào `eval_split`; cờ
  `--f14-q` ghim ngưỡng F14.
- `src/evaluation/recsys_bench/theme_study/eval_formula.py` — sửa: `eval_split(..., idx)` tính thêm `destHit@20` (điểm đến
  của target có trong list 20) khi có `idx`; `eval_formula.main` vẫn truyền `None` → số cũ không đổi.
- `src/evaluation/recsys_bench/theme_study/paired_ci.py` — sửa: `SPLIT_METRICS` thêm `destHit@20`.
- `src/evaluation/recsys_bench/tests/test_paired_ci.py` — sửa: test `index()` theo chỉ số mới (chỉ số vắng không tạo khoá).
- `src/evaluation/recsys_bench/tests/test_ac_rec02_danang.py` — thêm: AC-REC-02 trên catalog thật bằng lịch sử tổng hợp
  (skip khi thiếu `DATABASE_URL` / `RECSYS_VEC`).
- `src/backend/tests/unit/application/test_engines.py` — thêm: `test_ac_rec_02_booking_prioritises_flights_and_activities_at_the_destination`
  (catalog giả, chạy trong CI).
- `src/evaluation/recsys_bench/frozen/split-{llbo,temporal,nexttrip,coldstart}-prodcopy-asof20261008.json` — thêm.
- `src/evaluation/recsys_bench/frozen/baseline_v2-{llbo,temporal,nexttrip,coldstart}-prodcopy-asof20261008.json` — thêm.
- `src/evaluation/recsys_bench/theme_study/results/2026-10-08-lane-a/` — thêm: latency (`e2e-before-*.json`), `parity-prodcopy.json`,
  hai file tập khách, coldstart JSON + `ci_coldstart.json`, `ac/*.txt`.
- `src/evaluation/reports/eval-2026-10-08-recsys-latency-dau-cuoi-truoc.md` — thêm.
- `src/evaluation/reports/eval-2026-10-09-recsys-coldstart-ac-rec-baseline-v2.md` — thêm.
- `history/2026-10-09-recsys-lane-a-latency-coldstart-ac-baseline.md` — thêm: entry này.

## Quyết định

- Weaviate local: collection **mới** `ProductE5SmallProdcopy` (3.991 object) nạp từ `.npy` của gói bàn giao; không dùng
  `ProductBench_e5_small` (3.183 / 3.991 unit) và không cài torch vào `.venv` (vector phải y hệt bộ đã đo offline — parity
  60/60 chứng minh).
- Tiêu chí latency G1 cụ thể hoá: Δp95 **server `latencyMs`**, cùng hai file khách (`users-strata.json` 20/20/16/4 và
  `users60-prodcopy.json`), tổng và theo `strategy`, local; `client_ms` báo kèm; caveat cloud ghi trong report.
- Coldstart trên prodcopy là kiểm **không-hồi-quy** (mọi khách có chuyến chỉ-xem đang mở, `share_open = 1,0`), không đo
  được lợi ích; `destHit@20` thêm để lane B2 đo mức điểm đến.
- AC-REC-01 chạy ở hai mốc vì chuyến NT của P1 đã kết thúc 05/10; "phù hợp gia đình" không có nhãn máy → duyệt tay.
- AC-REC-02 mã hoá bằng lịch sử tổng hợp (không ghi DB prodcopy) + unit test fakes; phần "tour Hội An" không thể đạt theo
  thiết kế → sửa câu AC qua đề xuất [C].
- Baseline gate ghi trên **prodcopy asof20261008** (DB seed `asof20260924` không có trên máy này), bộ arm đúng Makefile
  `recsys-gate-run`; `regress` cùng run exit 0. Sau PR-A `regress` FAIL theo thiết kế → `baseline_v3` sau G5a.
- Makefile không đổi: GnuWin32 make 3.81 không chạy recipe nhiều dòng, lệnh python trực tiếp ghi trong report.

## Kiểm tra

- Collection: Aggregate count 3.991; `embed_products --dry-run` → `unchanged 3991, embedded 0, deletedOrphans 0`;
  `ProductBench_*` vẫn 3.183.
- Backend local: `startup.recsys.index.load.ready search_units=3991`, không `out_of_sync`; guest `popular` 10 ms.
- `parity --users users60-prodcopy.json --k 5 --vectors weaviate`: **PASS 60/60**, HTTP p50/p95 71/99 ms.
- `http-latency --runs 6 --k 4`: strata server p50/p95 **66 / 87 ms** (client 69 / 90), users60 **67 / 86 ms**, guest 9 / 9 ms;
  theo strategy: `long_term` 70 / 87,6 · `dormant` 70,5 / 89 · `cold_start_content` 57 / 69 · `recent_activity` 50,5 / 73,1.
  Không có mẫu `cross_vertical` (bản sao chỉ có 1 khách có purchase `usingDate` ≥ 08/10).
- Coldstart (5.243 khách): P2+F0 hit@20 −0,0011 [−0,0027, +0,0002], hit@4 −0,0011 [−0,0023, 0,0000]; P2+F14c(+destCap2)
  hit@4 −0,0013 [−0,0027, −0,0002] = 11 khách lật, toàn bộ do P2; `destHit@20` 0,9943 không đổi.
- AC-REC-01: `user --id VP0000001 --as-of 2026-09-21` day1Check **4/4**; `VP0000003` p3Check **4/4**; `contractErrors = []`.
- AC-REC-02: `test_ac_rec02_danang.py` **3 passed** (prodcopy); list = flight TP.HCM–ĐN, Charming Danang Show, combo bay+phòng,
  Sun World Bà Nà Hills, `because` 1 nguồn / món, cả hai trang; `test_engines.py` **12 passed**.
- Gate: split đóng băng 4 kind (sha `0bff46bb…`, `6b430216…`, `f5bd9dc9…`, `7c27c631…`); baseline_v2 4 kind; `regress` exit 0
  mọi kind; engine llbo Recall@20 0,8071 (4.023 khách), temporal 0,1604 (773).
- Hồi quy số cũ: `eval_split` nhận `idx` — 200 khách LLBO đầu: 0 lệch so với dòng từng khách 08/10.
- `pytest src/evaluation/recsys_bench/tests`: 160 passed, 3 skipped (AC-REC-02 gated), 4 xfailed; `pytest
  src/backend/tests/unit -k "recommend or profile"` 52 → 53 passed (PYTHONUTF8=1).

## Còn lại / rủi ro

- Latency SAU chỉ đo được khi engine PR-A tồn tại — cùng env, cùng collection, cùng hai file khách, xen kẽ trước / sau.
- Số local không chứng minh chi phí ô B trên Weaviate Cloud khác region.
- `baseline_v2` 3 MB / kind (4.023–5.243 khách × 7 arm) — chấp nhận như các split đã đóng băng.
- Backend local và container `vota-prodcopy-pg` vẫn chạy để dùng cho lane B2 / PR-A; tắt khi xong.
