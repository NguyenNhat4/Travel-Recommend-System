# Checklist 8 ngày — benchmark embedding + search (Weaviate + Cohere) cho V-OTA

Phục vụ: FR-SRC-01, FR-SRC-02, FR-SRC-03, NFR-PERF-01, NFR-PERF-03 (`docs/prd/requirements.md`).

Bản 23/09/2026 — rev 2: ngày 4–8 chạy theo cổng (`sb run --stage`, `sb promote`, `sb gold holes`), thêm bước đặt baseline regression · đi kèm `search-eval-local-spec.md` (code chạy local) và `arms.md` (danh sách arm) · nguồn: `EMBEDDING_STACK_SWITCH.md`, `EMBEDDING_AND_ENGINES.md` §9, `VECTOR_DB_BENCH_SPEC.md` Part 6b, `VECTOR_STORE_AND_ROBUSTNESS.md` §3.1.

**Người A** = Eval & Data (sở hữu gold, metric, report, QU/alias). **Người B** = Search & Infra (sở hữu Weaviate, Cohere client, text builder, arm, latency).
Quy tắc: gold chỉ được **thêm** sau khi tag `gold_v1` (holes, query mới, retire) — không sửa nhãn cũ; A gán mọi hole. B không đọc nhãn gold trong lúc chỉnh text builder (chỉ xem metric tổng hợp). Mỗi arm chỉ đổi một nhóm trường so với `parent`. Promote khác đề xuất của `select()` phải có `--note`.

Ký hiệu lệnh: `sb` = `python -m evaluation.search_bench` chạy từ `src/`.

---

## Trước ngày 1 — điều kiện tiên quyết (cả hai)

- [x] Chốt endpoint embed: Cohere API trực tiếp **hoặc** Bedrock `ap-southeast-1` (ghi vào `config/sbench.yaml → embedding.provider`) — *23/09: Cohere API trực tiếp, `provider: cohere`*
- [x] Có `COHERE_API_KEY` (trial đủ: ~105 lượt gọi / lần re-embed 5.000 search unit) — *23/09: trong `.env` gốc repo, `sb doctor` xác nhận hợp lệ*
- [x] Có `products.jsonl` bản mới nhất (contract `docs/spec/data-collection/schema.md`), đường dẫn ghi vào config — mặc định snapshot `src/data_collection/snapshots/2026-09-21/products.jsonl.gz`, `sb catalog build` tự bung — *23/09: snapshot 2026-09-21, 10.320 dòng → 2.897 search unit*
- [x] Docker Desktop chạy được; máy ≥ 16 GB RAM nếu chạy bge-m3 local làm đối chứng — *23/09: Docker 29.7.2, RAM 31,5 GB*
- [ ] Mentor xác nhận bằng văn bản việc lệch handbook ở 3 mục (backend, vector store, embedding)
- [x] Tạo nhánh `bench/embed-search` (đã có), thư mục `src/evaluation/search_bench/` theo spec

---

## Ngày 1 — Draft gold · Hạ tầng

### A
- [ ] Đọc `SCHEMA.md` §3–§5 để biết trường thật; xuất danh sách destination, tên sản phẩm, amenity thô: `sb catalog vocab`
- [ ] Viết prompt sinh draft (`gold/prompts/draft.txt` — AGENTS.md §7 không cho `.md` trong `src/`): ràng buộc destination / tên / amenity vào danh sách vừa xuất; mỗi dòng `query \t slice`
- [ ] Sinh ~600 draft, đủ 10 slice (quota ở config `gold.slices`)
- [ ] Soát tay, chọn 200 → `gold/drafts.txt` (giữ log số draft bị loại theo lý do: bịa tên / trùng / không tự nhiên)
- [ ] Với slice `multi_constraint`: điền cột `filter` mong đợi (AST JSON; amenity ghi **khoá** như `kids_club`, không ghi id — xem `filter_fields` trong `vocab.json`); slice `out_of_catalog`: cột `expected_no_result=true`

