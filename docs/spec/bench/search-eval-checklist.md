# Checklist 8 ngày — benchmark embedding + search (Weaviate + Cohere) cho V-OTA

Phục vụ: **FR-SRC-01..04**, **NFR-PERF-01**, **NFR-PERF-03**, **AC-SRC-01** (`docs/prd/requirements.md`).

Bản 23/09/2026 — rev 2: ngày 4–8 chạy theo cổng (`sb run --stage`, `sb promote`, `sb gold holes`), thêm bước đặt baseline regression · đi kèm `search-eval-local-spec.md` (code chạy local) và `arms.md` (danh sách arm) · nguồn: `EMBEDDING_STACK_SWITCH.md`, `EMBEDDING_AND_ENGINES.md` §9, `VECTOR_DB_BENCH_SPEC.md` Part 6b, `VECTOR_STORE_AND_ROBUSTNESS.md` §3.1.

Rev 3 (24/09/2026): gộp bản sửa người dùng đưa vào ngày 24/09 (`SEARCH_EVAL_CHECKLIST.md`, đã gộp rồi xoá) vào file này (file này là chuẩn, giữ nguyên các mục đã tick). Nội dung mới lấy từ bản sửa: tóm tắt LLM (T3) chuyển lên ngày 1 (B dựng text builder tối thiểu T1/T3 + `R`, chạy `sb enrich summaries`), A soát `summaries_review.csv` sáng ngày 2 trước khi B embed toàn catalog, mục text builder ngày 4 của B chỉ còn phần base/modifier chưa làm (T0, T2, DF, KV, NUM, w30/w150/wfull), và thêm một dòng buffer "Tóm tắt LLM chưa xong cuối ngày 1".

**Người A** = Eval & Data (sở hữu gold, metric, report, QU/alias). **Người B** = Search & Infra (sở hữu Weaviate, Cohere client, text builder, arm, latency).
Quy tắc: gold chỉ được **thêm** sau khi tag `gold_v1` (holes, query mới, retire) — không sửa nhãn cũ; A gán mọi hole. B không đọc nhãn gold trong lúc chỉnh text builder (chỉ xem metric tổng hợp). Mỗi arm chỉ đổi một nhóm trường so với `parent`. Promote khác đề xuất của `select()` phải có `--note`.

Ký hiệu lệnh: `sb` = `python -m evaluation.search_bench` chạy từ `src/`.

---

## Trước ngày 1 — điều kiện tiên quyết (cả hai)

- [x] Chốt endpoint embed: Cohere API trực tiếp **hoặc** Bedrock `ap-southeast-1` (ghi vào `config/sbench.yaml → embedding.provider`) — *23/09: Cohere API trực tiếp, `provider: cohere`*
- [x] Có `COHERE_API_KEY` (trial đủ: ~105 lượt gọi / lần re-embed 5.000 search unit) — *23/09: trong `.env` gốc repo, `sb doctor` xác nhận hợp lệ*
- [x] Có `products.jsonl` bản mới nhất (contract `docs/spec/data-collection/schema.md`), đường dẫn ghi vào config — mặc định snapshot `src/data_collection/snapshots/2026-09-23/products.jsonl.gz`, `sb catalog build` tự bung — *23/09: snapshot 2026-09-21, 10.320 dòng → 2.897 search unit* — ⚠ *24/09: sau merge `release-mvp-v1` (80c3611), snapshot `2026-09-23` (11.387 dòng) là mặc định của repo; `config/sbench.yaml` vẫn trỏ 2026-09-21 — chốt giữ hay đổi trước khi embed lại B0* — *24/09 chiều: chốt chuyển sang 2026-09-23 — 11.387 dòng → 3.183 search unit (hotel_property 2.321, attraction 610, combo 133, flight_route 113, golf 6)*
- [x] Docker Desktop chạy được; máy ≥ 16 GB RAM nếu chạy bge-m3 local làm đối chứng — *23/09: Docker 29.7.2, RAM 31,5 GB*
- [ ] Mentor xác nhận bằng văn bản việc lệch handbook ở 3 mục (backend, vector store, embedding) — *29/09: note soạn tại `docs/spec/bench/note-mentor-lech-handbook.md`, chưa gửi; tick khi mentor trả lời*
- [x] Tạo nhánh `bench/embed-search` (đã có), thư mục `src/evaluation/search_bench/` theo spec

