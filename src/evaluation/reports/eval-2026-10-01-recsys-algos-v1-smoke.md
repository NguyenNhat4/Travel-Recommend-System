# RecSys bench — registry thuật toán `algos_v1`: gate R4 trên dữ liệu thật và smoke Tier 1 hai chế độ (Day 4–5 R3–R6, 01/10)

- Commit: nhánh `bench/day4-rec` sau `993669d` (Day 4 R); code R3–R6 (`src/evaluation/recsys_bench/models/`, `algos_v1.yaml`, CLI
  `run --algos` / `regress`) **chưa commit lúc chạy** → `git describe gold_v2-118-g993669d-dirty`. Engine không đổi (`configHash
  b0aee886`, `ENGINE_RULES_VERSION 2026-10-02-trip-ended`).
- Chạy lúc: 2026-10-01 16:57–17:11 (+07), máy dev Windows; Postgres local seed 09-23 (`as_of` 2026-09-24, 7.145 event → 6.993 sau lọc,
  3.183 search unit / 2.384 recommendable); Weaviate local `Product` 3.183 object (`vectorsMissing 0`); gate dùng `--vectors weaviate`,
  smoke dùng `--vectors numpy` (vector tải một lần, cache `.npz`). Thư viện: numpy 2.5.3 · scipy 1.18.1 · implicit 0.7.3 · threadpoolctl 3.7.0.
- Split đóng băng (spec `recsys-offline-eval.md` §3.1): `frozen/split-llbo-asof20260924.json` (`1c31d43cfc28…`, 1.016 khách) ·
  `frozen/split-temporal-asof20260924.json` (`49727f856865…`, 98 khách, T = 2026-07-10T09:13Z). Mốc v5 = report
  `eval-2026-10-01-recsys-bench-v5-asof20260924.md`.
- Đặc tả: `docs/spec/bench/recsys-algos-v1.md` (errata E1–E12). Quyết định người dùng 01/10: funnel = mask engine; bảng chấm toàn mask
  (`pool mask`), gate `pool engine`; chạy cả hai `rerank` (`none`, `mmr`) cho mọi scorer. Phục vụ FR-REC-01/02/04, test-plan §2.5,
  handbook §12; plan Day 4–5 §2.2.

> **Caveat bắt buộc (handbook §12):** dữ liệu sinh — số đo cho biết pipeline chạy đúng, không nói gì về khách thật.
> **Smoke 50 khách đầu** (`--limit-users 50`) chỉ để kiểm mọi scorer chạy được và lấy thời gian fit; **không kết luận chất lượng**.
> Bảng full run (mọi Tier 1 × 2 rerank × 2 split, phân khúc, CI) là việc Day 5.

## 1. Gate R4 — `content_profile` qua funnel ≡ engine v5 (run `2026-10-01-{llbo,temporal}-gate`)

`run --algos algos_v1.yaml --only content_profile --only star_blend_a1 --mode funnel --funnel-pool engine --funnel-rerank none
--funnel-rerank mmr --vectors weaviate --split-file …` (cùng lời gọi `near_vector` với v5), `algosHash d0d38a58`; so với run v5 bằng
`regress` (`ids[:20]` theo khách, **khớp thứ tự**):

| Phép so | LLBO (1.016) | Temporal (98) |
|---|---:|---:|
| G1 `content_profile+mmr` ≡ `engine` (run v5) | **1016/1016 PASS** | **98/98 PASS** |
| G2 `content_profile` ≡ `engine_nommr[:20]` (run v5), theo thứ tự | 1016/1016 PASS | 98/98 PASS |
| G2 với `--tie-tolerant` | 1016/1016 PASS | 98/98 PASS |
| `star_blend_a1+mmr` ≡ `content_profile+mmr` (trong-run) | 1016/1016 PASS | 98/98 PASS |

Bảng gate LLBO (nguyên văn `run`): `content_profile` R@20 **0.8750** / NDCG@10 **0.5462** (= `engine_nommr` v5), `content_profile+mmr`
**0.8484** / **0.5169** (= `engine` v5), `star_blend_a1` và `star_blend_a1+mmr` trùng từng số; Coverage 0.563 / 0.565, Gini 0.823 / 0.834,
Cross-cat chuyến mở (có mua) 1.000, `Pool cắt` 0.00 (LLBO: pool engine không bị cắt ở 1.012/1.016 khách), p95 7–22 ms, fit
`star_blend_a1` 0.4 s. Temporal: `content_profile` 0.1939 / 0.1581, `content_profile+mmr` 0.1939 / 0.1542 (= `engine_nommr` / `engine` v5).
Kết luận: funnel mirror đúng engine (mask, pool ANN ∪ popular, sort ổn định, MMR) kể cả ở temporal nơi pool bị cắt ở 76/98 khách; sai số ulp
float32 không xuất hiện; mọi scorer khác chạy trên cùng funnel này.

## 2. Smoke Tier 1 (+ `rp3beta` Tier 2) — 50 khách, `pool mask`, rerank none + mmr, hai chế độ × hai split

Run `2026-10-01-{llbo,temporal}-smoke-{funnel,raw}` (`--max-tier 2 --limit-users 50 --vectors numpy`, kèm `most_popular_in_destination`
và `engine` để đối chiếu). `algosHash 3d99e4e8` (funnel) / `ee293a5c` (raw). Mọi scorer exit 0 ở cả bốn run; `expect_equal_to` của
`star_blend_a1` 50/50 PASS ở cả hai rerank. Bốn khối dưới là output nguyên văn của lệnh `report` (bảng, strategy, mẫu số cross-cat,
fit log, X_train, leak check).

### 2.1 Đọc nhanh (50 khách — chỉ là hướng)

1. **Funnel làm phần lớn việc**: LLBO `content_profile` funnel R@20 0.88 vs raw 0.36; `cooc_trip` 0.76 vs 0.48; `ials` 0.69 vs 0.37;
   `bpr` 0.65 vs 0.03. Ở raw, Cross-cat chuyến mở (có mua) của content chỉ 0.07 — không có exclusion thì engine gợi lại vertical đã
   mua. Trên temporal (73/98 khách không trip mở → mask gần như toàn catalog) funnel ≈ raw cho content (0.16 = 0.16).
2. **Co-occurrence thưa**: ở LLBO chỉ 10,3 % item có ≥ 1 láng giềng (279 cặp từ 1.710 trip), `Collab cov.` top-20 ≈ 0.05 →
   `cooc_trip` = `itemknn` = `rp3beta` ra **cùng** top-20 ở `rerank none` (phần còn lại xếp theo `pop_D`); temporal có nhiều trip hơn
   trước T (901 cặp, 23,8 % item) → `Collab cov.` 0.43 nhưng R@20 0.10 ≈ mpd 0.12.
3. **`+mmr` phá scorer thang điểm nhỏ**: cooc/ease/knn/rp3beta có điểm ∈ [0; 0,1] → term đa dạng `0,3·cos` của MMR (λ 0,7 chỉnh cho
   điểm content ≈ 0,3–0,8) lấn át: LLBO 0.76 → 0.54, temporal 0.10 → **0.00**. Chỉ đọc hàng `none` cho các scorer này; `+mmr` có
   nghĩa với `content_profile` / `star_blend` (cùng thang engine).
