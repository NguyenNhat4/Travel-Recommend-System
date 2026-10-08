# RecSys bench — engine v5 trên bộ split `asof20260924`, đủ cột handbook §12 (Day 4 R, 01/10)

- Commit: nhánh `bench/day4-rec` = `bench_search_recomSys@a6f920b` + merge `origin/bench/m6-trip-ended@8842c3a` → `69e01a5`; `git describe` lúc chạy `gold_v2-117-g69e01a5-dirty` (dirty = code harness Day 4 — Gini, cross-cat chuyến mở, `compare`, `report` — chưa commit lúc chạy; **engine không đổi** so với `69e01a5`).
- Chạy lúc: 2026-10-01 13:28–13:36 (+07), máy dev Windows. Postgres local `localhost:5432/vota` seed 2026-09-23 (`as_of` suy ra 2026-09-24; 7.145 event thô → 6.993 sau lọc: orphan 63, thiếu gid 94; 3.183 search unit / 2.384 recommendable). Weaviate local 1.27.0, collection `Product` 3.183 object, `vectorsMissing 0`.
- Sanity (spec §2.1) trên DB này 01/10: **PASS 6/6** kiểm tra cứng (lifecycle 25,1 / 45,0 / 20,0 / 10,0 %; tính lại lệch 0; chuyến ≥ 2 vertical 64,1 %; 0 chuyến ≥ 2 điểm đến; orphan 2,0 % · thiếu gid 3,0 %). Chỉ báo: top-10 % sản phẩm chiếm 39,0 % purchase, Gini sản phẩm 0,397 / search unit 0,502, Zipf −0,59.
- Split đóng băng (spec §3.1): `src/evaluation/recsys_bench/frozen/split-llbo-asof20260924.json` (sha `1c31d43cfc28…fd1dda`, **1.016 khách**, có VP0000001 và VP0000003) · `split-temporal-asof20260924.json` (sha `49727f856865…07cf5`, **98 khách**, T = 2026-07-10T09:13:21Z, phân vị 0,8); event sha `cccdf9d01c84…57d57`.
- Engine v5 (`ENGINE_RULES_VERSION 2026-10-02-trip-ended`, trip mở theo `usingDate`, N = 14): `configHash` eval **`b0aee886`** / prod **`81d16abd`** — **khớp** report v5 `eval-2026-10-02-recsys-bench-v5.md` (cùng code engine); `modelVersion embed-multilingual-v3.0:catalog-text-v2`; k = 20; `candidate_k` 200; không `--override`.
- Arm: `random` (3 seed 42/43/44) · `most_popular` (cửa sổ 90 ngày) · `most_popular_in_destination` (mpd) · `engine` (mode eval, bỏ cap) · `engine_prod` (cap 2 món/taxonomy = list production) · `engine_nommr` (pool 200 theo score, chẩn đoán).
- Run: `bench_out/recsys/runs/2026-10-01-llbo-v5/`, `…/2026-10-01-temporal-v5/` (không commit; mỗi thư mục có `summary.json`, `per_user.jsonl`, `ceiling/segments/strict/cases.md`, `compare-*.md`, `report.md` do lệnh `report` sinh).
- Phục vụ: FR-REC-01..04, NFR-PERF-01 (`docs/prd/requirements.md`); test-plan §2.5; handbook §12. Phân tích và định nghĩa cột: `docs/spec/bench/recsys-offline-eval.md` §4.15, §7.

> **Caveat bắt buộc (handbook §12):** lịch sử khách hàng là dữ liệu sinh. Các số này cho biết pipeline chạy đúng, không cho biết
> engine sẽ chạy thế nào trên khách thật.
>
> **Không so chữ số với report v5 (`asof20260922`, seed 21/09, 1.007 / 102 khách):** khác tập khách, target và catalog
> (2.897 vs 3.183 unit). `configHash` giống nhau chỉ chứng minh cùng code engine. Mọi kết luận dưới đây so **các arm trong cùng run**.