### B
- [x] `docker compose -f evaluation/search_bench/docker/compose.yml up -d --wait weaviate` từ `src/` (image pin theo spec, cổng 127.0.0.1:58080/55051) · `sb doctor` xanh — *23/09: Weaviate 1.37.3, ascii_fold analyzer*
- [x] Tạo collection theo `sb collection create --variant T3+R --model cohere-v3` (schema §3 spec): named vector `content`, BM25 `word` + fold dấu, `amenity_ids[]`, `parentProductId` — *23/09: tên vật lý `Products__T3_R__cohere_v3`; thêm `stopwords_preset: none` (đề xuất, cần xác nhận)*
- [x] Cohere client: batch ≤ 96, `input_type` đúng chiều, `truncate=NONE`, retry 429 backoff, log token/chi phí — *23/09: + pacer 2.000 input/phút, `sb cost`*
- [x] Cache embedding theo `sha1(model|input_type|text)` — chạy 2 lần không tốn tiền lần 2 — *23/09: `--limit 96` lần 1 = 1 lượt gọi, lần 2 = 0*
- [x] Chạy thử với 50 sản phẩm mẫu (`sample/products-sample.jsonl` = 26 search unit): `sb --dataset sample catalog build` → `sb --dataset sample embed --variant T3+R --model cohere-v3 --limit 50` → `sb --dataset sample load` — *23/09: 26 vector thật (3.654 token, $0,000365), load 26 object*

### Sync cuối ngày
- [x] B demo cho A: import 26 search unit mẫu, `sb --dataset sample query "resort Nha Trang" --arm B0` ra kết quả — *23/09: top-1 Vinpearl Resort & Spa Nha Trang Bay, top-2 Vinpearl Beachfront Nha Trang*
- [ ] A đưa B `gold/drafts.txt` (200 dòng)

---

## Ngày 2 — Metric · Baseline import · Pool

### A
- [ ] Viết `metrics.py`: Recall@10, nDCG@10 (`2^rel−1`), MRR@10 (rel=2), Judged@10, constraint precision, recall loss do filter, parent dup rate, zero-result, hub_score
- [ ] Paired bootstrap 1.000 lần → mean Δ, CI95, p một phía
- [ ] Unit test trên fixture `tests/fixtures/gold_small.jsonl` (10 query) — số ra đúng bằng tay
- [ ] Viết `docs/spec/bench/gold-guide.md` (1 trang; không đặt trong `src/` — AGENTS.md §7): định nghĩa nhãn 2 / 1 / 0, 5 ví dụ khó (đúng nơi sai loại, phòng vs khách sạn, combo chứa vé…)

### B
- [x] `sb embed --variant T3+R --model cohere-v3` toàn catalog → `sb load` → collection `products__T3+R__cohere_v3` (= B0) — *24/09: 2.897 vector (30 lượt gọi, 451.021 token, $0,045); load 2.897 object, complete. Gặp 22 lượt 429 (giới hạn thật của key trial ~90–100k token/phút) → thêm `embedding.max_tokens_per_min: 90000`*
- [x] `sb tokens --variant T3+R`: phân bố token bằng tokenizer Cohere; **p99 < 450, max < 512**; nếu vượt, sửa text builder (không dùng `truncate`) — *làm sớm 23/09: p50 174, p99 276, max 379 — qua gate*
- [ ] `sb gold pool --drafts gold/drafts.txt --depth 15` → `gold/pool.csv` (dense top-15 ∪ BM25 top-15, ~20–25 doc/query) — *24/09: công cụ + filter AST sẵn sàng, chạy thử 10 draft fixture trên B0 ra 258 dòng (~26 doc/query); **chờ `gold/drafts.txt` của A***
- [ ] Chia pool (`sb gold split --overlap 25`): `pool_A.csv` (qid lẻ + 25 chung), `pool_B.csv` (qid chẵn + 25 chung), 25 chung chọn stratified theo slice (theo spec Part 5) — *24/09: công cụ sẵn sàng, đã thử trên pool fixture; chờ pool thật*

### Sync cuối ngày
- [ ] A chốt `gold-guide.md`; cả hai đọc, thống nhất 5 ví dụ khó trước khi gán