4. `star_blend` a = 0,5: R@20 bằng content (0.88) nhưng NDCG@10 thấp hơn (0.489 vs 0.546) vì vế semantic bị chia đôi khi `collab` ≈ 0
   (spec §2.2 đã cảnh báo); `star_blend_a1` ≡ content theo cấu trúc.
5. `ease` λ = 200 với `maxDiagG` 19 / 38, `medianDiagG` 0 → ≈ co-occurrence thô / λ (spec §4); `ials` 3 seed ổn định (sd ≤ 0,04);
   `bpr` 3 seed dao động hơn (sd 0,03–0,08 R@20) và gần 0 ở raw — CF thuần ở 7k event ≈ popularity như plan dự đoán.
6. Fit: cooc 0,3–0,4 s · star 0,35–0,43 s · itemknn 0,03 s · ease 0,8–0,9 s · rp3beta 0,3 s · ials 0,1 s/seed · bpr 0,06 s/seed.
   Chấm: ≈ 0,3–0,5 ms/khách (`none`), ≈ 20–40 ms/khách (`mmr`, top-200 × E 1024-d) → full run LLBO 1.016 khách × 19 arm ≈ 5–7 phút.

### 2.2 Output nguyên văn của `report --run-id … ×4`

### Run `2026-10-01-llbo-smoke-funnel`

run 2026-10-01-llbo-smoke-funnel · as_of 2026-09-24T00:00:00+00:00 · model embed-multilingual-v3.0:catalog-text-v2 · configHash b0aee886 · split llbo frozen 1c31d43cfc28 · SUBSET 50/1016 khách · vectors numpy (thiếu 0) · git gold_v2-118-g993669d-dirty · algos 3d99e4e8 mode funnel pool mask rerank none,mmr

Split `llbo` · 1016 khách test · event sha cccdf9d01c84 · đóng băng `src/evaluation/recsys_bench/frozen/split-llbo-asof20260924.json` (1c31d43cfc28) · k = 20 · 3183 search unit / 2384 recommendable

| Arm | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Cross-category | Cross-cat chuyến mở | Cross-cat chuyến mở, có mua | Gini | Diversity@10 | Trả về (TB) | p95 ms | p99 ms | Collab cov. | Pool cắt | Fit s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| most_popular_in_destination | 50 | 0.4800 | 0.3071 | 0.5000 | 0.5200 | 0.3143 | 0.188 | 1.000 | 0.370 | 0.509 | 0.386 | 0.884 | 0.672 | 19.9 | 12.7 | 26.7 | — | — | — |
| engine | 50 | 0.6400 | 0.4755 | 0.7400 | 0.8600 | 0.5070 | 0.192 | 1.000 | 0.833 | 1.000 | 1.000 | 0.874 | 0.584 | 17.8 | 37.1 | 42.2 | — | — | — |
| content_profile | 50 | 0.6400 | 0.5069 | 0.7600 | 0.8800 | 0.5462 | 0.198 | 1.000 | 0.835 | 1.000 | 1.000 | 0.866 | 0.556 | 17.8 | 11.6 | 26.1 | — | 0.00 | 0.0 |
| content_profile+mmr | 50 | 0.6400 | 0.4755 | 0.7400 | 0.8600 | 0.5070 | 0.192 | 1.000 | 0.833 | 1.000 | 1.000 | 0.874 | 0.584 | 17.8 | 22.7 | 32.6 | — | 0.00 | 0.0 |
| cooc_trip | 50 | 0.5600 | 0.3295 | 0.6400 | 0.7600 | 0.3528 | 0.176 | 1.000 | 0.851 | 1.000 | 1.000 | 0.885 | 0.552 | 17.8 | 0.3 | 0.4 | 0.048 | 0.00 | 0.4 |
| cooc_trip+mmr | 50 | 0.2400 | 0.1492 | 0.4000 | 0.5400 | 0.2006 | 0.172 | 1.000 | 0.838 | 1.000 | 1.000 | 0.888 | 0.576 | 17.8 | 19.5 | 23.2 | 0.043 | 0.00 | 0.4 |
| star_blend | 50 | 0.6000 | 0.4295 | 0.7800 | 0.8800 | 0.4889 | 0.196 | 1.000 | 0.837 | 1.000 | 1.000 | 0.868 | 0.568 | 17.8 | 0.4 | 0.5 | 0.039 | 0.00 | 0.4 |
| star_blend+mmr | 50 | 0.6200 | 0.4120 | 0.7600 | 0.8400 | 0.4557 | 0.190 | 1.000 | 0.838 | 1.000 | 1.000 | 0.876 | 0.584 | 17.8 | 19.2 | 24.7 | 0.034 | 0.00 | 0.4 |
| star_blend_a1 | 50 | 0.6400 | 0.5069 | 0.7600 | 0.8800 | 0.5462 | 0.198 | 1.000 | 0.835 | 1.000 | 1.000 | 0.866 | 0.556 | 17.8 | 0.3 | 0.5 | 0.034 | 0.00 | 0.4 |
| star_blend_a1+mmr | 50 | 0.6400 | 0.4755 | 0.7400 | 0.8600 | 0.5070 | 0.192 | 1.000 | 0.833 | 1.000 | 1.000 | 0.874 | 0.584 | 17.8 | 18.2 | 22.0 | 0.030 | 0.00 | 0.4 |
| itemknn | 50 | 0.5600 | 0.3295 | 0.6400 | 0.7600 | 0.3528 | 0.176 | 1.000 | 0.851 | 1.000 | 1.000 | 0.885 | 0.552 | 17.8 | 0.3 | 0.5 | 0.048 | 0.00 | 0.0 |
| itemknn+mmr | 50 | 0.2600 | 0.1618 | 0.4000 | 0.5400 | 0.2065 | 0.172 | 1.000 | 0.838 | 1.000 | 1.000 | 0.888 | 0.572 | 17.8 | 17.8 | 21.7 | 0.046 | 0.00 | 0.0 |
| ease | 50 | 0.5400 | 0.3360 | 0.6200 | 0.7400 | 0.3604 | 0.175 | 1.000 | 0.849 | 1.000 | 1.000 | 0.885 | 0.540 | 17.8 | 0.2 | 0.3 | 0.097 | 0.00 | 0.8 |
| ease+mmr | 50 | 0.2600 | 0.1766 | 0.4000 | 0.5400 | 0.2213 | 0.166 | 1.000 | 0.838 | 1.000 | 1.000 | 0.893 | 0.576 | 17.8 | 18.4 | 22.5 | 0.047 | 0.00 | 0.8 |
| rp3beta | 50 | 0.5600 | 0.3295 | 0.6400 | 0.7600 | 0.3528 | 0.176 | 1.000 | 0.851 | 1.000 | 1.000 | 0.885 | 0.552 | 17.8 | 0.3 | 0.5 | 0.048 | 0.00 | 0.3 |
| rp3beta+mmr | 50 | 0.2200 | 0.1366 | 0.3800 | 0.5400 | 0.1880 | 0.173 | 1.000 | 0.838 | 1.000 | 1.000 | 0.888 | 0.576 | 17.8 | 19.1 | 24.0 | 0.042 | 0.00 | 0.3 |
| ials (3 seed) | 50 | 0.4933 ± 0.0094 | 0.3762 ± 0.0072 | 0.6000 ± 0.0283 | 0.6933 ± 0.0411 | 0.4092 ± 0.0097 | 0.186 ± 0.001 | 1.000 | 0.826 ± 0.002 | 1.000 | 1.000 | 0.875 ± 0.001 | 0.535 ± 0.005 | 17.8 | 2.2 ± 0.0 | 2.6 ± 0.4 | — | 0.00 | 0.1 ± 0.0 |
| ials+mmr (3 seed) | 50 | 0.4400 ± 0.0163 | 0.3515 ± 0.0089 | 0.5733 ± 0.0249 | 0.6800 ± 0.0432 | 0.3929 ± 0.0048 | 0.186 ± 0.001 | 1.000 | 0.831 ± 0.003 | 1.000 | 1.000 | 0.875 ± 0.001 | 0.560 ± 0.009 | 17.8 | 18.4 ± 0.2 | 22.6 ± 1.0 | — | 0.00 | 0.1 ± 0.0 |
| bpr (3 seed) | 50 | 0.3467 ± 0.0525 | 0.2130 ± 0.0560 | 0.5067 ± 0.0411 | 0.6533 ± 0.0340 | 0.2647 ± 0.0500 | 0.160 ± 0.000 | 1.000 | 0.827 ± 0.001 | 1.000 | 1.000 | 0.897 ± 0.000 | 0.523 ± 0.027 | 17.8 | 0.3 ± 0.0 | 0.4 ± 0.1 | — | 0.00 | 0.1 ± 0.0 |
| bpr+mmr (3 seed) | 50 | 0.2667 ± 0.0772 | 0.1736 ± 0.0593 | 0.3800 ± 0.0432 | 0.6200 ± 0.0283 | 0.2092 ± 0.0468 | 0.157 ± 0.001 | 1.000 | 0.831 ± 0.001 | 1.000 | 1.000 | 0.900 ± 0.001 | 0.560 ± 0.026 | 17.8 | 18.4 ± 0.4 | 23.2 ± 0.2 | — | 0.00 | 0.1 ± 0.0 |