## 1. LLBO (1.016 khách) — nguyên văn `run`

| Arm | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Cross-category | Cross-cat chuyến mở | Cross-cat chuyến mở, có mua | Gini | Diversity@10 | Trả về (TB) | p95 ms | p99 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| random (3 seed) | 1016 | 0.0010 ± 0.0008 | 0.0010 ± 0.0008 | 0.0036 ± 0.0020 | 0.0066 ± 0.0023 | 0.0018 ± 0.0012 | 0.999 ± 0.000 | 1.000 | 0.236 ± 0.000 | 0.303 ± 0.001 | 0.233 ± 0.001 | 0.191 ± 0.003 | 0.518 ± 0.004 | 20.0 | 0.0 ± 0.0 | 0.1 ± 0.0 |
| most_popular | 1016 | 0.0915 | 0.0543 | 0.1614 | 0.2530 | 0.0769 | 0.069 | 1.000 | 0.766 | 0.802 | 0.782 | 0.982 | 0.555 | 19.9 | 10.3 | 14.0 |
| most_popular_in_destination | 1016 | 0.4833 | 0.3593 | 0.5492 | 0.6024 | 0.3803 | 0.400 | 1.000 | 0.396 | 0.455 | 0.400 | 0.819 | 0.622 | 19.9 | 10.3 | 14.6 |
| engine | 1016 | 0.6398 | 0.4843 | 0.7411 | 0.8484 | 0.5169 | 0.565 | 1.000 | 0.914 | 1.000 | 1.000 | 0.834 | 0.560 | 16.3 | 63.1 | 92.8 |
| engine_prod | 1016 | 0.5817 | 0.4588 | 0.6191 | 0.6191 | 0.4718 | 0.207 | 1.000 | 0.953 | 1.000 | 1.000 | 0.930 | 0.642 | 5.3 | 50.1 | 79.8 |
| engine_nommr | 1016 | 0.6742 | 0.5117 | 0.7815 | 0.8750 | 0.5462 | 0.563 | 1.000 | 0.913 | 1.000 | 1.000 | 0.823 | 0.532 | 46.5 | 51.4 | 82.7 |

Khách có chuyến mở tại as_of: 1016 (trong đó đã mua ≥ 1 món trong chuyến: 923) — mẫu số hai cột *Cross-cat chuyến mở*; chuyến chỉ có view thì mọi item đều tính là cross. Gini và Coverage tính trên mọi unit recommendable.

- `most_popular` strategy: `{'most_popular': 1016}` · `most_popular_in_destination`: `{'most_popular_in_destination': 1014, 'most_popular_fallback': 2}`
- `engine` / `engine_prod` / `engine_nommr` strategy: `{'cross_vertical': 923, 'recent_activity': 93}` (LLBO: as_of = lúc mua món bị giấu nên mọi khách đều có chuyến mở; 923 chuyến đã mua ≥ 1 món = 923 `cross_vertical`).

## 2. Temporal (98 khách) — nguyên văn `run`

