# Day 4–5 R3–R6: registry thuật toán `models/`, funnel chung, `algos_v1.yaml`, CLI `run --algos` / `regress`, gate G1/G2 và smoke

- Ngày: 2026-10-01 (chiều)
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent)
- Nhánh: `bench/day4-rec` (sau commit Day 4 R `993669d`)
- Trạng thái: hoàn thành (R3–R6 theo plan đã duyệt; full run bảng thuật toán Day 5 chưa chạy — xem Còn lại)
- Phạm vi: evaluation, docs

## Mục tiêu

Hoàn thiện R3–R6 của `docs/plan/2026-10-01-chia-task-day4-search-rec.md` sau khi người dùng bổ sung đặc tả thuật toán (gỡ blocker
`cooc_trip` / `star_blend`): registry scorer có `fit` / `score`, funnel chung dùng mask engine + chế độ `raw`, đủ scorer Tier 1
(`content_profile`, `cooc_trip`, `star_blend`, `itemknn`, `ease`, `ials`, `bpr`; `rp3beta` Tier 2), `algos_v1.yaml`, CLI
`run --algos <yaml> --mode funnel|raw` sinh bảng tự động, lệnh `regress`; gate R4 `content_profile` qua funnel = đúng số v5
(mốc chốt = bộ split `asof20260924`). Phục vụ FR-REC-01/02/04, NFR-PERF-01, test-plan §2.5, handbook §12.

## File thay đổi

- `docs/spec/bench/recsys-algos-v1.md` — thêm (đổi tên từ `SPEC_RECSYS_ALGOS_V1.md` của người dùng theo AGENTS §7): dòng FR/NFR, mốc v5
  `asof20260924`, mục "Errata 01/10 — đối chiếu code engine sau M6" (E1–E12), sửa §0.1–0.4, §2, §3, §6, §8 yaml, §9 checklist đã tick.
- `src/evaluation/recsys_bench/models/__init__.py`, `base.py`, `data.py`, `seeds.py`, `funnel.py`, `itemitem.py`, `content.py`, `cooc.py`,
  `star.py`, `ease.py`, `rp3beta.py`, `knn_implicit.py`, `mf_implicit.py`, `registry.py`, `regress.py` — thêm: registry, X_train + ma trận,
  seed từ `build_profile`, funnel (mask engine / raw, knob `pool` × `rerank`), scorer, đọc yaml + `algosHash`, so `ids` theo khách.
- `src/evaluation/recsys_bench/algos_v1.yaml` — thêm: khung registry theo spec §8 + ước lượng fit từ smoke.
- `src/evaluation/recsys_bench/__main__.py` — sửa: `run` thêm `--algos`, `--mode`, `--only`, `--max-tier`, `--funnel-pool`,
  `--funnel-rerank` (validate + kiểm thư viện trước DB; `assert_no_leak`; fit một lần; `expect_equal_to`; `algosHash`, `fitLog`,
  `matrixStats`, `leakCheck`, `libs` vào summary; `run_id` mặc định có đuôi hash); lệnh mới `regress`; `analyze` nối scorer mới vào
  `arms_order`; docstring.
- `src/evaluation/recsys_bench/report.py` — sửa: cột `Collab cov.`, `Pool cắt`, `Fit s`; `header` in algos; `fit_log_markdown` (khối Fit log,
  X_train, expect_equal_to, caveat LLBO); `merge_run` từ chối khác `algosHash`, gộp `fitLog` / `expectations`.
- `src/evaluation/recsys_bench/bench.py` — sửa: `evaluate` trung bình `arm.mean_meta` (collabCoverage, poolTruncated, maskSize, poolSize).
- `src/evaluation/requirements.txt` — sửa: thêm `scipy`, `implicit>=0.7.3`, `threadpoolctl` (dev-only; CI không cài file này).
- `src/evaluation/recsys_bench/tests/synthetic_world.py`, `test_models_data.py`, `test_models_funnel_regression.py`, `test_models_itemitem.py`,
  `test_models_registry_cli.py`, `test_models_implicit.py` — thêm: 25 test (world tổng hợp 60 unit có pool bị cắt thật, toy tính tay,
  G1/G2 trên fixture, CLI qua CliRunner, implicit skip khi thiếu lib).
- `src/evaluation/reports/eval-2026-10-01-recsys-algos-v1-smoke.md` — thêm: gate + smoke, output `report` nguyên văn, caveat, lệnh.
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §1 (`run --algos`, `regress`), §4.16 (gate G1/G2, smoke, phát hiện), §7 (R3–R6 đã làm,
  việc còn lại).
- `docs/plan/2026-10-01-chia-task-day4-search-rec.md` — sửa: R3–R6 tick + bảng bàn giao §5.4, §4.1 blocker đã gỡ, §5.5.
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: log Day 4 → 5 (R).
- `history/2026-10-01-recsys-registry-funnel-algos-v1.md` — thêm: entry này.

## Quyết định

- **Người dùng chốt (01/10):** funnel = **mask engine** (bỏ "2 destination lịch sử" và "anh em cùng cha" của nháp spec); bảng so scorer
  chấm **toàn mask** (`pool mask`, vector numpy), gate dùng **`pool engine`** (tái tạo ANN top-200 ∪ 50 popular, cùng lời gọi `near_vector`);
  chạy **cả hai** `rerank` (`none`, `mmr`) cho mọi scorer (arm `name` / `name+mmr`).
- **Mirror glue, không refactor production**: funnel gọi thẳng `build_profile`, `mmr_select`; chỉ chép ~30 dòng mask + pool của
  `use_cases.py:131-164`. Đẳng thức chứng minh bằng gate thực nghiệm (1016/1016, 98/98) — không cần fallback `_LocalSpace`.
- Pool engine bị cắt ở 4/1.016 LLBO nhưng **76/98 temporal** (đo từ `per_user.jsonl` v5) → không thể chỉ "chấm toàn mask" như nháp spec;
  thêm knob `pool`.
- Arm `engine` eval của v5 vẫn MMR (chỉ bỏ cap) → nháp spec "k = 20 không MMR" sai; mốc không-MMR là `engine_nommr[:20]`.
- X_train ⊆ `kept` (không dùng `Split.train_purchases` vì chứa target); LLBO fit **toàn cục một lần** + caveat; seed `w_e` dạng `explain`;
  `raw` = recommendable/available trừ `bought_units`; `--algos` bắt buộc `--vectors`; `because[]` cho scorer mới hoãn; `bpr_dest`
  `status: not_run`; `content_no_decay` = run `--override H_*`; `content_no_mmr` = `content_profile` (rerank none).
- Với `pool mask` + `mmr`: 200 ứng viên vào MMR lấy theo khoá `(score, pop_D, item_id)` (sửa sau lần smoke đầu — lấy theo chỉ số unit làm
  `+mmr` của cooc/ease/knn sụp); với `pool engine` giữ thứ tự engine để G1 không đổi.
- Không import chéo `search_bench` (`deep_merge` chép 6 dòng); `implicit`/`scipy` import lười trong `fit`; `--help` không cần lib.
- `algosHash` riêng (yaml đã giải inherit + mode + funnel + k + phiên bản lib); `configHash` giữ nguyên nghĩa và vị trí 4 khoá đầu summary.
- Không commit / push phần R3–R6 (người dùng chưa yêu cầu); commit Day 4 R `993669d` đã làm theo yêu cầu "commit ngắn gọn không co-author".

## Kiểm tra

- `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q src/evaluation/recsys_bench/tests` (env DB/Weaviate local): **97 passed** (72 cũ + 25 mới).
- Gate dữ liệu thật (`run --only content_profile --only star_blend_a1 --funnel-pool engine --vectors weaviate`, run
  `2026-10-01-{llbo,temporal}-gate`, `algosHash d0d38a58`) + `regress` so run v5: G1 `content_profile+mmr` ≡ `engine` **1016/1016**,
  **98/98** khớp thứ tự; G2 `content_profile` ≡ `engine_nommr[:20]` 1016/1016, 98/98 khớp thứ tự; `star_blend_a1+mmr` ≡
  `content_profile+mmr` 1016/1016, 98/98. Số trùng v5 từng chữ số (0,8484 / 0,5169; 0,8750 / 0,5462).
- Smoke `--limit-users 50 --max-tier 2`, `funnel` và `raw`, hai split (`2026-10-01-{llbo,temporal}-smoke-{funnel,raw}`): mọi scorer exit 0;
  `expect_equal_to` 50/50 PASS; fit cooc 0,3–0,4 s · star 0,35–0,43 s · itemknn 0,03 s · ease 0,8–0,9 s · rp3beta 0,3 s · ials 0,1 s/seed ·
  bpr 0,06 s/seed; `leakCheck targetCellInTripRow 0`.
- `pip install scipy implicit threadpoolctl` vào `.venv`: scipy 1.18.1, implicit 0.7.3, threadpoolctl 3.7.0 (wheel cp313 win_amd64 OK).
- Không đổi contract / mock / schema → không chạy `validate_contract.py`, `db/verify.sql`.

## Còn lại / rủi ro

- **Full run Day 5** (mọi Tier 1 × 2 rerank × 2 split, phân khúc, CI `compare`, report "RecSys algorithms v1") chưa chạy — ước 5–7 phút LLBO.
- **`+mmr` phá scorer thang điểm nhỏ** (cooc/ease/knn/rp3beta điểm ∈ [0; 0,1] → term đa dạng 0,3·cos lấn át; temporal R@20 → 0,00): chỉ
  đọc hàng `none` cho chúng; muốn `+mmr` có nghĩa cần λ theo thang điểm hoặc chuẩn hoá trước MMR — đổi hành vi engine phải qua đề xuất PRD.
- Co-occurrence ở 7k event quá thưa (10 % item có láng giềng ở LLBO) → `cooc_trip` = `itemknn` = `rp3beta` cùng top-20; so sánh scorer
  collab chỉ có ý nghĩa khi dữ liệu nhiều hơn hoặc `include_views: true` (grid tuần sau).
- `bpr_dest` (negative cùng destination) không có cài đặt; `because[]` cho scorer mới hoãn; `rp3beta` Tier 2 đã chạy smoke nhưng không
  trong bảng chính.
- Spec gốc của người dùng được đổi tên + sửa khá nhiều (errata E1–E12) — lead nên đọc lại phần Errata trước khi dùng cho tuần sau.
- `--override` không lan tới `MAX_REPEAT_PER_TRIP` import theo giá trị ở `ceiling/arms/splits` (caveat cũ); funnel gọi `build_profile` nên
  đọc đúng giá trị module.
- Code R3–R6 chưa commit; `bench_out/` không commit (gitignore) — số trong report chép nguyên văn từ `report`.