- `most_popular_in_destination` strategy: {'most_popular_in_destination': 49, 'most_popular_fallback': 1}
- `engine` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `content_profile` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `content_profile+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `cooc_trip` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `cooc_trip+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `star_blend` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `star_blend+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `star_blend_a1` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `star_blend_a1+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `itemknn` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `itemknn+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `ease` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `ease+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `rp3beta` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `rp3beta+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}

Khách có chuyến mở tại as_of: 50 (trong đó đã mua ≥ 1 món trong chuyến: 40) — mẫu số hai cột *Cross-cat chuyến mở*; chuyến chỉ có view thì mọi item đều tính là cross. Gini và Coverage tính trên mọi unit recommendable.

#### Fit log

Fit log · algos `3d99e4e8` · mode funnel · funnel {"pool": "mask", "reranks": ["none", "mmr"]} · libs {"numpy": "2.5.3", "scipy": "1.18.1", "implicit": "0.7.3", "threadpoolctl": "3.7.0"}

| Algo | seed | rows | n hàng | nnz | item có láng giềng | tham số | khác | fit s |
|---|---|---|---:|---:|---:|---|---|---:|
| content_profile |  |  |  |  |  | {} | {} | 0.0 |
| cooc_trip |  | trip | 1710 | 1985 | 0.103 | {"beta": 5.0, "topK": 50} | {"nnzPairs": 279, "neighboursPerItemMean": 0.17530631479736097} | 0.381 |
| star_blend |  | trip | 1710 | 1985 | 0.103 | {"beta": 5.0, "topK": 50, "a": 0.5, "blendScope": "inner"} | {"nnzPairs": 279, "neighboursPerItemMean": 0.17530631479736097} | 0.351 |
| star_blend_a1 |  | trip | 1710 | 1985 | 0.103 | {"beta": 5.0, "topK": 50, "a": 1.0, "blendScope": "inner"} | {"nnzPairs": 279, "neighboursPerItemMean": 0.17530631479736097} | 0.376 |
| itemknn |  | trip | 1710 | 1985 | 0.103 | {"k": 50, "K_fit": 51} | {"nnzSimilarity": 558, "neighboursPerItemMean": 0.17530631479736097, "implicitVersion": "0.7.3"} | 0.034 |
| ease |  | trip | 1710 | 1985 |  | {"lam": 200.0} | {"maxDiagG": 19.0, "medianDiagG": 0.0, "itemsWithInteraction": 951} | 0.775 |
| rp3beta |  | trip | 1710 |  | 0.103 | {"alpha": 1.0, "beta": 0.6, "topK": 50} | {"nnzPairs": 279, "neighboursPerItemMean": 0.17530631479736097} | 0.298 |
| ials | 42 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 42, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.124 |
| ials | 43 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 43, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.122 |
| ials | 44 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 44, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.116 |
| bpr | 42 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 42, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.057 |
| bpr | 43 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 43, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.056 |
| bpr | 44 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 44, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.057 |

X_train: 5966 event · B 1710 trip × nnz 1985 · U 1486 user, nnz 2468 · ô theo event {"purchase": 1985, "add_to_cart": 1281} · bỏ orphan 0, thiếu gid 1281, thiếu vector 0 · leak check {"usersChecked": 1016, "targetCellInTripRow": 0}

expect_equal_to: `star_blend_a1` vs `content_profile` 50/50 PASS; `star_blend_a1+mmr` vs `content_profile+mmr` 50/50 PASS

Caveat LLBO: ma trận item-item / MF fit **một lần toàn cục** trên X_train (khách test cắt < as_of riêng), nên chứa event của khách khác xảy ra sau as_of của một khách; `pop_D` của engine thì cắt tại as_of — không rò rỉ target nhưng hai nguồn không đối xứng về thời gian. Kết luận so scorer ưu tiên temporal (B10).

### Run `2026-10-01-llbo-smoke-raw`

run 2026-10-01-llbo-smoke-raw · as_of 2026-09-24T00:00:00+00:00 · model embed-multilingual-v3.0:catalog-text-v2 · configHash b0aee886 · split llbo frozen 1c31d43cfc28 · SUBSET 50/1016 khách · vectors numpy (thiếu 0) · git gold_v2-118-g993669d-dirty · algos ee293a5c mode raw pool mask rerank none,mmr

Split `llbo` · 1016 khách test · event sha cccdf9d01c84 · đóng băng `src/evaluation/recsys_bench/frozen/split-llbo-asof20260924.json` (1c31d43cfc28) · k = 20 · 3183 search unit / 2384 recommendable

| Arm | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Cross-category | Cross-cat chuyến mở | Cross-cat chuyến mở, có mua | Gini | Diversity@10 | Trả về (TB) | p95 ms | p99 ms | Collab cov. | Pool cắt | Fit s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| most_popular_in_destination | 50 | 0.4800 | 0.3071 | 0.5000 | 0.5200 | 0.3143 | 0.188 | 1.000 | 0.370 | 0.509 | 0.386 | 0.884 | 0.672 | 19.9 | 7.8 | 19.1 | — | — | — |
| engine | 50 | 0.6400 | 0.4755 | 0.7400 | 0.8600 | 0.5070 | 0.192 | 1.000 | 0.833 | 1.000 | 1.000 | 0.874 | 0.584 | 17.8 | 32.0 | 34.2 | — | — | — |
| content_profile | 50 | 0.3000 | 0.2311 | 0.3600 | 0.3600 | 0.2506 | 0.267 | 1.000 | 0.111 | 0.255 | 0.069 | 0.806 | 0.408 | 20.0 | 17.9 | 37.2 | — | 0.00 | 0.0 |
| content_profile+mmr | 50 | 0.3200 | 0.2557 | 0.3800 | 0.4200 | 0.2749 | 0.281 | 1.000 | 0.137 | 0.281 | 0.101 | 0.788 | 0.540 | 20.0 | 40.9 | 48.3 | — | 0.00 | 0.0 |
| cooc_trip | 50 | 0.4200 | 0.2345 | 0.4600 | 0.4800 | 0.2466 | 0.190 | 1.000 | 0.304 | 0.441 | 0.301 | 0.888 | 0.652 | 20.0 | 0.5 | 0.6 | 0.079 | 0.00 | 0.4 |
| cooc_trip+mmr | 50 | 0.0200 | 0.0200 | 0.0400 | 0.0400 | 0.0267 | 0.076 | 1.000 | 0.448 | 0.582 | 0.477 | 0.972 | 0.704 | 20.0 | 30.0 | 34.5 | 0.027 | 0.00 | 0.4 |
| star_blend | 50 | 0.4000 | 0.2650 | 0.5000 | 0.5600 | 0.2979 | 0.264 | 1.000 | 0.147 | 0.291 | 0.114 | 0.809 | 0.508 | 20.0 | 4.7 | 4.9 | 0.034 | 0.00 | 0.3 |
| star_blend+mmr | 50 | 0.3800 | 0.2369 | 0.5400 | 0.5400 | 0.2877 | 0.274 | 1.000 | 0.171 | 0.316 | 0.145 | 0.797 | 0.620 | 20.0 | 42.7 | 45.0 | 0.033 | 0.00 | 0.3 |
| star_blend_a1 | 50 | 0.3000 | 0.2311 | 0.3600 | 0.3600 | 0.2506 | 0.267 | 1.000 | 0.111 | 0.255 | 0.069 | 0.806 | 0.408 | 20.0 | 4.4 | 5.4 | 0.020 | 0.00 | 0.4 |
| star_blend_a1+mmr | 50 | 0.3200 | 0.2557 | 0.3800 | 0.4200 | 0.2749 | 0.281 | 1.000 | 0.137 | 0.281 | 0.101 | 0.788 | 0.540 | 20.0 | 37.9 | 42.8 | 0.023 | 0.00 | 0.4 |
| itemknn | 50 | 0.4200 | 0.2445 | 0.4600 | 0.4800 | 0.2566 | 0.190 | 1.000 | 0.304 | 0.441 | 0.301 | 0.888 | 0.652 | 20.0 | 0.5 | 0.6 | 0.079 | 0.00 | 0.0 |
| itemknn+mmr | 50 | 0.0800 | 0.0626 | 0.0800 | 0.0800 | 0.0626 | 0.083 | 1.000 | 0.444 | 0.580 | 0.475 | 0.969 | 0.692 | 20.0 | 31.5 | 33.8 | 0.058 | 0.00 | 0.0 |
| ease | 50 | 0.3800 | 0.2319 | 0.4200 | 0.4800 | 0.2440 | 0.196 | 1.000 | 0.334 | 0.472 | 0.340 | 0.883 | 0.640 | 20.0 | 0.5 | 0.6 | 0.142 | 0.00 | 0.9 |
| ease+mmr | 50 | 0.0600 | 0.0600 | 0.0600 | 0.0600 | 0.0600 | 0.072 | 1.000 | 0.445 | 0.580 | 0.475 | 0.973 | 0.696 | 20.0 | 29.9 | 30.9 | 0.032 | 0.00 | 0.9 |
| rp3beta | 50 | 0.4200 | 0.2345 | 0.4600 | 0.4800 | 0.2466 | 0.190 | 1.000 | 0.304 | 0.441 | 0.301 | 0.888 | 0.652 | 20.0 | 0.5 | 0.7 | 0.079 | 0.00 | 0.3 |
| rp3beta+mmr | 50 | 0.0200 | 0.0200 | 0.0200 | 0.0200 | 0.0200 | 0.076 | 1.000 | 0.449 | 0.583 | 0.479 | 0.972 | 0.696 | 20.0 | 37.9 | 40.4 | 0.026 | 0.00 | 0.3 |
| ials (3 seed) | 50 | 0.3200 | 0.2720 ± 0.0032 | 0.3400 ± 0.0163 | 0.3667 ± 0.0094 | 0.2778 ± 0.0020 | 0.238 ± 0.001 | 1.000 | 0.233 ± 0.002 | 0.386 ± 0.003 | 0.233 ± 0.004 | 0.827 ± 0.002 | 0.533 ± 0.013 | 20.0 | 4.1 ± 1.3 | 5.0 ± 2.1 | — | 0.00 | 0.1 ± 0.0 |
| ials+mmr (3 seed) | 50 | 0.3200 | 0.2729 ± 0.0035 | 0.3267 ± 0.0094 | 0.3467 ± 0.0094 | 0.2749 ± 0.0032 | 0.240 ± 0.002 | 1.000 | 0.270 ± 0.009 | 0.424 ± 0.009 | 0.280 ± 0.011 | 0.825 ± 0.002 | 0.624 ± 0.011 | 20.0 | 38.6 ± 3.9 | 40.8 ± 4.6 | — | 0.00 | 0.1 ± 0.0 |
| bpr (3 seed) | 50 | 0.0067 ± 0.0094 | 0.0026 ± 0.0036 | 0.0133 ± 0.0094 | 0.0333 ± 0.0249 | 0.0045 ± 0.0033 | 0.009 ± 0.000 | 1.000 | 0.248 ± 0.068 | 0.395 ± 0.057 | 0.243 ± 0.071 | 0.992 ± 0.000 | 0.728 ± 0.091 | 20.0 | 0.9 ± 0.1 | 1.1 ± 0.1 | — | 0.00 | 0.1 ± 0.0 |
| bpr+mmr (3 seed) | 50 | 0.0067 ± 0.0094 | 0.0042 ± 0.0059 | 0.0267 ± 0.0249 | 0.0400 ± 0.0163 | 0.0110 ± 0.0084 | 0.009 ± 0.000 | 1.000 | 0.412 ± 0.054 | 0.540 ± 0.048 | 0.425 ± 0.061 | 0.992 ± 0.000 | 0.800 ± 0.163 | 20.0 | 38.2 ± 3.7 | 40.1 ± 4.7 | — | 0.00 | 0.1 ± 0.0 |

- `most_popular_in_destination` strategy: {'most_popular_in_destination': 49, 'most_popular_fallback': 1}
- `engine` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `content_profile` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `content_profile+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `cooc_trip` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `cooc_trip+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `star_blend` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `star_blend+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `star_blend_a1` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `star_blend_a1+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `itemknn` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `itemknn+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `ease` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `ease+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `rp3beta` strategy: {'cross_vertical': 40, 'recent_activity': 10}
- `rp3beta+mmr` strategy: {'cross_vertical': 40, 'recent_activity': 10}

Khách có chuyến mở tại as_of: 50 (trong đó đã mua ≥ 1 món trong chuyến: 40) — mẫu số hai cột *Cross-cat chuyến mở*; chuyến chỉ có view thì mọi item đều tính là cross. Gini và Coverage tính trên mọi unit recommendable.

#### Fit log

Fit log · algos `ee293a5c` · mode raw · funnel {"pool": "mask", "reranks": ["none", "mmr"]} · libs {"numpy": "2.5.3", "scipy": "1.18.1", "implicit": "0.7.3", "threadpoolctl": "3.7.0"}

| Algo | seed | rows | n hàng | nnz | item có láng giềng | tham số | khác | fit s |
|---|---|---|---:|---:|---:|---|---|---:|
| content_profile |  |  |  |  |  | {} | {} | 0.0 |
| cooc_trip |  | trip | 1710 | 1985 | 0.103 | {"beta": 5.0, "topK": 50} | {"nnzPairs": 279, "neighboursPerItemMean": 0.17530631479736097} | 0.359 |
| star_blend |  | trip | 1710 | 1985 | 0.103 | {"beta": 5.0, "topK": 50, "a": 0.5, "blendScope": "inner"} | {"nnzPairs": 279, "neighboursPerItemMean": 0.17530631479736097} | 0.349 |
| star_blend_a1 |  | trip | 1710 | 1985 | 0.103 | {"beta": 5.0, "topK": 50, "a": 1.0, "blendScope": "inner"} | {"nnzPairs": 279, "neighboursPerItemMean": 0.17530631479736097} | 0.362 |
| itemknn |  | trip | 1710 | 1985 | 0.103 | {"k": 50, "K_fit": 51} | {"nnzSimilarity": 558, "neighboursPerItemMean": 0.17530631479736097, "implicitVersion": "0.7.3"} | 0.034 |
| ease |  | trip | 1710 | 1985 |  | {"lam": 200.0} | {"maxDiagG": 19.0, "medianDiagG": 0.0, "itemsWithInteraction": 951} | 0.907 |
| rp3beta |  | trip | 1710 |  | 0.103 | {"alpha": 1.0, "beta": 0.6, "topK": 50} | {"nnzPairs": 279, "neighboursPerItemMean": 0.17530631479736097} | 0.3 |
| ials | 42 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 42, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.164 |
| ials | 43 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 43, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.113 |
| ials | 44 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 44, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.111 |
| bpr | 42 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 42, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.062 |
| bpr | 43 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 43, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.064 |
| bpr | 44 | user | 1486 | 2468 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 44, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.057 |

X_train: 5966 event · B 1710 trip × nnz 1985 · U 1486 user, nnz 2468 · ô theo event {"purchase": 1985, "add_to_cart": 1281} · bỏ orphan 0, thiếu gid 1281, thiếu vector 0 · leak check {"usersChecked": 1016, "targetCellInTripRow": 0}

expect_equal_to: `star_blend_a1` vs `content_profile` 50/50 PASS; `star_blend_a1+mmr` vs `content_profile+mmr` 50/50 PASS

Caveat LLBO: ma trận item-item / MF fit **một lần toàn cục** trên X_train (khách test cắt < as_of riêng), nên chứa event của khách khác xảy ra sau as_of của một khách; `pop_D` của engine thì cắt tại as_of — không rò rỉ target nhưng hai nguồn không đối xứng về thời gian. Kết luận so scorer ưu tiên temporal (B10).

### Run `2026-10-01-temporal-smoke-funnel`

run 2026-10-01-temporal-smoke-funnel · as_of 2026-09-24T00:00:00+00:00 · model embed-multilingual-v3.0:catalog-text-v2 · configHash b0aee886 · split temporal frozen 49727f856865 · SUBSET 50/98 khách · vectors numpy (thiếu 0) · git gold_v2-118-g993669d-dirty · algos 3d99e4e8 mode funnel pool mask rerank none,mmr

Split `temporal` · 98 khách test · event sha cccdf9d01c84 · đóng băng `src/evaluation/recsys_bench/frozen/split-temporal-asof20260924.json` (49727f856865) · T = 2026-07-10T09:13:21+00:00 · k = 20 · 3183 search unit / 2384 recommendable

| Arm | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Cross-category | Cross-cat chuyến mở | Cross-cat chuyến mở, có mua | Gini | Diversity@10 | Trả về (TB) | p95 ms | p99 ms | Collab cov. | Pool cắt | Fit s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| most_popular_in_destination | 50 | 0.0800 | 0.0400 | 0.1200 | 0.1200 | 0.0531 | 0.111 | 1.000 | 0.328 | 0.825 | 0.417 | 0.925 | 0.632 | 20.0 | 0.6 | 4.1 | — | — | — |
| engine | 50 | 0.1400 | 0.1400 | 0.1400 | 0.1600 | 0.1400 | 0.188 | 1.000 | 0.301 | 1.000 | 1.000 | 0.904 | 0.624 | 20.0 | 43.1 | 46.6 | — | — | — |
| content_profile | 50 | 0.1400 | 0.1400 | 0.1600 | 0.1600 | 0.1460 | 0.209 | 1.000 | 0.266 | 1.000 | 1.000 | 0.880 | 0.460 | 20.0 | 6.1 | 6.4 | — | 0.00 | 0.0 |
| content_profile+mmr | 50 | 0.1400 | 0.1400 | 0.1400 | 0.1600 | 0.1400 | 0.187 | 1.000 | 0.302 | 1.000 | 1.000 | 0.904 | 0.624 | 20.0 | 41.2 | 44.0 | — | 0.00 | 0.0 |
| cooc_trip | 50 | 0.0400 | 0.0155 | 0.0800 | 0.1000 | 0.0286 | 0.141 | 1.000 | 0.531 | 1.000 | 1.000 | 0.934 | 0.524 | 20.0 | 0.7 | 0.7 | 0.428 | 0.00 | 0.3 |
| cooc_trip+mmr | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.127 | 1.000 | 0.545 | 1.000 | 1.000 | 0.948 | 0.848 | 20.0 | 42.6 | 44.4 | 0.098 | 0.00 | 0.3 |
| star_blend | 50 | 0.1400 | 0.0857 | 0.1400 | 0.1600 | 0.0857 | 0.144 | 1.000 | 0.387 | 1.000 | 1.000 | 0.940 | 0.564 | 20.0 | 4.7 | 4.8 | 0.108 | 0.00 | 0.4 |
| star_blend+mmr | 50 | 0.1400 | 0.0831 | 0.1400 | 0.1400 | 0.0831 | 0.111 | 1.000 | 0.420 | 1.000 | 1.000 | 0.960 | 0.668 | 20.0 | 38.4 | 40.0 | 0.092 | 0.00 | 0.4 |
| star_blend_a1 | 50 | 0.1400 | 0.1400 | 0.1600 | 0.1600 | 0.1460 | 0.209 | 1.000 | 0.266 | 1.000 | 1.000 | 0.880 | 0.460 | 20.0 | 4.9 | 5.0 | 0.097 | 0.00 | 0.4 |
| star_blend_a1+mmr | 50 | 0.1400 | 0.1400 | 0.1400 | 0.1600 | 0.1400 | 0.187 | 1.000 | 0.302 | 1.000 | 1.000 | 0.904 | 0.624 | 20.0 | 41.8 | 43.5 | 0.100 | 0.00 | 0.4 |
| itemknn | 50 | 0.0400 | 0.0155 | 0.0800 | 0.1000 | 0.0286 | 0.142 | 1.000 | 0.532 | 1.000 | 1.000 | 0.933 | 0.524 | 20.0 | 0.7 | 0.8 | 0.428 | 0.00 | 0.0 |
| itemknn+mmr | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.150 | 1.000 | 0.519 | 1.000 | 1.000 | 0.931 | 0.776 | 20.0 | 33.4 | 38.1 | 0.227 | 0.00 | 0.0 |
| ease | 50 | 0.0400 | 0.0155 | 0.0600 | 0.0800 | 0.0215 | 0.188 | 1.000 | 0.462 | 1.000 | 1.000 | 0.887 | 0.532 | 20.0 | 0.6 | 0.7 | 0.696 | 0.00 | 0.9 |
| ease+mmr | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.119 | 1.000 | 0.531 | 1.000 | 1.000 | 0.950 | 0.816 | 20.0 | 35.8 | 36.9 | 0.098 | 0.00 | 0.9 |
| rp3beta | 50 | 0.0400 | 0.0155 | 0.0800 | 0.1000 | 0.0286 | 0.143 | 1.000 | 0.528 | 1.000 | 1.000 | 0.933 | 0.508 | 20.0 | 0.5 | 0.6 | 0.428 | 0.00 | 0.3 |
| rp3beta+mmr | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.125 | 1.000 | 0.542 | 1.000 | 1.000 | 0.948 | 0.828 | 20.0 | 31.2 | 35.1 | 0.093 | 0.00 | 0.3 |
| ials (3 seed) | 50 | 0.0000 | 0.0000 | 0.0200 | 0.0533 ± 0.0094 | 0.0071 | 0.243 ± 0.005 | 1.000 | 0.330 ± 0.005 | 1.000 | 1.000 | 0.825 ± 0.003 | 0.515 ± 0.010 | 20.0 | 2.6 ± 0.4 | 2.9 ± 0.4 | — | 0.00 | 0.1 ± 0.0 |
| ials+mmr (3 seed) | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.256 ± 0.006 | 1.000 | 0.347 ± 0.002 | 1.000 | 1.000 | 0.811 ± 0.006 | 0.592 ± 0.014 | 20.0 | 38.2 ± 2.0 | 39.6 ± 2.1 | — | 0.00 | 0.1 ± 0.0 |
| bpr (3 seed) | 50 | 0.0067 ± 0.0094 | 0.0042 ± 0.0059 | 0.0400 ± 0.0163 | 0.0800 ± 0.0163 | 0.0153 ± 0.0078 | 0.071 ± 0.001 | 1.000 | 0.341 ± 0.021 | 1.000 | 1.000 | 0.980 ± 0.000 | 0.547 ± 0.094 | 20.0 | 0.8 ± 0.0 | 1.0 ± 0.1 | — | 0.00 | 0.1 ± 0.0 |
| bpr+mmr (3 seed) | 50 | 0.0067 ± 0.0094 | 0.0033 ± 0.0047 | 0.0200 ± 0.0283 | 0.0333 ± 0.0249 | 0.0077 ± 0.0108 | 0.072 ± 0.000 | 1.000 | 0.429 ± 0.040 | 1.000 | 1.000 | 0.979 ± 0.000 | 0.793 ± 0.135 | 20.0 | 36.7 ± 3.0 | 39.5 ± 2.2 | — | 0.00 | 0.1 ± 0.0 |

- `most_popular_in_destination` strategy: {'most_popular_in_destination': 50}
- `engine` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `content_profile` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `content_profile+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `cooc_trip` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `cooc_trip+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `star_blend` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `star_blend+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `star_blend_a1` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `star_blend_a1+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `itemknn` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `itemknn+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `ease` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `ease+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `rp3beta` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `rp3beta+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}