| Arm | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Cross-category | Cross-cat chuyến mở | Cross-cat chuyến mở, có mua | Gini | Diversity@10 | Trả về (TB) | p95 ms | p99 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| random (3 seed) | 98 | 0.0034 ± 0.0048 | 0.0034 ± 0.0048 | 0.0034 ± 0.0048 | 0.0034 ± 0.0048 | 0.0034 ± 0.0048 | 0.563 ± 0.007 | 1.000 | 0.322 ± 0.010 | 0.767 ± 0.013 | 0.352 ± 0.036 | 0.562 ± 0.008 | 0.515 ± 0.005 | 20.0 | 0.0 ± 0.0 | 0.3 ± 0.3 |
| most_popular | 98 | 0.0000 | 0.0000 | 0.0102 | 0.0408 | 0.0031 | 0.008 | 1.000 | 0.643 | 0.898 | 0.717 | 0.992 | 0.600 | 20.0 | 0.4 | 0.8 |
| most_popular_in_destination | 98 | 0.0510 | 0.0244 | 0.0918 | 0.1020 | 0.0376 | 0.133 | 1.000 | 0.370 | 0.766 | 0.350 | 0.921 | 0.633 | 20.0 | 0.4 | 0.5 |
| engine | 98 | 0.1735 | 0.1505 | 0.1735 | 0.1939 | 0.1505 | 0.315 | 1.000 | 0.348 | 1.000 | 1.000 | 0.854 | 0.629 | 19.7 | 89.8 | 93.2 |
| engine_prod | 98 | 0.1327 | 0.1327 | 0.1327 | 0.1327 | 0.1327 | 0.083 | 1.000 | 0.640 | 1.000 | 1.000 | 0.970 | 0.810 | 7.4 | 58.5 | 68.1 |
| engine_nommr | 98 | 0.1735 | 0.1550 | 0.1837 | 0.1939 | 0.1581 | 0.342 | 1.000 | 0.308 | 1.000 | 1.000 | 0.820 | 0.449 | 176.6 | 58.9 | 64.6 |

Khách có chuyến mở tại as_of: 25 (trong đó đã mua ≥ 1 món trong chuyến: 9) — mẫu số hai cột *Cross-cat chuyến mở*. Target: hotel 93, attraction 4, combo 1.

- `engine` / `engine_prod` / `engine_nommr` strategy: `{'long_term': 57, 'dormant': 16, 'cold_start_content': 10, 'cross_vertical': 9, 'recent_activity': 6}`.

## 3. So cặp — paired bootstrap 10.000 lượt, seed 42 (`compare`; Δ = base − ref, điểm phần trăm; p một phía H0: base ≤ ref)

LLBO, n = 1.016:

| Cặp | hit@5 | hit@10 | hit@20 | ndcg@5 | ndcg@10 |
|---|---:|---:|---:|---:|---:|
| engine − mpd | +15.65 [+12.70; +18.60] p 0.0000 | +19.19 [+16.34; +22.05] p 0.0000 | **+24.61 [+21.75; +27.56]** p 0.0000 | +12.50 [+10.43; +14.62] p 0.0000 | **+13.66 [+11.69; +15.60]** p 0.0000 |
| engine_prod − mpd | +9.84 [+6.99; +12.70] p 0.0000 | +6.99 [+4.33; +9.65] p 0.0000 | **+1.67 [−1.08; +4.43] p 0.1157** | +9.95 [+7.88; +12.12] p 0.0000 | +9.16 [+7.19; +11.16] p 0.0000 |
| engine − engine_nommr | −3.44 [−5.41; −1.48] p 0.9999 | −4.04 [−6.01; −2.07] p 1.0000 | −2.66 [−4.33; −0.98] p 0.9988 | −2.74 [−3.75; −1.75] p 1.0000 | −2.93 [−3.78; −2.10] p 1.0000 |

Temporal, n = 98:

| Cặp | hit@5 | hit@10 | hit@20 | ndcg@5 | ndcg@10 |
|---|---:|---:|---:|---:|---:|
| engine − mpd | +12.24 [+5.10; +20.41] p 0.0008 | +8.16 [+2.04; +15.31] p 0.0065 | **+9.18 [+3.06; +16.33]** p 0.0015 | +12.61 [+6.21; +19.57] p 0.0001 | **+11.28 [+5.44; +17.79]** p 0.0001 |
| engine_prod − mpd | +8.16 [+1.02; +15.31] p 0.0123 | +4.08 [−3.06; +11.22] p 0.1210 | **+3.06 [−3.06; +9.18] p 0.1815** | +10.83 [+4.59; +17.81] p 0.0003 | +9.50 [+3.64; +15.99] p 0.0006 |

