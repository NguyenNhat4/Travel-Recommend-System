# Lịch 10 ngày — hoàn thiện 3 engine + benchmark (28/09 → 09/10/2026)

- Phục vụ: **FR-SRC-01..04**, **FR-REC-01..04**, **NFR-PERF-01**, **NFR-PERF-03** (`docs/prd/requirements.md`); đánh giá theo `docs/prd/test-plan.md` §2.4–2.5.
- Căn cứ: `docs/plan/2026-09-28-summary-search-recsys-benchmark.md` (trạng thái tại `bench/embed-search @ a0efb2f`) đối chiếu `recsys-internship-handbook-v3` §2, §7, §11 (Week 3–5), §12.
- Phạm vi: `/search`, `/products/{id}/similar`, `/recommendations` và bộ đánh giá (`src/evaluation/search_bench`, RecSys offline harness). Web, booking flow, itinerary agent thuộc nhóm khác — chỉ ghi điểm giao.
- Cách dùng file này: tick `[x]` khi xong; ghi số đo ngay cạnh mục (không để "đã chạy" mà không có số); **không sửa** mục đã đóng băng (`gold/drafts.txt` sau Day 1, `gold_v1` sau Day 4, tag release sau Day 9). Cuối ngày ghi 3 dòng vào §8 Log.

## 0. Giả định lịch

| Day | Ngày | Day | Ngày |
|---|---|---|---|
| 1 | T2 28/09 | 6 | T2 05/10 |
| 2 | T3 29/09 | 7 | T3 06/10 |
| 3 | T4 30/09 | 8 | T4 07/10 |
| 4 | T5 01/10 | 9 | T5 08/10 — **code freeze + tag** |
| 5 | T6 02/10 — checkpoint tuần | 10 | T6 09/10 — sinh lại số từ tag, viết |

Nếu Day 1 thực tế bắt đầu 29/09: mọi mốc lùi 1 ngày, freeze rơi vào T6 09/10, không còn buffer → README/report làm song song từ Day 8.

## 0.1. Đính chính 29/09 (B, C)

Các dòng dưới đây thay chỗ tương ứng trong các mục sau; nội dung gốc giữ nguyên để đối chiếu.