Khách có chuyến mở tại as_of: 10 (trong đó đã mua ≥ 1 món trong chuyến: 3) — mẫu số hai cột *Cross-cat chuyến mở*; chuyến chỉ có view thì mọi item đều tính là cross. Gini và Coverage tính trên mọi unit recommendable.

#### Fit log

Fit log · algos `3d99e4e8` · mode funnel · funnel {"pool": "mask", "reranks": ["none", "mmr"]} · libs {"numpy": "2.5.3", "scipy": "1.18.1", "implicit": "0.7.3", "threadpoolctl": "3.7.0"}

| Algo | seed | rows | n hàng | nnz | item có láng giềng | tham số | khác | fit s |
|---|---|---|---:|---:|---:|---|---|---:|
| content_profile |  |  |  |  |  | {} | {} | 0.0 |
| cooc_trip |  | trip | 1444 | 2400 | 0.238 | {"beta": 5.0, "topK": 50} | {"nnzPairs": 901, "neighboursPerItemMean": 0.5661325793276782} | 0.326 |
| star_blend |  | trip | 1444 | 2400 | 0.238 | {"beta": 5.0, "topK": 50, "a": 0.5, "blendScope": "inner"} | {"nnzPairs": 901, "neighboursPerItemMean": 0.5661325793276782} | 0.427 |
| star_blend_a1 |  | trip | 1444 | 2400 | 0.238 | {"beta": 5.0, "topK": 50, "a": 1.0, "blendScope": "inner"} | {"nnzPairs": 901, "neighboursPerItemMean": 0.5661325793276782} | 0.359 |
| itemknn |  | trip | 1444 | 2400 | 0.238 | {"k": 50, "K_fit": 51} | {"nnzSimilarity": 1802, "neighboursPerItemMean": 0.5661325793276782, "implicitVersion": "0.7.3"} | 0.034 |
| ease |  | trip | 1444 | 2400 |  | {"lam": 200.0} | {"maxDiagG": 38.0, "medianDiagG": 0.0, "itemsWithInteraction": 943} | 0.897 |
| rp3beta |  | trip | 1444 |  | 0.238 | {"alpha": 1.0, "beta": 0.6, "topK": 50} | {"nnzPairs": 901, "neighboursPerItemMean": 0.5661325793276782} | 0.277 |
| ials | 42 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 42, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.104 |
| ials | 43 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 43, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.12 |
| ials | 44 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 44, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.094 |
| bpr | 42 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 42, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.052 |
| bpr | 43 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 43, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.067 |
| bpr | 44 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 44, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.066 |