---

## Ngày 1 — Draft gold · Hạ tầng

### A
- [x] Đọc `docs/spec/data-collection/schema.md` §3–§5 để biết trường thật; xuất danh sách destination, tên sản phẩm, amenity thô: `sb catalog vocab` — *24/09: `vocab.json` đã dựng lại trên snapshot 2026-09-23 (38 điểm đến · 3.183 sản phẩm · 517 amenity) — draft dùng bản này; id amenity đổi so với 2026-09-21, nên ghi **khoá** amenity, không ghi id*
- [x] Viết prompt sinh draft (`docs/spec/bench/gold-draft-prompt.md` — AGENTS.md §7 không cho `.md` trong `src/`): ràng buộc destination / tên / amenity vào danh sách vừa xuất; mỗi dòng `query \t slice`
- [x] Sinh ~600 draft, đủ 13 slice (quota ở config `gold.slices`) → lưu `gold/drafts_raw.tsv`
- [x] Bổ sung ứng viên cho slice đã cạn ý định: append vào `gold/drafts_raw.tsv`, không đánh số lại dòng cũ, mỗi ý định 3 cách nói (`docs/spec/bench/gold-draft-prompt.md` rule 10) — *24/09: `c0601`–`c0672` (72 dòng / 24 ý định) trên snapshot 2026-09-23; luật chọn ở `drafts_manifest.json → supplements`*
- [ ] Người dùng soát tay, chọn 200 → `gold/drafts.txt` bằng app `streamlit_app.py` rồi `sb gold drafts --fill` (giữ log số draft bị loại theo lý do: bịa tên / trùng / không tự nhiên) — *24/09: **200/200, 13/13 slice đúng quota**. 158 dòng từ quyết định của người soát (kể cả 29 dòng ghi đè có bằng chứng trong `gold/overrides.tsv`), **42 dòng do `--fill` lấp tự động** — đã qua một vòng phản biện máy trên catalog 2026-09-23 nhưng **chưa có người rà**; tick ô này sau khi rà xong 42 dòng đó* — *28/09 (người dùng chốt): drafts.txt = mọi câu người soát chọn, không cần đủ 200, không tự lấp; mỗi slice ≥ 3 câu*
- [x] Với slice `multi_constraint`: điền cột `filter` mong đợi (AST JSON; amenity ghi **khoá** như `kids_club`, không ghi id — xem `filter_fields` trong `vocab.json`); slice `out_of_catalog`: cột `expected_no_result=true`