Đọc: `engine` (eval) thắng mpd có ý nghĩa ở mọi chỉ số trên cả hai split. List production (`engine_prod`, cap 2/taxonomy) chỉ còn thắng ở NDCG (thứ hạng đầu) — ở hit@20 CI chứa 0 trên **cả hai** split (I-5). MMR làm engine mất ~3 điểm hit/NDCG so với xếp theo score (`engine_nommr`), CI không chứa 0.

## 4. Ceiling — trần recall theo bộ lọc cứng của engine (`analyze`)

| Split | Khách | Ceiling | Recall@20 engine | Recall@20 trên khách tới được | mpd Recall@20 | Đồng thuận chính xác / xấp xỉ | Lý do không tới được (đa nhãn → lý do đầu) |
|---|---:|---:|---:|---:|---:|---:|---|
| LLBO | 1016 | **0.988** (1004/1016) | 0.848 | 0.859 | 0.602 | 1.000 | `already_bought` 10 → 10 · `destination_mismatch` 2 → 2 |
| Temporal | 98 | **0.918** (90/98) | 0.194 | 0.211 | 0.102 | 1.000 | `taxonomy_excluded` 4 → 4 · `destination_mismatch` 7 → 3 · `already_bought` 1 → 1 |

Cả hai: ceiling ≥ Recall@20 mpd → filter **không** phải nút thắt (luật đọc plan Day 3). Temporal: 4 khách (`VP0000935`, `VP0001058`, `VP0001254`, `VP0001466`, đều `cross_vertical`) mang **cả hai** nhãn `taxonomy_excluded` + `destination_mismatch` nên tổng đa nhãn 12 > 8 khách không tới được — chuyến mở tại T chưa đi, target là chuyến kế ở điểm đến khác và cùng loại (hotel): giới hạn của split temporal (as_of = T), không phải lỗi engine.

Engine trượt top-20 mà mpd trúng (`cases.md`): LLBO **20/1.016** (`mmr_demoted` 10, `filtered` 6, `ranked_low` 3, `wrong_active_trip` 1); temporal **1/98** (`filtered`: VP0000001, target là unit đã mua — `already_bought`, loại có chủ đích).

## 5. Phân khúc — hit@20 / NDCG@10 (`segments.md`; nhãn tính một lần từ train, áp cho mọi arm)

LLBO:

| Nhãn | Giá trị | n | engine | engine_prod | engine_nommr | most_popular | mpd |
|---|---|---:|---:|---:|---:|---:|---:|
| strategy | cross_vertical | 923 | 0.844 / 0.491 | 0.600 / 0.445 | 0.872 / 0.523 | 0.274 / 0.083 | 0.634 / 0.406 |
| strategy | recent_activity | 93 | 0.892 / 0.773 | 0.806 / 0.740 | 0.903 / 0.774 | 0.043 / 0.011 | 0.290 / 0.125 |
| coldStart | False | 678 | 0.851 / 0.527 | 0.614 / 0.477 | 0.879 / 0.553 | 0.224 / 0.070 | 0.575 / 0.353 |
| coldStart | True | 338 | 0.843 / 0.497 | 0.630 / 0.461 | 0.867 / 0.533 | 0.311 / 0.092 | 0.657 / 0.434 |
| lifecycleAtAsOf | active | 984 | 0.848 / 0.508 | 0.613 / 0.463 | 0.874 / 0.538 | 0.260 / 0.079 | 0.611 / 0.388 |
| lifecycleAtAsOf | dormant | 32 | 0.875 / 0.776 | 0.812 / 0.747 | 0.906 / 0.784 | 0.031 / 0.013 | 0.344 / 0.155 |
| targetTaxonomy | flight | 433 | 0.827 / 0.510 | 0.679 / 0.500 | 0.891 / 0.587 | 0.409 / 0.146 | 0.762 / 0.529 |
| targetTaxonomy | attraction | 330 | 0.845 / 0.495 | 0.500 / 0.402 | 0.833 / 0.477 | 0.200 / 0.043 | 0.582 / 0.373 |
| targetTaxonomy | combo | 123 | 0.829 / 0.321 | 0.447 / 0.254 | 0.870 / 0.368 | 0.008 / 0.000 | 0.293 / 0.093 |
| targetTaxonomy | hotel | 80 | 0.912 / 0.798 | 0.812 / 0.760 | 0.925 / 0.807 | 0.000 / 0.000 | 0.212 / 0.062 |
| targetTaxonomy | golf | 50 | 1.000 / 0.753 | 1.000 / 0.762 | 0.940 / 0.671 | 0.260 / 0.012 | 0.740 / 0.351 |

Temporal (nhóm n < 20 là *ồn*, chỉ đọc hướng):

| Nhãn | Giá trị | n | engine | engine_prod | engine_nommr | most_popular | mpd |
|---|---|---:|---:|---:|---:|---:|---:|
| strategy | long_term | 57 | 0.035 / 0.000 | 0.000 / 0.000 | 0.035 / 0.005 | 0.035 / 0.005 | 0.035 / 0.018 |
| strategy | dormant *(ồn)* | 16 | 0.062 / 0.024 | 0.000 / 0.000 | 0.062 / 0.039 | 0.000 / 0.000 | 0.062 / 0.022 |
| strategy | cold_start_content *(ồn)* | 10 | 1.000 / 0.950 | 0.900 / 0.900 | 1.000 / 0.963 | 0.000 / 0.000 | 0.300 / 0.065 |
| strategy | cross_vertical *(ồn)* | 9 | 0.111 / 0.048 | 0.000 / 0.000 | 0.111 / 0.048 | 0.222 / 0.000 | 0.111 / 0.043 |
| strategy | recent_activity *(ồn)* | 6 | 0.833 / 0.738 | 0.667 / 0.667 | 0.833 / 0.750 | 0.000 / 0.000 | 0.500 / 0.217 |
| coldStart | False | 74 | 0.108 / 0.065 | 0.054 / 0.054 | 0.095 / 0.073 | 0.041 / 0.004 | 0.081 / 0.036 |
| coldStart | True | 24 | 0.458 / 0.414 | 0.375 / 0.375 | 0.500 / 0.419 | 0.042 / 0.000 | 0.167 / 0.043 |
| lifecycleAtAsOf | active | 68 | 0.103 / 0.057 | 0.044 / 0.044 | 0.103 / 0.062 | 0.059 / 0.004 | 0.074 / 0.032 |
| lifecycleAtAsOf | dormant *(ồn)* | 18 | 0.111 / 0.077 | 0.056 / 0.056 | 0.111 / 0.091 | 0.000 / 0.000 | 0.111 / 0.048 |
| lifecycleAtAsOf | new *(ồn)* | 12 | 0.833 / 0.792 | 0.750 / 0.750 | 0.833 / 0.803 | 0.000 / 0.000 | 0.250 / 0.054 |

Strict vs lenient (`strict.md`): flight (433) và hotel (80) có target là chuyến / phòng con → strict = 0 theo cấu trúc ở mọi arm; attraction / combo / golf strict = lenient.

## 6. P1 / P3 sau M6 (R7) — `user --id … --k 5`, as_of 2026-09-24, engine mode prod, không HTTP

| Khách | Kỳ vọng | Kết quả |
|---|---|---|
| P1 `VP0000001` (12 event, 8 trip; chuyến mở Nha Trang có `usingDate` = as_of + 12, đã mua hotel) | `cross_vertical` · `excludedVerticals ["hotel"]` · không hotel · `nextVertical ∈ {flight, attraction}` | **4/4 đạt**: flight, golf, attraction, flight, attraction (đều Nha Trang, mỗi món 1 `because`, `daysAgo` 2); `nextVertical flight`; `latencyMs` 42; 0 lỗi contract; dư field `sections` (I-4); rank 2 là golf (I-1 còn) |
| P3 `VP0000003` (6 event, 4 trip; chuyến cuối as_of − 190) | `dormant` · `excludedVerticals []` · `coldStart false` · `because` có và mọi `daysAgo` > `DORMANT_AFTER_DAYS` 180 | **4/4 đạt**: hotel Phú Quốc, attraction Phan Thiết, flight Phú Quốc, hotel Phú Quốc, golf Phú Quốc (mỗi món 2 `because`, `daysAgo` 189); `nextVertical hotel`, `destination null`; `latencyMs` 74; 0 lỗi contract; dư `sections` |

Contract 1.12.0 đủ field (`nextVertical`, `excludedVerticals`, `modelVersion`, `diagnostics`) → không mở PR contract. Lệch còn ghi nhận: contract §4.4 nói dormant ⟹ `because.daysAgo > 90`, code dùng 180 (spec §6 I-8).

## 7. Đối chiếu ngưỡng (handbook §12, lịch 10 ngày M5, NFR-PERF-01)

| Ngưỡng | LLBO | Temporal |
|---|---|---|
| Thắng mpd rõ ở Recall@20 và NDCG@10 | engine **đạt** (Δ +24,6 / +13,7 điểm, CI không chứa 0); engine_prod chỉ đạt NDCG | engine **đạt** (+9,2 / +11,3); engine_prod chỉ đạt NDCG |
| Availability ≥ 95 % | 1,000 mọi arm | 1,000 mọi arm |
| Coverage > 20 % | engine 0,565 đạt · engine_prod 0,207 đạt sát | engine 0,315 đạt · engine_prod **0,083 không đạt** (98 khách × 7,4 món) |
| p95 ≤ 250 ms (NFR-PERF-01) | offline 63,1 ms (xếp hạng, không HTTP) — **không thay** số đo HTTP | offline 89,8 ms |

## 8. Đọc nhanh (hướng, không phải quyết định — ADR 2 của plan Day 4–5 ra danh sách tuần sau)

1. **Cap 2 món/taxonomy (I-5) là nút thắt lớn nhất của list production:** hit@20 0,848 → 0,619, coverage 0,565 → 0,207 (LLBO); trên temporal `engine_prod` ≈ mpd ở hit@20. Mất ở attraction (0,845 → 0,500) và combo (0,829 → 0,447), không ở hotel / golf.
2. **MMR (λ 0,7) đổi ~3 điểm hit/NDCG** lấy Diversity@10 0,560 vs 0,532 — ứng viên grid tuần sau (λ 0,85 / chỉ MMR sau top-5), chạy trên temporal theo quy ước B10.
3. **Cross-cat chuyến mở của engine = 1,000 theo cấu trúc** (hard filter FR-REC-02) — cột này kiểm engine đúng luật, không đo chất lượng; mpd gợi lại vertical đã mua trong chuyến ~60 % (0,400), most_popular 0,782. Khi nói về cross-sell, trích cột **có mua**.
4. **Gini:** engine 0,834 ≈ mpd 0,819 dù coverage cao hơn (0,565 vs 0,400) → engine chạm nhiều unit hơn nhưng exposure vẫn dồn; `engine_prod` 0,930 (ít món); random 0,191 (sàn), most_popular 0,982 (trần).
5. **Temporal:** engine ≈ mpd ở `long_term` (57 khách, 0,035 cả hai) và `dormant` — vector dài hạn không hơn popular theo điểm đến cho chuyến kế (như finding 7 cũ); hit đến từ `cold_start_content` 10/10 và `recent_activity` 5/6. Random 0,0034 ≈ 20/5.800 kỳ vọng.
6. **Ceiling** không phải nút thắt ở cả hai split; 8 target temporal không tới được là chuyến chưa đi tại T → cần split "next trip" trước khi kết luận gì về `cross_vertical` giữa hai chuyến.

## 9. Caveat khi trích dẫn

- Dữ liệu sinh (handbook §12) — xem khung đầu file. `activeTripIsSolo` (view lẻ ngay trước purchase) vẫn là phân khúc do seed tạo ra; `recent_activity` LLBO 0,892 phản ánh cấu trúc seed.
- **Khác DB với report v5** (`asof20260922`): không so chữ số; `configHash` khớp chỉ nói cùng code.
- Temporal 98 khách: chênh 0,01 hit@20 = 1 khách; nhóm n < 20 trong phân khúc là ồn. Target temporal 93/98 là hotel.
- `Cross-cat chuyến mở` (biến thể 1) bị kéo lên bởi chuyến mở chỉ có view (tập đã mua rỗng → mọi item cross): LLBO 93/1.016, temporal 16/25 khách. Cột **có mua** là cột đúng nghĩa handbook.
- Gini và Coverage cùng mẫu số 2.384 unit recommendable; `exposure_gini` đếm cả unit 0 lượt.
- Availability đo theo `attributes.availability` của catalog hôm nay, không tái dựng lịch sử tại `as_of`.
- p95/p99 ms là thời gian xếp hạng offline (Weaviate local, không HTTP, không đọc CDP, máy chạy song song) — không thay số đo HTTP của NFR-PERF-01.
- Code harness lúc chạy chưa commit (`-dirty`); engine production và `configHash` không phụ thuộc phần đó.

## 10. Lệnh tái sinh (từ gốc repo; DSN local theo `.env.example` dòng 98 / 103, không ghi ở đây)

```bash
# env: DATABASE_URL (vota_app_login), EVAL_DATABASE_URL (cdp_eval_login) → Postgres local 5432; Weaviate local
export WEAVIATE_URL=http://127.0.0.1:8080 WEAVIATE_API_KEY= WEAVIATE_GRPC_PORT=50051 PYTHONUTF8=1
python -m src.evaluation.recsys_bench doctor && python -m src.evaluation.recsys_bench sanity
python -m src.evaluation.recsys_bench split --kind llbo --freeze && python -m src.evaluation.recsys_bench split --kind temporal --freeze   # đã commit frozen/*-asof20260924.json
ARMS="--arm random --arm most_popular --arm most_popular_in_destination --arm engine --arm engine_prod --arm engine_nommr"
python -m src.evaluation.recsys_bench run $ARMS --split llbo --vectors weaviate --split-file src/evaluation/recsys_bench/frozen/split-llbo-asof20260924.json --run-id 2026-10-01-llbo-v5
python -m src.evaluation.recsys_bench run $ARMS --split temporal --vectors weaviate --split-file src/evaluation/recsys_bench/frozen/split-temporal-asof20260924.json --run-id 2026-10-01-temporal-v5
for r in 2026-10-01-llbo-v5 2026-10-01-temporal-v5; do python -m src.evaluation.recsys_bench analyze --run-id $r; done
python -m src.evaluation.recsys_bench compare --run-id 2026-10-01-llbo-v5 --base engine --ref most_popular_in_destination
python -m src.evaluation.recsys_bench compare --run-id 2026-10-01-llbo-v5 --base engine_prod --ref most_popular_in_destination
python -m src.evaluation.recsys_bench compare --run-id 2026-10-01-llbo-v5 --base engine --ref engine_nommr
python -m src.evaluation.recsys_bench compare --run-id 2026-10-01-temporal-v5 --base engine --ref most_popular_in_destination
python -m src.evaluation.recsys_bench compare --run-id 2026-10-01-temporal-v5 --base engine_prod --ref most_popular_in_destination
python -m src.evaluation.recsys_bench user --id VP0000001 --k 5 && python -m src.evaluation.recsys_bench user --id VP0000003 --k 5
python -m src.evaluation.recsys_bench report --run-id 2026-10-01-llbo-v5 --run-id 2026-10-01-temporal-v5   # report.md trong từng thư mục run
```