X_train: 5562 event · B 1444 trip × nnz 2400 · U 1212 user, nnz 2442 · ô theo event {"purchase": 2400, "add_to_cart": 1037} · bỏ orphan 0, thiếu gid 1037, thiếu vector 0 · leak check {"usersChecked": 98, "targetCellInTripRow": 0}

expect_equal_to: `star_blend_a1` vs `content_profile` 50/50 PASS; `star_blend_a1+mmr` vs `content_profile+mmr` 50/50 PASS

### Run `2026-10-01-temporal-smoke-raw`

run 2026-10-01-temporal-smoke-raw · as_of 2026-09-24T00:00:00+00:00 · model embed-multilingual-v3.0:catalog-text-v2 · configHash b0aee886 · split temporal frozen 49727f856865 · SUBSET 50/98 khách · vectors numpy (thiếu 0) · git gold_v2-118-g993669d-dirty · algos ee293a5c mode raw pool mask rerank none,mmr

Split `temporal` · 98 khách test · event sha cccdf9d01c84 · đóng băng `src/evaluation/recsys_bench/frozen/split-temporal-asof20260924.json` (49727f856865) · T = 2026-07-10T09:13:21+00:00 · k = 20 · 3183 search unit / 2384 recommendable

| Arm | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Cross-category | Cross-cat chuyến mở | Cross-cat chuyến mở, có mua | Gini | Diversity@10 | Trả về (TB) | p95 ms | p99 ms | Collab cov. | Pool cắt | Fit s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| most_popular_in_destination | 50 | 0.0800 | 0.0400 | 0.1200 | 0.1200 | 0.0531 | 0.111 | 1.000 | 0.328 | 0.825 | 0.417 | 0.925 | 0.632 | 20.0 | 0.5 | 3.5 | — | — | — |
| engine | 50 | 0.1400 | 0.1400 | 0.1400 | 0.1600 | 0.1400 | 0.188 | 1.000 | 0.301 | 1.000 | 1.000 | 0.904 | 0.624 | 20.0 | 40.5 | 43.5 | — | — | — |
| content_profile | 50 | 0.1400 | 0.1400 | 0.1600 | 0.1600 | 0.1460 | 0.202 | 1.000 | 0.222 | 0.775 | 0.250 | 0.886 | 0.468 | 20.0 | 5.9 | 6.0 | — | 0.00 | 0.0 |
| content_profile+mmr | 50 | 0.1400 | 0.1400 | 0.1400 | 0.1600 | 0.1400 | 0.180 | 1.000 | 0.258 | 0.775 | 0.250 | 0.910 | 0.640 | 20.0 | 39.3 | 40.3 | — | 0.00 | 0.0 |
| cooc_trip | 50 | 0.0400 | 0.0155 | 0.0800 | 0.0800 | 0.0286 | 0.132 | 1.000 | 0.498 | 0.830 | 0.433 | 0.938 | 0.528 | 20.0 | 0.8 | 1.2 | 0.448 | 0.00 | 0.4 |
| cooc_trip+mmr | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.093 | 1.000 | 0.523 | 0.855 | 0.517 | 0.962 | 0.884 | 20.0 | 32.6 | 36.9 | 0.093 | 0.00 | 0.4 |
| star_blend | 50 | 0.1400 | 0.0857 | 0.1400 | 0.1600 | 0.0857 | 0.135 | 1.000 | 0.346 | 0.790 | 0.300 | 0.944 | 0.572 | 20.0 | 4.8 | 5.4 | 0.115 | 0.00 | 0.4 |
| star_blend+mmr | 50 | 0.1400 | 0.0831 | 0.1400 | 0.1400 | 0.0831 | 0.104 | 1.000 | 0.381 | 0.800 | 0.333 | 0.963 | 0.684 | 20.0 | 49.3 | 54.9 | 0.098 | 0.00 | 0.4 |
| star_blend_a1 | 50 | 0.1400 | 0.1400 | 0.1600 | 0.1600 | 0.1460 | 0.202 | 1.000 | 0.222 | 0.775 | 0.250 | 0.886 | 0.468 | 20.0 | 4.7 | 5.0 | 0.100 | 0.00 | 0.4 |
| star_blend_a1+mmr | 50 | 0.1400 | 0.1400 | 0.1400 | 0.1600 | 0.1400 | 0.180 | 1.000 | 0.258 | 0.775 | 0.250 | 0.910 | 0.640 | 20.0 | 32.2 | 32.5 | 0.103 | 0.00 | 0.4 |
| itemknn | 50 | 0.0400 | 0.0155 | 0.0800 | 0.0800 | 0.0286 | 0.132 | 1.000 | 0.499 | 0.830 | 0.433 | 0.938 | 0.528 | 20.0 | 0.7 | 0.8 | 0.448 | 0.00 | 0.0 |
| itemknn+mmr | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.117 | 1.000 | 0.494 | 0.850 | 0.500 | 0.949 | 0.804 | 20.0 | 31.0 | 33.8 | 0.235 | 0.00 | 0.0 |
| ease | 50 | 0.0400 | 0.0155 | 0.0400 | 0.0600 | 0.0155 | 0.173 | 1.000 | 0.428 | 0.805 | 0.350 | 0.898 | 0.528 | 20.0 | 0.7 | 0.7 | 0.726 | 0.00 | 0.8 |
| ease+mmr | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.088 | 1.000 | 0.508 | 0.850 | 0.500 | 0.963 | 0.832 | 20.0 | 30.8 | 31.8 | 0.086 | 0.00 | 0.8 |
| rp3beta | 50 | 0.0400 | 0.0155 | 0.0800 | 0.0800 | 0.0286 | 0.133 | 1.000 | 0.495 | 0.830 | 0.433 | 0.937 | 0.508 | 20.0 | 0.7 | 0.8 | 0.448 | 0.00 | 0.3 |
| rp3beta+mmr | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.090 | 1.000 | 0.521 | 0.860 | 0.533 | 0.962 | 0.864 | 20.0 | 41.4 | 43.0 | 0.088 | 0.00 | 0.3 |
| ials (3 seed) | 50 | 0.0000 | 0.0000 | 0.0200 | 0.0200 | 0.0071 | 0.235 ± 0.003 | 1.000 | 0.300 ± 0.003 | 0.832 ± 0.006 | 0.439 ± 0.021 | 0.831 ± 0.002 | 0.512 ± 0.011 | 20.0 | 3.1 ± 0.3 | 3.4 ± 0.3 | — | 0.00 | 0.1 ± 0.0 |
| ials+mmr (3 seed) | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.236 ± 0.002 | 1.000 | 0.317 ± 0.001 | 0.832 ± 0.002 | 0.439 ± 0.008 | 0.828 ± 0.002 | 0.589 ± 0.010 | 20.0 | 37.4 ± 2.2 | 39.2 ± 2.6 | — | 0.00 | 0.1 ± 0.0 |
| bpr (3 seed) | 50 | 0.0067 ± 0.0094 | 0.0042 ± 0.0059 | 0.0400 ± 0.0163 | 0.0467 ± 0.0249 | 0.0153 ± 0.0078 | 0.034 ± 0.001 | 1.000 | 0.315 ± 0.025 | 0.830 ± 0.007 | 0.433 ± 0.024 | 0.989 ± 0.000 | 0.567 ± 0.113 | 20.0 | 0.8 ± 0.0 | 0.9 ± 0.0 | — | 0.00 | 0.1 ± 0.0 |
| bpr+mmr (3 seed) | 50 | 0.0067 ± 0.0094 | 0.0033 ± 0.0047 | 0.0200 ± 0.0283 | 0.0200 ± 0.0283 | 0.0077 ± 0.0108 | 0.029 ± 0.001 | 1.000 | 0.407 ± 0.041 | 0.845 ± 0.007 | 0.483 ± 0.024 | 0.990 ± 0.000 | 0.844 ± 0.151 | 20.0 | 39.7 ± 3.8 | 41.5 ± 4.1 | — | 0.00 | 0.1 ± 0.0 |

- `most_popular_in_destination` strategy: {'most_popular_in_destination': 50}
- `engine` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `content_profile` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `content_profile+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `cooc_trip` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `cooc_trip+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `star_blend` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `star_blend+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `star_blend_a1` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `star_blend_a1+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `itemknn` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `itemknn+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `ease` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `ease+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `rp3beta` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}
- `rp3beta+mmr` strategy: {'long_term': 32, 'dormant': 8, 'cold_start_content': 4, 'cross_vertical': 3, 'recent_activity': 3}

Khách có chuyến mở tại as_of: 10 (trong đó đã mua ≥ 1 món trong chuyến: 3) — mẫu số hai cột *Cross-cat chuyến mở*; chuyến chỉ có view thì mọi item đều tính là cross. Gini và Coverage tính trên mọi unit recommendable.

#### Fit log

Fit log · algos `ee293a5c` · mode raw · funnel {"pool": "mask", "reranks": ["none", "mmr"]} · libs {"numpy": "2.5.3", "scipy": "1.18.1", "implicit": "0.7.3", "threadpoolctl": "3.7.0"}

| Algo | seed | rows | n hàng | nnz | item có láng giềng | tham số | khác | fit s |
|---|---|---|---:|---:|---:|---|---|---:|
| content_profile |  |  |  |  |  | {} | {} | 0.0 |
| cooc_trip |  | trip | 1444 | 2400 | 0.238 | {"beta": 5.0, "topK": 50} | {"nnzPairs": 901, "neighboursPerItemMean": 0.5661325793276782} | 0.394 |
| star_blend |  | trip | 1444 | 2400 | 0.238 | {"beta": 5.0, "topK": 50, "a": 0.5, "blendScope": "inner"} | {"nnzPairs": 901, "neighboursPerItemMean": 0.5661325793276782} | 0.386 |
| star_blend_a1 |  | trip | 1444 | 2400 | 0.238 | {"beta": 5.0, "topK": 50, "a": 1.0, "blendScope": "inner"} | {"nnzPairs": 901, "neighboursPerItemMean": 0.5661325793276782} | 0.365 |
| itemknn |  | trip | 1444 | 2400 | 0.238 | {"k": 50, "K_fit": 51} | {"nnzSimilarity": 1802, "neighboursPerItemMean": 0.5661325793276782, "implicitVersion": "0.7.3"} | 0.033 |
| ease |  | trip | 1444 | 2400 |  | {"lam": 200.0} | {"maxDiagG": 38.0, "medianDiagG": 0.0, "itemsWithInteraction": 943} | 0.773 |
| rp3beta |  | trip | 1444 |  | 0.238 | {"alpha": 1.0, "beta": 0.6, "topK": 50} | {"nnzPairs": 901, "neighboursPerItemMean": 0.5661325793276782} | 0.266 |
| ials | 42 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 42, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.109 |
| ials | 43 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 43, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.11 |
| ials | 44 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 15, "seed": 44, "alpha": 40.0, "confidence": "c = alpha*r = 40", "userVector": "recalculate_user"} | {"itemFactorShape": [3183, 64], "implicitVersion": "0.7.3"} | 0.098 |
| bpr | 42 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 42, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.065 |
| bpr | 43 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 43, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.053 |
| bpr | 44 | user | 1212 | 2442 |  | {"factors": 64, "regularization": 0.01, "iterations": 100, "seed": 44, "learningRate": 0.01, "negatives": "global", "bias": "factors+1 cột"} | {"itemFactorShape": [3183, 65], "implicitVersion": "0.7.3"} | 0.059 |

X_train: 5562 event · B 1444 trip × nnz 2400 · U 1212 user, nnz 2442 · ô theo event {"purchase": 2400, "add_to_cart": 1037} · bỏ orphan 0, thiếu gid 1037, thiếu vector 0 · leak check {"usersChecked": 98, "targetCellInTripRow": 0}

expect_equal_to: `star_blend_a1` vs `content_profile` 50/50 PASS; `star_blend_a1+mmr` vs `content_profile+mmr` 50/50 PASS

## 3. Caveat khi trích dẫn

- Dữ liệu sinh (handbook §12); 50 khách đầu theo thứ tự `cdpUserId` — không phải mẫu ngẫu nhiên, không có CI; chênh 0,02 R@20 = 1 khách.
- Gate so với run v5 cùng DB local seed 09-23 và cùng kho Weaviate; `configHash` khớp chỉ chứng minh cùng code engine.
- LLBO: ma trận item-item / MF fit **một lần toàn cục** trên X_train (khách test cắt `< as_of_u`), nên chứa event của khách khác xảy ra sau
  `as_of_u`; `pop_D` của engine cắt tại `as_of_u` — không rò rỉ target (`leakCheck targetCellInTripRow 0`) nhưng hai nguồn không đối xứng
  về thời gian; kết luận so scorer ưu tiên temporal (B10).
- Trên seed hiện tại chỉ `purchase` có `event_group_id` → ma trận trip × item chỉ có purchase; `add_to_cart` (1.281 / 1.037 event thiếu
  gid) chỉ vào ma trận user × item của `ials` / `bpr`.
- `+mmr` dùng λ 0,7 của engine cho mọi scorer mà không chuẩn hoá thang điểm (spec §2.2 cấm chuẩn hoá theo request) — xem đọc nhanh #3.
- p95/p99 ms là thời gian chấm offline trên máy dev chạy song song; không thay số đo HTTP của NFR-PERF-01.
- `Pool cắt` = 0.00 ở mọi run smoke vì pool mask không cắt; ở pool engine temporal 76/98 khách bị cắt (report v5 / spec §4.16).

## 4. Lệnh tái sinh (từ gốc repo; DSN local theo `.env.example` dòng 98 / 103, không ghi ở đây)

```bash
export WEAVIATE_URL=http://127.0.0.1:8080 WEAVIATE_API_KEY= WEAVIATE_GRPC_PORT=50051 PYTHONUTF8=1   # + DATABASE_URL / EVAL_DATABASE_URL local
Y=src/evaluation/recsys_bench/algos_v1.yaml; F=src/evaluation/recsys_bench/frozen
for kind in llbo temporal; do
  python -m src.evaluation.recsys_bench run --algos $Y --only content_profile --only star_blend_a1 --mode funnel --funnel-pool engine \
    --funnel-rerank none --funnel-rerank mmr --split $kind --vectors weaviate --split-file $F/split-$kind-asof20260924.json --run-id 2026-10-01-$kind-gate
  python -m src.evaluation.recsys_bench regress --run-id 2026-10-01-$kind-gate --ref-run-id 2026-10-01-$kind-v5 --base content_profile+mmr --ref engine
  python -m src.evaluation.recsys_bench regress --run-id 2026-10-01-$kind-gate --ref-run-id 2026-10-01-$kind-v5 --base content_profile --ref engine_nommr
  python -m src.evaluation.recsys_bench regress --run-id 2026-10-01-$kind-gate --base star_blend_a1+mmr --ref content_profile+mmr
  for mode in funnel raw; do
    python -m src.evaluation.recsys_bench run --algos $Y --max-tier 2 --mode $mode --arm most_popular_in_destination --arm engine \
      --split $kind --vectors numpy --split-file $F/split-$kind-asof20260924.json --limit-users 50 --run-id 2026-10-01-$kind-smoke-$mode
  done
done
python -m src.evaluation.recsys_bench report --run-id 2026-10-01-llbo-smoke-funnel --run-id 2026-10-01-llbo-smoke-raw \
  --run-id 2026-10-01-temporal-smoke-funnel --run-id 2026-10-01-temporal-smoke-raw --out <bản nháp>
```
