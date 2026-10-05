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
- [x] Rà 42 câu `--fill` trong `gold/drafts.txt` bằng app Streamlit hiện có (KEEP / REJECT / NEEDS_EDIT). Mỗi câu kiểm 3 điều: đúng slice; tiếng Việt tự nhiên như khách gõ; có ≥ 1 sản phẩm trong catalog có thể liên quan (trừ slice `out_of_catalog`). REJECT → thay bằng câu trong 472 draft chưa dùng. *(2h)* — *05/10 rà: đóng, không làm theo dạng này — người dùng chốt 28/09 drafts = mọi câu người soát chọn, mỗi slice ≥ 3, không lấp (`history/2026-09-28-draft-chon-tu-do-va-app-gan-nhan.md`); `gold/drafts.txt` đóng băng 29/09 ở 132 câu / 13 slice (`history/2026-09-29-split-gold-a-b-theo-132-cau.md`).*
- [x] Sửa `c0241`, `c0503`, `c0531` theo ghi chú đã có. *(0,5h)* — *05/10 rà: đóng, không làm theo dạng này — người dùng chốt 28/09 drafts = mọi câu người soát chọn, mỗi slice ≥ 3, không lấp (`history/2026-09-28-draft-chon-tu-do-va-app-gan-nhan.md`); `gold/drafts.txt` đóng băng 29/09 ở 132 câu / 13 slice (`history/2026-09-29-split-gold-a-b-theo-132-cau.md`).*
- [x] Thêm 2 câu dự phòng cho 5 slice đang đúng 10 câu: `amenity_multi`, `amenity_negation`, `amenity_offtaxonomy`, `cross_vertical`, `out_of_catalog` — chọn câu khác mẫu với 10 câu đang có. *(1h)* — *05/10 rà: đóng, không làm theo dạng này — người dùng chốt 28/09 drafts = mọi câu người soát chọn, mỗi slice ≥ 3, không lấp (`history/2026-09-28-draft-chon-tu-do-va-app-gan-nhan.md`); `gold/drafts.txt` đóng băng 29/09 ở 132 câu / 13 slice (`history/2026-09-29-split-gold-a-b-theo-132-cau.md`).*
- [x] `sb gold check` trên drafts → commit → ghi hash vào `docs/spec/bench/search-eval-checklist.md` → **đóng băng `drafts.txt`** (210 câu, 13 slice đủ quota). *(0,5h)* — *05/10 rà: đóng, không làm theo dạng này — người dùng chốt 28/09 drafts = mọi câu người soát chọn, mỗi slice ≥ 3, không lấp (`history/2026-09-28-draft-chon-tu-do-va-app-gan-nhan.md`); `gold/drafts.txt` đóng băng 29/09 ở 132 câu / 13 slice (`history/2026-09-29-split-gold-a-b-theo-132-cau.md`).*

### A2 — app gán nhãn
- [x] Dựng app gán nhãn 0/1/2 theo `docs/spec/bench/prompts/may2-label-app.md`: đọc file pool; hiển thị query + slice + product card (name, taxonomy, destination, price, amenities, description rút gọn); phím tắt `0/1/2`, skip, flag; lưu tăng dần để resume; xuất đúng `gold_schema.py`. *(4–5h)* — *28/09: xong (`history/2026-09-28-draft-chon-tu-do-va-app-gan-nhan.md`), A/B gán hết bằng app ngày 30/09.*
- [x] Test: gán thử trên fixture `gold_small/` → `sb gold import` nhận file xuất không lỗi. — *30/09: file xuất của app import thật vào `gold.jsonl` không lỗi (`history/2026-09-30-gold-merge-import-retire-tag-v1.md`).*
- [x] Chọn ~20 cặp khó từ pool thử `bench_out/` cho phiên calibration: negation, off-taxonomy, cross_vertical, hạng phòng anh em, out_of_catalog. *(0,5h)* — *05/10 rà: không làm phiên calibration trước khi gán; thay bằng 7 quy ước chốt 30/09 sau khi gán, dựa trên 640 cặp chung (`history/2026-09-30-gold-guide-quy-uoc-chot.md`).*