### B
- [x] `docker compose -f evaluation/search_bench/docker/compose.yml up -d --wait weaviate` từ `src/` (image pin theo spec, cổng 127.0.0.1:58080/55051) · `sb doctor` xanh — *23/09: Weaviate 1.37.3, ascii_fold analyzer*
- [x] Tạo collection theo `sb collection create --variant T3+R --model cohere-v3` (schema §3 spec): named vector `content`, BM25 `word` + fold dấu, `amenity_ids[]`, `parentProductId` — *23/09: tên vật lý `Products__T3_R__cohere_v3`; thêm `stopwords_preset: none` (đề xuất, cần xác nhận)*; property trong Weaviate là **`parent_product_id`** (snake_case, tokenization FIELD, chỉ để lọc) — `parentProductId` ở đây là tên field của `products.jsonl`
- [x] Cohere client: batch ≤ 96, `input_type` đúng chiều, `truncate=NONE`, retry 429 backoff, log token/chi phí — *23/09: + pacer 2.000 input/phút, `sb cost`*
- [x] Cache embedding theo `sha1(model|input_type|text)` — chạy 2 lần không tốn tiền lần 2 — *23/09: `--limit 96` lần 1 = 1 lượt gọi, lần 2 = 0*
- [ ] Text builder tối thiểu cho B0: base `T1`, `T3` + modifier `R` (spec Part 2); các base/modifier còn lại để ngày 4 — *24/09: chưa làm — B0 hiện là `build_text` của backend (spec §1.1, `text_builder: app`); chờ chốt B0 dựng từ `textbuild.py` (T3 = T1 + tóm tắt LLM khi description tự sinh, còn lại description gốc — spec Part 2) hay giữ bản backend* — *24/09 chiều: chốt B0 = `build_text` backend `catalog-text-v2` như production (spec §1.1) → `T1`/`T3`/`R` của `textbuild.py` chỉ còn phục vụ E1a (ngày 4), không chặn B0 hay pool*
- [ ] `sb enrich summaries` chạy nền (chỉ từ attributes, prompt cấm thêm sự kiện) → `llm_summaries.jsonl` + `summaries_review.csv` (5%) → **A soát** (B không tự soát) — *24/09: chưa làm (cần `LLM_PROVIDER` + key trong `.env`); không chặn B0 (B0 = `build_text` backend)*
- [x] Chạy thử với 50 sản phẩm mẫu (`sample/products-sample.jsonl` = 26 search unit): `sb --dataset sample catalog build` → `sb --dataset sample embed --variant T3+R --model cohere-v3 --limit 50` → `sb --dataset sample load` — *23/09: 26 vector thật (3.654 token, $0,000365), load 26 object*

> *24/09 kiểm lại trên clone mới (PR gộp app gán nhãn của Người A vào `bench/embed-search`): `.venv-sbench` dựng lại từ `requirements.txt`; `sb doctor` xanh exit 0 (Docker 29.4.2, Weaviate 1.37.3, ascii_fold analyzer, gRPC 55051, `COHERE_API_KEY` hợp lệ, snapshot 10.320 dòng) — `bge-m3` WARN và `gold tags` INFO là bình thường. `--dataset sample catalog build` 26 search unit / 50 bản ghi, 9 điểm đến. `collection create` → `Products__T3_R__cohere_v3__sample`. `embed --limit 50` = 26 vector × 1024, 1 lượt gọi, 3.654 token, $0,000365; chạy lại = 0 lượt gọi / 26 từ cache. `load` 26 object, `collection list` `complete=True`, `items=39e24f766b`. `tokens` n=26 p50 134 p90 188 p99 214 max 217 — qua gate. `query "resort Nha Trang" --arm B0` top-1 Vinpearl Resort & Spa Nha Trang Bay (0,3225), top-2 Vinpearl Beachfront Nha Trang (0,3608), `input_type=query`. `sb cost` tổng 4 lượt gọi / 3.659 token / $0,000365. `pytest` 129 passed, 9 skipped; `pytest -m integration` 9 passed (gồm 50 filter ngẫu nhiên khớp evaluator pandas). App gán nhãn: mật khẩu sai bị chặn, mật khẩu đúng hiện 600 case và 13 slice. Chi tiết: `history/2026-09-24-sbench-ngay-1-kiem-lai-tren-clone-moi.md`.*

### Sync cuối ngày
- [x] B demo cho A: import 26 search unit mẫu, `sb --dataset sample query "resort Nha Trang" --arm B0` ra kết quả — *23/09: top-1 Vinpearl Resort & Spa Nha Trang Bay, top-2 Vinpearl Beachfront Nha Trang*
- [ ] A đưa B `gold/drafts.txt` (200 dòng) — *28/09 (người dùng chốt): drafts.txt = mọi câu người soát chọn, không cần đủ 200, không tự lấp; mỗi slice ≥ 3 câu*

---

## Ngày 2 — Metric · Baseline import · Pool