| Chỗ trong lịch | Thay bằng | Vì sao |
|---|---|---|
| Day 1 thực tế | B và C bắt đầu 29/09 → áp dòng "mọi mốc lùi 1 ngày" ở trên | |
| B: "Tạo nhánh `bench/recsys-harness` từ `release-mvp-v1`; merge `origin/khoa/recsys-research`" | Nhánh `bench/recsys-harness` tách từ `bench/embed-search`; **port có chọn lọc** split, metric, `all_events()` từ `origin/khoa/recsys-research@6b9b0af` vào `src/evaluation/recsys_bench/`, không merge | `bench/embed-search` đã chứa trọn `release-mvp-v1` và có CDP fallback 28/09. Nhánh khoa dựng trên nền 21/09: `ports/recsys.py` đã đổi thành `ports/unit_index.py`, `UnitIndex` không còn `E`, `PostgresVectorStore.load()` trả tuple, `SentenceTransformersEmbedder` đã comment → merge thì vỡ |
| C: timing per-stage `/search` | Nhánh riêng `feat/search-stage-timing` tách từ `release-mvp-v2`, field `diagnostics.stageMs` khai trong contract trước | `release-mvp-v2` là nhánh deploy VM và đã chứa `bench/embed-search`; cần lên VM để Day 2 đo trên cloud |
| "test backend vẫn **495 passed**" | **651 passed, 19 skipped** (Docker `python:3.11`, 29/09) | 495 là số ngày 25/09 |
| "loại event thiếu `event_group_id` … ≈ 2 % purchase orphan + 3 % thiếu group" | Chỉ lọc trên **purchase**: orphan 63/3.153 (2,0 %), thiếu gid 94/3.153 (3,0 %) theo `seed_report.md`. View/cart/search không có gid theo thiết kế — giữ | `MOCK_DATA_SPEC.md` mục "Chỉ `purchase` mang `event_group_id`"; lọc trên mọi event sẽ mất ~56 % dữ liệu |
| Day 2 B: "Zipf 1.1 phải thấy rõ" | `ZIPF_S = 0,8` (`src/data_collection/seed/config.py`); top-10 % sản phẩm chiếm 39 % purchase | Hạ từ 1.1 xuống 0.8 ngày 21/09 để baseline Recall@20 < 0,60 |
| `eval/report.md` | Số và cách chạy: `docs/spec/bench/recsys-offline-eval.md`; số thô: `bench_out/recsys/` (không commit) | `AGENTS.md` §7 không cho tài liệu ngoài `docs/` |
| `docs/decisions/` (Day 5: giữ Cohere hay đổi model) | Đổi embedding khỏi Cohere là lệch FR-SRC-02 → đề xuất trong `docs/prd/update/`; giữ Cohere thì ghi ở `history/` | `AGENTS.md` §7, §8 |
| Checkpoint Day 1: "note đã gửi mentor" | Vẫn 3 mục (backend, vector store, embedding) so với **bản handbook gốc** (`e33bdb6^`); ghi rõ bản trong repo đã được nhóm sửa ngày 16/09 (`e33bdb6`) nên chỉ còn pin pgvector và embedding local. Note: `docs/spec/bench/note-mentor-lech-handbook.md` | |
| C: "Bật `SEARCH_HYBRID=true` trên cloud" | Mặc định đã `true` (`core/config.py`), `ops/` không ghi đè → việc thật là backfill property BM25 rồi xác nhận `diagnostics.searchMode = HYBRID_CANDIDATE_SCORE` và `lexicalCandidates > 0` | |
| C: backfill BM25 | Chỉ chạy với DB **khớp cloud**: *(30/09)* đó là Postgres seed snapshot 2026-09-23 (3.183 unit), **không** phải DB trên VM (3.008 unit, sẽ xoá 285 vector). Thêm bước `PUT /v1/schema/Product` đặt stopwords `none` trước; `--dry-run` vẫn POST property thiếu lên schema | Job xoá vector không có trong DB của máy chạy (`.env.example`, history 24/09, 30/09) |
| C: kiểm P1 `nextVertical ∈ {flight, attraction}` | Có thể ra `combo`/`golf` vì engine không loại combo; nếu vậy chỉ ghi issue | `application/recommendation/use_cases.py` (mask, `nextVertical`) |
| Ngưỡng p95 `/search`, `/recommendations` | **250 ms** theo NFR-PERF-01 (PRD thắng handbook/spec 300 ms) | `AGENTS.md` §2 |
| Issue | Ghi ở mục "Issue Day 1" của `docs/spec/bench/recsys-offline-eval.md` và `history/` | Repo không dùng GitHub Issue cho việc này |

## 1. Mục tiêu phải đạt (Definition of Done)