### A1 + A2 — calibration (cuối ngày, 1,5h)
- [x] Đọc `docs/spec/bench/gold-guide.md`; gán độc lập 20 cặp khó; so đáp án; bất đồng ≤ 3/20. — *05/10 rà: không làm phiên calibration trước khi gán; thay bằng 7 quy ước chốt 30/09 sau khi gán, dựa trên 640 cặp chung (`history/2026-09-30-gold-guide-quy-uoc-chot.md`).*
- [x] Ghi quy ước vào mục "ví dụ khó" của guide. Phải trả lời được: — *05/10 rà: không làm phiên calibration trước khi gán; thay bằng 7 quy ước chốt 30/09 sau khi gán, dựa trên 640 cặp chung (`history/2026-09-30-gold-guide-quy-uoc-chot.md`).*
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
- [x] Backfill BM25 trên Weaviate Cloud: `python -m src.backend.jobs.embed_products --backfill-lexical`. Kiểm số object có `nameAscii` / `searchTextAscii` = **3.183**. Bật `SEARCH_HYBRID=true` trên cloud. *(2h)* — *29/09: chưa chạy. Máy làm B/C không có quyền VM hay khoá Weaviate Cloud, và job chỉ được chạy trên VM (§0.1). Runbook từng bước: `history/2026-09-29-cloud-backfill-lexical.md`.* — *30/09: đã kiểm chỉ đọc. Cloud có 3.183 object, 0 có dữ liệu BM25, stopwords `en`. DB trên VM chỉ có 3.008 unit: chạy job với DB đó sẽ xoá 285 vector và embed lại 158, nên **không chạy trên VM**. Postgres local seed 24/09 khớp cloud tuyệt đối (embed 0, xoá 0, backfill 3.183). Phần ghi chưa chạy, chờ người dùng. Runbook đã sửa: `history/2026-09-30-backfill-bm25-cloud-kiem-nguon-db.md`.* — *30/09: **đã chạy.** Nguồn DB là Postgres local seed 24/09 (dry-run: embed 0, xoá 0). Stopwords `en` → `none`; `backfilledLexical 3183`, dry-run lại `missingLexical 0`, **3.183/3.183 object có `nameAscii`/`searchTextAscii`**. BM25 trên cloud trả kết quả đúng cho "VinWonders", "Hội An", "Vinpearl Nha Trang". Còn mở: xác nhận `/search` trên backend VM ra `HYBRID_CANDIDATE_SCORE` (máy này không vào được backend; khoá Cohere trial đã hết 1.000 lượt/tháng). Chi tiết: `history/2026-09-30-backfill-bm25-cloud-da-chay.md`.*
- [x] Thêm timing per-stage cho `/search` (normalize → embed → dense → BM25 → RRF → hydrate) vào `diagnostics` hoặc log — đầu vào cho Day 2. *(2h)* — *29/09: code xong trên nhánh `feat/search-stage-timing` (tách từ `release-mvp-v2`, chưa commit/PR): `diagnostics.stageMs` {normalize, embed, dense, lexical, fuse, hydrate} (ms, làm tròn xuống nên tổng ≤ `latencyMs`), contract 1.9.0; backend 689 passed, 19 skipped. Day 2 đo được từng bước trên cloud sau khi nhánh này merge vào `release-mvp-v2` và deploy.*
- [x] Kiểm nhanh `/recommendations` với persona P1 `VP0000001` (đã mua hotel Nha Trang, chưa flight): kỳ vọng `strategy = cross_vertical`, `excludedVerticals = ["hotel"]`, `nextVertical ∈ {flight, attraction}`, có `diagnostics`. **Chỉ ghi nhận vào issue, chưa sửa.** *(1h)* — *29/09 (local, `recsys_bench user --id VP0000001`): đạt cả 4 kỳ vọng, `nextVertical = flight`, 0 lỗi contract; top-5 gồm flight, golf, attraction. 7 issue (I-1…I-7) ở `docs/spec/bench/recsys-offline-eval.md` §6. Chưa kiểm trên cloud.*

### Checkpoint Day 1
- [ ] `drafts.txt` đóng băng · app gán nhãn chạy · guide có ví dụ khó · harness load được DB seed · cloud có BM25 · note đã gửi mentor — *05/10 rà: đạt mọi mục (drafts 29/09, app 28/09, guide 30/09, harness 29/09, BM25 cloud 30/09) **trừ mentor**: note đã soạn 29/09 (`docs/spec/bench/note-mentor-lech-handbook.md`), chưa có ghi nhận mentor trả lời.*

## 4. Day 2 — T3 29/09

### A1 + A2 — pool, split, pilot κ
- [x] `sb gold pool` trên drafts đã đóng băng → ghi vào `gold/` (không phải `bench_out/`). Kiểm: 0 câu rỗng, p50 ≈ 26 ứng viên/câu, tổng ≈ 5.000 cặp. *(0,5h)* — *29/09: 132 câu / 3.359 dòng, 6–30 ứng viên/câu (p50 26), 0 câu rỗng (`docs/spec/bench/search-eval-checklist.md` Ngày 2 B).*
- [x] `sb gold split` → 2 phần + phần overlap để tính κ. *(0,5h)* — *29/09: A 78 câu / 1.999 cặp, B 79 câu / 2.000 cặp, 25 câu chung / 640 cặp, mọi slice có câu chung.*
- [x] **Pilot κ:** cả hai gán 100 cặp overlap đầu tiên → `sb gold kappa`. κ = ____. κ ≥ 0,6 → gán tiếp; < 0,6 → dừng, sửa guide, gán lại 100 cặp đó. **Không gán đại trà khi pilot chưa đạt.** *(1,5h)* — *05/10 rà: không chạy pilot riêng; κ chính thức trên 640 cặp chung sau khi gán hết: **0,692** (0,661 sau rà slice), đạt ngưỡng 0,6 (`history/2026-09-30-gold-merge-import-retire-tag-v1.md`).*

### A1, A2 — gán nhãn chính (5–6h)
- [x] Làm theo block slice để giữ nhất quán; flag cặp khó; chốt chung 15 phút cuối ngày. Nhịp ~20 s/cặp. — *30/09: gán xong (`history/2026-09-30-gan-nhan-gold-xong.md`).*
- [x] Cuối ngày: A1 1.999 cặp · A2 2.000 cặp *(gán hết ngày 30/09, không theo mốc ngày 2)* (mục tiêu ≥ 1.000 mỗi người, ~35 % phần của mình).