---

## Ngày 3 — Gán nhãn (cả hai, ~5–6 giờ/người)

### A
- [ ] Gán `pool_A.csv` (đúng theo GUIDE, không tra thêm web)
- [ ] Gán 25 query chung **độc lập**, không trao đổi với B

### B
- [ ] Gán `pool_B.csv`
- [ ] Gán 25 query chung độc lập

### Sync cuối ngày
- [ ] `sb gold kappa pool_A.csv pool_B.csv` → Cohen κ trên 25 chung
- [ ] κ ≥ 0,6 → tiếp. κ < 0,6 → ghi lại chỗ lệch, sửa GUIDE, **gán lại 25 chung** sáng ngày 4 (lịch lùi ½ ngày, chấp nhận)
- [ ] Hoà nhãn 25 chung: lệch 1 bậc lấy nhãn thấp hơn; lệch 2 bậc thảo luận

---

## Ngày 4 — Khoá gold · B0 · SAN · E1a

### A
- [ ] `sb gold import gold/pool_labeled.csv` → `gold/gold.jsonl`; `sb gold check` xanh (mỗi query ≥ 1 nhãn 2 trừ out_of_catalog, không slice < 10 query)
- [ ] `git tag gold_v1`; từ đây gold chỉ **thêm** (spec Part 11)
- [ ] `sb arms check` xanh (arms.md ↔ `arms/*.yaml` ↔ `stages.yaml`)
- [ ] `sb run --stage B0 --until SAN` → đọc `sb compare --stage SAN`
  - [ ] `SANITY_FAIL` → dừng, cùng B kiểm cache / `input_type` (spec Part 12.2), không chạy tiếp
  - [ ] `SANITY_WARN` → xem Δ của E3 / T6 / T7, `sb ack SAN --note "…"`
- [ ] Kiểm B0: **Judged@10 ≥ 80%**, slice ≥ 70%; thiếu → `sb gold holes --stage B0`, gán, `holes import`, tag `gold_v2`, `sb rescore`
- [ ] `sb run --stage E1a` (khi B đã nạp T0–T3) → nếu `NEEDS_LABELS`: holes → gán → import → tag → rescore → chạy lại lệnh

### B
- [ ] Cài text builder dạng base + modifier (spec Part 2): T0–T3, `R`, `DF`, `KV`, `NUM`, `w30/w60/w150/wfull`; snapshot test
- [ ] `sb enrich summaries` cho T3 (chỉ từ attributes, prompt cấm thêm sự kiện); xuất 5% `summaries_review.csv` → **A soát** (B không tự soát)
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
| κ < 0,6 sau lần gán lại | Thu hẹp nhãn 1 thành định nghĩa cụ thể theo taxonomy (đúng nơi + đúng loại, thiếu điều kiện); gán lại 25 chung lần cuối; lịch lùi 1 ngày |
| Judged@10 < 80% ở ≥ 3 slice | Pool sâu hơn (depth 25) cho slice đó, gán thêm ½ ngày |
| SAN `SANITY_FAIL` | Kiểm tra cứng hỏng (vector hai `input_type` giống nhau, cache sai, collection thiếu, gold bị sửa) — dừng mọi cổng cho tới khi sửa, `--force` chạy lại |
| SAN `SANITY_WARN` | E3/T6/T7 không thua B0 như kỳ vọng — xem Δ theo slice, `sb ack` kèm ghi chú; không chặn chuỗi |
| `NEEDS_LABELS` lặp ở nhiều cổng | Bình thường ở E1a, S4, S7, Pb; ước vài chục cặp mỗi lần — A gán ngay trong ngày, không dồn |
| Token p99 > 450 | Sửa text builder (cắt description / amenities), không bật `truncate` |
| Cohere 429 khi re-embed | Tăng backoff; không chạy 2 variant song song |
| bge-m3 local quá chậm | Dùng ONNX int8 hoặc bỏ E2.bge, ghi rõ "không có đối chứng local" trong FINAL.md |