| # | Mục tiêu | Tiêu chí đạt | Hạn |
|---|---|---|---|
| M1 | Tag `gold_v1` | κ ≥ 0,6; đủ 13 slice; `sb gold check` xanh | Day 4 |
| M2 | Search có số trên gold | Recall@10 / nDCG@10 / MRR@10 / zero-result theo slice cho dense-only (B0), hybrid, hybrid + normalize; S1/S2/S9/S10 chốt bằng số → spec §10; ≥ 1 arm E so Cohere vs `multilingual-e5-base` | Day 6 |
| M3 | Latency search | p50/p95 tách embed / Weaviate / rerank; cache embedding theo query đã chuẩn hoá + prewarm; p95 cache-hit và cache-miss báo riêng. **Quyết định giữ Cohere hay đổi model chậm nhất Day 5** | Day 7 |
| M4 | Weaviate Cloud = local | `--backfill-lexical` xong; parity test 20 query cloud vs local | Day 1–2 |
| M5 | RecSys có số trên DB seed | Harness merge; sanity check data seed; bảng Recall@10/20, NDCG@10, cross-category, availability, coverage, p95/p99 cho random / most-popular / most-popular-in-destination / engine. Đạt: thắng rõ most-popular-in-destination ở Recall@20 và NDCG@10; availability ≥ 95 %; coverage > 20 % | v0 Day 5, chốt Day 7 |
| M6 | Tham số recsys khớp spec | Grid-search event weight, half-life, ngưỡng dormant, công thức điểm; giá trị thắng → config + `modelVersion`; sửa spec §4.3–4.7 khớp code; test tiêu chí 20–23 | Day 6 |
| M7 | Ablation | Tối thiểu trip decay on/off, category exclusion on/off (recsys) + hybrid vs dense (search); MMR on/off nếu còn thời gian | Day 7 |
| M8 | Tích hợp | E2E feedback loop chạy được; response `/recommendations` khớp handbook §7; p95 `/search` và `/recommendations` đo **trên cloud** | Day 8 |
| M9 | Freeze + report | Gate FINAL xanh; tag; README chạy từ đầu bởi người chưa từng chạy; mọi số trong `eval/report.md` sinh lại từ tag, kèm caveat dữ liệu sinh; 1 trang/workstream | Day 9–10 |

## 2. Vai trò & nhịp

- **A1, A2** — gold + search bench (bắt buộc 2 người để tính κ)
- **B** — RecSys offline harness
- **C** — engine fixes, latency, tích hợp
- Standup 15 phút đầu ngày; checkpoint cuối ngày theo mục "Checkpoint" của từng Day. Từ Day 6, A và B nhập thành evaluation + report.

## 3. Day 1 — T2 28/09

### A1 — đóng băng drafts
- [ ] Rà 42 câu `--fill` trong `gold/drafts.txt` bằng app Streamlit hiện có (KEEP / REJECT / NEEDS_EDIT). Mỗi câu kiểm 3 điều: đúng slice; tiếng Việt tự nhiên như khách gõ; có ≥ 1 sản phẩm trong catalog có thể liên quan (trừ slice `out_of_catalog`). REJECT → thay bằng câu trong 472 draft chưa dùng. *(2h)*
- [ ] Sửa `c0241`, `c0503`, `c0531` theo ghi chú đã có. *(0,5h)*
- [ ] Thêm 2 câu dự phòng cho 5 slice đang đúng 10 câu: `amenity_multi`, `amenity_negation`, `amenity_offtaxonomy`, `cross_vertical`, `out_of_catalog` — chọn câu khác mẫu với 10 câu đang có. *(1h)*
- [ ] `sb gold check` trên drafts → commit → ghi hash vào `docs/spec/bench/search-eval-checklist.md` → **đóng băng `drafts.txt`** (210 câu, 13 slice đủ quota). *(0,5h)*

### A2 — app gán nhãn
- [ ] Dựng app gán nhãn 0/1/2 theo `docs/spec/bench/prompts/may2-label-app.md`: đọc file pool; hiển thị query + slice + product card (name, taxonomy, destination, price, amenities, description rút gọn); phím tắt `0/1/2`, skip, flag; lưu tăng dần để resume; xuất đúng `gold_schema.py`. *(4–5h)*
- [ ] Test: gán thử trên fixture `gold_small/` → `sb gold import` nhận file xuất không lỗi.
- [ ] Chọn ~20 cặp khó từ pool thử `bench_out/` cho phiên calibration: negation, off-taxonomy, cross_vertical, hạng phòng anh em, out_of_catalog. *(0,5h)*

### A1 + A2 — calibration (cuối ngày, 1,5h)
- [ ] Đọc `docs/spec/bench/gold-guide.md`; gán độc lập 20 cặp khó; so đáp án; bất đồng ≤ 3/20.
- [ ] Ghi quy ước vào mục "ví dụ khó" của guide. Phải trả lời được:
  - hạng phòng anh em của đúng khách sạn → 1 hay 2?
  - đúng amenity nhưng sai destination → 0?
  - `out_of_catalog` → mọi ứng viên = 0?
  - sai taxonomy nhưng đúng ý (ví dụ hỏi hotel, ra combo có hotel đó) → ?