### B — sanity check + 3 baseline
- [x] `eval/sanity.py` (chạy lại được, in bảng): phân bố `lifecycle_stage` khớp 25/45/20/10 ± 5 %; tỉ lệ chuyến ≥ 2 vertical ≈ 65 %; mỗi chuyến 1 destination (trừ 1 % nhiễu cố ý); top-10 % sản phẩm chiếm ____ % purchase (Zipf 1.1 phải thấy rõ) + Gini; số khách vào test split = ____. *(2h)* — *01/10: `recsys_bench sanity` PASS 5/5 kiểm tra cứng (lifecycle 25,1/45,0/20,0/10,0 %; tính lại từ event lệch 0/2.000; chuyến ≥ 2 vertical 63,6 %; 0 chuyến nhiều điểm đến; orphan 2,0 % / thiếu gid 3,0 %); top-10 % sản phẩm chiếm **41,1 %** purchase, Gini sản phẩm 0,423 / unit 0,525, Zipf slope −0,63 (seed 0,8 — phẳng hơn vì cắt theo điểm đến); khách test LLBO **1.007** · temporal **102**. Spec recsys §2.1.*
- [x] Chạy 3 baseline bắt buộc: random (3 seed, báo trung bình); most-popular **theo cửa sổ thời gian** (không phải toàn thời gian); most-popular-in-destination (destination = chuyến đang mở hoặc gần nhất). Metric: Recall@10/20, NDCG@10, coverage, availability precision. *(3h)* — *30/09: run `2026-09-30-llbo-v1` (seed 09-21), số ở bảng dưới; spec `docs/spec/bench/recsys-offline-eval.md` §4.4.*
- [x] Kiểm thứ tự bắt buộc: random ≈ 20 / số sản phẩm bookable ≪ most-popular < most-popular-in-destination. Thứ tự sai → lỗi split hoặc data, **sửa trước khi chạy engine**. Ghi tham số split + bảng v0 vào `eval/report.md` mục "Baselines". *(1h)* — *30/09: thứ tự đúng — random 0,008 ≪ most-popular 0,293 < most-popular-in-destination 0,635 (Recall@20, LLBO).*

| Baseline v0 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability |
|---|---|---|---|---|---|
| random (3 seed) | 0.0040 | 0.0083 | 0.0017 | 0.999 | 1.000 |
| most-popular (window) | 0.1867 | 0.2929 | 0.0891 | 0.068 | 1.000 |
| most-popular-in-destination | 0.5780 | 0.6346 | 0.3890 | 0.416 | 1.000 |

*LLBO, run `2026-09-30-llbo-v1`, seed 09-21, 1.007 khách, k = 20 — chép từ `docs/spec/bench/recsys-offline-eval.md` §4.4 (điền 05/10).*

### C — parity, latency, cache
- [x] Parity test cloud vs local: 20 query cố định trải 13 slice (gồm "VinWonders", "KS biển tại NT", "Vinpeal"). So top-10: overlap ≥ 8/10 và top-1 trùng ≥ 18/20. Lệch → kiểm backfill hoặc version Weaviate (bench local 1.37.3). Kết quả (01/10, `sb parity --mode weaviate`, cùng `SearchProducts` trên catalog VM, `ProductVM` nạp từ vector Cloud): overlap **min 8/10 trên 16 câu đủ dài (13 câu 10/10)**, 4 câu ngắn trùng hết / top-1 **20/20** → PASS. Chi tiết `docs/spec/bench/search-eval-results.md` §1. *(2h)*
- [x] Latency breakdown `/search` trên cloud: 50 query × 3 lần, bỏ lần đầu (warm-up); p50/p95 từng stage. *(2h)* — *01/10 11:19: `sb latency http` trên VM (`release-mvp-v2 @ fe7e04d`, contract 1.12.0, cache + prewarm bật), 25 prewarmed + 25 cold, số server; run `20261001-1059-8842c3a`, report `src/evaluation/reports/eval-2026-10-01-search-cloud-latency.md`, phân tích `docs/spec/bench/search-eval-results.md` §2–3.*

| Stage | p50 (ms) | p95 (ms) |
|---|---|---|
| normalize | 0 | 0 |
| embed (Cohere) | 0 (cache hit; miss 281 / 437) | 0 |
| Weaviate dense | 1.809 | 1.830 |
| BM25 | 2.131 | 2.181 |
| RRF + hydrate | 1 | 1 |
| **tổng** | **3.940** | **4.007** |

Vì sao 4 s: Weaviate Cloud ở `eu-central-1` (Frankfurt), VM ở `asia-southeast1`; mỗi lượt gọi gửi mask 3.146 id (`contains_any`) — dense 1.827 → 354 ms khi mask còn 64 id; dense và BM25 nối tiếp. Local cùng adapter: 20 / 11 ms. Không tune tuần này (plan Day 4–5 §0); đầu vào M3 và tuần performance.

- [x] Thiết kế cache embedding query: key = query **sau** `domain/search/normalize.py`; value = vector; TTL dài (embedding không đổi theo thời gian); LRU in-process (+ Redis nếu đã có trong stack); danh sách prewarm = 200 câu gold + head query từ `app.search_logs`. PR khung; code chính Day 3. *(2h)* — *PR2 `feat/search-embed-cache` (1.12.0) merge + deploy 30/09–01/10: LRU in-process 10k, single-flight, prewarm 131 câu gold_v1 active + head query (`app.search_logs` hiện 0 dòng). Trên VM 01/10: prewarmed hit 25/25 ngay lượt 1, cache tiết kiệm 0,3–0,45 s/câu, top-10 miss = hit 50/50.*
- [x] Đo p95 `/recommendations` **trên cloud** với 60 user đã dùng cho brute-force check (local: p50 127 / p95 143 ms). Cloud (01/10, **guest path** — không cookie → `popular`, không phải 60 khách vì `/internal/recommendations` cần IAP + `X-Service-Token`; `recsys_bench http-latency`, 3 lượt × 5 GET, bỏ lượt 1): server `latencyMs` p50 **9** / p95 **10** ms · client qua BFF p50 141 / p95 391 ms. Run `bench_out/recsys/runs/20261001-cloud-guest/`. *(1h)*

### Checkpoint Day 2
- [x] pilot κ đạt · ≥ 2.000 cặp có nhãn · bảng sanity + baseline v0 với thứ tự đúng · cloud parity + latency breakdown · p95 recsys cloud — *đủ 01/10: κ 0,692, gold_v2, sanity 6/6, baseline 6 arm, parity 20/20, breakdown 4,0 s (C), recsys cloud guest 10 ms.*

