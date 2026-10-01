# Chia task Day 4 (T5 01/10) cho 2 người — Search (S) và Rec (R)

- Phục vụ: FR-SRC-01..04, AC-SRC-01, NFR-PERF-01 (phía search); FR-REC-01..04 (phía rec); test-plan §2.4–2.5.
- Bản chi tiết của §1 `docs/plan/2026-10-01-plan-day4-5.md`. Plan đó chia cho 4 vai (A1, A2, B, C). File này gộp lại cho **2 người**: **S** nhận Track A + phần search của Track C, **R** nhận Track B + phần recsys của Track C.
- Nhánh làm việc: `bench_search_recomSys` (= `fe7e04d`, PR #68). Mỗi người tách nhánh con từ đây (`bench/day4-search`, `bench/day4-rec`) và merge lại cuối ngày.
- **Mốc engine recsys = v5 (theo quyết định ghi ở history phân công 01/10):** merge M6 (`origin/bench/m6-trip-ended`, đề xuất `2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md` đã áp dụng) **trước** mọi số đo Day 4. Trong plan Day 4–5, mọi chỗ ghi "v0" (engine qua funnel = v0, `baseline_v1.json`) đều hiểu là **v5**.
- Người phụ trách: **S (Search): chưa điền tên**; **R (RecSys): chưa điền tên**. Giữ đầy đủ phạm vi Day 4; việc chưa xong phải ghi blocker và bàn giao, không tự coi là đã được duyệt giảm phạm vi.
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

- [ ] **Thực hiện:** `git merge origin/bench/m6-trip-ended` vào nhánh con. **Không** merge thêm `feat/recsys-trip-ended`: nếu engine của hai nhánh khác nhau (diff `profile.py`, `use_cases.py`), báo lead. Chạy `pytest src/evaluation/recsys_bench/tests` + test recommendation của backend (env `vsf2`). Chạy lại `run … --split-file frozen/split-{llbo,temporal}-asof20260922.json --run-id 2026-10-01-{llbo,temporal}-v5-check`
- [ ] **Nghiệm thu:** Metric chất lượng tái lập khớp report v5 với cùng dữ liệu, split, seed và config; latency đo lại, không yêu cầu trùng từng chữ số. Đối chiếu report v5 (`eval-2026-10-02-recsys-bench-v5.md`); `configHash` eval/prod = `b0aee886` / `81d16abd`. Lệch → dừng, tìm nguyên nhân trước khi làm R2
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


### R2 — **Đủ cột §12 cho 4 arm trên v5**

- [ ] **Thực hiện:** Trong `metrics.score`: thêm **Gini** độ phủ (exposure top-20 trên mọi khách test); thêm `cross_category_open_trip`: chỉ khách có chuyến mở tại `as_of`, tỉ lệ item top-20 thuộc vertical **chưa mua trong chuyến đó** (lấy chuyến mở từ `ceiling.engine_view`). Giữ cột cũ. Ghi caveat: availability đo theo `attributes.availability` hiện tại, không tái dựng lịch sử. Thêm test
- [ ] **Nghiệm thu:** Bảng v5 (random 3 seed, most_popular, mpd, engine, engine_prod): Recall@10/20, NDCG@10, cross-category (2 kiểu), availability, coverage, Gini, p95/p99 offline
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


### R3 — **Registry thuật toán**

- [ ] **Thực hiện:** `src/evaluation/recsys_bench/models/`: `base.py` (`fit(train_events, catalog, vectors)`, `score(user_ctx, candidate_ids) → scores`; `UserCtx` = event < `as_of`, chuyến mở, destination, vertical đã mua). Đăng ký theo tên trong `src/evaluation/recsys_bench/algos_v1.yaml`, tham số **mặc định**, không tune. Port logic (không chép file ra gốc `src/evaluation/`) từ `recommender_prototypes.py` của nhánh research. Thêm `implicit`, `scipy` vào `src/evaluation/requirements.txt`
- [ ] **Nghiệm thu:** Chạy end-to-end trên split với 2 scorer rẻ nhất: `cooc_trip` (cosine + shrinkage theo trip, top-50/item) và `ease` (nghiệm đóng, λ mặc định)
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


### R4 — **Funnel chung + chế độ `raw`**

- [ ] **Thực hiện:** `funnel.py`: `candidates = filter(destination chuyến mở ∥ 2 destination lịch sử, taxonomy ∉ vertical đã mua, is_recommendable, available)` → `score` → top-20; điểm 0 / không có tín hiệu thì phá hoà bằng `pop_D`. **Dùng lại `ceiling.engine_view`** làm bộ lọc để mask trùng engine. `raw` = không lọc, xếp toàn catalog. Bọc engine production thành scorer `content_profile`
- [ ] **Nghiệm thu:** Test regression: `content_profile` qua funnel = **đúng số v5** (LLBO + temporal). Chưa bằng thì không chạy scorer khác
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


### R5 — **Đủ scorer Tier 1 + `algos_v1.yaml`**

- [ ] **Thực hiện:** Baseline: `random` (3 seed), `mostpop_window` (90 ngày = `most_popular` hiện có), `mostpop_in_dest`. Content: `content_profile`, `content_no_decay`, `content_no_mmr` (= `engine_nommr`). Co-occurrence: `cooc_trip`, `star_blend` (a = 0,5). CF: `ease`, `itemknn` (`implicit` cosine). MF: `ials` (64 factor, α = 40), `bpr` (64 factor, negative toàn cục nếu research chưa có negative theo destination; ghi rõ). Tier 2 `rp3beta` chỉ khi còn giờ. Chạy thử mỗi scorer `--limit-users 50` cả hai chế độ
- [ ] **Nghiệm thu:** Mọi scorer Tier 1 chạy không lỗi; yaml có tier · tham số · cần train? · thời gian fit + thời gian ước cho full run
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


### R6 — **CLI chạy lại được**

- [ ] **Thực hiện:** `python -m src.evaluation.recsys_bench run --algos algos_v1.yaml --split-file <file> --mode funnel\|raw` → `bench_out/recsys/runs/<hash config>/`; bảng markdown sinh tự động; đầu file ghi `git describe` + `modelVersion` + `configHash`
- [ ] **Nghiệm thu:** Chạy `content_profile` bằng CLI mới ra đúng số v5
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


### R7 — **Kiểm exclusion/diagnostics sau M6** (phần C)

- [ ] **Thực hiện:** `recsys_bench user --id VP0000001` (P1: chuyến mở, đã mua hotel) và một khách P3 dormant: `strategy`, `excludedVerticals`, `nextVertical`, `coldStart` đúng FR-REC-02 bản mới. Đối chiếu field `/recommendations` trong contract 1.12.0 với plan §1.3 #5
- [ ] **Nghiệm thu:** Ghi kết quả vào spec recsys §5. Sai logic → mở issue / fix và báo lại R1. Contract thiếu field → báo lead (không tự mở PR contract nếu không thiếu)
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


### R8 — **Mục "Ceiling" trong report**

- [ ] **Thực hiện:** v5: LLBO 0,990, temporal 0,892 > Recall@20 của mpd (0,098) → **không** kích hoạt nhánh "ceiling < mpd" của plan. Viết 1 đoạn: 11/102 ca temporal chưa tới được mask; report v5 ghi lý do 6 `taxonomy_excluded`, 9 `destination_mismatch`, 1 `already_bought` (tổng 16 > 11, nên một ca có thể mang nhiều lý do; kiểm lại trong `ceiling.json`); kèm hướng cho tuần sau
- [ ] **Nghiệm thu:** Đoạn trong `docs/spec/bench/recsys-offline-eval.md` §7
- [x] **Bàn giao:** đã điền artifact, lệnh, kết quả kiểm tra và blocker vào §5.


**Checkpoint 17:15 (R):** v5 tái lập đúng số · bảng v5 đủ cột §12 (có Gini, cross-category theo chuyến) · registry + funnel + `raw` · `content_profile` qua funnel = v5 · `algos_v1.yaml` · mọi Tier-1 scorer chạy thử 50 user · CLI `run --algos` · P1/P3 đã kiểm sau M6.

## 3. Điểm nối giữa S và R

- **Weaviate local dùng chung:** R chỉ đọc collection production (`Product`, Cohere v3); S tạo collection mới theo tên arm. Không ai `drop` / `--recreate` collection của người kia.
- **Máy:** S4 (embed local CPU) nặng. R chạy recsys sau 15:00 (full run Day 5) thì tránh trùng giờ embed `bge-m3`, hoặc chạy trên máy khác.
- **History:** mỗi người một entry `history/2026-10-01-<slug>.md` cho phần của mình. Report kết quả chạy để trong `src/evaluation/reports/eval-2026-10-01-*.md` (AGENTS.md §7).
- **Merge cuối ngày:** R merge trước (đụng `recsys_bench/`, backend recommendation qua M6), S merge sau (chỉ `search_bench/`, `gold/`). Hai bên gần như không chung file, trừ `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` (tick + log). Người merge sau xử lý conflict ở file này.

## 4. Chưa rõ — cần lead xác nhận

1. `TRAINING_FREE_RECSYS.md`, `RECSYS_METHODS_BY_SCALE.md`, `serve_bench.py` (plan Day 4–5 dẫn cho `cooc_trip` / `star_blend`) **không có trong repo**. R cần file gốc hoặc đặc tả công thức/tham số được xác nhận; **không tự cài theo mô tả một dòng**. Ghi blocker cho scorer liên quan, vẫn làm registry/funnel và các scorer đủ đặc tả.
2. `bge-m3` bản int8 cộng đồng như plan ghi, hay fp32 theo `sbench.yaml` hiện tại? (S4)
3. Gold mới nhất là `gold_v2`, sau S5 có thể là `gold_v3`. Plan Day 5 ghi `gold_v1.1` → hiểu là "gold mới nhất sau top-up", không đổi tên tag cũ.
4. `/search` cloud 500 (lỗi embed Cohere trên VM) vẫn chưa ai xử lý; gate P Day 5 cần nó. Không giao cho S hay R hôm nay.

## 5. Checklist phối hợp và bàn giao cuối Day 4

### 5.1 Trước khi bắt đầu

- [ ] Điền tên S/R ở đầu file; S review đầu ra R, R review đầu ra S.
- [x] Ghi HEAD thực tế (`b692047`) và snapshot/checksum catalog (`ad3f3be25647a44c027ab21592f4defc3740f247090a146ea3614eb83adff4ab`); `fe7e04d` là mốc khảo sát, không mặc định là HEAD sau merge.
- [x] S xác nhận gold/tag/hash (`gold_v2`, SHA-256 `61a312e0ea6be510c72a337d07d928d00e67c5e7f031eab84837174b29c7ad7e`); R xác nhận frozen split/hash và mốc v5 sau R1. Không so số khác phiên bản mà chưa rescore/tái chạy.
- [ ] R kiểm tra PRD sau tích hợp M6 trước khi dùng hành vi mới; lịch sử chốt trên nhánh khác không thay thế bước cập nhật PRD tại nhánh làm việc.
- [ ] Mỗi người đọc tài liệu bắt buộc theo AGENTS.md trước khi code. `src/evaluation/README.md` hiện thiếu: cần hỏi người dùng theo AGENTS.md §1.2 trước khi giả định nội dung; việc chỉnh checklist này không thay thế bước đó.
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

- [ ] random — 3 seed.
- [ ] mostpop_window — 90 ngày.
- [ ] mostpop_in_dest.
- [ ] content_profile — regression khớp v5.
- [ ] content_no_decay.
- [ ] content_no_mmr.
- [ ] cooc_trip — chỉ triển khai khi đủ đặc tả.
- [ ] star_blend — a = 0,5, chỉ triển khai khi đủ đặc tả.
- [ ] ease — ghi λ cụ thể từ nguồn đã xác nhận, không để “mặc định” mơ hồ.
- [ ] itemknn — ghi k và cách chuẩn hóa.
- [ ] ials — 64 factor, α = 40; ghi seed/iterations.
- [ ] bpr — 64 factor; ghi seed/iterations và cách lấy negative.

**Bổ sung điều kiện nghiệm thu:**

- [ ] R2 ghi mẫu số Gini/coverage, xử lý danh sách rỗng và user không có chuyến mở; test fixture có kết quả tính tay.
- [ ] R4 kiểm mask/tie-break và metric trên cả LLBO + temporal; chưa khớp v5 thì chưa công bố bảng so scorer.
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
| R — chưa điền tên | R1–R8 (tách dòng theo task khi cập nhật) | Chưa nghiệm thu | — | — | Chưa chạy trong lần cập nhật tài liệu | Điền sau khi nhận việc |

Mỗi report phải có commit + run ID + gold/split version/hash + cấu hình arm, bảng số nguyên văn từ output, caveat và lệnh tái sinh. Không ghi DSN/secret vào lệnh bàn giao.

### 5.5 Điểm còn cần xác nhận

- [ ] Tên hai người tương ứng S/R.
- [ ] Nguồn đặc tả `cooc_trip`/`star_blend` và tham số còn thiếu của thuật toán; không suy đoán để bỏ blocker.
- [ ] bge-m3 dùng int8 hay fp32, model revision cụ thể.
- [ ] Kích thước split dev/test hợp lệ nếu làm S8 (131 câu không đủ 100/100).
- [ ] Owner xử lý `/search` cloud và thời điểm bàn giao cho người đo gate P.