### B — harness lên DB seed
- [x] Tạo nhánh `bench/recsys-harness` từ `release-mvp-v1`; merge `origin/khoa/recsys-research`; giải quyết conflict; test backend vẫn **495 passed**. *(2h)* — *29/09: nhánh tách từ `bench/embed-search @ f2a697a`; port có chọn lọc từ `khoa/recsys-research@6b9b0af` thay cho merge (§0.1). `src/backend/tests` + `recsys_bench/tests` trong Docker `python:3.11`, không `.env`: 683 passed, 19 skipped (651 cũ + 3 test reader + 29 test harness).*
- [x] Nối harness vào DB đã seed: đọc `cdp.events` / `cdp.profiles` / `cdp.products` thật (2.000 khách, ~7.000 event) thay cho lịch sử tổng hợp. Loại event thiếu `event_group_id` hoặc `product_id` không tồn tại; **in số bị loại** (kỳ vọng ≈ 2 % purchase orphan + 3 % thiếu group theo MOCK_DATA_SPEC). *(2h)* — *29/09: `python -m src.evaluation.recsys_bench load` trên Postgres local seed 24/09: 7.145 event; purchase orphan 63/3.153 (2,0 %), thiếu gid 94 (3,0 %), loại 152 (hợp); giữ 6.993 event của 1.582 khách; view/cart/search thiếu gid giữ nguyên (§0.1). Event đọc qua `PostgresCdpReader.all_events()` bằng `EVAL_DATABASE_URL`.*
- [x] Chốt split trong `src/evaluation/.../splits.py`: leave-last-booking-out (giấu purchase gần nhất của khách có ≥ 2 purchase; khách 1 purchase không vào test) **và** temporal split (train < T, test ≥ T). Ghi số user train/test, số test item vào `eval/report.md` mục "Split". *(1,5h)* — *29/09: `src/evaluation/recsys_bench/splits.py`. LLBO 1.016 khách test (269 nếu chọn như seed, ≥ 2 trip); temporal T = 2026-07-10T09:13Z (phân vị 80 %), 98 khách test, 262 khách chưa có event trước T bị loại. Số ở `docs/spec/bench/recsys-offline-eval.md` §3.*
- [x] Bọc engine production thành hàm offline `recommend(cdp_user_id, as_of, k)` gọi trực tiếp (không HTTP). Kiểm tra engine **không nhìn thấy event sau `as_of`**. Chạy random baseline end-to-end trên DB seed. *(1,5h)* — *29/09: `OfflineEngine.recommend` (`recsys_bench/engine.py`) gọi `RecommendForUser` + `BuildPopularity(now=as_of)` từ purchase trước as_of; chặn event ≥ as_of ở hai tầng, có test (engine tự nó không loại mà kẹp `days_ago` về 0). Random 3 seed trên LLBO: Recall@20 0,0066 ± 0,0023. Engine v0 chạy sớm: Recall@10 0,619, NDCG@10 0,472, coverage 0,207, p95 58 ms (Weaviate local).*

