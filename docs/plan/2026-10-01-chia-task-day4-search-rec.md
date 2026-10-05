# Chia task Day 4 (T5 01/10) cho 2 người — Search (S) và Rec (R)

- Phục vụ: FR-SRC-01..04, AC-SRC-01, NFR-PERF-01 (phía search); FR-REC-01..04 (phía rec); test-plan §2.4–2.5.
- Bản chi tiết của §1 `docs/plan/2026-10-01-plan-day4-5.md`. Plan đó chia cho 4 vai (A1, A2, B, C). File này gộp lại cho **2 người**: **S** nhận Track A + phần search của Track C, **R** nhận Track B + phần recsys của Track C.
- Nhánh làm việc: `bench_search_recomSys` (= `fe7e04d`, PR #68). Mỗi người tách nhánh con từ đây (`bench/day4-search`, `bench/day4-rec`) và merge lại cuối ngày.
- **Mốc engine recsys = v5 (theo quyết định ghi ở history phân công 01/10):** merge M6 (`origin/bench/m6-trip-ended`, đề xuất `2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md` đã áp dụng) **trước** mọi số đo Day 4. Trong plan Day 4–5, mọi chỗ ghi "v0" (engine qua funnel = v0, `baseline_v1.json`) đều hiểu là **v5**.
- Người phụ trách: **S (Search): chưa điền tên**; **R (RecSys): tqanh123 / Claude (agent), nhận 01/10**. Giữ đầy đủ phạm vi Day 4; việc chưa xong phải ghi blocker và bàn giao, không tự coi là đã được duyệt giảm phạm vi.
- Đây là **file phân công và bàn giao chính**. Checklist là việc cần nghiệm thu, không phải xác nhận đã chạy benchmark trong lần cập nhật tài liệu này.
- Ưu tiên theo số thứ tự. Đọc file muộn thì làm theo số, không theo giờ. Checkpoint 17:15.

## 0. Hiện trạng trên nhánh so với plan Day 4

### 0.1 Search (Track A + phần search của C)

| Việc trong plan Day 4 | Trạng thái trên nhánh | Ghi chú |
|---|---|---|
| κ chính thức, merge, import, check, tag `gold_v1` | **Xong (30/09)**: κ linear 0,692 trước rà / 0,661 sau rà, 640 cặp chung; tag `gold_v1` | `history/2026-09-30-gold-merge-import-retire-tag-v1.md` |
| Top-up arm E (Judged@10) | **Xong cho e5-base**: vòng hole D4a 597 cặp, tag `gold_v2`; judged@10 = 1,000 cho B0 và E2.e5 | Lệnh `sb gold holes` thay cho `topup_v1.1.jsonl` |
| Bảng B0 vs E2.e5 | **Xong**: TIE (ΔnDCG +1,37, CI [−2,16; +5,24]) | `src/evaluation/reports/eval-2026-10-01-search-bench-gold-v2.md` |
| `docs/spec/bench/search-gold-summary.md` (số câu, phân bố nhãn, depth, κ) | **Xong** | Đã cập nhật đến D5a/gold_v3: 5.021 nhãn |
| Cổng SAN trên gold | **Xong** | `gold check` kiểm câu active, nhãn dương và phân bố theo slice |
| Bảng Search v1, 3 arm (dense / hybrid / hybrid+normalize, Cohere) | **Xong** | D4b đủ nhãn; dense giữ làm mốc vì hybrid+normalize vi phạm guard slice |
| `sb compare` đọc bản rescore `results@gold_vN.json` | **Xong** | Có `--gold`, `--condensed` và test Parquet/rescore |
| Index đủ model Tier 1 | **Xong** | 8 bộ × 3.183 = 25.464 vector; sanity PASS |
| Latency embed query theo model | **Xong trong điều kiện hợp lệ** | Local CPU cho e5/GTE/BGE; v3 API ổn định; v4 API 429 được loại |
| Chế độ *condensed*, `stages.yaml`, `baseline_v1.json`, `sb regress`, dev/test split | **Condensed xong** | Stages/regression/split giữ cho Day 5; 131 câu không đủ split 100/100 |
| `/search` cloud 500, `sb latency http` (gate P) | Chưa đo được (lỗi embed trên VM) | Day 5, không vào Day 4 |

### 0.2 Rec (Track B + phần recsys của C)

| Việc trong plan Day 4 | Trạng thái | Ghi chú |
|---|---|---|
| Split đóng băng, sanity, parity offline = HTTP 60/60, ceiling, phân khúc, 20 ca, `--override`, grid lần 1 | **Xong (Day 3, 01/10)** | spec `docs/spec/bench/recsys-offline-eval.md` §2.1–4.13 |
| M6 (trip mở theo `usingDate`, N = 14), report v5 | **Xong nhưng ở nhánh khác**, chưa merge vào `bench_search_recomSys` | `origin/bench/m6-trip-ended@8842c3a` (có harness + report v5); `origin/feat/recsys-trip-ended@1d1102e` là bản cùng thay đổi cho release, **không merge cả hai** |
| Cross-category, availability, coverage, p95/p99 offline | **Có trong `metrics.score`** cho mọi arm | Thiếu **Gini**. Cross-category hiện tính trên mọi khách, theo mọi taxonomy đã mua. Plan định nghĩa: chỉ khách có chuyến mở, chỉ vertical đã mua **trong chuyến** |
| Registry thuật toán `models/` + `algos_v1.yaml` | **Chưa có** | Code mẫu: `origin/khoa/recsys-research:src/evaluation/recommender_prototypes.py` (random, pop, dest-season pop, content, embedding content, item-item CF, ALS numpy, PPR, Markov, hybrid). **Không có** EASE, BPR, `cooc_trip`, `star_blend` |
| Funnel chung `funnel` / `raw` | **Chưa có** | `ceiling.engine_view` đã mô phỏng đúng mask của engine. Nên dùng nó làm bộ lọc của funnel để engine qua funnel = v5 |
| CLI `run --algos … --mode` | **Chưa có** (hiện `run --arm`) | |
| Kiểm exclusion/diagnostics P1, P3 | Đã kiểm P1 ngày 29/09 trên engine cũ | Phải kiểm lại sau M6 |
| PR contract additive | **Phần lớn đã có**: `/recommendations` có `nextVertical`, `excludedVerticals`, `modelVersion`; `/search` có `stageMs`, `embedCache` (contract 1.12.0) | Chỉ còn đối chiếu; không mở PR mới nếu không thiếu |

## 1. S — Search


### S1 — **Cổng SAN trên `gold_v2`**

- [x] **Thực hiện:** Thêm check vào `search_bench/sanity.py` (hoặc `sb gold check --san`): mọi câu active, trừ `out_of_catalog`, có ≥ 1 nhãn > 0; 0 câu rỗng; phân bố nhãn 0/1/2 theo slice in ra bảng. Test trên fixture `gold_small/`
- [x] **Nghiệm thu:** SAN xanh trên `gold_v2`. Đỏ thì xác minh lỗi dữ liệu hay lỗi checker; nhãn chỉ sửa theo guide và review, không sửa nhãn hoặc nới checker chỉ để PASS
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


### S2 — **`docs/spec/bench/search-gold-summary.md`**

- [x] **Thực hiện:** 131 câu active / 13 slice; số nhãn theo version (`gold_v1` 3.359 → `gold_v2` +612); phân bố 0/1/2 theo slice (lấy từ S1); pooling depth 15 + hole depth 10 (D4a); κ 0,692 / 0,661 (640 cặp); retire `c0463`; changelog guide 30/09; nhãn D4a là nhãn máy được QAnh duyệt
- [x] **Nghiệm thu:** Tài liệu gold cập nhật đến D5a/gold_v3, đúng vị trí `docs/spec/bench/`
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


### S3 — **Vá `sb compare`** đọc `results@<gold_version>.json`

- [x] **Thực hiện:** Thêm `--gold gold_v2` (mặc định = gold mới nhất có rescore), gọi `runner.read_results_at`. Thêm test
- [x] **Nghiệm thu:** compare đọc đúng artifact theo version; full/condensed chạy trên Parquet và paired bootstrap
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


### S4 — **Chạy nền: index Tier 1** (song song với S5)

- [x] **Thực hiện:** Thêm vào `config/sbench.yaml`: `e5-small` (`intfloat/multilingual-e5-small`, 384, prefix `query: ` / `passage: `), `cohere-v4-1536/512/256` (cùng `api_model: embed-v4.0`, đổi `output_dimension`). Mỗi model một arm `arms/E2.<model>.yaml` (dense-only, cùng text builder `T3+R` với B0). Chạy từ nhẹ đến nặng: `e5-small` → `gte-mb` → `bge-m3` → v4 × 4 chiều: `sb embed` → `sb collection create` → `sb load`. Chỉ Weaviate **local**
- [x] **Nghiệm thu:** 8 collection/model đều đúng 3.183 object; sanity PASS. BGE-M3 dùng revision tải từ `BAAI/bge-m3`, fp32, safetensors, CPU local theo lựa chọn local của phiên này; bản int8 không có trong repo và không được dùng.
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả và blocker commit/tag tại §5.


### S5 — **Bảng Search v1, 3 arm, Cohere v3**

- [x] **Thực hiện:** `sb run --arm APP.dense --arm APP.hybrid --arm APP.hybrid_norm` trên `gold_v2`. Arm nào judged@10 < 0,80 → `sb gold holes --arms APP.* --tag D4b` → gán máy + người duyệt toàn bộ nhãn máy như D4a → `holes import` → `gold check` / `verify-append` → tag `gold_v3` → `sb rescore`. Paired bootstrap 95 % CI cho dense → hybrid và hybrid → +normalize. Theo 13 slice. Ngưỡng cutoff giữ nguyên, **không sweep**
- [x] **Nghiệm thu:** `src/evaluation/reports/eval-2026-10-01-search-v1-3arm.md`: Recall@10, nDCG@10, MRR@10, Judged@10, zero-result theo slice + CI + caveat. Trả lời câu (1) checkpoint: hybrid+normalize có thắng dense-only có ý nghĩa không
- [x] **Bàn giao:** D4b đủ 278/278, import/check/verify/rescore và report cuối đã cập nhật theo gold_v3.


### S6 — **Judged@10 cho từng arm E** khi S4 xong từng model

- [x] **Thực hiện:** `sb run --arm E2.<model>` trên gold mới nhất. Gộp cặp chưa nhãn của mọi arm: `sb gold holes --arms E2.gte,E2.bge,E2.e5s,E2.v4-1536,E2.v4-1024,E2.v4-512,E2.v4-256 --tag D5a`. Bỏ trùng, cap **700 cặp**. Arm vượt cap → ghi "so sánh ở chế độ condensed"
- [x] **Nghiệm thu:** D5a gán/import đủ 700/700 + 72 auto-OOC; 7 arm đã rescore full/condensed; v4-512 và v4-1024 đạt mọi cổng judged sau tolerance số thực
- [x] **Bàn giao:** report và §5 ghi đủ số full/condensed, coverage, CI và lệnh tái sinh.


### S7 — **Latency embed query theo model**

- [x] **Thực hiện:** Thêm `sb latency embed --models …`: tập câu gold được khóa (ghi số câu/hash, prefix đúng từng model), warm-up 20 lượt riêng rồi đo toàn tập, p50/p95 trên máy chạy backend. Cohere v3 cache-miss có thể tham chiếu số Day 2–3 nhưng ghi riêng điều kiện đo; v4 đo cùng tập query, ghi số request, batch, cache và số lượt lặp
- [x] **Nghiệm thu:** Bảng local cho e5-small/GTE/BGE và API v3; v4 API bị 429 nên loại, thay bằng Weaviate local cùng run cho so sánh kích thước
- [x] **Bàn giao:** artifact latency, điều kiện máy/cache/warm-up và caveat 429 đã ghi trong report/§5.


### S8 — *Nếu còn giờ* — chuẩn bị Day 5

- [x] **Thực hiện (a):** chế độ **condensed** trong `metrics.py`: bỏ cặp chưa nhãn khỏi list rồi tính, báo cạnh full và retained ratio. [ ] (b) stages; [ ] (c) dev/test split — chuyển Day 5 vì 131 câu không thể chia 100/100
- [x] **Nghiệm thu:** condensed có unit + Parquet/rescore regression test; stages và split được ghi rõ là việc Day 5
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


**Checkpoint 17:15 (S):** SAN xanh · `docs/spec/bench/search-gold-summary.md` · `sb compare` đọc rescore · bảng Search v1 3 arm (Cohere) · checklist collection S4 đầy đủ; ghi riêng từng model/chiều chưa xong (không dùng ngưỡng “≥ 4” thay cho danh sách) · Judged@10 theo arm + hole D5a ≤ 700 cặp · bảng latency embed.

## 2. R — Rec


### R1 — **Merge M6, chốt mốc v5**

- [x] **Thực hiện (01/10):** `git merge origin/bench/m6-trip-ended` vào nhánh con. **Không** merge thêm `feat/recsys-trip-ended`: nếu engine của hai nhánh khác nhau (diff `profile.py`, `use_cases.py`), báo lead. Chạy `pytest src/evaluation/recsys_bench/tests` + test recommendation của backend (env `vsf2`). Chạy lại `run … --split-file frozen/split-{llbo,temporal}-asof20260922.json --run-id 2026-10-01-{llbo,temporal}-v5-check`
- [x] **Nghiệm thu (01/10):** Metric chất lượng tái lập khớp report v5 với cùng dữ liệu, split, seed và config; latency đo lại, không yêu cầu trùng từng chữ số. Đối chiếu report v5 (`eval-2026-10-02-recsys-bench-v5.md`); `configHash` eval/prod = `b0aee886` / `81d16abd`. Lệch → dừng, tìm nguyên nhân trước khi làm R2
- [x] **Bàn giao (01/10):** đã điền §5.4. *Gate thay thế vì DB local (seed 09-23) ≠ split 0922: `configHash b0aee886 / 81d16abd` khớp, test xanh, thứ tự baseline đúng, ceiling ≥ mpd; bộ split mới `asof20260924` (người dùng chốt 01/10).*


### R2 — **Đủ cột §12 cho 4 arm trên v5**

- [x] **Thực hiện (01/10):** Trong `metrics.score`: thêm **Gini** độ phủ (exposure top-20 trên mọi khách test); thêm `cross_category_open_trip`: chỉ khách có chuyến mở tại `as_of`, tỉ lệ item top-20 thuộc vertical **chưa mua trong chuyến đó** (lấy chuyến mở từ `ceiling.engine_view`). Giữ cột cũ. Ghi caveat: availability đo theo `attributes.availability` hiện tại, không tái dựng lịch sử. Thêm test
- [x] **Nghiệm thu (01/10):** Bảng v5 (random 3 seed, most_popular, mpd, engine, engine_prod): Recall@10/20, NDCG@10, cross-category (2 kiểu), availability, coverage, Gini, p95/p99 offline
- [x] **Bàn giao (01/10):** đã điền §5.4. *Gini + 2 biến thể cross-cat chuyến mở (người dùng chốt báo cả hai), test tính tay; bảng 6 arm × 2 split trong report `eval-2026-10-01-recsys-bench-v5-asof20260924.md`.*


### R3 — **Registry thuật toán**

> *01/10 chiều — xong:* người dùng bổ sung đặc tả `docs/spec/bench/recsys-algos-v1.md` (gỡ blocker §4.1); registry `models/` + `algos_v1.yaml` + funnel chung + CLI `run --algos`/`regress` đã có, gate G1/G2 đạt 1016/1016 và 98/98 (xem §5.4).

- [x] **Thực hiện (01/10 chiều):** `src/evaluation/recsys_bench/models/`: `base.py` (`fit(train_events, catalog, vectors)`, `score(user_ctx, candidate_ids) → scores`; `UserCtx` = event < `as_of`, chuyến mở, destination, vertical đã mua). Đăng ký theo tên trong `src/evaluation/recsys_bench/algos_v1.yaml`, tham số **mặc định**, không tune. Port logic (không chép file ra gốc `src/evaluation/`) từ `recommender_prototypes.py` của nhánh research. Thêm `implicit`, `scipy` vào `src/evaluation/requirements.txt`
- [x] **Nghiệm thu (01/10 chiều):** Chạy end-to-end trên split với 2 scorer rẻ nhất: `cooc_trip` (cosine + shrinkage theo trip, top-50/item) và `ease` (nghiệm đóng, λ mặc định)
- [x] **Bàn giao (01/10 chiều):** đã điền §5.4. *`models/{base,data,seeds,funnel,itemitem,content,cooc,star,ease,rp3beta,knn_implicit,mf_implicit,registry,regress}.py`, `algos_v1.yaml`; `scipy`/`implicit`/`threadpoolctl` vào `src/evaluation/requirements.txt` và `.venv`; end-to-end `cooc_trip` + `ease` chạy trên split thật (smoke 50 khách).*


### R4 — **Funnel chung + chế độ `raw`**

> *01/10 chiều — xong:* người dùng bổ sung đặc tả `docs/spec/bench/recsys-algos-v1.md` (gỡ blocker §4.1); registry `models/` + `algos_v1.yaml` + funnel chung + CLI `run --algos`/`regress` đã có, gate G1/G2 đạt 1016/1016 và 98/98 (xem §5.4).

- [x] **Thực hiện (01/10 chiều):** `funnel.py`: `candidates = filter(destination chuyến mở ∥ 2 destination lịch sử, taxonomy ∉ vertical đã mua, is_recommendable, available)` → `score` → top-20; điểm 0 / không có tín hiệu thì phá hoà bằng `pop_D`. **Dùng lại `ceiling.engine_view`** làm bộ lọc để mask trùng engine. `raw` = không lọc, xếp toàn catalog. Bọc engine production thành scorer `content_profile`
- [x] **Nghiệm thu (01/10 chiều):** Test regression: `content_profile` qua funnel = **đúng số v5** (LLBO + temporal). Chưa bằng thì không chạy scorer khác
- [x] **Bàn giao (01/10 chiều):** đã điền §5.4. *Funnel = mask engine (quyết định người dùng), knob `pool ∈ {engine, mask}` × `rerank ∈ {none, mmr}`; `content_profile` qua funnel (pool engine, mmr) ≡ `engine` v5 **1016/1016 và 98/98**, ≡ `engine_nommr[:20]` 1016/1016 và 98/98 — `regress`.*


### R5 — **Đủ scorer Tier 1 + `algos_v1.yaml`**

> *01/10 chiều — xong:* người dùng bổ sung đặc tả `docs/spec/bench/recsys-algos-v1.md` (gỡ blocker §4.1); registry `models/` + `algos_v1.yaml` + funnel chung + CLI `run --algos`/`regress` đã có, gate G1/G2 đạt 1016/1016 và 98/98 (xem §5.4).

- [x] **Thực hiện (01/10 chiều):** Baseline: `random` (3 seed), `mostpop_window` (90 ngày = `most_popular` hiện có), `mostpop_in_dest`. Content: `content_profile`, `content_no_decay`, `content_no_mmr` (= `engine_nommr`). Co-occurrence: `cooc_trip`, `star_blend` (a = 0,5). CF: `ease`, `itemknn` (`implicit` cosine). MF: `ials` (64 factor, α = 40), `bpr` (64 factor, negative toàn cục nếu research chưa có negative theo destination; ghi rõ). Tier 2 `rp3beta` chỉ khi còn giờ. Chạy thử mỗi scorer `--limit-users 50` cả hai chế độ
- [x] **Nghiệm thu (01/10 chiều):** Mọi scorer Tier 1 chạy không lỗi; yaml có tier · tham số · cần train? · thời gian fit + thời gian ước cho full run
- [x] **Bàn giao (01/10 chiều):** đã điền §5.4. *Mọi Tier 1 (+ `rp3beta` Tier 2) chạy không lỗi ở `funnel` và `raw`, 50 khách, hai split; fit log có tier · tham số · rows · thời gian fit. `cooc_trip`/`star_blend` theo spec mới; `bpr_dest` `status: not_run`; `content_no_decay` = run `--override H_SHORT_DAYS/H_LONG_DAYS`, `content_no_mmr` = `content_profile` (rerank none).*


### R6 — **CLI chạy lại được**

> *01/10 chiều — xong:* `report`, `compare` (sáng) và `run --algos <yaml> --mode funnel|raw` + `regress` (chiều); `run_id` mặc định có đuôi `algosHash`; bảng markdown sinh tự động với cột `Collab cov.` / `Pool cắt` / `Fit s` và khối Fit log.

- [x] **Thực hiện (01/10 chiều):** `python -m src.evaluation.recsys_bench run --algos algos_v1.yaml --split-file <file> --mode funnel\|raw` → `bench_out/recsys/runs/<hash config>/`; bảng markdown sinh tự động; đầu file ghi `git describe` + `modelVersion` + `configHash`
- [x] **Nghiệm thu (01/10 chiều):** Chạy `content_profile` bằng CLI mới ra đúng số v5
- [x] **Bàn giao (01/10 chiều):** đã điền §5.4. *`run --algos … --split-file … --mode funnel|raw` → `bench_out/recsys/runs/<run-id|…-algosHash>/`, bảng + fit log tự động, đầu khối `git describe` + `modelVersion` + `configHash` + `algosHash`; `content_profile` qua CLI mới ra đúng số v5.*


### R7 — **Kiểm exclusion/diagnostics sau M6** (phần C)

- [x] **Thực hiện (01/10):** `recsys_bench user --id VP0000001` (P1: chuyến mở, đã mua hotel) và một khách P3 dormant: `strategy`, `excludedVerticals`, `nextVertical`, `coldStart` đúng FR-REC-02 bản mới. Đối chiếu field `/recommendations` trong contract 1.12.0 với plan §1.3 #5
- [x] **Nghiệm thu (01/10):** Ghi kết quả vào spec recsys §5. Sai logic → mở issue / fix và báo lại R1. Contract thiếu field → báo lead (không tự mở PR contract nếu không thiếu)
- [x] **Bàn giao (01/10):** đã điền §5.4. *P1 4/4, P3 4/4 (`user … p3Check`), ghi spec §5.1; contract đủ field, không mở PR; lệch dormant 90/180 → I-8.*


### R8 — **Mục "Ceiling" trong report**

- [x] **Thực hiện (01/10):** v5: LLBO 0,990, temporal 0,892 > Recall@20 của mpd (0,098) → **không** kích hoạt nhánh "ceiling < mpd" của plan. Viết 1 đoạn: 11/102 ca temporal chưa tới được mask; report v5 ghi lý do 6 `taxonomy_excluded`, 9 `destination_mismatch`, 1 `already_bought` (tổng 16 > 11, nên một ca có thể mang nhiều lý do; kiểm lại trong `ceiling.json`); kèm hướng cho tuần sau
- [x] **Nghiệm thu (01/10):** Đoạn trong `docs/spec/bench/recsys-offline-eval.md` §7
- [x] **Bàn giao (01/10):** đã điền §5.4. *Spec §7 đoạn "Ceiling": bộ 0924 ceiling 0,988 / 0,918 ≥ mpd 0,602 / 0,102; lý do đa nhãn (4 khách temporal mang 2 nhãn) kiểm trong `ceiling.json`.*


**Checkpoint 17:15 (R):** v5 tái lập đúng số · bảng v5 đủ cột §12 (có Gini, cross-category theo chuyến) · registry + funnel + `raw` · `content_profile` qua funnel = v5 · `algos_v1.yaml` · mọi Tier-1 scorer chạy thử 50 user · CLI `run --algos` · P1/P3 đã kiểm sau M6.

## 3. Điểm nối giữa S và R

- **Weaviate local dùng chung:** R chỉ đọc collection production (`Product`, Cohere v3); S tạo collection mới theo tên arm. Không ai `drop` / `--recreate` collection của người kia.
- **Máy:** S4 (embed local CPU) nặng. R chạy recsys sau 15:00 (full run Day 5) thì tránh trùng giờ embed `bge-m3`, hoặc chạy trên máy khác.
- **History:** mỗi người một entry `history/2026-10-01-<slug>.md` cho phần của mình. Report kết quả chạy để trong `src/evaluation/reports/eval-2026-10-01-*.md` (AGENTS.md §7).
- **Merge cuối ngày:** R merge trước (đụng `recsys_bench/`, backend recommendation qua M6), S merge sau (chỉ `search_bench/`, `gold/`). Hai bên gần như không chung file, trừ `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` (tick + log). Người merge sau xử lý conflict ở file này.

## 4. Chưa rõ — cần lead xác nhận

1. ~~`TRAINING_FREE_RECSYS.md`, `RECSYS_METHODS_BY_SCALE.md`, `serve_bench.py` (plan Day 4–5 dẫn cho `cooc_trip` / `star_blend`) **không có trong repo**.~~ **Đã gỡ 01/10 chiều:** người dùng viết đặc tả `docs/spec/bench/recsys-algos-v1.md` (công thức chốt tại đó, hai file gốc vẫn không có trong repo); R cài theo spec này.
2. `bge-m3` bản int8 cộng đồng như plan ghi, hay fp32 theo `sbench.yaml` hiện tại? (S4)
3. Gold mới nhất là `gold_v2`, sau S5 có thể là `gold_v3`. Plan Day 5 ghi `gold_v1.1` → hiểu là "gold mới nhất sau top-up", không đổi tên tag cũ.
4. `/search` cloud 500 (lỗi embed Cohere trên VM) vẫn chưa ai xử lý; gate P Day 5 cần nó. Không giao cho S hay R hôm nay.

## 5. Checklist phối hợp và bàn giao cuối Day 4

### 5.1 Trước khi bắt đầu

- [ ] Điền tên S/R ở đầu file; S review đầu ra R, R review đầu ra S.
- [x] Ghi HEAD thực tế (`b692047`) và snapshot/checksum catalog (`ad3f3be25647a44c027ab21592f4defc3740f247090a146ea3614eb83adff4ab`); `fe7e04d` là mốc khảo sát, không mặc định là HEAD sau merge. *(R, 01/10: nhánh `bench/day4-rec`, HEAD sau merge M6 = `69e01a5`; DB local seed 09-23, 3.183 unit / 2.384 recommendable, 7.145 event; Weaviate local `Product` 3.183 object, `modelVersion embed-multilingual-v3.0:catalog-text-v2`.)*
- [x] S xác nhận gold/tag/hash (`gold_v2`, SHA-256 `61a312e0ea6be510c72a337d07d928d00e67c5e7f031eab84837174b29c7ad7e`); R xác nhận frozen split/hash và mốc v5 sau R1. Không so số khác phiên bản mà chưa rescore/tái chạy. *(R, 01/10: split `asof20260924` sha `1c31d43c…` / `49727f85…`, `configHash b0aee886 / 81d16abd`; chờ lead xác nhận mốc `v5@asof20260924`.)*
- [x] R kiểm tra PRD sau tích hợp M6 trước khi dùng hành vi mới; lịch sử chốt trên nhánh khác không thay thế bước cập nhật PRD tại nhánh làm việc. *(01/10: sau merge, FR-REC-02 bản mới và đề xuất `đã áp dụng` đã có trên `bench/day4-rec`.)*
- [x] Mỗi người đọc tài liệu bắt buộc theo AGENTS.md trước khi code. `src/evaluation/README.md` hiện thiếu: cần hỏi người dùng theo AGENTS.md §1.2 trước khi giả định nội dung; việc chỉnh checklist này không thay thế bước đó. *(R, 01/10: đã đọc; không tạo README mới, hướng dẫn chạy ở spec §1.)*
- [ ] Phân lịch CPU/Weaviate: S chạy embed nền; không đo latency trong lúc máy chịu tải embed/fit của người kia.
- [ ] Giữ model production Cohere v3/1024; các model/scorer khác chỉ là benchmark local. Đổi production hoặc PRD phải qua đề xuất được chốt.

### 5.2 Checklist chi tiết cần đối chiếu trong các task

**S4 — từng collection phải có số object khớp snapshot, sanity PASS và metadata model:**

- [x] Cohere v3/1024: 3.183 object, sanity 4/4 PASS, chạy ba arm APP. e5-base/768 chưa tái lập ở checkout này.
- [x] e5-small/384 — 3.183 object, sanity 4/4 PASS; run `20261001-day4-local`.
- [x] gte-multilingual-base/768 — 3.183 object, sanity 4/4 PASS; run `20261001-day4-local`, NEEDS_LABELS.
- [x] bge-m3/1024 — 3.183 object, sanity 4/4 PASS; fp32/safetensors/CPU, 2.057,12 giây; run `20261001-day4-local`, NEEDS_LABELS.
- [x] Cohere v4/1536 — 3.183 object, sanity 4/4 PASS; run `20261001-day4-local`, NEEDS_LABELS.
- [x] Cohere v4/1024 — 3.183 object, sanity 4/4 PASS; run `20261001-day4-local`, đạt judged gate.
- [x] Cohere v4/512 — 3.183 object, sanity 4/4 PASS; run `20261001-day4-local`, NEEDS_LABELS.
- [x] Cohere v4/256 — 3.183 object, sanity 4/4 PASS; run `20261001-day4-local`, NEEDS_LABELS.

**R5 — mỗi dòng có cấu hình/seed, fit chỉ trên train, smoke 50 user ở funnel và raw, thời gian fit/chạy:**

- [x] random — 3 seed. *(Day 5: seed 42/43/44, run `2026-10-01-{llbo,temporal}-algos-{funnel,raw}`; LLBO hit@20 0,0066 ± 0,0023.)*
- [x] mostpop_window — 90 ngày. *(arm `most_popular`, `popularityWindowDays` 90 trong `engineConfig`; LLBO 0,253.)*
- [x] mostpop_in_dest. *(arm `most_popular_in_destination` + `pop_funnel` = cùng xếp hạng qua funnel chung; LLBO 0,602 / 0,820.)*
- [x] content_profile — regression khớp v5. *(gate numpy trong-run 1016/1016, 98/98; `baseline_v1` ghi từ run `…-gate-numpy`.)*
- [x] content_no_decay. *(run `2026-10-01-{llbo,temporal}-content-nodecay`, `--override H_SHORT_DAYS=H_LONG_DAYS=1000000`, `configHash c557f49b`; Δhit@20 +0,1 / 0,0.)*
- [x] content_no_mmr. *(= hàng `content_profile` rerank none; MMR −2,7 [−4,3; −1,0] hit@20 LLBO.)*
- [x] cooc_trip — chỉ triển khai khi đủ đặc tả. *(β 5, top-K 50; run `2026-10-01-{llbo,temporal}-algos-{funnel,raw}`; fit 0,8 s LLBO.)*
- [x] star_blend — a = 0,5, chỉ triển khai khi đủ đặc tả. *(inner; kèm `star_blend_a1` ≡ content; run `2026-10-01-{llbo,temporal}-algos-{funnel,raw}`.)*
- [x] ease — ghi λ cụ thể từ nguồn đã xác nhận, không để “mặc định” mơ hồ. *(λ = 200 theo spec algos §4; `maxDiagG` 19 / 38, `medianDiagG` 0 trong fit log.)*
- [x] itemknn — ghi k và cách chuẩn hóa. *(implicit `CosineRecommender`, K = k + 1 = 51, cosine không shrink.)*
- [x] ials — 64 factor, α = 40; ghi seed/iterations. *(reg 0,01, 15 iter, seed 42/43/44, `recalculate_user`.)*
- [x] bpr — 64 factor; ghi seed/iterations và cách lấy negative. *(lr 0,01, reg 0,01, 100 iter, seed 42/43/44, negative toàn cục theo popularity của implicit; đối chứng `bpr_numpy` + `bpr_dest` ở run `…-bpr-tier2`.)*

**Bổ sung điều kiện nghiệm thu:**

- [x] R2 ghi mẫu số Gini/coverage, xử lý danh sách rỗng và user không có chuyến mở; test fixture có kết quả tính tay. *(01/10: spec §7; mẫu số in dưới bảng; rỗng → 0,0 / 0; `tests/test_metrics_open_trip_gini.py`.)*
- [x] R4 kiểm mask/tie-break và metric trên cả LLBO + temporal; chưa khớp v5 thì chưa công bố bảng so scorer. *(G1/G2 1016/1016, 98/98 với Weaviate (R4) và numpy (Day 5); test fixture tie-break.)*
- [x] S5 D4b đủ 278/278; import/check/verify append/rescore PASS. Cả 3 arm Judged@10 = 1; hybrid+normalize tăng recall nhưng LOSE guard slice so với dense.
- [x] S6 hợp đủ 7 arm: 2.024 cặp trước cap → D5a 700/700 nhãn người + 72 auto-OOC đã import; rescore full/condensed; v4-512 và v4-1024 đạt gate.
- [x] S7 ghi máy, 131 query, warm-up 20, cache off và điều kiện đo; latency embedding không thay thế latency toàn API NFR-PERF-01.

### 5.3 Thứ tự và checkpoint 17:15

- S: S1 → S2/S3 → S5; chạy S4 nền, xử lý S6/S7 theo model sẵn sàng. S8 là tùy thời gian.
- R: R1 → R2/R3 → R4 → R5/R6 → R7/R8. R1 và R4 là cổng chặn kết luận so sánh.
- Mục tiêu Day 4 giữ như §1–2; bảng full run và quyết định model/thuật toán thuộc Day 5. Nếu không kịp, ghi từng mục chưa xong và đề xuất ngày tiếp theo, không tự đánh dấu hoàn thành.

- [x] S đã điền đủ bảng bàn giao Search; R tự điền phần RecSys.
- [ ] Review chéo artifact, phiên bản dữ liệu và lệnh tái sinh; chỉ tick task khi đủ bằng chứng.
- [x] Search ghi test thật đã chạy; phần RecSys/backend do R nghiệm thu riêng.
- [x] Search đã có history riêng, checklist và report đúng thư mục; R tạo history riêng cho RecSys.
- [ ] R tích hợp trước, S sau; phối hợp khi cùng sửa checklist này và lịch 10 ngày để không ghi đè trạng thái.
- [ ] Chốt người xử lý lỗi `/search` cloud trước gate P Day 5; hiện **chưa có owner**, không coi đây là lỗi đã được xác minh lại hôm nay.

### 5.4 Bảng bàn giao — điền khi thực hiện, không điền số dự kiến

**File bàn giao chính là file này:** `docs/plan/2026-10-01-chia-task-day4-search-rec.md`.
Report là bằng chứng kèm theo, history ghi lý do/quyết định; chúng không thay thế trạng thái task tại đây.

| Owner | Task | Trạng thái | Commit/PR | Artifact/report và run ID | Lệnh + kết quả test | Blocker / bước tiếp theo / người nhận |
|---|---|---|---|---|---|---|
| S — Codex thực hiện theo yêu cầu người dùng | S1 | Xong | chờ review/commit | `gold_v3` | `gold check` PASS: 131 active, 13 slice | Không còn blocker Day 4 |
| S — Codex | S2 | Xong | chờ review/commit | `docs/spec/bench/search-gold-summary.md` | 5.021 tổng / 4.991 active; append-only PASS | Không còn blocker |
| S — Codex | S3 | Xong | chờ review/commit | `sb compare --gold --condensed`; run `20261001-day4-local` | full/condensed compare và Parquet regression PASS | Không còn blocker |
| S — Codex | S4 | Xong | chờ review/commit | 8 model × 3.183 = 25.464 document vector; run `20261001-day4-local` | cả 8 collection đủ 3.183; sanity PASS | Production vẫn Cohere v3 |
| S — Codex | S5 | Xong | chờ review/commit | `eval-2026-10-01-search-v1-3arm.md`; D4b 278/278 | gold cuối nDCG 0,620/0,597/0,648; judged 1,000 | Dense giữ làm mốc vì guard slice |
| S — Codex | S6 | Xong | chờ review/commit | report + `gold/holes/gold_v3__D5a/` | 700/700 +72 auto-OOC; v4-512 full nDCG 0,709, judged 0,898; paired với 1024/1536 đều TIE | Shortlist v4-512 (hiệu quả) + v4-1024 (quality-first); không đổi production |
| S — Codex | S7 | Xong | chờ review/commit | `bench_out/search/runs/20261001-day4-local/latency-embed.json` | e5s 9,192/11,369; GTE 66,487/78,001; BGE 148,779/245,814 ms local; v3 API 459,105/734,967 ms | v4 API 429 đã loại; không trộn điều kiện |
| S — Codex | S8 | Hoàn thành phần (a) | chờ review/commit | full + condensed + coverage trong results/compare | focused tests PASS | stages và split chuyển Day 5; split 100/100 không khả thi |
| R — tqanh123 / Claude | R1 Merge M6, mốc v5 | **Xong 01/10** (gate thay thế) | nhánh `bench/day4-rec`; merge `8842c3a` → `69e01a5`; code Day 4 chưa commit lúc ghi | `configHash b0aee886 / 81d16abd` khớp report v5; DB local seed 09-23 ≠ split 0922 → đóng băng `frozen/split-{llbo,temporal}-asof20260924.json` (1.016 / 98 khách) | pytest harness 62 → **70 passed**; backend recommendation **25 passed**; `doctor` OK; `sanity` **PASS 6/6** | Không tái lập chữ số v5 (khác DB; tunnel VM đóng; seed lại không cùng catalog). Lead xác nhận mốc `v5@asof20260924` |
| R | R2 đủ cột §12 | **Xong 01/10** | như R1 | run `2026-10-01-llbo-v5`, `2026-10-01-temporal-v5` (`bench_out/`); report `src/evaluation/reports/eval-2026-10-01-recsys-bench-v5-asof20260924.md`; spec §4.15 | `metrics.py` Gini + 2 biến thể cross-cat chuyến mở + bootstrap, test tính tay; `run` 6 arm × 2 split exit 0: LLBO engine R@20 0,848 / NDCG@10 0,517 vs mpd 0,602 / 0,380; availability 1,000; coverage 0,565; Gini 0,834 | Cross-cat chuyến mở của engine = 1,0 theo cấu trúc; trích cột "có mua" khi nói cross-sell |
| R | R3 registry | **Xong 01/10 chiều** | nhánh `bench/day4-rec` sau `993669d` (code R3–R6 chưa commit lúc ghi) | `src/evaluation/recsys_bench/models/` (14 module), `algos_v1.yaml`; spec `docs/spec/bench/recsys-algos-v1.md` (đổi tên + errata E1–E12) | pytest harness **96 passed** (`test_models_{data,funnel_regression,itemitem,registry_cli,implicit}.py`); toy cooc/EASE tính tay; `cooc_trip(β=0) ≡ itemknn` 1e-6; `scipy 1.18.1`, `implicit 0.7.3` cài vào `.venv` | `bpr_dest` chưa có cài đặt (`status: not_run`); `because[]` cho scorer mới hoãn |
| R | R4 funnel + `raw` | **Xong 01/10 chiều** | như R3 | run gate `2026-10-01-{llbo,temporal}-gate` (pool engine, vectors weaviate, `algosHash d0d38a58`); `regress-*.json` trong thư mục run | G1 `content_profile+mmr` ≡ `engine` v5: **1016/1016**, **98/98**; G2 `content_profile` ≡ `engine_nommr[:20]`: 1016/1016, 98/98 (khớp cả thứ tự); `star_blend_a1` ≡ `content_profile` 1016/1016, 98/98 | Funnel = mask engine theo quyết định người dùng (bỏ "2 destination lịch sử", "anh em cùng cha" khỏi spec); bảng so scorer dùng pool mask, khác engine ở 76/98 khách temporal → đọc cột `Pool cắt`/`regress` |
| R | R5 scorer Tier 1 | **Xong 01/10 chiều** (smoke) | như R3 | run `2026-10-01-{llbo,temporal}-smoke-{funnel,raw}` (50 khách, pool mask, rerank none + mmr, `--max-tier 2`); report `src/evaluation/reports/eval-2026-10-01-recsys-algos-v1-smoke.md` | Mọi scorer exit 0; fit: cooc 0,4 s · star 0,4 s · itemknn < 0,1 s · ease 1,0 s · rp3beta 0,3 s · ials 0,1 s/seed · bpr 0,1 s/seed; `fitLog` đủ 6 khoản | Full run Day 5 (mọi Tier 1 × 2 rerank × 2 split) chưa chạy; smoke 50 khách chỉ để kiểm chạy được, không kết luận |
| R | R6 CLI | **Xong 01/10 chiều** | như R3 | `run --algos … --mode`, `regress`, `report` (sáng), `compare` (sáng) | test CLI CliRunner: lỗi cấu hình thoát trước DB, `expect_equal_to` thất bại → mã 1 và bỏ hàng, `merge_run` từ chối khác `algosHash`, `analyze` có scorer mới trong phân khúc | `--help` không cần `implicit`; `--algos` bắt buộc `--vectors` |
| R | R7 P1/P3 sau M6 | **Xong 01/10** | như R1 | spec §5.1 | `user --id VP0000001` 4/4; `user --id VP0000003` 4/4 (`p3Check` mới); 0 lỗi contract; dư `sections` (I-4) | Contract 1.12.0 không thiếu field → không mở PR; dormant 90 (contract) vs 180 (code) → I-8 |
| R | R8 Ceiling | **Xong 01/10** | như R1 | spec §7 "Ceiling", §4.15; `bench_out/…/ceiling.{json,md}` | `analyze` hai run: ceiling 0,988 (1004/1016) / 0,918 (90/98) ≥ mpd 0,602 / 0,102; đa nhãn 12 > 8 (4 khách 2 nhãn) | Hướng tuần sau: split "next trip"; cap theo `parentProductId` (I-5) qua đề xuất PRD; λ MMR vào grid |
| R | R9 Full run bảng thuật toán (Day 5) | **Xong 01/10 tối** | nhánh `bench/day4-rec` sau `8fffd4b` (code Day 5 chưa commit lúc chạy) | run `2026-10-01-{llbo,temporal}-algos-{funnel,raw}`, `…-content-nodecay`, `…-gate-numpy`; report `src/evaluation/reports/eval-2026-10-01-recsys-algos-v1.md`; spec §4.17 | 6 run + 2 gate exit 0; `expectFailed []`; leak 0; 102 `compare` có CI | 441/1.016 khách LLBO có target trong giỏ trước khi mua → harness thêm nhãn trước grid (ADR 2 #2) |
| R | R10 `baseline_v1` + `regress --baseline` | **Xong 01/10 tối** | như R9 | `frozen/baseline_v1-{llbo,temporal}-asof20260924.json`; `models/baseline.py`; lệnh `baseline`; `make recsys-{test,gate-run,regress,baseline}` | pytest 7 test baseline; `regress --baseline auto` PASS mã 0 trên run nguồn; `make recsys-regress` PASS (run `2026-10-01-{llbo,temporal}-make-regress`) | Regress chưa vào CI (CI không có Postgres seed) |
| R | R11 ADR 2 hướng recsys | **Xong 01/10 tối**; **đã xác nhận 02/10**, giữ nguyên thứ tự | — | `history/2026-10-01-adr2-huong-cai-thien-recsys-tuan-sau.md`, `history/2026-10-02-xac-nhan-adr2-recsys.md`; report mục 12; spec §4.17 | — | 3 đề xuất PRD chưa soạn (I-5, giỏ hàng, I-8) |
| R | R12 because[] cho scorer mới | **Xong 01/10 tối** | như R9 | `models/because.py`; `run --because-k K` (K = 5/10/15/20); run `2026-10-01-{llbo,temporal}-because-k{5,10,15,20}`; report phụ lục A | pytest 7 test because (star a = 1 trùng bit engine, ials cộng đúng điểm) | `content_profile` vi phạm luật contract ở coldStart / dormant — finding, không sửa engine; khoá `kind` ngoài contract |
| R | R13 `bpr_numpy` / `bpr_dest` | **Xong 01/10 tối** | như R9 | `models/bpr_numpy.py`; yaml Tier 2; run `2026-10-01-{llbo,temporal}-bpr-tier2`; report phụ lục B; spec algos §6.3 | pytest 6 test (bước SGD tính tay, sampler, tất định, đối chứng implicit) | Không bit-identical với implicit (RNG khác) — so theo CI |
| S — tqanh123 / Claude (05/10, nhánh `fix/search`) | S-F1/F2: lọc cứng điểm đến suy từ câu (FR-SRC-03) + bộ ngưỡng riêng câu không dấu, sau cờ | **Xong 05/10** (code chưa commit lúc ghi) | nhánh `fix/search` từ `942f5aa`; sửa thêm import `Protocol` ở `ports/unit_index.py` | contract **1.14.0** (`derivedDestinations`, `destinationFilter`, `queryProfile`); `history/2026-10-05-search-dest-filter-no-diacritics.md` | backend domain + application + architecture + contract **610 passed**; `validate_contract.py` PASS | Cờ mặc định tắt; bật sau khi có dev/test; cherry-pick vào `release-mvp-v2` cần giải conflict `scored()` |
| S — tqanh123 / Claude | S-APP-e5: cổng APP theo model, 12 arm `APP.e5s.*` qua `SearchProducts` thật, đo F1/F2/cutoff | **Xong 05/10** | như trên | run `2026-10-05-fix-search-e5s`, `2026-10-05-e5s-det`; report `src/evaluation/reports/eval-2026-10-05-search-e5s-dest-nodia.md`; `history/2026-10-05-search-bench-app-e5s.md` | `test_app_adapter.py` 8 passed; sanity 4/4; 12 arm exit 0; F1 WIN Δrecall +2,34 [+1,03; +3,84]; `hybrid_norm + F1 + F2(0,80)` WIN +2,82 / ΔnDCG +3,54 [+1,48; +5,78] | Không có arm Cohere (chốt bỏ Cohere); chưa HTTP; ngưỡng trong mẫu chờ `devtest.py`; thêm `wait_bm25_stable` vì index BM25 chưa ổn định ~30 s sau nạp |
| S — tqanh123 / Claude | Đề xuất PRD FR-SRC-02 → e5-small local | **Chờ chốt** | — | `docs/prd/update/2026-10-05-fr-src-02-embedding-local-e5-small.md`; `history/2026-10-05-de-xuat-fr-src-02-e5-small.md` | — | Lead chốt; adapter backend + đo HTTP chỉ làm sau khi chốt (AGENTS §8) |
| S — tqanh123 / Claude (05/10 tối) | Phase A query plan F3–F6 (backend + contract 1.15.0 + spec) | **Xong 05/10** (chưa commit) | `fix/search` | `history/2026-10-05-search-query-plan-f3-f6.md` | backend **825 passed**; `validate_contract.py` PASS; identity bench 131/131 | Cờ tắt; bật từng cờ sau gold v4 (F4 cần thu hẹp cue trước) |
| S — tqanh123 / Claude (05/10 tối) | Bench guard Phase A (Forbidden@10, direction, filter pass, parse; `gold-scan`, `topids-diff`; 6 arm) | **Xong 05/10** | `fix/search` | run `2026-10-05-fix-search-qp`; `eval-2026-10-05-search-query-plan-plumbing.md`; `history/2026-10-05-search-bench-query-plan-guards.md` | bench 48 fail có sẵn không tăng, +53 test; F3 Forbidden@10 → 0/10; F6 +11,0; F4 −6,1 abbrev_typo | Gold v4: chờ tên trường/slice → `gold_schema.py` + `sb gold append` (Sprint 2 bước 0) |

Mỗi report phải có commit + run ID + gold/split version/hash + cấu hình arm, bảng số nguyên văn từ output, caveat và lệnh tái sinh. Không ghi DSN/secret vào lệnh bàn giao.

### 5.5 Điểm còn cần xác nhận

- [ ] Tên hai người tương ứng S/R. *(R = tqanh123 / Claude, 01/10; S chưa.)*
- [x] Nguồn đặc tả `cooc_trip`/`star_blend` và tham số còn thiếu của thuật toán; không suy đoán để bỏ blocker. *(01/10 chiều: người dùng bổ sung `docs/spec/bench/recsys-algos-v1.md`; errata E1–E12 đối chiếu code sau M6 ghi trong spec.)*
- [ ] bge-m3 dùng int8 hay fp32, model revision cụ thể. *(05/10 rà: thực tế đã chạy **fp32**, safetensors, CPU, `BAAI/bge-m3` bản tải mặc định; revision commit chưa ghi vào meta. BGE không vào shortlist nên không chặn việc gì; còn chờ lead xác nhận.)*
- [x] Kích thước split dev/test hợp lệ nếu làm S8 (131 câu không đủ 100/100). *(05/10 người dùng chốt: chia đôi ~65/66, phân tầng theo slice, seed cố định, file riêng không sửa `gold.jsonl`; chưa chạy.)*
- [ ] Owner xử lý `/search` cloud và thời điểm bàn giao cho người đo gate P. *(05/10 rà: vẫn chưa có owner. Nguyên nhân đã đo 01/10: Weaviate Cloud `eu-central-1` khác vùng VM, mask 3.146 id mỗi lượt, dense và BM25 nối tiếp — `eval-2026-10-01-search-cloud-latency.md`.)*
- [ ] Chốt đề xuất FR-SRC-02 (model embedding tìm kiếm → `intfloat/multilingual-e5-small` local): `docs/prd/update/2026-10-05-fr-src-02-embedding-local-e5-small.md`. *(05/10: bằng chứng pipeline thật ở `eval-2026-10-05-search-e5s-dest-nodia.md`; chưa có so sánh cùng thang với Cohere v3 — nhóm bỏ bước này. Adapter backend và đo HTTP chờ chốt.)*
