# Bench RecSys với vector e5-small và e5-base — đo và viết report (Day 6 → Day 8, 05/10 → 07/10/2026)

- Phục vụ: **FR-REC-01..04**, **FR-SRC-02** (model embedding dùng chung cho Search và RecSys), **NFR-PERF-01**; đánh giá theo
  `docs/prd/test-plan.md` §2.5.
- Người làm: Phạm Nguyễn Đăng Khôi. Review: tqanh123 (chủ `src/evaluation/recsys_bench/`).
- **Phạm vi (tqanh123 giao, người dùng chốt 05/10):**
  - chạy **local**;
  - đo bench RecSys với **e5-small** (model đã chọn) và **e5-base** (so sánh);
  - **không dùng Cohere**: không chạy, không so với `baseline_v1`;
  - viết report chi tiết.
  - Không gồm đề xuất PRD, `baseline_v2`, grid ADR 2, đổi production (mục "Ngoài phạm vi").
- Căn cứ (trạng thái `bench_search_recomSys @ 942f5aa`, 05/10):
  - `docs/spec/bench/recsys-offline-eval.md` §1 (lệnh, `make recsys-*`), §3 (split đóng băng), §4.17 (cấu hình full run Day 5);
  - `docs/spec/bench/recsys-algos-v1.md` (registry, funnel);
  - `src/evaluation/reports/eval-2026-10-01-recsys-algos-v1.md` (mẫu report chi tiết);
  - `src/evaluation/reports/eval-2026-10-02-search-local-fair.md` (lý do chọn e5-small).
- Lịch: theo `docs/plan/2026-09-28-lich-10-ngay-3-engine.md`.

## 0. Đã có trên nhánh và còn thiếu

| Mục | Đã có | Còn thiếu |
|---|---|---|
| Quyết định model | Nhóm chốt **e5-small / 384** (`intfloat/multilingual-e5-small`), bỏ Cohere (05/10) | Đề xuất PRD FR-SRC-02 — ngoài phạm vi plan này |
| Vector | `bench_out/search/data/vec_T3+R_e5-{small,base}.{npy,ids.json,meta.json}`: 3.183 unit, catalog 2026-09-23, text `catalog-text-v2`, đã chuẩn hoá L2. e5-small 384 chiều, e5-base 768 chiều | — (không embed lại) |
| Split đóng băng | `frozen/split-{llbo,temporal}-asof20260924.json` (LLBO 1.016 khách, `frozenSha256 1c31d43c…`; temporal 98 khách). `run --split-file` tự đối chiếu event với file, lệch thì dừng mã 1 | DB local phải seed đúng catalog 2026-09-23, `AS_OF=2026-09-24`, `SEED=42` |
| Lệnh chạy | `run --arm … --algos algos_v1.yaml --mode funnel\|raw`, `analyze`, `compare`, `report`; `regress --ref-run-id` so ids giữa hai run; `make recsys-gate-run` nhận `RECSYS_VECTORS` | `--vectors` chỉ nhận `none` / `weaviate` / `numpy`, và luôn lấy vector có `modelVersion` Cohere từ Weaviate → **thiếu chế độ đọc `.npy`**. `compare` (Δ + CI) chỉ so hai arm **trong cùng run** → Δ giữa hai model tính bằng script riêng (phụ lục report) |
| Máy Khôi | Docker; container `travel-recommendation-product-postgres-1` (đã dừng, seed chưa rõ) | Chưa từng chạy bench RecSys (chưa có `bench_out/recsys/`); `vsf2` thiếu `implicit`; working tree có thay đổi chưa commit ở `src/data_collection/seed/` |

**Không cần Weaviate:** chế độ `.npy` nạp vector vào `NumpyVectorSearch` trong RAM. Engine và funnel lấy số chiều từ chính ma trận
(`NumpyVectorSearch.dimension`, `models/data.py`), nên 384 hay 768 chiều đều chạy.

**Phần không đổi theo vector:** scorer CF (`itemknn`, `ease`, `rp3beta`, `ials`, `bpr`, `cooc_trip`) chấm trên pool mask bằng đồng
tương tác. Khi `vectorsMissing = 0` ở cả hai model, ids của các scorer này phải **trùng** giữa run e5-small và run e5-base. Đây là
kiểm chéo đường nạp (7.3). Phần đổi theo vector: `engine`, `content_profile*`, `star_blend*`, pool `engine` (ANN top-200).

**Quy tắc đọc kết quả — ghi trước khi nhìn số:**
- **Engine dùng e5-small phải vượt baseline trong cùng run:** `engine` thắng `most_popular_in_destination` ở hit@20 và NDCG@10 trên
  LLBO, với CI95 nằm hẳn trên 0 (tiêu chí M5, lịch 10 ngày). Availability ≥ 95 %, coverage > 20 %.