### C — mentor, cloud, timing
- [ ] Backfill BM25 trên Weaviate Cloud: `python -m src.backend.jobs.embed_products --backfill-lexical`. Kiểm số object có `nameAscii` / `searchTextAscii` = **3.183**. Bật `SEARCH_HYBRID=true` trên cloud. *(2h)* — *29/09: chưa chạy. Máy làm B/C không có quyền VM hay khoá Weaviate Cloud, và job chỉ được chạy trên VM (§0.1). Runbook từng bước: `history/2026-09-29-cloud-backfill-lexical.md`.* — *30/09: đã kiểm chỉ đọc. Cloud có 3.183 object, 0 có dữ liệu BM25, stopwords `en`. DB trên VM chỉ có 3.008 unit: chạy job với DB đó sẽ xoá 285 vector và embed lại 158, nên **không chạy trên VM**. Postgres local seed 24/09 khớp cloud tuyệt đối (embed 0, xoá 0, backfill 3.183). Phần ghi chưa chạy, chờ người dùng. Runbook đã sửa: `history/2026-09-30-backfill-bm25-cloud-kiem-nguon-db.md`.*
- [x] Thêm timing per-stage cho `/search` (normalize → embed → dense → BM25 → RRF → hydrate) vào `diagnostics` hoặc log — đầu vào cho Day 2. *(2h)* — *29/09: code xong trên nhánh `feat/search-stage-timing` (tách từ `release-mvp-v2`, chưa commit/PR): `diagnostics.stageMs` {normalize, embed, dense, lexical, fuse, hydrate} (ms, làm tròn xuống nên tổng ≤ `latencyMs`), contract 1.9.0; backend 689 passed, 19 skipped. Day 2 đo được từng bước trên cloud sau khi nhánh này merge vào `release-mvp-v2` và deploy.*
- [x] Kiểm nhanh `/recommendations` với persona P1 `VP0000001` (đã mua hotel Nha Trang, chưa flight): kỳ vọng `strategy = cross_vertical`, `excludedVerticals = ["hotel"]`, `nextVertical ∈ {flight, attraction}`, có `diagnostics`. **Chỉ ghi nhận vào issue, chưa sửa.** *(1h)* — *29/09 (local, `recsys_bench user --id VP0000001`): đạt cả 4 kỳ vọng, `nextVertical = flight`, 0 lỗi contract; top-5 gồm flight, golf, attraction. 7 issue (I-1…I-7) ở `docs/spec/bench/recsys-offline-eval.md` §6. Chưa kiểm trên cloud.*

### Checkpoint Day 1
- [ ] `drafts.txt` đóng băng · app gán nhãn chạy · guide có ví dụ khó · harness load được DB seed · cloud có BM25 · note đã gửi mentor

## 4. Day 2 — T3 29/09

### A1 + A2 — pool, split, pilot κ
- [ ] `sb gold pool` trên drafts đã đóng băng → ghi vào `gold/` (không phải `bench_out/`). Kiểm: 0 câu rỗng, p50 ≈ 26 ứng viên/câu, tổng ≈ 5.000 cặp. *(0,5h)*
- [ ] `sb gold split` → 2 phần + phần overlap để tính κ. *(0,5h)*
- [ ] **Pilot κ:** cả hai gán 100 cặp overlap đầu tiên → `sb gold kappa`. κ = ____. κ ≥ 0,6 → gán tiếp; < 0,6 → dừng, sửa guide, gán lại 100 cặp đó. **Không gán đại trà khi pilot chưa đạt.** *(1,5h)*

### A1, A2 — gán nhãn chính (5–6h)
- [ ] Làm theo block slice để giữ nhất quán; flag cặp khó; chốt chung 15 phút cuối ngày. Nhịp ~20 s/cặp.
- [ ] Cuối ngày: A1 ____ cặp · A2 ____ cặp (mục tiêu ≥ 1.000 mỗi người, ~35 % phần của mình).

### B — sanity check + 3 baseline
- [ ] `eval/sanity.py` (chạy lại được, in bảng): phân bố `lifecycle_stage` khớp 25/45/20/10 ± 5 %; tỉ lệ chuyến ≥ 2 vertical ≈ 65 %; mỗi chuyến 1 destination (trừ 1 % nhiễu cố ý); top-10 % sản phẩm chiếm ____ % purchase (Zipf 1.1 phải thấy rõ) + Gini; số khách vào test split = ____. *(2h)*
- [ ] Chạy 3 baseline bắt buộc: random (3 seed, báo trung bình); most-popular **theo cửa sổ thời gian** (không phải toàn thời gian); most-popular-in-destination (destination = chuyến đang mở hoặc gần nhất). Metric: Recall@10/20, NDCG@10, coverage, availability precision. *(3h)*
- [ ] Kiểm thứ tự bắt buộc: random ≈ 20 / số sản phẩm bookable ≪ most-popular < most-popular-in-destination. Thứ tự sai → lỗi split hoặc data, **sửa trước khi chạy engine**. Ghi tham số split + bảng v0 vào `eval/report.md` mục "Baselines". *(1h)*

| Baseline v0 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability |
|---|---|---|---|---|---|
| random | | | | | |
| most-popular (window) | | | | | |
| most-popular-in-destination | | | | | |

### C — parity, latency, cache
- [ ] Parity test cloud vs local: 20 query cố định trải 13 slice (gồm "VinWonders", "KS biển tại NT", "Vinpeal"). So top-10: overlap ≥ 8/10 và top-1 trùng ≥ 18/20. Lệch → kiểm backfill hoặc version Weaviate (bench local 1.37.3). Kết quả: overlap ____ / top-1 ____. *(2h)*
- [ ] Latency breakdown `/search` trên cloud: 50 query × 3 lần, bỏ lần đầu (warm-up); p50/p95 từng stage. *(2h)*

| Stage | p50 (ms) | p95 (ms) |
|---|---|---|
| normalize | | |
| embed (Cohere) | | |
| Weaviate dense | | |
| BM25 | | |
| RRF + hydrate | | |
| **tổng** | | |

- [ ] Thiết kế cache embedding query: key = query **sau** `domain/search/normalize.py`; value = vector; TTL dài (embedding không đổi theo thời gian); LRU in-process (+ Redis nếu đã có trong stack); danh sách prewarm = 200 câu gold + head query từ `app.search_logs`. PR khung; code chính Day 3. *(2h)*
- [ ] Đo p95 `/recommendations` **trên cloud** với 60 user đã dùng cho brute-force check (local: p50 127 / p95 143 ms). Cloud: p50 ____ / p95 ____. *(1h)*

### Checkpoint Day 2
- [ ] pilot κ đạt · ≥ 2.000 cặp có nhãn · bảng sanity + baseline v0 với thứ tự đúng · cloud parity + latency breakdown · p95 recsys cloud

Dự phòng nếu pilot κ < 0,6 hai lần liên tiếp: hạ thang 0/1/2 xuống nhị phân 0/1 (Recall/MRR không đổi, chỉ nDCG mất phần graded). Phải ghi rõ trong report, không âm thầm đổi.

## 5. Day 3 – Day 5 (tuần 1, phần còn lại)

### Day 3 — T4 30/09
- [ ] A: gán nhãn ngày 2. **Checkpoint cuối ngày: < 50 % → cắt pool còn top-15/câu.**
- [ ] B: engine production chạy trên harness → bảng metric v0 (cùng cột với bảng baseline).
- [ ] C: code query-embedding cache + prewarm; đo lại p95 cache-hit / cache-miss.
- [ ] C: viết `stages.yaml` cho search bench (mới có `arms/B0.yaml`).

### Day 4 — T5 01/10
- [ ] A: `sb gold kappa` (κ = ____) → `merge` → `import` → `check` → **tag `gold_v1`**.
- [ ] B: cross-category rate, availability precision, catalog coverage; p95/p99 offline.
- [ ] C: test tiêu chí 20–23 (decay theo ngày, `userVectorNorm` ≈ 1, `tripFactor`); xác nhận category exclusion & `diagnostics` (từ issue Day 1), sửa nếu lệch §7.

### Day 5 — T6 02/10 — checkpoint tuần
- [ ] A: gate SAN; arm E (Cohere vs `multilingual-e5-base`); S0–S9 lần 1.
- [ ] B: grid-search lần 1: event weight (1/0.5/0.2 vs 5/3/1), half-life, dormant 90 vs 180, công thức điểm.
- [ ] C + cả nhóm: **quyết định embedding model** (giữ Cohere + cache, hay đổi sang local). Ghi quyết định vào `docs/decisions/`.
- [ ] Checkpoint tuần: có số v0 cho cả search lẫn recsys. Mentor đã xác nhận lệch handbook: có / chưa.