### A
- [x] Viết `metrics.py`: Recall@10, nDCG@10 (`2^rel−1`), MRR@10 (rel=2), Judged@10, constraint precision, recall loss do filter, parent dup rate, zero-result, hub_score — *24/09: thêm Recall@5 (test-plan §2.5, `metrics.extra_recall_k`)*
- [x] Paired bootstrap 1.000 lần → mean Δ, CI95, p một phía — *24/09: p theo mid-p để arm so với chính nó ra p = 0,5; kèm `win_verdict` / `compare_rows`*
- [x] Unit test trên fixture `tests/fixtures/gold_small.jsonl` (10 query) — số ra đúng bằng tay — *24/09: + `run_small.json` (arm A/B), 13 test; tính tay q001, q004, q007*
- [ ] Sáng: soát `summaries_review.csv` (5% tóm tắt LLM) **trước khi B embed toàn catalog**; có câu bịa sự kiện → báo B sửa prompt, chạy lại — *24/09: B đã embed toàn catalog bằng `build_text` backend (không dùng tóm tắt LLM); mục này áp dụng khi T3 dựng từ tóm tắt* — *24/09 chiều: B0 chốt là `build_text` backend nên mục này không chặn B0; làm trước khi embed T3 cho E1a*
- [x] Viết `docs/spec/bench/gold-guide.md` (1 trang; không đặt trong `src/` — AGENTS.md §7): định nghĩa nhãn 2 / 1 / 0, 5 ví dụ khó (đúng nơi sai loại, phòng vs khách sạn, combo chứa vé…) — *25/09: viết theo `prompts/may1-gold-cli.md`; luật destination đã chốt (sai destination → 0, kể cả đúng loại); ví dụ lấy từ fixture `gold_small/` — còn chờ cả hai đọc và thống nhất (mục sync bên dưới)*

### B
- [x] `sb embed --variant T3+R --model cohere-v3` toàn catalog → `sb load` → collection `products__T3+R__cohere_v3` (= B0) — *24/09: 2.897 vector (30 lượt gọi, 451.021 token, $0,045); load 2.897 object, complete. Gặp 22 lượt 429 (giới hạn thật của key trial ~90–100k token/phút) → thêm `embedding.max_tokens_per_min: 90000`* — ⚠ *24/09 (12:36): merge `release-mvp-v1` (80c3611) đổi `build_text` backend sang `catalog-text-v2` và thêm snapshot catalog `2026-09-23` → B0 hiện có đã cũ (builder_fingerprint khác), cần chốt rồi embed + load lại. Muốn B0 khớp production v2 thì adapter của bench phải truyền `combo_items` (production truyền, bench chưa) và spec §1.1 phải cập nhật mô tả builder* — ✅ *24/09 chiều: đã xử lý — bench gọi `build_text` như `PostgresCatalogReader` (con + `combo_items` từ `parse_combos` + `combo_items_manual.jsonl`); 3.183/3.183 text trùng khít production (test `test_t3r_equals_production_path`). Embed lại trên snapshot 2026-09-23: 3.183 vector (34 lượt gọi, 425.088 token, $0,0425, 0 lượt 429 nhờ pacer token); load 3.183 object, complete; `check_ready` giờ từ chối collection dựng từ text cũ*
- [x] `sb tokens --variant T3+R`: phân bố token bằng tokenizer Cohere; **p99 < 450, max < 512**; nếu vượt, sửa text builder (không dùng `truncate`) — *làm sớm 23/09: p50 174, p99 276, max 379 — qua gate* — ⚠ *24/09: đo trên text trước `catalog-text-v2` — chạy lại `sb tokens` khi dựng lại B0* — *24/09 chiều: đo lại trên `catalog-text-v2`, snapshot 2026-09-23: p50 142, p90 201, p99 234, max 299 — qua gate*
- [ ] `sb gold pool --drafts gold/drafts.txt --depth 15` → `gold/pool.csv` (dense top-15 ∪ BM25 top-15, ~20–25 doc/query) — *24/09: công cụ + filter AST sẵn sàng, chạy thử 10 draft fixture trên B0 ra 258 dòng (~26 doc/query); **chờ `gold/drafts.txt` của A** và B0 dựng lại (⚠ ở trên; `sb gold pool` hiện chỉ kiểm items, chưa kiểm builder, nên vẫn chạy được trên B0 cũ — chấp nhận được theo quy tắc buffer "pool chỉ cần đa dạng")* — *24/09 chiều: B0 đã dựng lại; `sb gold pool` giờ kiểm cả builder_fingerprint + file combo soát tay; chạy lại fixture: 255 dòng (p50 26, max 30 doc/query), 0 query rỗng — chỉ còn **chờ `gold/drafts.txt` của A*** — *25/09: `pool` viết lại theo hợp đồng `gold_schema.py` (bước 0): đủ `POOL_COLUMNS`, filter tách `filter_json` / `child_filter_json` + `filter_text`, tiện ích / snippet / hạng phòng, qid = `case_id`, kèm `pool.build.json`. Thử trên 200 draft hiện tại (ghi vào `bench_out/`, không vào `gold/`): 5.046 dòng, 6–30 ứng viên/câu (p50 26), 0 câu rỗng. Chạy thật vào `gold/` sau khi đóng băng `drafts.txt` (`docs/spec/bench/README.md`)*
- [ ] Chia pool (`sb gold split --overlap 25`): `pool_A.csv` (qid lẻ + 25 chung), `pool_B.csv` (qid chẵn + 25 chung), 25 chung chọn stratified theo slice (theo spec Part 5) — *24/09: công cụ sẵn sàng, đã thử trên pool fixture; chờ pool thật* — *25/09: ghi thêm `pool_meta.json` (sha, số dòng, `overlap_qids`) và `is_overlap`; câu riêng chia **xen kẽ A/B trong từng slice** thay cho lẻ/chẵn (qid giờ là `case_id`, lẻ/chẵn lệch theo slice); mỗi người một thứ tự xáo. Thử trên 200 draft: A 113 câu / 2.871 cặp, B 112 câu / 2.830 cặp* — *29/09: drafts chốt 132 câu → split viết lại (spec Part 5): slice ≥ 2 câu có ≥ 1 câu chung, câu riêng cân theo **số cặp**, mỗi người đi slice theo khối và B lệch nửa vòng, câu chung rải đều nên không lộ (`gold-guide.md` mục Gán độc lập). Mô phỏng 124/132 câu: A 74 câu / 1.889 cặp, B 75 / 1.890, 25 chung / 636 cặp, mọi slice có câu chung. Pool thật chờ khoá Cohere: 11 câu mới/sửa chưa có vector truy vấn trong cache, khoá Trial hết lượt tháng* — *29/09 (sau khi có khoá): `sb gold pool` → `gold/pool.csv` 132 câu / 3.359 dòng (6–30 ứng viên, p50 26), 0 câu rỗng; `sb gold split` → `pool_A.csv` 78 câu / 1.999 cặp, `pool_B.csv` 79 câu / 2.000 cặp, 25 câu chung / 640 cặp, mọi slice có câu chung; A bắt đầu `dest_type`, B bắt đầu `named_entity`; sha trong `pool_meta.json` khớp — sẵn sàng gán*

### Sync cuối ngày
- [ ] A chốt `gold-guide.md`; cả hai đọc, thống nhất 5 ví dụ khó trước khi gán

---

## Ngày 3 — Gán nhãn (cả hai, ~5–6 giờ/người)

### A
- [ ] Gán hết `pool_A.csv` theo thứ tự app (đúng theo `gold-guide.md`, không tra thêm web); file đã gồm ~25 câu chung với B nhưng không biết là câu nào — không trao đổi từng câu với B tới khi `sb gold kappa` chạy xong (`gold-guide.md` mục Gán độc lập) — *29/09: thay mục cũ "Gán 25 query chung độc lập": từ luật split 29/09 câu chung rải trong file, không tách thành việc riêng*

### B
- [ ] Gán hết `pool_B.csv` theo thứ tự app — như A (câu chung không lộ; không trao đổi từng câu tới khi có κ)

### Sync cuối ngày
- [ ] `sb gold kappa gold/labels/labels_A.csv gold/labels/labels_B.csv` → Cohen κ (linear) trên 25 chung — *25/09: lệnh đã có, đúng đáp án fixture (κ linear 0,731343); lệnh cũ ghi `pool_A.csv pool_B.csv`, nay nhãn ở file riêng do app xuất*
- [ ] κ ≥ 0,6 → tiếp. κ < 0,6 → ghi lại chỗ lệch, sửa `gold-guide.md`, **gán lại 25 chung** sáng ngày 4 (lịch lùi ½ ngày, chấp nhận)
- [ ] Hoà nhãn 25 chung: lệch 1 bậc lấy nhãn thấp hơn; lệch 2 bậc thảo luận — *25/09: `sb gold merge gold/labels/labels_A.csv gold/labels/labels_B.csv` → `gold/labels/merged.csv`; sửa dòng `needs_discussion` ngay trong file (`gold-guide.md`)*

---

## Ngày 4 — Khoá gold · B0 · SAN · E1a

### A
- [ ] `sb gold import gold/labels/merged.csv` → `gold/gold.jsonl`; `sb gold check` xanh (mỗi query ≥ 1 nhãn 2 trừ out_of_catalog, không slice < `gold.min_per_slice` = 3 query — 28/09: trước là 10) — *25/09: hai lệnh đã có (thêm luật: out_of_catalog có `expected_no_result`, parent_child nhãn 2 có `expected_children`; import kiểm id với catalog snapshot); lệnh cũ ghi `gold/pool_labeled.csv`*
- [ ] `git tag gold_v1`; từ đây gold chỉ **thêm** (spec Part 11)
- [ ] `sb arms check` xanh (arms.md ↔ `arms/*.yaml` ↔ `stages.yaml`)
- [ ] `sb run --stage B0 --until SAN` → đọc `sb compare --stage SAN`
  - [ ] `SANITY_FAIL` → dừng, cùng B kiểm cache / `input_type` (spec Part 12.2), không chạy tiếp
  - [ ] `SANITY_WARN` → xem Δ của E3 / T6 / T7, `sb ack SAN --note "…"`
- [ ] Kiểm B0: **Judged@10 ≥ 80%**, slice ≥ 70%; thiếu → `sb gold holes --stage B0`, gán, `holes import`, tag `gold_v2`, `sb rescore`
- [ ] `sb run --stage E1a` (khi B đã nạp T0–T3) → nếu `NEEDS_LABELS`: holes → gán → import → tag → rescore → chạy lại lệnh

### B
- [ ] Cài phần còn lại của text builder: base `T0`, `T2`; modifier `DF`, `KV`, `NUM`, `w30/w150/wfull`; snapshot test — *24/09: + `T1`, `T3`, `R` nếu mục ngày 1 chưa xong (phục vụ E1a; B0 là `build_text` backend)*
- [ ] `sb embed + load` cho `T0`, `T1`, `T2`, `T3`, `T3+R+KV`, `T3+R+NUM`
- [ ] Viết `config/stages.yaml` theo spec Part 12.1 và YAML cho mọi arm trong arms.md (tham chiếu `@<cổng>`, không điền id cứng)

### Sync cuối ngày
- [ ] `sb status`: B0 `INFO_DONE`, SAN `PROMOTED`/đã ack, E1a `READY` hoặc `NEEDS_LABELS`
- [ ] Ghi nhận xét slice vào `reports/NOTES.md` (chưa quyết định)

---

## Ngày 5 — E1a → E1b → E4 → E2 (chốt text + model)

### A
- [ ] `sb compare --stage E1a` → đọc bảng tie → `sb promote <arm>` (khác đề xuất → `--note`)
- [ ] `sb run --stage E1b --until E4 --auto-promote` → dừng ở cổng nào thì xử lý cổng đó (holes / ack / promote tay)
- [ ] E4 bị `SKIPPED` nếu E1a chọn T1 — đúng thiết kế, không phải lỗi
- [ ] `sb run --stage E2` → cổng `model`: đề xuất = cohere-v3 thì promote; khác → `DECISION_NEEDED`, **không tự đổi**, ghi vào `reports/NOTES.md` để bàn ở ngày 8
- [ ] `sb run --stage E6` (chỉ khi model chốt là Cohere; cổng info)
- [ ] Viết `reports/E_stages.md` từ `sb status` + `sb compare --stage` của E1a, E1b, E4, E2

### B
- [ ] `sb embed + load` cho `@E1a+R`, `@E1a+R+DF` ngay khi A promote E1a (dùng `sb list-arms --resolved` để biết chuỗi variant thật)
- [ ] `sb embed + load` cho `@E1b+w30`, `@E1b+w150`, `@E1b+wfull` (nếu E4 không bị skip); `wfull` không qua token gate thì arm bị loại, có ghi lý do
- [ ] E2: cùng text `@E4` với `cohere-v4` (1024-d), `bge-m3` local; `gte-mb` nếu máy chạy nổi
- [ ] E6: `embedding_types=int8` cho Cohere v3

### Sync cuối ngày
- [ ] Text + model đã promote; `sb cost` ghi chi phí API đến hôm nay

---

## Ngày 6 — E5 · S0 → S2 · QU

### A
- [ ] `sb run --stage E5` (khi B nạp xong hai collection vector phụ) → promote chế độ `doc` hoặc `qry`
- [ ] `sb run --stage S0 --until S2 --auto-promote` → xử lý cổng dừng; S2 là chỗ quyết định RRF vs relativeScore
- [ ] Viết `qu.py` + gazetteer + `config/aliases.yaml` + SymSpell; `sb qu test gold/qu_cases.yaml` (≥ 30 case) đạt ngưỡng spec Part 6

### B
- [ ] `sb synth generate` → `sb synth filter` (cross-encoder CPU 1–2 giờ, chạy nền) → `sb synth load --mode doc` và `--mode qry` trên `@E2`
- [ ] Cài filter `contains_all` / `not`, boost amenity, dedupe theo `parent_product_id` (cho S4, S5)
- [ ] Cài fallback BM25-only khi embed timeout 150 ms (cho F1)
- [ ] Nếu làm S1.k1b: clone collection từ cache, không sửa collection dùng chung

### Sync cuối ngày
- [ ] B nối `qu.py` của A vào runner; `sb status` tới S2 `PROMOTED`

---

## Ngày 7 — S3 → S7 (→ S9) · S8 · F1 · Đường nóng

### A
- [ ] `sb run --stage S3 --until S7 --auto-promote`; theo dõi **QU exact-match** ở slice multi_constraint
- [ ] Sau S4 và sau S7: `sb gold holes --stage <cổng>` nếu `NEEDS_LABELS` (filter và cutoff hay kéo lên sản phẩm chưa gán)
- [ ] S7 `NO_CANDIDATE` (không cutoff nào đạt zero-result out_of_catalog = 100%) → xem query ooc nào lọt; `--override-guard --note`, hoặc `sb gold retire` nếu catalog đã có sản phẩm liên quan
- [ ] `sb run --stage S9` (tự skip nếu hub ≤ 3) → `sb run --stage S8` → `sb run --stage F1`
- [ ] Viết `reports/S_stages.md`

### B
- [ ] `sb latency embed --n 500` tới endpoint đã chọn và endpoint còn lại: p50/p95/p99
- [ ] `sb latency e2e --arm P2 --cache-hit 0 0.5 0.8`
- [ ] `sb latency load --qps 50 --seconds 60`: 429 xuất hiện ở đâu; fallback `degraded` kích hoạt đúng
- [ ] Dựng trước collection còn thiếu cho P4/P5 (text `@E4` × v4 / bge-m3, và vector phụ nếu cần)

### Sync cuối ngày
- [ ] `sb status` tới F1; B đưa A `latency.json` + `cost.jsonl` cho bảng cuối

---

## Ngày 8 — Pa → Pb → Pc → FINAL · Baseline regression

### A
- [ ] `sb run --stage Pa --until Pc --auto-promote` (Pb tự sweep lại cutoff cho v4, bge-m3)
- [ ] `sb gold holes --stage Pa` / `Pb` nếu `NEEDS_LABELS` → tag → rescore → chạy lại
- [ ] `sb report final` → `reports/FINAL.md` (bảng 6 luồng, bảng slice, chuỗi cổng); quy tắc chọn **không đổi sau khi thấy số**
- [ ] Decision record `reports/DECISION.md`

### B
- [ ] Đóng gói luồng thắng: adapter `SearchClient` Weaviate + `config/search.yaml`
- [ ] Liệt kê docs phải sửa theo `EMBEDDING_STACK_SWITCH.md` §7
- [ ] Nếu repo dùng GitHub Actions: thêm `.github/workflows/search-regression.yml` theo spec Part 13 (path filter, cache embedding, secret)

### Sync cuối ngày (1 giờ)
- [ ] Review FINAL.md; `sb promote <P*> --stage FINAL --note "…"` (cổng này luôn cần người)
- [ ] `sb regression baseline set --flow <P*> --note "chốt tuần 2"` → commit `regression/baseline.json`
- [ ] `sb regression run` ngay sau đó phải ra **PASS** (exit 0) — kiểm tra regression chạy được trước khi giao
- [ ] Gửi mentor. Nếu E2 hoặc P5 cho thấy model khác thắng Cohere v3 ≥ 2 điểm ở slice không dấu / đối tượng → đưa lên bàn, không tự đổi
- [ ] Xoá collection thua **sau** khi FINAL.md và baseline đã commit

---

## Buffer và điều kiện dừng

| Tình huống | Xử lý |
|---|---|
| κ < 0,6 sau lần gán lại | Thu hẹp nhãn 1 thành định nghĩa cụ thể theo taxonomy (đúng nơi + đúng loại, thiếu điều kiện — hẹp hơn luật hiện tại của `gold-guide.md`: đúng nơi mà sai loại hoặc thiếu điều kiện); gán lại 25 chung lần cuối; lịch lùi 1 ngày |
| Judged@10 < 80% ở ≥ 3 slice | Pool sâu hơn (depth 25) cho slice đó, gán thêm ½ ngày |
| Slice không đủ **ý định phân biệt** cho quota | Sinh thêm ứng viên cho slice đó (ý định mới × 3 cách nói); **không** đưa hai cách nói của cùng một ý định vào bộ 200 — n tăng mà thông tin không tăng |
| SAN `SANITY_FAIL` | Kiểm tra cứng hỏng (vector hai `input_type` giống nhau, cache sai, collection thiếu, gold bị sửa) — dừng mọi cổng cho tới khi sửa, `--force` chạy lại |
| SAN `SANITY_WARN` | E3/T6/T7 không thua B0 như kỳ vọng — xem Δ theo slice, `sb ack` kèm ghi chú; không chặn chuỗi |
| `NEEDS_LABELS` lặp ở nhiều cổng | Bình thường ở E1a, S4, S7, Pb; ước vài chục cặp mỗi lần — A gán ngay trong ngày, không dồn |
| Tóm tắt LLM chưa xong cuối ngày 1 | Dựng pool trên `T1+R` (pool chỉ cần đa dạng); nạp B0 = `T3+R` khi xong; sản phẩm mới lọt top-10 của B0 xử lý bằng `sb gold holes` ngày 4 — **không đổi định nghĩa B0** — *24/09: áp dụng nếu chốt B0 = T3 từ tóm tắt LLM; hiện B0 = `build_text` backend* — *24/09 chiều: không áp dụng (chốt B0 = `build_text` backend v2); tóm tắt LLM chưa xong chỉ làm lùi E1a*|
| Token p99 > 450 | Sửa text builder (cắt description / amenities), không bật `truncate` |
| Cohere 429 khi re-embed | Tăng backoff; không chạy 2 variant song song |
| bge-m3 local quá chậm | Dùng ONNX int8 hoặc bỏ E2.bge, ghi rõ "không có đối chứng local" trong FINAL.md |