- **e5-small so với e5-base:** e5-small được giữ nếu `engine` không thua e5-base quá **1,0 điểm** hit@20 hoặc NDCG@10 với CI95 nằm hẳn
  dưới 0, và không phân khúc nào có n ≥ 20 thua quá **3,0 điểm** hit@20 (ngưỡng như `baseline_v1.thresholds`). Thua quá ngưỡng → ghi
  thành rủi ro trong report cho lead; không tự đổi model.
- Temporal chỉ có 98 khách: chênh 1–3 khách là nhiễu, chỉ đọc kèm CI.
- LLBO: 441/1.016 khách đã `add_to_cart` đúng target trước khi mua (§4.17). Số LLBO cao một phần vì tín hiệu này; ghi caveat.

## Day 5 — T6 02/10: nền đã có (RecSys)

Đã xong trên nhánh (R9–R13 trong `docs/plan/2026-10-01-chia-task-day4-search-rec.md` §5.4; spec recsys §4.17): registry thuật toán,
funnel chung, full run hai chế độ, `because[]`, `bpr_numpy` / `bpr_dest`, ADR 2 (xác nhận 02/10), `report_week_3.md`. Các run đó dùng
vector Cohere v3 nên **không dùng làm mốc so** trong plan này. Plan chỉ lấy lại **cấu hình chạy** (tham số funnel, `--max-tier 2`,
split đóng băng) để kết quả e5 cùng điều kiện.

Phần Day 5 còn lại: quyết định model — chốt trễ 05/10 (e5-small); chạy lại RecSys với model mới (D8 `report_week_3.md`) — chính là
plan này.

## Day 6 — T2 05/10: môi trường, DB khớp split, đường nạp `.npy`

| # | Việc | Lệnh / đầu ra | Xong khi |
|---|---|---|---|
| 6.1 | Báo tqanh123 phạm vi sửa code | Chỉ `recsys_bench/data_source.py` (chế độ `npy`) + test mới; `compare` giữ nguyên | Bạn ấy đồng ý; pull `bench_search_recomSys` mới nhất |
| 6.2 | Môi trường | Cài `scipy`, `implicit 0.7.3`, `threadpoolctl` vào `vsf2`; chạy `make recsys-test RECSYS_PYTHON=<python vsf2>` | Test `recsys_bench` xanh |
| 6.3 | DB local khớp split đóng băng | Seed từ **worktree sạch** của commit hiện tại, để không đụng thay đổi chưa commit ở `src/data_collection/seed/`: `make demo-db CATALOG_SNAPSHOT=data_collection/snapshots/2026-09-23/products.jsonl.gz AS_OF=2026-09-24 SEED=42` (Makefile mặc định snapshot 2026-09-30). Rồi chạy `doctor` | `doctor`: 3.183 search unit, 2.384 recommendable |
| 6.4 | File môi trường `RECSYS_ENV` | `DATABASE_URL` (role `vota_app`), `EVAL_DATABASE_URL` (role `cdp_eval_login`) trỏ Postgres local. Không commit file này | `doctor` qua phần catalog và CDP |
| 6.5 | Code `--vectors npy:<prefix>` | `data_source.load_index` đọc `<prefix>.npy` + `.ids.json` + `.meta.json` → `NumpyVectorSearch`. `modelVersion = cache_model + ":" + text_builder_version`. Từ chối khi `text_builder_version` ≠ `TEXT_BUILDER_VERSION`, khi `dim` lệch, khi không chuẩn hoá L2, hoặc khi có < 50 % unit có vector (như luật hiện tại). Báo `vectorsMissing`; `summary.vectors = "npy:<tên file>"` | Test toy không cần DB (`tests/test_data_source_npy.py`); `--help` vẫn không cần `implicit`; `make recsys-test` xanh |
| 6.6 | Smoke | `run --arm random --arm most_popular_in_destination --arm engine --split llbo --vectors npy:<dir>/vec_T3+R_e5-small --split-file frozen/split-llbo-asof20260924.json --limit-users 50` | Exit 0, `frozenSha256` khớp, `vectorsMissing 0`, `modelVersion intfloat/multilingual-e5-small:catalog-text-v2` |
| 6.7 | Ghi lại | Entry `history/2026-10-05-recsys-bench-npy-vectors.md` | Kèm lệnh và kết quả thật |

## Day 7 — T3 06/10: chạy bench e5-small và e5-base

Mỗi model chạy đủ bộ dưới đây; `<m>` ∈ {`e5s`, `e5b`}.

| # | Việc | Lệnh / đầu ra | Xong khi |
|---|---|---|---|
| 7.1 | Arm engine + baseline | `run --arm random --arm most_popular --arm most_popular_in_destination --arm engine --arm engine_nommr --vectors npy:… --split {llbo,temporal} --split-file … --run-id 2026-10-06-{llbo,temporal}-v5-<m>` | Exit 0 cả hai split; availability ≥ 95 % |
| 7.2 | Gate trong run | `make recsys-gate-run RECSYS_VECTORS=npy:… RECSYS_SPLIT={llbo,temporal} RECSYS_RUN=2026-10-06-{llbo,temporal}-gate-<m>` | G1 `content_profile+mmr` ≡ `engine`, G2 `content_profile` ≡ `engine_nommr[:20]`, `star_blend_a1` ≡ `content_profile`: 100 % |
| 7.3 | Full run bảng thuật toán | Cùng cấu hình Day 5 (§4.17): `run --algos algos_v1.yaml --mode {funnel,raw} --funnel-pool mask --funnel-rerank none --funnel-rerank mmr --max-tier 2 --vectors npy:…`, cả hai split. Run id `2026-10-06-{llbo,temporal}-algos-{funnel,raw}-<m>` | 8 run exit 0, `expectFailed []`, leak 0 |
| 7.4 | Kiểm chéo phần không đổi | `regress --run-id …-algos-funnel-e5s --ref-run-id …-algos-funnel-e5b --base itemknn --ref itemknn`; tương tự với `ease`, `ials` | Trùng 100 %. Không trùng → đường nạp vector ảnh hưởng nhầm chỗ, dừng và sửa |
| 7.5 | So trong run | `compare --run-id 2026-10-06-{split}-v5-<m> --base engine --ref most_popular_in_destination` | Δ + CI95 engine so với baseline, cho từng model |
| 7.6 | So e5-small với e5-base | Script trong phụ lục report: ghép `per_user.jsonl` hai run theo khách, paired bootstrap (10.000 lần, seed 42, cùng công thức `compare.py`) cho `engine`, `content_profile`, `star_blend_a1` | Δ e5-small − e5-base + CI95 + p, hai split |
| 7.7 | Phân tích | `analyze --run-id 2026-10-06-{split}-v5-<m>`: ceiling, phân khúc cold-start / chuyến mở / dormant, strict / lenient, 20 ca | Có `ceiling.md`, `segments.md`, `cases.md` cho cả hai model |
| 7.8 | Tốc độ | `p95/p99 ms` của `engine` (384 so với 768 chiều) và `Fit s` của scorer | Ghi vào report; không thay số đo HTTP |

## Day 8 — T4 07/10: kết luận và report chi tiết

| # | Việc | Đầu ra | Xong khi |
|---|---|---|---|
| 8.1 | Áp quy tắc §0 | Đoạn kết luận: engine e5-small có vượt baseline không; e5-small có giữ được so với e5-base không; theo từng split | Có số, CI, phân khúc |
| 8.2 | Report chi tiết | `src/evaluation/reports/eval-2026-10-07-recsys-e5-small-vs-e5-base.md`, theo mẫu `eval-2026-10-01-recsys-algos-v1.md`: commit, run id, split sha, `modelVersion`, bảng engine + baseline, bảng thuật toán (funnel / raw, hai split, hai model), Δ + CI, phân khúc, ceiling, coverage / Gini, because, tốc độ, caveat dữ liệu sinh, lệnh tái sinh, script phụ lục | Mọi số chép nguyên văn từ output lệnh |
| 8.3 | Bàn giao | Gửi report cho tqanh123 và lead; entry `history/` | Report được review |

## Ngoài phạm vi plan này

- So với Cohere v3 / `baseline_v1`.
- Đề xuất `docs/prd/update/` đổi FR-SRC-02 sang e5-small — track Search / lead; report 8.2 là bằng chứng phía RecSys.
- `baseline_v2` cho e5 — sau khi đề xuất PRD được chốt (tqanh123).
- Grid ADR 2 (`W_SHORT/W_POP`, λ MMR), `targetInOwnHistory` — tqanh123.
- Đổi production sang e5 (collection Weaviate mới, kiểm index = bench, parity offline = HTTP).

## Rủi ro

- **Seed lệch split đóng băng:** seed bằng snapshot 2026-09-30 (mặc định Makefile) hoặc kèm thay đổi chưa commit → `run --split-file`
  dừng mã 1. Seed từ worktree sạch như 6.3.
- **`implicit` khác phiên bản Day 5:** chỉ ảnh hưởng `ials` / `bpr`; hai model e5 chạy cùng môi trường nên so với nhau vẫn công bằng.
- **Không có mốc ngoài:** bỏ Cohere nên không biết e5 hơn hay kém hệ thống đang chạy. Kết luận chỉ là "e5-small đủ tốt so với baseline
  và so với e5-base".
- **Search và RecSys dùng chung collection `Product`:** đổi model là đổi cho cả hai.
- **Sửa code của người khác:** `recsys_bench/data_source.py` do tqanh123 làm; thay đổi có test và được review (6.1).