## 6. Day 6 – Day 10 (tuần 2)

### Day 6 — T2 05/10
- [ ] Chốt S1/S2/S9/S10 → config + spec §10; `qu.py`; baseline regression cho search bench.
- [ ] Chốt tham số recsys → config, `modelVersion`, sửa spec §4.3–4.7 khớp code.
- [ ] Đóng bug phát hiện từ bench.

### Day 7 — T3 06/10
- [ ] Ablation search: hybrid vs dense-only (từ S-arms).
- [ ] Ablation recsys: trip decay on/off, category exclusion on/off (MMR on/off nếu còn thời gian).
- [ ] Latency p95 `/search` và `/recommendations` trên cloud, ghi vào report.

### Day 8 — T4 07/10
- [ ] Gate F1, P.
- [ ] E2E feedback loop với BE/Web: login P1 → đặt hotel Nha Trang → home đổi sang flight/ticket. Tự động hoá nếu kịp (integration test).
- [ ] Contract `/recommendations` khớp handbook §7 và `src/shared/contracts/openapi.yaml`.
- [ ] Viết chương kết quả recsys (draft).
- [ ] (Nếu nhận) activation loop batch → Insider clone: 1.000 user/request, < 5 MB, `not_append: true`, loại khách suppressed; báo số request, bytes/khách, thời gian toàn population.

### Day 9 — T5 08/10 — freeze
- [ ] Gate FINAL xanh → **code freeze**, tag release.
- [ ] README: người chưa từng chạy project chạy từ đầu theo README. OpenAPI hoàn tất.

### Day 10 — T6 09/10
- [ ] Sinh lại **toàn bộ** số từ bản tag → `eval/report.md`, kèm caveat: "lịch sử khách hàng là dữ liệu sinh — đo pipeline chạy đúng, không đo hiệu năng trên khách thật".
- [ ] 1 trang/workstream (search, recsys, evaluation, tích hợp).
- [ ] Backup video cùng nhóm Web.

## 7. Cắt gì nếu trễ (theo drop order handbook §2 + phần riêng của nhóm)

1. So sánh 10 kiến trúc recommender → chỉ giữ engine production + 3 baseline (+ item-kNN/EASE tham chiếu nếu rảnh).
2. Arm E rút còn 2 (Cohere, e5-base); arm S chỉ giữ dense / hybrid / hybrid + normalize.
3. Index tuning (HNSW `ef`, `efConstruction`) — bỏ.
4. Ablation rút còn 2 biến.
5. Activation loop → đề xuất "6 tuần tiếp theo".
6. Pool gold rút còn top-15/câu (handbook chỉ cần ~80 cặp).

**Không cắt:** `gold_v1`, harness với 3 baseline, số latency thật, feedback loop E2E, sinh lại số từ tag.

## 8. Log

Mỗi ngày 3 dòng: xong gì (kèm số) · vướng gì · quyết định gì.

- Day 1 (B, C — 29/09): **xong** harness `src/evaluation/recsys_bench` trên DB seed (orphan 63, thiếu gid 94; LLBO 1.016 khách; random Recall@20 0,0066; engine v0 Recall@10 0,619); `diagnostics.stageMs` cho `/search` (contract 1.9.0, nhánh riêng chờ PR vào `release-mvp-v2`); P1 đạt 4/4 kỳ vọng ở local; note mentor soạn xong, chưa gửi. · **vướng** backfill BM25 Cloud cần quyền VM (chưa chạy, có runbook); `.env` trỏ DB tunnel làm test backend chậm hoặc treo khi service local đang bật; 3 test `test_golden.py` đã fail sẵn trên `bench/embed-search`. · **quyết định** port thay merge nhánh khoa; nhánh C tách từ `release-mvp-v2`; lọc gid chỉ áp purchase; số đặt ở `docs/spec/bench/recsys-offline-eval.md`.
- Day 2:
- Day 3:
- Day 4:
- Day 5:
- Day 6:
- Day 7:
- Day 8:
- Day 9:
- Day 10:
