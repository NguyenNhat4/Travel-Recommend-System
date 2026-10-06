# Day 5 R: full run bảng thuật toán, `baseline_v1` + `regress --baseline`, because[] (K tuỳ chọn), `bpr_numpy` / `bpr_dest`, report RecSys v1

- Ngày: 2026-10-01 (tối)
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent)
- Nhánh: `bench/day4-rec` (sau commit R3–R6 `8fffd4b`)
- Trạng thái: hoàn thành (xem Còn lại)
- Phạm vi: evaluation, docs

## Mục tiêu

Plan đã duyệt 01/10 tối ("Day 5 lõi trước, rồi because[] và bpr_dest nối tiếp cùng đợt"; README vào spec §1; because cần K thay đổi được
5/10/15/20…; commit R3–R6 trước, không co-author): (A) full run Day 5 theo `docs/plan/2026-10-01-plan-day4-5.md` §2.2–§2.5 — bảng thuật
toán Tier 1 (+ Tier 2) hai chế độ × hai rerank, CI, phân khúc, ceiling, report "RecSys v1", ADR 2; `baseline_v1.json` + regress tự động
(phần 5 của "bench hoàn thiện"); (B) because[] cho scorer mới (FR-REC-03); (C) `bpr_dest` (spec algos §6.2). Phục vụ FR-REC-01..04,
NFR-PERF-01, test-plan §2.5, handbook §12. Không đổi engine production, contract, DDL, PRD.

## File thay đổi

- `src/evaluation/recsys_bench/models/popular.py` — thêm: scorer `pop_funnel` (điểm 0 → funnel xếp `(pop_D↓, item_id↑)`), baseline "CF ≈
  popularity" đi qua cùng funnel.
- `src/evaluation/recsys_bench/models/baseline.py` — thêm: `baseline_v1` (`build`, `write` theo fingerprint, `check` → PASS / WARN / FAIL /
  INCONCLUSIVE, `NotComparable`, `markdown`, `dumps` gọn theo khách); vai trò primary / scorer / canary; ngưỡng 1,0 điểm ∧ ≥ 3 khách ∧
  p < 0,05, phân khúc n ≥ 20 ∧ ≥ 3,0 điểm ∧ ≥ 2 khách.
- `src/evaluation/recsys_bench/models/because.py` — thêm: `event_weights` / `finalize` (y hệt `profile.explain`), `content`, `from_rows`,
  `star`, `latent`, `contract_items`, `violations` (luật contract popular / coldStart / dormant 90).
- `src/evaluation/recsys_bench/models/bpr_numpy.py` — thêm: `BprNumpy` (khởi tạo + SGD theo `implicit/gpu/bpr.cu`), sampler `global` /
  `same_destination` (`DestinationPools`, uniform | pop, rút lại ≤ 10, lùi global khi destination < 20 unit), fit log `trainAucLastEpoch`,
  `skippedShare`, `destStats`.
- `src/evaluation/recsys_bench/models/funnel.py` — sửa: `AlgoArm(..., because_k)` ghi because[] top-K + `coldStart` + `becauseCoverage` /
  `becauseViolations` / `becauseViolationRules`; `mean_meta` thêm hai khoá.
- `src/evaluation/recsys_bench/models/content.py`, `cooc.py`, `ease.py`, `rp3beta.py`, `knn_implicit.py`, `star.py`, `mf_implicit.py` — sửa:
  `explain` cho từng scorer (ials qua `implicit` explain + `item_contributions`; bpr rỗng); thông báo lỗi `Bpr` trỏ `bpr_numpy`.
- `src/evaluation/recsys_bench/models/data.py` — sửa: `stats.events` (event vào ma trận).
- `src/evaluation/recsys_bench/models/registry.py` — sửa: `entry_reranks` (rerank của run ∩ `funnel.rerank` của entry), validate
  `funnel.rerank` từng entry, `build_arms(..., because_k)`.
- `src/evaluation/recsys_bench/models/__init__.py` — sửa: đăng ký `pop_funnel`, `bpr_numpy`.
- `src/evaluation/recsys_bench/algos_v1.yaml` — sửa: `pop_funnel` (rerank none), `bpr_numpy` (Tier 2, global, 3 seed), `bpr_dest`
  (`inherit: bpr_numpy`, `same_destination`) thay entry `not_run`.
- `src/evaluation/recsys_bench/__main__.py` — sửa: lệnh mới `baseline`; `regress --baseline auto|PATH` (+ `--allow-subset`, ngưỡng; mã 0/1/2/3);
  `run --because-k K` (0 ≤ K ≤ k, chỉ với `--algos`; `summary.because`, `history.params.becauseK`, `because_k` / `because_unmapped` trên hàng);
  docstring mã thoát.
- `src/evaluation/recsys_bench/report.py` — sửa: cột `Because@K` (nhãn theo K thật) và `Vi phạm because`, chỉ in khi có khoá.
- `src/evaluation/recsys_bench/frozen/baseline_v1-llbo-asof20260924.json`, `…-temporal-asof20260924.json` — thêm: baseline từ run
  `2026-10-01-{llbo,temporal}-gate-numpy` (sha file `f0920877…` / `433bd3c3…`, fingerprint `cbc76becd0ec` / `555695c49d41`).
- `src/evaluation/recsys_bench/tests/test_models_baseline.py` (7 test), `test_models_because.py` (8), `test_models_bpr_numpy.py` (6) —
  thêm; `test_models_funnel_regression.py` (+ `pop_funnel` xếp `(pop_D, id)` trên hai world), `test_models_registry_cli.py`
  (+ `entry_reranks`, `funnel.rerank` sai, `pop_funnel+mmr` không sinh) — sửa.
- `Makefile` — sửa: `recsys-test`, `recsys-gate-run`, `recsys-regress`, `recsys-baseline` (`RECSYS_ENV` nạp file env, không ghi DSN;
  nạp env cùng dòng lệnh để chạy được cả make không `.ONESHELL`).
- `src/evaluation/reports/eval-2026-10-01-recsys-algos-v1.md` — thêm: report RecSys v1 (13 mục + phụ lục A because, B BPR Tier 2).
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §1 (= README: `baseline`, `regress --baseline`, bảng mã thoát, vai trò, `make recsys-*`,
  đường dẫn phải chạy regress, cách thêm scorer), §3.1 (bảng baseline + chính sách cập nhật), §4.17 (full run + ADR 2), §7, dòng cập nhật.
- `docs/spec/bench/recsys-algos-v1.md` — sửa: §1.2 / §2.3 because đã cài (công thức theo event, Z = Σc xấp xỉ, kind, metric), §6.1, §6.2,
  §6.3 mới (`bpr_numpy` / `bpr_dest`, 4 khác biệt so implicit), §7 (hàng `pop_funnel`, `bpr_numpy`), §8 yaml, E12.
- `docs/plan/2026-10-01-chia-task-day4-search-rec.md` — sửa: tick 12 dòng R5 + R4 (§5.2) kèm run ID / tham số; hàng R9–R13 (§5.4).
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: log Day 5 (R), ghi chú thứ tự grid Day 6 theo ADR 2.
- `docs/plan/2026-10-01-plan-day4-5.md` — sửa: cột "Có?" dòng 4–7 của §2.5 (phần RecSys; ghi rõ phần thiếu).
- `history/2026-10-01-adr2-huong-cai-thien-recsys-tuan-sau.md` — thêm: ADR 2 (entry riêng).

## Quyết định

- Thứ tự Phase A → B → C (người dùng); code B/C chỉ áp sau khi run Phase A đã nạp module, và `make recsys-regress` chạy **sau** khi áp B/C
  để chứng minh because / `bpr_numpy` không đổi ids (LLBO 0/1016 khách đổi).
- Baseline neo **pool engine + `--vectors numpy`** (quét chính xác, tái lập; Weaviate HNSW lệch 6/1016, 4/98 khách so với numpy); arm
  `engine`, `engine_nommr`, `content_profile[+mmr]`, `star_blend_a1[+mmr]` = primary (ids phải khớp 100 %), `most_popular_in_destination` =
  canary (lệch → mã 3 "môi trường đổi"). Fingerprint gồm meta + ids + metric + vai trò + nhãn phân khúc; ghi lại cùng run = no-op; thêm nhãn
  sau `analyze` cần `--force`.
- because[]: trọng số event lấy bằng vòng lặp của `profile.explain` (float64) chứ không từ `Seeds.weights` float32 → `star_blend` a = 1 trùng
  **bit** với engine; không thêm `Seeds.events` như plan nháp (không cần). `ials` map đóng góp theo item về event gần nhất trên **mọi** trip
  (iALS dựng vector từ cả hàng user). `--because-k` không vào `algosHash` (không đổi ids) nhưng ghi vào summary / history; because chạy run
  riêng để run bảng không phình.
- `bpr_numpy` rút mẫu theo vector rồi cập nhật tuần tự (≈ 6 µs/bước → ≈ 5,6 s/seed) — không cần batch / numba. `bpr_dest` giữ `uniform` trên
  mọi unit cùng destination như spec; `pop` để grid.
- `pop_funnel` chỉ `rerank none` (MMR trên điểm toàn 0 vô nghĩa) → registry tôn trọng `funnel.rerank` của entry.
- Phát hiện khi kiểm "đẹp bất thường" theo plan §5: 441/1.016 khách LLBO có `add_to_cart` không gid đúng unit target trước khi mua (temporal
  2/98) — không phải rò rỉ thời gian; ghi caveat + phân khúc `targetInOwnHistory` trong report, đưa vào ADR 2 (#2, #6).
- Makefile: GnuWin32 make 3.81 trên máy dev không có `.ONESHELL` → nạp env và lệnh trên một dòng logic; `RECSYS_PYTHON` truyền tay trên Windows.

## Kiểm tra

- `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q src/evaluation/recsys_bench/tests` → **119 passed** (97 trước Day 5 + 1 `pop_funnel` +
  7 baseline + 8 because + 6 bpr_numpy).
- Gate numpy trong-run (`regress`): G1 / G2 / `star_blend_a1` **1016/1016**, **98/98**; drift numpy ↔ run v5 Weaviate 1010/1016, 94/98 (thông tin).
- 6 run bảng + 2 nodecay + 2 gate exit 0, `expectFailed []`, `leakCheck.targetCellInTripRow 0`; `analyze` 6 run; `compare` 102 cặp (4 run bảng).
- `baseline --run-id 2026-10-01-{llbo,temporal}-gate-numpy` → written; `regress --baseline auto` → PASS mã 0 cả hai;
  `make recsys-regress RECSYS_SPLIT=temporal|llbo RECSYS_RUN=2026-10-01-{temporal,llbo}-make-regress` → PASS mã 0 (LLBO chạy trên code đã có B/C).
- Run because `2026-10-01-{llbo,temporal}-because-k{5,10,15,20}` và `2026-10-01-{llbo,temporal}-bpr-tier2` exit 0 (số ở phụ lục A, B).
- Backend không đổi (không chạy lại test backend).

## Còn lại / rủi ro

- Code Day 5 **chưa commit** (người dùng chưa yêu cầu); mọi run Day 5 ghi `gitDescribe gold_v2-119-g8fffd4b-dirty`.
- Regress chưa vào CI (CI chỉ test backend, không có Postgres seed) — cần workflow riêng được duyệt.
- ADR 2 theo quy tắc, chưa đồng thuận; ba đề xuất PRD (cap `parentProductId` I-5, tín hiệu giỏ hàng, dormant 90/180 I-8) chưa soạn; đề xuất
  thêm khoá `kind` vào `BecauseItem` (additive) chưa soạn.
- Nhãn `targetInOwnHistory` mới chỉ có trong script phân tích của report; đưa vào `analyze` là ADR 2 #2.
- `compare --ref-run-id` (so hai run khác nhau) chưa làm; Δ nodecay trong report tính bằng script một lần.