Dự phòng nếu pilot κ < 0,6 hai lần liên tiếp: hạ thang 0/1/2 xuống nhị phân 0/1 (Recall/MRR không đổi, chỉ nDCG mất phần graded). Phải ghi rõ trong report, không âm thầm đổi.

## 5. Day 3 – Day 5 (tuần 1, phần còn lại)

### Day 3 — T4 30/09
- [x] A: gán nhãn ngày 2. **Checkpoint cuối ngày: < 50 % → cắt pool còn top-15/câu.** — *30/09: gán xong 100 % hai phía (A 1.999, B 2.000 cặp); không cần cắt pool.*
- [x] B: engine production chạy trên harness → bảng metric v0 (cùng cột với bảng baseline). — *29–30/09: run `2026-09-29-llbo-v0`, `2026-09-30-llbo-v1` (engine Recall@20 0,851 / NDCG@10 0,524 LLBO seed 09-21); spec recsys §4.1, §4.4.*
- [x] C: code query-embedding cache + prewarm; đo lại p95 cache-hit / cache-miss. — *30/09–01/10: cache + prewarm deploy (contract 1.12.0, `history/2026-09-30-search-query-embedding-cache-prewarm.md`); đo trên VM 01/10: embed miss p50 281 / p95 437 ms, hit 0 ms (`src/evaluation/reports/eval-2026-10-01-search-cloud-latency.md`).*
- [ ] C: viết `stages.yaml` cho search bench (mới có `arms/B0.yaml`). — *05/10 rà: **chưa làm**. Day 4–5 chạy arm trực tiếp bằng `sb run --arm`, không qua cổng; plan Day 4–5 S8(b) chuyển sang Day 5 và vẫn chưa làm.*

### Day 4 — T5 01/10
- [x] A: `sb gold kappa` (κ = ____) → `merge` → `import` → `check` → **tag `gold_v1`**. — *30/09: κ = 0,692 (0,661 sau rà slice) → merge → import → retire c0463 → check xanh 131 câu / 13 slice, commit `6fb5053` (`history/2026-09-30-gold-merge-import-retire-tag-v1.md`). ⚠ 05/10: **tag `gold_v1` không có trên git** (local lẫn remote chỉ có `gold_v2`, `gold_v3`) — cần gắn lại vào `6fb5053` sau khi kiểm sha `gold.jsonl` khớp changelog. Sau đó: `gold_v2` (D4a, 01/10), `gold_v3` (D4b + D5a, 01/10, 5.021 nhãn).*
- [x] B: cross-category rate, availability precision, catalog coverage; p95/p99 offline. *(01/10, Day 4 R — engine v5, bộ split `asof20260924` trên DB local seed 09-23: LLBO 1.016 khách engine Recall@20 **0,848** / NDCG@10 **0,517** vs mpd 0,602 / 0,380 (Δ +24,6 điểm, CI95 [+21,8; +27,6]); availability 1,000; coverage 0,565 (prod 0,207); Gini 0,834; cross-cat chuyến mở có mua 1,000 (mpd 0,400); p95/p99 offline 63 / 93 ms; temporal 98 khách engine 0,194 / 0,151 vs mpd 0,102 / 0,038. Report `src/evaluation/reports/eval-2026-10-01-recsys-bench-v5-asof20260924.md`, spec §4.15. Không so chữ số với v5 bộ 0922.)*
- [ ] C: test tiêu chí 20–23 (decay theo ngày, `userVectorNorm` ≈ 1, `tripFactor`); xác nhận category exclusion & `diagnostics` (từ issue Day 1), sửa nếu lệch §7. — *05/10 rà: chưa thấy bằng chứng trong history / spec recsys; phần exclusion + `diagnostics` đã kiểm lại sau M6 (spec recsys §5.1, R7).*

### Day 5 — T6 02/10 — checkpoint tuần
- [ ] A: gate SAN; arm E (Cohere vs `multilingual-e5-base`); S0–S9 lần 1. — *05/10 rà: **SAN xong** (`sb gold check` xanh, sanity 4/4 mọi model); **arm E xong** (B0 vs e5-base TIE trên gold_v2; 01–02/10 mở rộng 8 model + e5-large, `eval-2026-10-01-search-day4-local.md`, `eval-2026-10-02-search-local-fair.md`); **S0–S9 chưa** — mới có 3 arm APP dense / hybrid / hybrid + normalize (`eval-2026-10-01-search-v1-3arm.md`), chưa chạy S1–S9 của `arms.md`.*
- [x] B: grid-search lần 1: event weight (1/0.5/0.2 vs 5/3/1), half-life, dormant 90 vs 180, công thức điểm. — *01/10: `run --override` (hằng engine đổi trong tiến trình, vào `configHash`), 9 run một-yếu-tố trên temporal đóng băng; Chỉ **cửa sổ trip mở** đổi kết quả: `ACTIVE_TRIP_MAX_AGE_DAYS` 60 → 30 / 14 nâng Recall@20 0,196 → 0,216 / **0,225** và NDCG@10 0,144 → 0,154 (+0,010), prod NDCG@5 +0,006 — cùng hướng với finding M6 (trip cũ còn trong 60 ngày bị coi là đang mở nên loại nhầm). `W_SHORT=0,7 / W_POP=0,15` +0,006 NDCG@10 và prod NDCG@5 +0,026; `W_SHORT=0,5 / W_POP=0,35` tệ hẳn (NDCG@10 −0,046). MMR λ 0,85 / 1,0, `H_SHORT_DAYS` 60, `DORMANT_AFTER_DAYS` 90 và `W_TYPE` 5/3/1 không đổi hoặc giảm nhẹ. Khác biệt trên 102 khách là 1–3 khách nên chỉ là hướng dò, không phải quyết định; muốn áp dụng phải qua M6 (đề xuất PRD) và chạy lại LLBO. Bảng: spec recsys §4.13.*
- [ ] C + cả nhóm: **quyết định embedding model** (giữ Cohere + cache, hay đổi sang local). Ghi quyết định vào `docs/decisions/`. — *05/10: **nhóm chốt e5-small / 384** (`intfloat/multilingual-e5-small`), bỏ Cohere — người dùng báo; bằng chứng `eval-2026-10-02-search-local-fair.md` (e5-small hoà e5-base, BGE, GTE; rẻ và nhanh nhất). Còn phải: đề xuất `docs/prd/update/` cho FR-SRC-02 (đang ghi Cohere v3 / 1024) và chờ chốt trước khi sửa backend; chạy lại bench RecSys bằng vector e5 (report tuần 3 D8).*
- [ ] Checkpoint tuần: có số v0 cho cả search lẫn recsys. Mentor đã xác nhận lệch handbook: có / chưa. — *05/10 rà: số v0 **có** cả hai (search: B0 + 3 arm APP trên gold; recsys: 4 arm + bảng thuật toán, `report_week_3.md`); mentor: **chưa** có ghi nhận trả lời.*

## 6. Day 6 – Day 10 (tuần 2)

### Day 6 — T2 05/10
- [ ] Chốt S1/S2/S9/S10 → config + spec §10; `qu.py`; baseline regression cho search bench. — *05/10: mở. Cần trước: split dev/test (người dùng chốt 05/10: ~65/66 phân tầng slice), `baseline_v1` + `sb regress` bản gọn (người dùng chốt 05/10).* *05/10 chiều (Search Day 5): split dev/test `gold/splits/devtest@gold_v3.json` (66 / 65); `baseline_v1` = `APP.e5s.hybrid_norm` + `sb regress` PASS; cutoff e5-small sweep trên dev → đề xuất **0,85** (test: nDCG@10 0,647, zero-result trong catalog 1,6 %; chưa chốt, chưa sửa config); S1/S2/S9/S10 và `qu.py` không làm (người dùng chỉ giữ phần cần cho đổi model). Report `src/evaluation/reports/eval-2026-10-05-search-day5-e5s-app.md`.*
- [ ] Chốt tham số recsys → config, `modelVersion`, sửa spec §4.3–4.7 khớp code. *(Thứ tự theo ADR 2 — `history/2026-10-01-adr2-huong-cai-thien-recsys-tuan-sau.md`: harness `targetInOwnHistory` + split biến thể trước; grid trên temporal `W_SHORT/W_POP` rồi λ MMR; bỏ `H_*`.)*
- [ ] Đóng bug phát hiện từ bench.
- [x] RecSys chạy lại bằng vector e5-small / e5-base đã có (`bench_out/search/data/vec_T3+R_e5-*.npy`, 3.183 unit, text `catalog-text-v2`; không embed lại) → so `baseline_v1` (report tuần 3 D8). Harness cần chế độ đọc `.npy` vì settings backend khoá Cohere v3 / 1024. *(thêm 05/10; vector e5-small + e5-base đã đóng gói gửi bên RecSys 05/10, kèm sha256)* Chi tiết theo ngày: `docs/plan/2026-10-05-bench-recsys-e5-small.md`. — *05/10 xong (không so `baseline_v1` — phạm vi plan bỏ Cohere): harness thêm `--vectors npy:`; engine e5-small LLBO hit@20 **0,860** / NDCG@10 **0,506** vs mpd 0,602 / 0,380 (Δ +25,8 [+22,9; +28,6]); temporal 0,184 vs 0,102 (Δ +8,2 [+2,0; +15,3]); e5-small − e5-base engine LLBO +0,2 [−0,9; +1,3] hit@20, +0,4 [−0,2; +0,9] NDCG@10 → hoà, giữ e5-small; gate G1/G2 + kiểm chéo CF 100 %. Report `src/evaluation/reports/eval-2026-10-05-recsys-e5-small-vs-e5-base.md`.*

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
- Day 2 (C — 30/09): **xong** backfill BM25 Weaviate Cloud 3.183/3.183 object, stopwords `none`, không embed lại, không xoá. · **vướng** DB trên VM lệch cloud (3.008 vs 3.183 unit; chạy job với DB VM sẽ xoá 285 vector); khoá Cohere trial hết hạn mức tháng (429); tài khoản SSH chỉ forward được tới DB nên chưa kiểm được `/search` trên backend VM. · **quyết định** dùng Postgres seed 24/09 làm nguồn backfill vì khớp cloud tuyệt đối.
- Day 3 (A, Claude — 30/09): **xong** nhãn gold đủ 100 % hai phía (A 1.999, B 2.000 cặp; nhãn máy đã duyệt hết), κ linear **0,692** (≥ 0,6), 12 cặp lệch 2 bậc; search bench có runner (`sb run --arm`, `sb compare`), gold append-only (`retire`, `verify-append`, `holes`, `holes import`, `rescore`, `changelog.yaml`), e5-base local (arm E2.e5, collection 3.183 object, token max 301 < 512), cổng APP đi đúng `SearchProducts` production (6 arm, `ProductBench` 3.183 object, parity `APP.dense_nocut` = B0 10/10 câu fixture); test 323 passed; nhánh `bench/recsys-harness` merge vào (`dc9a22c`), thêm 2 baseline most-popular; recsys 4 arm × 2 split trên seed 09-21: LLBO (1.007 khách) random 0,0083 ≪ most_popular 0,293 < mpd 0,635 (Recall@20); engine mode eval (bỏ cap 2/taxonomy, quyết định 30/09) Recall@20 **0,851** / NDCG@10 **0,524** thắng rõ mpd 0,635 / 0,389 (M5 đạt); list production (cap) 0,591 / 0,460 (I-5). · **vướng** 6 câu gold không có nhãn 2 (5 câu sửa nhãn / chốt quy ước, c0463 retire); sentence-transformers không dùng được (scipy DLL bị Application Control chặn) → e5 chạy bằng transformers + torch; Postgres local là seed 09-21 (khác snapshot 09-23 của search bench). · **quyết định** retire c0463 trước tag; số trước, cổng Part 12 rút gọn; đo hybrid bằng SearchProducts thật; không seed lại DB chung. Kế hoạch chi tiết: `docs/plan/2026-09-30-bench-search-recsys-3-ngay.md`.
- Day 3 (C, Claude — 30/09 chiều): **xong** PR1 `feat/search-stage-timing-v2` (cherry-pick `stageMs` lên `release-mvp-v2`, contract **1.11.0** vì v2 đã dùng 1.10.0; validator PASS, backend 902 passed / 21 skipped; commit local `391a00f`, chưa push); công cụ đo Day 2 C: `sb latency http` (50 câu × 3 lượt, p50/p95 từng stage, hit/miss theo `embedCache`), `sb parity --mode http|weaviate` (20 câu, cổng 18/20 & 8/10; mode weaviate = cùng `SearchProducts` trên catalog VM, `ProductVM` nạp từ vector Cloud), `recsys_bench http-latency` (guest path); search bench 336 passed, recsys 35 passed. · **vướng** tunnel SSH tới DB VM chưa mở (C6 backfill BM25 + parity weaviate chờ); Cloud chưa có `stageMs` tới khi PR1 merge + deploy. · **quyết định** PR2 (cache + prewarm) sẽ là 1.12.0; `/recommendations` Cloud chỉ đo guest path; số server (`latencyMs`/`stageMs`) là số đầu bảng, wall client báo riêng.
- Day 4 (B, C — 01/10): **xong** C6 đồng bộ index Cloud với catalog VM (embed 168, xoá 0; BM25 đã đủ từ trước), parity M4 **PASS** 20/20 (`sb parity --mode weaviate`, overlap min 8/10 trên 16 câu đủ dài; lần đầu FAIL giả do HNSW `ProductVM` đang dựng → guard READY), p95 `/recommendations` Cloud guest path 9/10 ms; PR1 `stageMs` (1.11.0) và PR2 cache + prewarm (1.12.0) đã push, CI PR2 xanh sau khi sửa race test; Track B Phase 0 (split đóng băng + hash, `configHash`, NDCG@5, `ids`/`rankStrict`, v3 = v2) và Phase 1 (ceiling LLBO 0,990 / temporal 0,784; `engine_nommr` 0,863 vs MMR 0,851; 21/1.007 ca engine trượt-mpd trúng: đã mua 9, MMR đẩy ra 6, score chưa đủ 6; phân khúc, strict/lenient; 10 findings §4.11 spec recsys). · **vướng** `/api/v1/search` trên VM 500 sau ~64 s (Cohere trên VM) → chưa đo breakdown/hit-miss; PR1 chưa merge. · **quyết định** ghi Cloud từ DB VM (người dùng xác nhận); cổng overlap parity theo độ dài list; category exclusion cho chuyến kế là đề xuất M6 phải qua `docs/prd/update/`. Thêm cùng ngày: B Phase 2 `sanity` PASS 5/5 (top-10 % sản phẩm 41,1 % purchase) và Phase 3 parity offline = HTTP **60/60** (backend local, p95 321 ms) — Track B theo plan Day 3 đủ.
- Day 5 (B — 02/10): **xong** người dùng chốt đề xuất M6 → PRD FR-REC-02 sửa, spec §4.4–4.5, engine: trip mở theo `usingDate` (`trip_is_open`, `ENGINE_RULES_VERSION`) + N = 14 cho trip chỉ view; harness mô phỏng cùng luật; temporal R@20 0,196 → **0,216**, NDCG@10 0,144 → 0,154, ceiling **0,892** (91/102; 11 còn lại: 6 `taxonomy_excluded`, 9 `destination_mismatch`, 1 `already_bought` — đều là chuyến chưa đi tại T); LLBO không đổi (0,851 / 0,524); backend đầy đủ xanh. · **vướng** 10/21 target temporal bị chặn là chuyến chưa đi tại T — giới hạn của split temporal (as_of = T), không phải engine; `/search` trên VM vẫn 500, PR1 chưa merge. · **quyết định** N chọn trên temporal đóng băng theo B10, LLBO không giảm; đề xuất lưu `update-archive/`; cần split "next trip" cho câu hỏi gợi ý chuyến kế.
- Day 4 (C, tiếp — 01/10 trưa): **xong** CI/CD `release-mvp-v2` xanh (Frontend CI #83 sau PR #67 type-check của Khoa, Backend CI/CD #114 sau PR #68 gold) → VM chạy 1.12.0 (`stageMs`, `embedCache`); C5 + C3 đo trên VM: `/search` p50 3,94 / p95 **4,0 s** = dense 1,8 + BM25 2,1 s nối tiếp, embed hit 0 / miss 437 ms p95, prewarm đã chạy (25/25 hit lượt 1), top-10 không đổi 50/50. · **vướng** Weaviate Cloud ở `eu-central-1` còn VM ở `asia-southeast1`; mask 3.146 id gửi mỗi lượt gọi (dense 1.827 → 354 ms khi mask 64 id); BM25 sàn 1,4 s bất kể mask. · **quyết định** không tune tuần này; ba đòn bẩy ghi vào `search-eval-results.md` §2 làm đầu vào M3 / tuần performance: kho vector cùng vùng, bỏ mask id khi mask ≈ toàn bộ, dense ∥ BM25.
- Day 4 (R = B + phần recsys của C, Claude — 01/10 chiều): **xong** merge M6 vào nhánh con `bench/day4-rec` (`69e01a5`; `configHash` v5 `b0aee886` / `81d16abd` khớp, harness 70 + backend recommendation 25 test xanh); DB local là seed 09-23 ≠ split 0922 → đóng băng bộ mới `asof20260924` (LLBO 1.016 / temporal 98 khách, sanity PASS 6/6); đủ cột handbook §12: Gini độ phủ, cross-cat theo chuyến mở (2 biến thể: mọi chuyến mở / chuyến đã mua), `compare` paired bootstrap CI95, `report` sinh markdown + `gitDescribe`/`history` trong `summary.json`; 6 arm × 2 split: engine Recall@20 0,848 / NDCG@10 0,517 (LLBO), thắng mpd +24,6 điểm hit@20 [+21,8; +27,6]; engine_prod ≈ mpd ở hit@20 (CI chứa 0, cả hai split — I-5); MMR −2,7 điểm; ceiling 0,988 / 0,918 ≥ mpd; P1 4/4, P3 4/4 sau M6; spec §4.15 / §5.1 / §7, report `eval-2026-10-01-recsys-bench-v5-asof20260924.md`. · **vướng** không tái lập chữ số report v5 trên máy này (khác DB; tunnel VM đóng); R3–R5 (registry / funnel / scorer Tier 1) chưa làm; `cooc_trip` / `star_blend` không có đặc tả gốc. · **quyết định** (người dùng, 01/10) phạm vi Day 4 R = report đủ metric cho engine v5 + baseline; đóng băng split mới thay vì seed lại; báo cả hai biến thể cross-cat; gate R1 thay bằng `configHash` + thứ tự baseline + ceiling.
- Day 4 → 5 (R, Claude — 01/10 chiều, R3–R6): **xong** commit Day 4 R `993669d`; spec thuật toán của người dùng đổi tên `docs/spec/bench/recsys-algos-v1.md` + errata E1–E12 đối chiếu code sau M6 (trip mở theo `usingDate` N = 14, arm `engine` eval vẫn MMR, funnel = mask engine, pool engine bị cắt 4/1.016 LLBO nhưng 76/98 temporal); registry `src/evaluation/recsys_bench/models/` (14 module: data/seeds/funnel/content/cooc/star/ease/rp3beta/itemknn/ials/bpr/registry/regress), `algos_v1.yaml`, CLI `run --algos … --mode funnel|raw` (knob `pool` × `rerank`, `algosHash`, fit log, cột `Collab cov.`/`Pool cắt`/`Fit s`) và `regress`; `scipy`/`implicit` vào `.venv`; test harness 96 → 97 passed. **Gate R4** trên dữ liệu thật: `content_profile+mmr` ≡ `engine` v5 **1016/1016 và 98/98**, `content_profile` ≡ `engine_nommr[:20]` 1016/1016 và 98/98, `star_blend_a1` ≡ `content_profile` 100 %. Smoke 50 khách × 2 split × 2 mode: mọi Tier 1 + `rp3beta` chạy exit 0, fit ≤ 1 s. · **vướng** `+mmr` phá scorer thang điểm nhỏ (cooc/ease/knn R@20 0,76 → 0,54 trên 50 khách) — chỉ đọc hàng `none` cho chúng; ở 7k event chỉ ≈ 5 % item top-20 có co-occurrence > 0 nên cooc/itemknn/rp3beta ra cùng top-20; `bpr_dest` không có cài đặt. · **quyết định** (người dùng 01/10) funnel = mask engine, bảng pool mask + gate pool engine, chạy cả hai rerank; R chốt X_train ⊆ `kept`, LLBO fit toàn cục + caveat, seed dạng `explain`, `because[]` hoãn. Full run Day 5 chưa chạy.
- Day 5 (R, Claude — 01/10 tối, full Day 5 + because + bpr_dest): **xong** commit R3–R6 `8fffd4b`; gate numpy trong-run G1/G2 1016/1016 và 98/98; 6 run bảng (`2026-10-01-{llbo,temporal}-algos-{funnel,raw}` pool mask × rerank none/mmr, `--max-tier 2`, thêm baseline `pop_funnel`) + `content-nodecay`, 102 so cặp có CI, phân khúc, ceiling → report `src/evaluation/reports/eval-2026-10-01-recsys-algos-v1.md`; `baseline_v1` (`frozen/baseline_v1-{llbo,temporal}-asof20260924.json`) + lệnh `baseline` / `regress --baseline` (mã 0/1/2/3) + `make recsys-{test,gate-run,regress,baseline}`, PASS trên chính nó; because[] cho scorer mới với `--because-k K` (K = 5/10/15/20); `bpr_numpy` / `bpr_dest` (numpy, sampler cắm được) Tier 2; ADR 2 ở `history/2026-10-01-adr2-huong-cai-thien-recsys-tuan-sau.md`. Số chính LLBO funnel hit@20: content 0,875 · `star_blend` 0,896 · `pop_funnel` = cooc = itemknn = rp3beta 0,820 · `ials` 0,835 · engine 0,848; temporal: content 0,194, mọi CF ≤ 0,112. · **vướng** 441/1.016 khách LLBO đã `add_to_cart` (không gid) đúng target trước khi mua — `ials` thắng NDCG@10 ở LLBO nhờ tín hiệu này (0,977 trên nhóm có giỏ, −13,2 điểm ở nhóm còn lại); temporal chỉ 2/98. · **quyết định** (ADR 2, theo quy tắc, chưa đồng thuận) giữ engine v5 làm lõi; harness thêm nhãn `targetInOwnHistory` + split biến thể trước grid; đề xuất PRD cap theo `parentProductId` (I-5); grid temporal `W_SHORT/W_POP` rồi λ MMR; bỏ grid `H_*`; không chạy kiến trúc sâu.
- Day 4–5 (S, Codex / Claude — 01–02/10, ghi bù 05/10): **xong** S1–S8a (`history/2026-10-01-search-day4-local.md`): gold_v3 5.021 nhãn; 8 model × 3.183 vector; 3 arm APP (dense giữ làm mốc vì hybrid + normalize thua guard slice); v4-512 / v4-1024 qua gate judged; 02/10 so 5 model local cùng thang đo condensed-deep → e5-small hoà e5-base / BGE / GTE, e5-large kém. · **vướng** chưa có stages / regress / split; gate P kẹt ở `/search` cloud p95 4,0 s; tag `gold_v1` không có trên git. · **quyết định** không đổi production; quyết định model còn treo.
- Day 6 (05/10 sáng, rà checklist): đối chiếu ô tick với history; điền bảng baseline v0; ghi việc mở quá hạn (`stages.yaml`, tiêu chí 20–23); nhóm chốt model e5-small / 384 (cần đề xuất PRD FR-SRC-02); gửi vector e5 cho RecSys.
- Day 6 (S, Claude — 05/10 chiều, nhánh `fix/search`): **xong** sửa import `Protocol` ở `ports/unit_index.py` (backend không import được sau merge); F1 lọc cứng điểm đến suy từ câu (hiện thực FR-SRC-03) + F2 bộ ngưỡng riêng cho câu không dấu, sau cờ mặc định tắt, contract **1.14.0** additive (`derivedDestinations`, `destinationFilter`, `queryProfile`), backend 610 passed, validator PASS; cổng APP của bench tham số hoá theo model → 12 arm `APP.e5s.*` chạy đúng `SearchProducts` trên `ProductBench_e5_small` (3.183, sanity 4/4): mốc hybrid + normalize không cutoff nDCG@10 0,677 (Judged 0,842); F1 **WIN** (Δrecall +2,34 [+1,03; +3,84]); F2 không đổi top-10 khi không cutoff; cutoff tuyệt đối 0,84 làm `no_diacritics` −14,5 mà 3/3 câu ngoài catalog vẫn có kết quả; cutoff riêng 0,80 cho câu không dấu bù lại hết; `hybrid_norm + F1 + F2(0,80)` so mốc 0,84 **WIN** Δrecall +2,82, ΔnDCG +3,54 [+1,48; +5,78], nDCG 0,701; embed e5 p95 10,3 ms laptop; đề xuất PRD FR-SRC-02 → e5-small soạn xong (`docs/prd/update/2026-10-05-fr-src-02-embedding-local-e5-small.md`, chờ chốt); report `eval-2026-10-05-search-e5s-dest-nodia.md`. · **vướng** arm hybrid chạy trong ~30 s đầu sau khi nạp collection cho kết quả sai (index BM25 Weaviate chưa ổn định) → thêm `wait_bm25_stable`, chạy lại 3 arm; không có arm Cohere nên chưa có số F1/F2 trên pipeline production; chưa đo HTTP; phủ định / chiều bay chờ câu gold mới; ngưỡng chờ dev/test. · **quyết định** (người dùng 05/10) bỏ so e5 vs Cohere cùng thang; F1 là hiện thực FR-SRC-03, không cần đề xuất; adapter e5 backend và HTTP chờ chốt đề xuất; chuyển hẳn sang e5, không gọi Cohere; chưa làm recommendation tuần này.
- Day 6 (S, Claude — 05/10 tối, nhánh `fix/search`, plan Phase A): **xong** query plan theo kiến trúc Phase A — F3 phủ định tiện ích (từ vựng `domain/search/amenities.py`, loại unit có ghi nhận), F4 loại sản phẩm suy từ câu, F5 chiều bay (gazetteer thành phố bay + IATA, param `origin`), F6 giá hard / sao soft; mọi họ sau cờ mặc định tắt, tham số request tường minh áp ngay; contract **1.15.0** (`queryPlan`, `origin`, GET đủ param); backend **825 passed**; bench: 4 khoá arm, 6 arm mới, cột RAM `features/origin_city`, metric Forbidden@10 / direction / filter pass / parse, `sb qu gold-scan` (5/5 · 10/10 · 12/12 · 9/9 ×3 · 1/1), `sb topids-diff`; run `2026-10-05-fix-search-qp`: identity cờ tắt 131/131; F3 Forbidden@10 5 câu phủ định → 0/10, `amenity_negation` +8,95 (cond +19,58); F6 `multi_constraint` +11,04; F5 c0373 đúng chiều; **F4 chưa bật được** (`abbrev_typo` −6,09, `filter_recall_loss` 148 — gold chấm nhiều loại cho câu nêu một loại, cue `kdl`/`nghỉ dưỡng`/`combo` quá rộng). Report `eval-2026-10-05-search-query-plan-plumbing.md`. · **vướng** gold v4 chưa có (tên slice/trường người dùng sẽ gửi → chưa sửa `gold_schema.py`); không arm Cohere, chưa HTTP; verifier bắt 3 lỗi major (500 m = 500 triệu, cue `trừ` trên "lưu trú", dựng thuộc tính 9 s) và identity bench bắt lỗi sắp xếp sao khi cờ tắt — đều đã sửa. · **quyết định** (người dùng 05/10) F3–F6 là hiện thực FR-SRC-01/03 không cần đề xuất; F rỗng do filter suy ra không nới; sao soft theo [C6]; gold schema chờ bộ tên từ máy gán nhãn.
- Day 7:
- Day 8:
- Day 9:
- Day 10:
