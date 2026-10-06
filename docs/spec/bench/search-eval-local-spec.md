# spec.md — `sbench`: benchmark embedding + search trên Weaviate + Cohere, chạy local

Bản 23/09/2026 — rev 2: thêm Part 11 (`gold holes`, gold append-only, rescore), Part 12 (chạy theo cổng, `promote`), Part 13 (regression); text builder thành biến thể ghép (base + modifier) · để Claude Code sinh code ở local, **mỗi Part chạy thử được độc lập** · lịch và phân việc ở `search-eval-checklist.md` · danh sách arm ở `arms.md` (mô tả) và `config/stages.yaml` (máy đọc) · nguồn yêu cầu: `EMBEDDING_STACK_SWITCH.md` (Cohere, Weaviate, cái gì đổi), `EMBEDDING_AND_ENGINES.md` §1–§2, §4, §9 (text builder, hybrid, bộ đánh giá), `VECTOR_STORE_AND_ROBUSTNESS.md` §2–§3 (query preproc, amenity), `VECTOR_DB_BENCH_SPEC.md` Part 6b (gold tool — dùng lại định nghĩa nhãn), `docs/spec/data-collection/schema.md` (contract `products.jsonl`), `ARCHITECTURE.md` §4, §12 (vị trí code, không folder `utils`).

Phục vụ: **FR-SRC-01..04**, **NFR-PERF-01**, **NFR-PERF-03**, **AC-SRC-01** (`docs/prd/requirements.md`); độ đo theo `docs/prd/test-plan.md` §2.5.

> **Đối chiếu repo (23/09/2026).** `EMBEDDING_STACK_SWITCH.md`, `EMBEDDING_AND_ENGINES.md`, `VECTOR_STORE_AND_ROBUSTNESS.md` **không có trong repo**. `VECTOR_DB_BENCH_SPEC.md` = `docs/spec/vector-bench/spec.md`; `ARCHITECTURE.md` = `docs/spec/architecture-repo.md` (bản PRD: `docs/prd/architecture.md` §6). **Chỉ dùng trong bench:** index `flat` (exact, < 10k object) và collection nhiều property — production vẫn theo NFR-PERF-03 (HNSW) và `docs/prd/architecture.md` §5 (Weaviate chỉ giữ vector + `productId`); đưa luồng thắng vào backend (ngày 8) cần đề xuất ở `docs/prd/update/`.

Spec này **không đặt ra ngưỡng mới**: quota slice, ngưỡng metric, quy tắc chọn chép từ plan đã chốt vào **một** file config (§1.2). Tham số kỹ thuật spec thêm ghi *(đề xuất)*.

---

## 0. Tóm tắt

**Làm gì.** Một CLI Python (`sbench`) dựng `embed_text` theo nhiều biến thể, embed bằng Cohere (v3 / v4) hoặc bge-m3 local, nạp vào Weaviate chạy Docker, chạy các **arm** (mỗi arm = một cấu hình retrieval) trên **một** bộ gold, tính metric theo slice, so cặp bằng paired bootstrap, đo latency đường nóng, và xuất bảng benchmark cuối để chọn luồng + model.

**Không làm.**
- Không ghi vào DB `vota` của app; chỉ đọc `products.jsonl`.
- Không đo `/recommendations` (làm sau khi chốt model — cần event, không cần gold).
- Không xây amenity taxonomy chính thức: dùng `config/amenity_seed.yaml` + fallback `raw:<slug>` như `VECTOR_DB_BENCH_SPEC` P1.3.
- Không fine-tune (Cohere không hỗ trợ).
- Không đo managed Weaviate Cloud; latency Weaviate ở local chỉ để tham khảo, latency **embed API** mới là số dùng thật.

**Mọi Part chạy được với `--provider fake`** (vector giả, deterministic theo hash text) để thử khung không tốn tiền. Số đo thật chỉ lấy từ Cohere / bge-m3.

**Các Part** — làm theo thứ tự; Part sau dùng đầu ra Part trước. `sb` = `python -m evaluation.search_bench` chạy từ `src/`.

| Part | Nội dung | Lệnh chạy thử | Cần trước |
|---|---|---|---|
| 0 | Khung package, config, compose Weaviate, `doctor` | `sb doctor` | — |
| 1 | Catalog → `items.parquet` + vocab | `sb catalog build` · `sb catalog vocab` | 0 |
| 2 | Text builder: base T0–T3 + modifier (`R`, `DF`, `KV`, `NUM`, `wN`) + đếm token | `sb text --variant T3+R` · `sb tokens --variant T3+R` | 1 |
| 3 | Embedding provider (cohere-v3, cohere-v4, bge-m3, gte-mb, fake) + cache | `sb embed --variant T3+R --model fake` | 2 |
| 4 | Adapter Weaviate: collection, load, query dense / bm25 / hybrid, filter | `sb load --variant T3+R --model fake` · `sb query "..."` | 3 |
| 5 | Gold: pool, kappa, import, kiểm tra | `sb gold pool` · `sb gold import` | 4 |
| 6 | Query understanding, alias, SymSpell | `sb qu "resort PQ có kids club dưới 3tr"` | 1 |
| 7 | Synthetic query: generate, filter, load `query_vec` (2 chế độ doc / qry) | `sb synth generate` · `sb synth filter` | 3, 4 |
| 8 | Arm runner, metric, so cặp | `sb run --arm B0` · `sb compare E1.T1 E1.T3` | 4, 5, 6 |
| 9 | Latency đường nóng | `sb latency embed` · `sb latency e2e` | 3, 4 |
| 10 | Report cuối + quy tắc chọn (`select()` dùng chung với Part 12) | `sb report final` | 8, 9 |
| 11 | Gold append-only: `gold holes`, `retire`, `rescore` | `sb gold holes --stage E1a` · `sb rescore` | 5, 8 |
| 12 | Chạy theo cổng: `stages.yaml`, `run --stage`, `promote`, `status` | `sb run --stage E1a` · `sb promote E1.T3` | 8, 10, 11 |
| 13 | Regression sau khi chốt | `sb regression baseline set` · `sb regression run` | 11, 12 |

---

## 1. Quy ước chung

### 1.1 Vị trí code và dữ liệu

```
src/evaluation/search_bench/
├── __main__.py            # CLI (typer) — mọi lệnh ở §1.3
├── config.py              # nạp config/sbench.yaml + .env, validate pydantic
├── paths.py               # SBENCH_HOME, run dir, tên file chuẩn
├── doctor.py              # Part 0
├── catalog.py             # Part 1: products.jsonl → items.parquet, vocab
├── amenities.py           # map amenity thô → amenity_ids (seed + fallback raw:)
├── textbuild.py           # Part 2: base T0–T3 + modifier (import text builder của Search nếu repo đã có)
├── tokens.py              # Part 2: đếm token Cohere
├── embed/
│   ├── base.py            # Protocol Embedder(texts, input_type) → np.ndarray
│   ├── cohere_api.py      # v3 / v4, batch 96, retry 429
│   ├── bedrock.py         # cohere.embed-multilingual-v3 qua boto3 (tuỳ chọn)
│   ├── local_st.py        # bge-m3 sentence-transformers
│   ├── fake.py            # vector theo hash, deterministic
│   └── cache.py           # sqlite: key=sha1(model|input_type|text) → vector
├── store/
│   ├── weaviate_store.py  # Part 4: schema, load, dense/bm25/hybrid, filter, aggregate
│   └── filters.py         # AST JSON → weaviate Filter (chép từ vector_bench/filters.py nếu có)
├── gold.py                # Part 5
├── qu.py                  # Part 6: rule + gazetteer + alias + SymSpell
├── synth.py               # Part 7
├── arms.py                # Part 8: nạp arms/*.yaml, validate, resolve parent
├── runner.py              # Part 8: chạy 1 arm trên gold → results.json
├── metrics.py             # Part 8: mọi metric + paired bootstrap
├── latency.py             # Part 9
├── report.py              # Part 10: report + select() (quy tắc chọn dùng chung với Part 12)
├── holes.py               # Part 11: gold holes, retire, rescore, verify-append
├── stages.py              # Part 12: nạp stages.yaml, run --stage, gate, promote, status
├── sanity.py              # Part 12: kiểm tra toàn vẹn pipeline (cứng) + control (mềm)
├── regression.py          # Part 13
├── config/
│   ├── sbench.yaml        # MỌI con số (§1.2)
│   ├── stages.yaml        # thứ tự cổng, ứng viên, sanity (Part 12) — nguồn máy đọc của arms.md
│   ├── aliases.yaml       # viết tắt, tên gọi khác (Part 6)
│   ├── (amenity seed)     # dùng chung src/evaluation/vector_bench/config/amenity_seed.yaml (catalog.amenity_seed_path) — không chép
│   └── synth_prompts.yaml # prompt sinh synthetic query (Part 7)
├── arms/                  # mỗi arm một YAML (arms.md) — commit
├── gold/                  # drafts_raw.tsv, drafts.txt, pool.csv + pool.build.json, pool_A/B.csv + pool_meta.json, labels/ (labels_A/B.csv, merged.csv), gold.jsonl, changelog.yaml, holes/ — commit; định dạng file: gold_schema.py (prompt ở docs/spec/bench/gold-draft-prompt.md, GUIDE ở docs/spec/bench/gold-guide.md: AGENTS.md §7 không cho .md trong src/)
├── state/promotions.yaml  # arm được promote ở mỗi cổng (Part 12) — commit
├── regression/baseline.json  # mốc regression (Part 13) — commit, chỉ đổi bằng lệnh
├── docker/compose.yml     # Weaviate (project `sbench`)
├── requirements.txt       # lõi; requirements-extra.txt = sentence-transformers, boto3 (ngày 5 / Bedrock)
└── tests/                 # unit (không cần Weaviate/mạng) · integration (pytest -m integration)

bench_out/search/          # SBENCH_HOME, thêm vào .gitignore
├── data/items.parquet · vocab.json · text_<variant>.parquet · vec_<variant>_<model>.npy/.ids.json · llm_summaries.jsonl · synth_*.jsonl
├── data/_sample/ · data/_fake/   # cùng bố cục cho --dataset sample | fake (không đè catalog thật)
├── cache/embeddings.sqlite · cost.jsonl · tokenizers/   # dùng chung mọi dataset
├── runs/<run_id>/<arm>/results.json · results@<gold_version>.json · per_query.parquet
├── runs/<run_id>/stages/<stage>.json      # trạng thái cổng + đề xuất
└── reports/<run_id>/*.md · reports/regression/<date>.md
```

- Gốc repo = thư mục chứa `.git`. `SBENCH_HOME` mặc định `<repo>/bench_out/search`.
- Text builder production có sẵn: `src/backend/app/domain/catalog/text_builder.py::build_text` (repo không có hàm tên `build_embed_text`) — import dùng lại cho variant **`T3+R`** (bản production dự kiến, dùng ở B0) và ghi `text_builder: app` vào `stats.json`; các variant khác vẫn ở `textbuild.py`. Từ 24/09 builder là `catalog-text-v2` (merge `release-mvp-v1`): khung 5 ô HEADLINE · FIT · FEATURES · ROLLUP · EXCERPT, không đưa giá / ngày / điểm đánh giá vào text, tuyến bay không lấy description. Bench gọi đúng như `PostgresCatalogReader` của production: truyền phòng / chuyến bay con, `combo_items` (tính trong bộ nhớ bằng `data_collection.seed.parse_combos` + `combo_items_manual.jsonl` đi kèm snapshot) và thuộc tính combo mà loader gắn (`priceBasis / nights / minPax`); ghi `text_builder_version` vào meta. **Người dùng chốt 24/09: B0 = bản production này**, không phải T3 dựng từ tóm tắt LLM; T1 / T3 / `R` của `textbuild.py` phục vụ cổng E1a.
- `src/evaluation/vector_bench/` có `filters.py`, `dataset/amenities.py`, `dataset/catalog.py`, `lexical.py` (không có `gold.py`): import dùng lại, không chép.
- Không tạo folder `utils` chung.

### 1.2 Config — `config/sbench.yaml`

```yaml
run:
  seed: 42
  default_run_id: dev            # sb run ghi <YYYYMMDD-HHMM>-<git sha>

catalog:
  products_path: src/data_collection/data/snapshots/2026-09-23/products.jsonl   # bản bung (gitignore) của snapshot
  snapshot_path: src/data_collection/snapshots/2026-09-23/products.jsonl.gz      # thiếu bản bung → tự bung, kiểm checksum
  sample_path: src/data_collection/sample/products-sample.jsonl
  search_unit_variants: [hotel_property, flight_route, attraction, combo, golf]  # variant = taxonomy + attributes.level (như catalog.product_meta)
  amenity_seed_path: src/evaluation/vector_bench/config/amenity_seed.yaml
  amenity_scope: property_plus_rooms
  amenity_min_freq: 5
  amenity_fuzzy_min: 0.6          # similarity trigram kiểu pg_trgm

text:                             # Part 2
  max_words: 150
  max_amenities: 12
  max_room_names: 8
  max_description_words: 60
  sentence_df_drop: 20            # modifier DF: câu xuất hiện ở > 20 sản phẩm bị loại
  desc_words_by_modifier: {w30: 30, w60: 60, w150: 150, wfull: null}   # modifier wN; mặc định w60
  token_p99_max: 450              # gate
  token_hard_max: 512

embedding:                        # Part 3
  provider: cohere                # cohere | bedrock | local | fake
  models:
    cohere-v3: {api_model: embed-multilingual-v3.0, dim: 1024, max_batch: 96, truncate: NONE}
    cohere-v4: {api_model: embed-v4.0, dim: 1024, max_batch: 96, output_dimension: 1024, truncate: NONE}
    bge-m3:    {hf_model: BAAI/bge-m3, dim: 1024, max_seq_length: 512, device: cpu, batch_size: 16}
    gte-mb:    {hf_model: Alibaba-NLP/gte-multilingual-base, dim: 768, max_seq_length: 512, device: cpu, batch_size: 32, trust_remote_code: true}   # E2.gte, tuỳ chọn
    fake:      {dim: 1024}
  input_type: {document: search_document, query: search_query}
  bedrock: {model_id: cohere.embed-multilingual-v3, region: ap-southeast-1}
  retry: {max_attempts: 6, backoff_s: [1, 2, 4, 8, 16, 32]}
  cost_per_1m_tokens_usd: {cohere-v3: 0.10, cohere-v4: 0.12}   # xác nhận lại trên trang giá chính thức
  max_inputs_per_min: 2000        # (đề xuất) giới hạn tốc độ Cohere — pacer phía app
  max_tokens_per_min: 90000       # (đề xuất) đo 24/09: key trial trả 429 quanh 90–100k token/phút — pacer đếm token offline

weaviate:                         # Part 4
  url: http://127.0.0.1:58080     # cổng riêng: Weaviate 1.27 của app (docker-compose.yml gốc) giữ 8080/50051
  grpc_port: 55051
  image: semitechnologies/weaviate:1.37.3      # pin; cần ≥ 1.37 cho text_analyzer ascii_fold
  load_batch_size: 200            # (đề xuất)
  vector_index: flat              # < 10k object → exact
  bm25: {k1: 1.2, b: 0.75, tokenization: word, stopwords_preset: none}   # (đề xuất) none: preset mặc định 'en' của Weaviate
                                  # bỏ các âm tiết Việt trùng stopword tiếng Anh (an, be, no, to, the…) — 'Hội An', 'bể bơi'
  ascii_fold: analyzer            # analyzer | shadow  (shadow = property *_ascii do app tạo, fallback)
  hybrid_default: {fusion: ranked, alpha: 0.5}
  query_timeout_s: 5

gold:                             # Part 5
  target: 200                     # mục tiêu tham khảo — 28/09: không bắt buộc đủ, lấy mọi câu người soát chọn
  minimum: 39                     # 13 slice × min_per_slice (trước: 150)
  pool_depth: 15
  overlap_queries: 25
  kappa_min: 0.6
  judged_at_10_min: 0.80
  judged_at_10_slice_min: 0.70     # cổng Part 12 chặn nếu slice nào thấp hơn
  min_per_slice: 3                # 28/09 (người dùng chốt): mỗi slice ≥ 3 câu (trước: 10)
  slices:                         # mục tiêu tham khảo mỗi slice — không cắt, không bắt đủ
    dest_type: 25
    audience_style: 20
    amenity_single: 15
    amenity_multi: 10
    amenity_negation: 10
    amenity_offtaxonomy: 10
    parent_child: 15
    named_entity: 20
    no_diacritics: 20
    abbrev_typo: 15
    multi_constraint: 20
    cross_vertical: 10
    out_of_catalog: 10
    taxonomy_collision: 5          # 05/10 (gold_v4, D3): nối cuối SLICES — target 211, minimum 45
    flight_direction: 6

synth:                            # Part 7
  per_unit: 8
  strata: [dest_type, audience, amenity, no_diacritics, abbrev]
  retrieve_depth: 20
  reranker: BAAI/bge-reranker-v2-m3
  keep_if_rank_le: 3

metrics:                          # Part 8
  k: 10
  ndcg_gain: pow2                 # 2^rel - 1
  mrr_relevant_min: 2
  recall_relevant_min: 1
  extra_recall_k: [5]             # (đề xuất) docs/prd/test-plan.md §2.5: Recall@K với K = 5, 10
  bootstrap: 1000
  win_rule: {min_delta_recall: 2.0, p_max: 0.05, max_slice_loss: 3.0, tie_delta_ndcg: 2.0}
  guards:
    constraint_precision_min: 0.95
    parent_dup_max: 1
    zero_result_in_catalog_max: 0.02
    hub_score_max: 3.0
    p95_cache_miss_ms_max: 250      # = NFR-PERF-01 (p95 ≤ 250 ms); p99 được đo và báo cáo, không có ngưỡng (PRD không đặt)
  rerank_keep_if_delta_ndcg: 3.0
  hub_random_queries: 500

latency:                          # Part 9
  embed_calls: 500
  cache_hit_rates: [0.0, 0.5, 0.8]
  load_qps: 50
  load_seconds: 60
  embed_timeout_ms: 150

holes:                            # Part 11
  k: 10                           # quét top-k của per_query
  auto_label_out_of_catalog: true # query expected_no_result → hole tự gán 0, src=auto_ooc
  labeler: A                      # người gán hole (không phải người dựng arm)

stages:                           # Part 12 (cấu trúc cổng ở config/stages.yaml)
  file: config/stages.yaml
  pipeline_checks:                # sanity cứng — hỏng là dừng chuỗi
    input_type_min_cos_gap: 0.005     # 1 − cos(embed_q, embed_d) trung bình trên 200 query gold phải > giá trị này
    cache_recheck_n: 20               # embed lại n text ngẫu nhiên không qua cache, cos với cache phải ≥ 0.999
  default_model: cohere-v3        # quyết định team 23/09; cổng E2 không tự đổi model

regression:                       # Part 13
  max_drop_ndcg: 2.0              # điểm nDCG@10 overall, kèm p < 0.05
  max_slice_drop: 3.0
  p_max: 0.05
  latency_warn_ratio: 1.3         # p95 Weaviate local tăng > 30% → WARN (không FAIL)
  watch_paths:                    # đổi file nào thì phải chạy regression
    - src/evaluation/search_bench/textbuild.py
    - src/evaluation/search_bench/qu.py
    - src/evaluation/search_bench/config/aliases.yaml
    - src/evaluation/search_bench/config/sbench.yaml
    - src/backend/app/**/text_builder*.py
    - src/data_collection/snapshots/*/products.jsonl.gz
    - src/evaluation/search_bench/gold/gold.jsonl
```

`.env` (file `.env` ở gốc repo; sbench chỉ nạp các khoá trong danh sách cho phép, không ghi đè biến môi trường thật): `COHERE_API_KEY`, `AWS_PROFILE` (nếu bedrock), `LLM_PROVIDER` + key (Part 2 T3, Part 7). Không commit `.env`.

```yaml
doctor:                           # (đề xuất) Part 0
  min_free_gb: 5
  min_weaviate_version: "1.37"
```

### 1.3 CLI

| Lệnh | Part |
|---|---|
| `sb doctor` | 0 |
| `sb catalog build [--source jsonl\|sample\|fake]` · `sb catalog vocab` | 1 |
| `sb text --variant T3+R [--limit N] [--show 20]` · `sb tokens --variant T3+R` · `sb enrich summaries` | 2 |
| `sb embed --variant T3+R --model cohere-v3 [--limit N] [--input-type document]` · `sb cost` | 3 |
| `sb load --variant T3+R --model cohere-v3` · `sb collection list\|drop <name>` · `sb query "<q>" --arm B0` | 4 |
| `sb gold pool [--drafts gold/drafts.txt] [--depth 15] [--slice s] [--qid case\|line]` · `sb gold split [--overlap 25]` · `sb gold kappa LABELS_A LABELS_B [--meta] [--min]` · `sb gold merge LABELS_A LABELS_B [-o] [--meta]` · `sb gold import MERGED [--meta] [--catalog] [-o] [--provenance]` · `sb gold check [GOLD] [--min-per-slice N]` (Part 11 thêm `--catalog` cho check) | 5 |
| `sb qu "<q>"` · `sb qu test gold/qu_cases.yaml` | 6 |
| `sb synth generate` · `sb synth filter` · `sb synth load --variant V --model M --mode doc\|qry` | 7 |
| `sb run --arm <id> [--arm <id>…] [--gold PATH] [--allow-untagged] [--model M] [--force]` (`--run-id` là option toàn cục; mặc định `<YYYYMMDD-HHMM>-<git sha>`; arm đã có kết quả cùng `resolved_config_hash` + `gold_version` trong run thì bỏ qua trừ `--force`; `--allow-untagged` chỉ để chạy thử, kết quả ghi `gold_version: null` và không được trích dẫn / promote; gold ngoài `gold/` ghi `fixture:<sha8>`) · `sb compare <arm> <arm> [--gold gold_vN] [--condensed]` (cùng run; mặc định gold version mới nhất hiện có, yêu cầu cả hai arm có kết quả trên version đó; đọc cả bản `results@<version>.json`; `--condensed` bỏ kết quả chưa nhãn rồi dồn hạng, đồng thời báo full judged và retained ratio) · `sb app-load [--recreate]` (cổng APP: dựng collection `ProductBench` hình dạng production từ vector B0 — `arms.md` "Cổng APP"; `sb run` tự gọi khi có arm `engine: app`) · `sb list-arms [--resolved]` · `sb arms check` | 8 |
| `sb latency http --base-url URL [--queries config/latency_queries.yaml] [--runs 3] [--drop-first] [--limit 10] [--label L]` (30/09: đo `/search` thật qua HTTP — Cloud hoặc local) · `sb parity [--mode http\|weaviate] [--queries config/parity_queries.yaml] [--k 10]` (30/09) · `sb latency embed --models M[,M…] [--gold PATH] [--warmup 20] [--delay-ms 0]` (đã làm 01/10: từng query gold active, no-cache, bỏ warm-up; `delay-ms` nghỉ giữa request API và nằm ngoài khoảng đo để tránh rate limit; ghi `runs/<run_id>/latency-embed.json`) · `sb latency e2e` · `sb latency load` (hai lệnh sau chưa làm) | 9 |
| `sb report final [--run-id R]` · `sb report arm <id>` | 10 |
| `sb gold holes [--stage S \| --arms A,B] [--run-id R] [--cap N]` · `sb gold holes import <csv>` · `sb gold retire <qid> --reason "…" [--gold] [--version]` · `sb gold verify-append <old> [<new>]` · `sb rescore [--run-id R] [--gold gold_vN]` (`sb gold import` cũng nhận `--version` cho mục changelog) | 11 |
| `sb sanity --arms A,B [--gold] [--n-queries]` (30/09: kiểm tra cứng 12.2 chạy rời, trước khi có máy trạng thái cổng; exit 1 = `SANITY_FAIL`) · `sb run --stage S [--until T] [--auto-promote] [--force]` · `sb compare --stage S` · `sb promote <arm> [--note "…"] [--override-guard]` · `sb ack <stage> --note "…"` · `sb unpromote <stage>` · `sb status` | 12 |
| `sb regression baseline set --flow <P*> --note "…"` · `sb regression run [--reason "…"] [--latency] [--rescore-only <run_id>]` | 13 |

### 1.4 Định dạng kết quả

`runs/<run_id>/<arm>/results.json`:

```json
{"arm": "S2.ranked", "stage": "S2", "parent": "S0", "run_id": "20260929-1030-ab12cd3",
 "gold_version": "gold_v1", "gold_sha256": "…", "resolved_config_hash": "sha1 của YAML arm sau khi giải @-tham chiếu",
 "stale": false,
 "model": "cohere-v3", "text_variant": "T3+R", "collection": "products__T3+R__cohere_v3",
 "overall": {"recall@10": 0.71, "ndcg@10": 0.58, "mrr@10": 0.62, "judged@10": 0.84,
             "constraint_precision": 0.97, "filter_recall_loss": 3, "parent_dup_rate": 0.4,
             "zero_result_in_catalog": 0.01, "zero_result_out_of_catalog": 1.0, "hub_score_max": 2.1},
 "by_slice": {"dest_type": {"recall@10": 0.8, "ndcg@10": 0.7, "n": 25}, "...": {}},
 "latency_ms": {"weaviate_p50": 8, "weaviate_p95": 15, "weaviate_p99": 22},
 "cost_usd": {"embed_docs": 0.05, "embed_queries": 0.001, "rerank": 0.0},
 "vs_parent": {"delta_recall": 2.4, "ci95": [0.6, 4.1], "p_one_sided": 0.012}}
```

Runner (30/09) ghi thêm: `gold_path`, `dataset`, `n_items`, `k`, `created_at`, `n_queries`, `n_defined` (số câu mỗi metric thật sự tính), `embed` (`model`, `input_type`, `n_new`, `n_cached`, `usd`, `n_calls` của lượt embed câu), `needs_labels` (danh sách lý do NEEDS_LABELS theo `gold.judged_at_10_min` / `judged_at_10_slice_min`, rỗng = đạt), và `condensed` (`overall`, `by_slice`, `coverage`) để đọc chất lượng trên kết quả đã nhãn khi pool đã chạm cap. Metric full vẫn là số chính; condensed luôn đi cùng `coverage.full_results`, `coverage.judged_results`, `coverage.retained_ratio`, `coverage.empty_queries`. `by_slice` có thêm `zero_result` (tỷ lệ câu không kết quả trong slice; slice out_of_catalog cao là đúng) và `constraint_precision` (null nếu slice không có câu filter). `vs_parent` chỉ có khi `parent` là id arm đã chạy trong cùng run và cùng `gold_version`; `cost_usd.embed_docs` null (chi phí embed catalog xem `sb cost`).

`per_query.parquet`: `qid, slice, top_ids (top-10, đúng thứ tự trả về), top_scores, ranks_of_relevant, recall, ndcg, mrr, constraint_ok, n_dup_parent, zero_result`. `top_ids` là thứ duy nhất cần để tính lại metric khi gold thêm nhãn (Part 11 `rescore`) — không bao giờ bỏ cột này. Runner ghi thêm `expected_no_result`, `judged@k`, `recall@5`, `constraint_n`, `filter_recall_loss`, `applied_filter` (JSON của filter arm đã áp, để `rescore` tính lại `filter_recall_loss`) và `latency_ms` (một lượt gọi store).

### 1.5 Quy ước khác

- Mọi con số vào config; code không có hằng số ngưỡng.
- `sb run` từ chối chạy nếu `gold/gold.jsonl` hiện tại không khớp một tag git `gold_v*`. Hai kết quả chỉ được so khi cùng `gold_version`; khác version thì `sb compare` tự `rescore` bản cũ lên version mới (Part 11) rồi mới so — không bao giờ so chéo version.
- Mỗi lượt gọi Cohere ghi `cost.jsonl`: `ts, model, input_type, n_texts, n_tokens, usd`.
- Log: `structlog`, level qua `--verbose`.
- Không commit `bench_out/`. Commit `arms/`, `gold/`, `config/`, `state/`, `regression/`.

### 1.6 `requirements.txt`

`requirements.txt` (lõi, venv riêng `.venv-sbench`):

```
typer, pydantic>=2, pyyaml, structlog, numpy, pandas, pyarrow, httpx
weaviate-client>=4.23,<5  # bản đã kiểm có Configure.text_analyzer (ascii_fold) và Vectors.self_provided
cohere>=5
tokenizers               # đếm token Cohere offline (Part 2)
symspellpy
unidecode
scipy                    # bootstrap
pytest
streamlit>=1.64,<2       # app soát draft gold (streamlit_app.py) — cùng file này vì Streamlit Community Cloud chỉ tự nhận requirements.txt cạnh entrypoint hoặc ở gốc repo
```

`requirements-extra.txt` (chỉ khi cần):

```
torch, transformers      # model local: e5-base, bge-m3, gte (embed/local_hf.py — mean / cls pooling theo model card; 30/09: thay
                         # sentence-transformers vì gói đó kéo scipy mà DLL scipy bị Application Control chặn trên máy dev)
boto3                    # chỉ khi bedrock
```

Config model local (`embedding.models.<key>`): `hf_model`, `dim`, `max_seq_length`, `device`, `batch_size`, `pooling: mean | cls`, `query_prefix` / `passage_prefix` (e5 bắt buộc `query: ` / `passage: `). Tên embedder (khoá cache, `cache_model` của collection) = `hf_model`. `sb tokens --model <key>` đếm bằng tokenizer HF của model, kể cả prefix, hard max = `max_seq_length`; text vượt bị từ chối lúc embed (không cắt ngầm).

### 1.7 Việc Claude Code KHÔNG được tự quyết

1. Không đổi quota slice, ngưỡng metric, quy tắc chọn — chỉ đọc config.
2. Không bật `truncate=END`. Text vượt 512 token là lỗi của text builder.
3. Không đổi `input_type` mặc định; arm E3 là arm **duy nhất** cố tình đặt sai.
4. Không sửa `gold/gold.jsonl` bằng code ngoài `sb gold import` (kể cả `--append`, 05/10), `sb gold holes import`, `sb gold retire` — cả ba chỉ **thêm**, không sửa nhãn đã có.
5. Không thêm arm ngoài `arms.md` + `config/stages.yaml`; `sb arms check` phải xanh trước mọi `run --stage`.
6. Không promote khi cổng ở trạng thái `SANITY_FAIL` hoặc `NEEDS_LABELS`; không bỏ qua `--note` khi promote khác đề xuất.
7. `--auto-promote` không bao giờ đổi model khỏi `stages.default_model` và không bao giờ vượt cổng `SANITY_WARN`.
8. Không cập nhật `regression/baseline.json` ngoài lệnh `sb regression baseline set` có `--note`; CI không có quyền chạy lệnh này.

---

## Part 0 — Khung, compose, `doctor`

**`docker/compose.yml`** — một service:

```yaml
name: sbench                                 # project riêng → volume sbench_weaviate_data, không đụng stack app
services:
  weaviate:
    image: ${WEAVIATE_IMAGE:-semitechnologies/weaviate:1.37.3}
    command: ["--host", "0.0.0.0", "--port", "8080", "--scheme", "http"]
    ports:                                   # chỉ loopback (deployment-plan §2); 8080/50051 để cho Weaviate của app
      - "127.0.0.1:${SBENCH_WEAVIATE_HTTP_PORT:-58080}:8080"
      - "127.0.0.1:${SBENCH_WEAVIATE_GRPC_PORT:-55051}:50051"
    environment:
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: "true"
      PERSISTENCE_DATA_PATH: /var/lib/weaviate
      DEFAULT_VECTORIZER_MODULE: none        # app tự cung cấp vector
      ENABLE_MODULES: ""                     # không bật text2vec-cohere: cần kiểm soát input_type + cache
      QUERY_DEFAULTS_LIMIT: 25
      LIMIT_RESOURCES: "true"
      CLUSTER_HOSTNAME: node1                # giữ metadata cluster khi container được tạo lại
    volumes: [weaviate_data:/var/lib/weaviate]
volumes: {weaviate_data: {}}
```

Chạy từ `src/`: `docker compose -f evaluation/search_bench/docker/compose.yml up -d --wait weaviate`.

Không dùng module `text2vec-cohere` vì (a) `nearText` không cache được vector query, (b) bench cần embed query ở app để đo RTT và mô phỏng cache hit — đúng khuyến nghị `EMBEDDING_STACK_SWITCH.md` §6.2.

**`sb doctor`** kiểm và in ✔/✖: Docker daemon; Weaviate `/v1/.well-known/ready` và version ≥ `doctor.min_weaviate_version`; `ascii_fold` trong config làm được không (server ≥ 1.37 và client có `text_analyzer` — không thì ✖, gợi ý đặt `shadow`); cổng Weaviate mở được (Windows: gợi ý `netsh int ipv4 show excludedportrange protocol=tcp`); `COHERE_API_KEY` (gọi `co.tokenize("xin chào", offline=False)`, in số token, chi phí 0 — vẫn tính một lượt gọi, ghi vào `cost.jsonl`); `products.jsonl` hoặc snapshot tồn tại và số dòng; `bge-m3` có tải được (chỉ cảnh báo); dung lượng trống ≥ `doctor.min_free_gb`; `git` có tag `gold_v*` hay chưa (chỉ thông tin).

**Done khi:** `sb doctor` xanh với Weaviate lên; đỏ có hướng dẫn sửa từng dòng.

---

## Part 1 — Catalog → `items.parquet`

Đọc `products.jsonl` (contract `docs/spec/data-collection/schema.md` §3; thiếu bản bung thì bung `catalog.snapshot_path`, kiểm checksum bằng `data_collection.seed.snapshot`). Search unit = `variant ∈ search_unit_variants`, với `variant` = `taxonomy` + `attributes.level` như view `catalog.product_meta` (`hotel` → `hotel_<level>`, `flight` → `flight_route` khi `level = route`) — trường `taxonomy` của jsonl chỉ có `hotel · flight · attraction · combo · golf`. Phòng / chuyến bay không thành item nhưng được gom vào cha (`parentProductId`) để lấy từ vựng phòng, hãng bay, min giá. `--source sample|fake` ghi vào `data/_sample/`, `data/_fake/` (các lệnh sau chọn bằng `--dataset`) để không đè catalog thật.

Cột `items.parquet`: `product_id, taxonomy, variant, name, brand, destination, province, city, property_type, star_rating, audience[], family_friendly, ocean_view, ticketed, nights, amenities_raw[], amenity_ids[] (smallint), room_vocab[] (từ con, khử trùng), airlines[] (từ con), description, description_is_derived, description_source, unit_price_min, review_score, lat, lon, parent_product_id (null với search unit), n_children`.

`amenity_ids`: map theo `amenities.py` (alias exact / cụm từ dài nhất sau NFC/unaccent/lower — `vector_bench/dataset/amenities.py` → similarity trigram kiểu `pg_trgm` (Jaccard tập trigram) > `amenity_fuzzy_min` = 0,6, tự cài — **không** dùng `rapidfuzz` ratio vì trên snapshot nó map sai ~141 chuỗi, ví dụ `ban công → bữa sáng` → còn lại `raw:<slug>` nếu tần suất ≥ `amenity_min_freq`). Mọi lần khớp trigram ghi ra `amenity_fuzzy_hits.csv` để Người A soát. Id không ổn định khi vocab đổi → filter trong gold ghi **khoá** amenity (`kids_club`, `raw:<slug>`), không ghi id; `catalog build` từ chối nếu id của khoá đã có bị đổi (trừ `--allow-id-drift`). Chỉ có trạng thái **có** (mảng), không có `false`/`unknown` — theo quyết định 23/09. **05/10 (gold_v4, D11):** chuỗi "Không có …" (phủ định) và chuỗi khoảng cách tới nơi lân cận ("Chợ Đà Lạt 1,6 km", "… 570 m") bị bỏ trước khi khớp (`amenities.is_not_amenity`) — trước đó "Không có Thang máy" thành `elevator` ở 74 khách sạn; build lại đổi `items_sha256` và id amenity (`--allow-id-drift`), phải `sb load` lại collection (vector lấy từ cache, text không đổi).

`sb catalog vocab` → `vocab.json`: danh sách destination, tên sản phẩm + brand, amenity (khoá, label, id), hạng phòng, airline, mã IATA; kèm bản bỏ dấu; mục `filter_fields` (miền giá trị của trường lọc được: taxonomy, variant, destination, khoảng sao/giá, khoá amenity) để Người A viết filter JSON. Dùng cho Part 5 (draft gold), Part 6 (gazetteer, SymSpell), Part 7 (synthetic).

`stats.json`: số search unit theo taxonomy, coverage amenity, % description derived, phân bố `n_children`.

**Done khi:** `sb catalog build --source sample` ra 26 search unit (50 dòng mẫu gồm 15 phòng + 9 chuyến bay); `--source jsonl` in số search unit thật (snapshot 2026-09-21: 2.897; 2026-09-23: 3.183); `vocab.json` có ≥ 10 destination.

---

## Part 2 — Text builder: base + modifier, đếm token

Một hàm `build(item, variant) -> str`. Chuẩn hoá NFC, dấu kiểu mới, không bỏ dấu, không `key: value`, không số giá/toạ độ/ngày/mã (trừ modifier control `KV`, `NUM`).

**Variant là chuỗi ghép** `<base>[+<modifier>…]`, thứ tự modifier chuẩn hoá theo bảng dưới (ví dụ `T3+R+DF`, `T2+R+w150`). Chuỗi chuẩn hoá dùng làm tên collection, khoá cache và `text_variant` trong results. Lý do ghép thay vì 8 biến thể cố định: `R` (từ vựng phòng) và `DF` phải thử được trên **base thắng** của cổng E1a, không chỉ trên T3 — nếu không, khi LLM summary (T3) không thắng thì lợi ích của `R` không bao giờ được đo.

| Base | Nội dung |
|---|---|
| T0 | `description` gốc như trong jsonl (baseline hiện trạng) |
| T1 | template canonical: tên → loại + destination → đối tượng/flag → ≤ 12 amenity dạng cụm; **không** description (theo `EMBEDDING_AND_ENGINES` §2.6) |
| T2 | T1 + description gốc ≤ `wN` từ **chỉ khi** `description_is_derived = false` |
| T3 | T1 + tóm tắt LLM 2–3 câu từ `data/llm_summaries.jsonl` khi derived; description gốc ≤ `wN` từ khi không derived (cần `sb enrich summaries`) |

| Modifier (thứ tự chuẩn) | Nội dung | Áp lên |
|---|---|---|
| `R` | + `room_vocab` ≤ 8 hạng phòng; flight_route thêm hãng + "bay thẳng"; combo thêm câu tổng hợp BOM | mọi base |
| `DF` | loại câu có DF > `sentence_df_drop` (DF theo câu đã chuẩn hoá trên toàn catalog, tính một lần) | mọi base |
| `w30` · `w60` · `w150` · `wfull` | độ dài phần description; mặc định `w60` (không ghi trong tên) | T0, T2, T3 (T1 không có description → modifier bị từ chối) |
| `KV` | viết lại toàn bộ thành `key: value` từng dòng — **control** | chỉ dùng trong E1.T6 |
| `NUM` | + "Giá từ X đ, điểm đánh giá Y, toạ độ (lat, lon)" — **control** | chỉ dùng trong E1.T7 |

Mapping arm → variant (chi tiết ở `arms.md`): B0 = `T3+R` · E1.T0–T3 = `T0`…`T3` · E1.T4 = `@E1a+R` · E1.T5 = `@E1a+R+DF` · E1.T6 = `T3+R+KV` · E1.T7 = `T3+R+NUM` · E4.* = `@E1b+w30|w150|wfull`. `@E1a` là base được promote ở cổng E1a (Part 12).

`sb enrich summaries`: gọi LLM (provider từ `.env`) với prompt: *chỉ dùng attributes cho sẵn, cấm thêm địa điểm/giá/tiện ích không có, 2–3 câu, giữ amenity và đối tượng có giá trị tìm kiếm*. Output `llm_summaries.jsonl {product_id, summary, prompt_hash}`; cache theo `sha1(attributes)`. In 5% ngẫu nhiên ra `summaries_review.csv` để soát tay.

`sb tokens --variant`: đếm bằng tokenizer của Cohere v3 tải **một lần** (`models.get(...).tokenizer_url`) vào `cache/tokenizers/`, đếm offline, tính cả token đặc biệt, **không** fallback gọi API (key trial chỉ 1.000 lượt/tháng) cho toàn bộ text của variant → in p50/p90/p99/max và danh sách item > `token_p99_max`. **Gate:** p99 ≤ 450 và max < 512, nếu không exit code 2. `sb embed` dùng cùng bộ đếm để từ chối trước khi gọi API text > `token_hard_max`.

**Done khi:** `sb text --variant T3+R --show 20` in 20 văn bản; `T1+w150` bị từ chối với thông báo rõ; `T3+DF+R` được chuẩn hoá thành `T3+R+DF`; snapshot test 5 item cố định cho mỗi base và mỗi modifier; `sb tokens --variant T3+R` qua gate trên dữ liệu thật.

---

## Part 3 — Embedding provider + cache

`Embedder.embed(texts: list[str], input_type: Literal["document","query"]) -> np.ndarray[float32, (n, dim)]`, L2-normalise đầu ra.

| Provider | Chi tiết |
|---|---|
| `cohere_api.py` | `cohere.ClientV2`; `co.embed(model, texts, input_type=map[input_type], embedding_types=["float"], truncate="NONE")`; batch ≤ 96; `embed-v4.0` thêm `output_dimension=1024`; arm E6 dùng `embedding_types=["int8"]` rồi cast float; retry 429/5xx theo `retry`; ghi `cost.jsonl` với `meta.billed_units.input_tokens` |
| `bedrock.py` | `boto3 bedrock-runtime.invoke_model(modelId, body={"texts", "input_type": search_document/search_query, "truncate": "NONE"})`; region `ap-southeast-1` |
| `local_st.py` | `SentenceTransformer("BAAI/bge-m3")`, `max_seq_length=512`, không prefix; CPU; in tốc độ text/s |
| `fake.py` | vector = hash(`input_type` + text) → RNG chuẩn, normalise; cùng (input_type, text) → cùng vector, để test khung và để kiểm tra `input_type` của Part 12 chạy được; cờ `--fake-ignore-input-type` giả lập lỗi `input_type` không tới API |

`cache.py`: sqlite `embeddings.sqlite(key TEXT PK, model, input_type, dim, vec BLOB, created_at)`, `key = sha1(model|input_type|text)`. `embed` luôn qua cache; `--no-cache` để đo RTT (Part 9).

`sb embed --variant V --model M` → `data/vec_<V>_<M>.npy` + `vec_<V>_<M>.ids.json` + `vec_<V>_<M>.meta.json`; in số text embed mới / lấy từ cache / số lượt gọi / token / USD. Khoá cache ghi chuỗi model API kèm tuỳ chọn làm đổi vector (`@int8`, `@d<dim>`; fake bật `--fake-ignore-input-type` → `@noit`) để các chế độ không dùng lẫn vector của nhau.

**Bẫy:** (1) query và document phải cùng model, khác `input_type`; (2) `E3` cố tình embed query bằng `document` — chỉ arm này; (3) không chạy hai `sb embed` Cohere song song (rate limit 2.000 input/phút — client tự giãn theo `embedding.max_inputs_per_min`, tôn trọng `Retry-After`).

**Done khi:** `--model fake` chạy toàn catalog < 10 s; `--model cohere-v3 --limit 96` gọi đúng 1 lượt, chạy lần 2 gọi 0 lượt; `sb cost` in tổng USD.

---

## Part 4 — Adapter Weaviate

**Collection** `products__<variant>__<model_slug>` (một collection / cặp variant × model; không dùng multi-tenancy). Tên này là tên **logic** (ghi trong results). Weaviate chỉ nhận tên khớp `^[A-Z][_0-9A-Za-z]*$`, nên tên **vật lý** là `Products__<variant, "+"→"_">__<model, "-"→"_">`, thêm hậu tố `__<dataset>` khi dataset không phải `jsonl` — ví dụ `products__T3+R__cohere_v3` → `Products__T3_R__cohere_v3`. Mô tả collection (JSON) ghi tên logic, dataset, `items_sha256`, số object, variant, model, `ascii_fold_mode`, text builder.

- Vector: named vector `content` do app cung cấp (`Configure.Vectors.self_provided(name="content")` ở client ≥ 4.16, hoặc `Configure.NamedVectors.none(name="content")` ở client cũ hơn), `vector_index_config = Configure.VectorIndex.flat()`, distance cosine. Part 7 thêm named vector `query_vec` cùng cách.
- Property: `product_id (TEXT, không tokenization cho BM25 — `skip_vectorization` không liên quan vì self-provided)`, `taxonomy, variant, destination, province, brand (TEXT, tokenization field)` — các property `field` đặt `index_searchable=False` (chỉ để lọc) và BM25 luôn truyền `query_properties` tường minh, `name (TEXT, word)`, `embed_text (TEXT, word)`, `amenity_ids (INT[])`, `parent_product_id (TEXT, field)`, `star_rating (NUMBER)`, `unit_price_min (NUMBER)`, `ticketed, family_friendly, ocean_view (BOOL)`, `available (BOOL, mặc định true)`.
- Fold dấu cho BM25: `ascii_fold: analyzer` → cấu hình `text_analyzer(ascii_fold=True)` cho `name`, `embed_text` (Weaviate ≥ 1.37). Nếu client chưa có API này → `ascii_fold: shadow`: app tạo thêm `name_ascii`, `embed_text_ascii` (unidecode, lower) và BM25 `query_properties=["name_ascii^2", "embed_text_ascii"]` với query cũng fold. `doctor` in cách nào đang dùng; results.json ghi `ascii_fold_mode`.

**Query** (`WeaviateStore`):

| Hàm | Weaviate |
|---|---|
| `dense(qvec, filters, limit, target="content")` | `near_vector(near_vector=qvec, target_vector=target, filters, limit, return_metadata=distance)` |
| `bm25(q, filters, limit)` | `bm25(query=q_folded_if_shadow, query_properties, filters, limit, return_metadata=score)` |
| `hybrid(q, qvec, alpha, fusion, filters, limit, max_distance=None)` | `hybrid(query, vector=qvec, target_vector="content", alpha, fusion_type=HybridFusion.RANKED\|RELATIVE_SCORE, query_properties, filters, limit, max_vector_distance)` |
| `max_sim_query_vec(qvec, filters, limit)` | `near_vector(target_vector="query_vec")` trên collection có nhiều object / product (Part 7) → gộp theo `product_id` lấy max ở app |
| `count(filters)` / `facets(filters, prop)` | `aggregate.over_all(filters, total_count=True)` / `aggregate.over_all(group_by=prop)` — exact khi không có vector |

Filter AST (JSON, dùng lại `vector_bench/filters.py` nếu có): `{"and": [{"eq": ["destination", "Nha Trang"]}, {"in": ["taxonomy", [...]]}, {"contains_all": ["amenity_ids", [3, 17]]}, {"not": {"contains_any": ["amenity_ids", [5]]}}, {"lte": ["unit_price_min", 3000000]}, {"gte": ["star_rating", 4]}]}` → `weaviate.classes.query.Filter`.

Cài đặt (24/09): `store/filters.py` — `validate` · `resolve` (khoá amenity → id theo `amenity_vocab.json`) · `to_weaviate` · `mask` (evaluator pandas). `not` chỉ bọc `eq` trên trường không null (`product_id, taxonomy, variant, destination`) hoặc `contains_any` trên `amenity_ids` (→ `contains_none`; sản phẩm không ghi nhận amenity nào vẫn thoả). Collection bật `index_null_state`. 50 filter ngẫu nhiên khớp pandas 100%.

Dedupe theo cha: làm ở app (lấy `limit × 3`, giữ ≤ 1 / `parent_product_id`, cắt `limit`) — không phụ thuộc `group_by` của Weaviate với hybrid.

`sb load` batch `weaviate.load_batch_size` (200) object, `wait_ready`, verify `count ==` số id trong `vec_<V>_<M>.ids.json` (khác `n_items` khi embed có `--limit`).

**Done khi:** `sb load --variant T3+R --model fake` xong < 1 phút; `sb query "resort Nha Trang" --arm B0` in top-10 với distance; `bm25` với query không dấu "da nang" trả sản phẩm Đà Nẵng (chứng minh fold dấu chạy — "nha trang" không có dấu nên không chứng minh gì); filter `contains_all` trả đúng so với evaluator tham chiếu trên pandas (test 50 filter ngẫu nhiên).

---

## Part 5 — Gold

Định nghĩa nhãn và luật gán: **`docs/spec/bench/gold-guide.md`** (chốt 25/09). Tóm tắt: **2** = đúng thứ khách tìm · **1** = liên quan một phần (đúng nơi nhưng sai loại hoặc thiếu điều kiện) · **0** = không liên quan; câu có nêu destination mà sản phẩm sai destination → **0** kể cả đúng loại (thay câu "đúng loại hoặc đúng nơi → 1" chép từ `VECTOR_DB_BENCH_SPEC` P6.3). Cặp chưa gán = không có dòng trong file nhãn.

Hợp đồng file giữa các bước (pool, nhãn, merged, meta, `gold.jsonl`): `src/evaluation/search_bench/gold_schema.py` (bước 0, `docs/spec/bench/README.md`). Mã thoát của nhóm lệnh `sb gold`: **0** đạt · **1** dữ liệu vi phạm luật · **2** lỗi đầu vào (file thiếu, sai định dạng, sai sha).

`gold/drafts.txt`: mỗi dòng `query \t slice [\t filter_json] [\t expected_no_result]`.

| Lệnh | Việc |
|---|---|
| `sb gold drafts` | nhãn của app soát draft (`bench_out/search/labels/labels.jsonl`: KEEP / REJECT / NEEDS_EDIT) → `gold/drafts.txt`: lấy nhãn mới nhất theo `(case_id, annotator)`, bất đồng giữa annotator thì **bỏ qua và báo**, `NEEDS_EDIT` thay câu bằng `edited_query`, **giữ một cách nói cho mỗi ý định** (3 dòng liền nhau trong `drafts_raw.tsv` = 1 ý định; riêng `out_of_catalog` mỗi dòng là một ý định vì 3 dòng là 3 taxonomy), rồi cắt theo `gold.slices`. In bảng quota/thiếu/chưa gán; `--dry-run` chỉ in. `--fill`: slice thiếu quota thì lấy lại **1 cách nói** của ý định chưa có — chỉ nhận ý định *chưa gán* hoặc *bị loại toàn bộ vì cách nói* (`duplicate`/`unnatural`); bỏ qua ý định bị loại vì lỗi thật (`fabricated_entity`/`bad_grounding`/`invalid_filter`/`wrong_slice`), ý định trùng khoá `review_note` ở `dest_type`/`out_of_catalog` (hai slice duy nhất mà note là khoá đủ), và ý định mà mọi `source_refs` đã chết hoặc `filter_json` khớp 0 sản phẩm. Một dòng bị loại vì lỗi thật (hoặc REJECT trong `overrides.tsv`) loại **cả ý định**, kể cả khi còn dòng chưa gán; ở `dest_type`/`out_of_catalog` loại luôn mọi dòng cùng `review_note` (vd. "resort ở X" bị loại vì X có trong catalog thì không lấp "vé tham quan X"). Trong một ý định, lấy cách nói đầu tiên chưa gán hoặc chỉ bị loại vì trùng — không lấy câu người soát đã đánh `unnatural`. `gold/overrides.tsv` (`case_id, verdict, edited_query, reason, note`, commit) ghi đè nhãn của app cho từng case khi người dùng chốt sửa một quyết định — thắng mọi nhãn kể cả bất đồng, bắt buộc có `note`; dùng thay cho việc ghi event giả mạo tên annotator vào kho nhãn | **Luật 28/09 (người dùng chốt):** mặc định lấy **mọi** ý định người soát chọn (KEEP / NEEDS_EDIT, kể cả trong `overrides.tsv`), **không cắt** theo `gold.slices` (chỉ còn là mục tiêu tham khảo) và **không tự lấp**; mỗi slice cần ≥ `gold.min_per_slice` = 3 câu (thiếu thì in cảnh báo, vẫn ghi — `gold check` chặn ở bước cuối). `--fill` vẫn dùng được để lấp slice dưới mục tiêu. App Streamlit, chế độ **Bộ câu đã chọn**, tính giống hệt và cho thêm / thay / viết lại / loại từng câu (ghi `overrides.tsv`).
| `sb gold pool [--drafts] [--depth 15] [--slice] [--qid case\|line]` | với mỗi draft: dense top-15 (`cohere-v3`, `T3+R` = collection của B0) ∪ BM25 top-15, cùng filter **đầy đủ** của draft → `gold/pool.csv` đúng `POOL_COLUMNS` của `gold_schema` + `pool.build.json` (snapshot, collection, depth, seed, sha `drafts.txt` và pool). qid = `case_id` của `drafts_raw.tsv` (khớp query + slice, kể cả `edited_query` trong `overrides.tsv` **cạnh** `drafts_raw.tsv` — 05/10: đọc từ thư mục của `--raw`, ví dụ `gold/v4a/`; `--qid line` = `q001…` cho fixture). Filter ghi ra tách hai phần: `filter_json` cấp parent và `child_filter_json` (giá / số khách / ngày, `CHILD_FILTER_FIELDS`; `unit_price_min` của drafts → `unit_price`), kèm `filter_text` tiếng Việt. Mỗi dòng mang `taxonomy` (= variant), `destination`, `star_rating`, tối đa 12 tiện ích (trong filter → khớp câu hỏi → seed → raw), `snippet` (40 từ đầu text B0), `children` (hạng phòng của `hotel_property`); không có cột giá. Câu thường không có ứng viên → exit 1 (`--allow-empty` để vẫn ghi) |
| `sb gold split [--overlap 25] [--force]` | `pool_A.csv`, `pool_B.csv` (`write_pool_csv`) + `pool_meta.json` (`write_pool_meta`: snapshot, collection B0, depth, seed, sha `drafts.txt`, sha và số dòng từng file, `overlap_qids`), ghi `is_overlap`. **Luật 29/09** (drafts chốt 132 câu; trước đó: câu riêng xen kẽ A/B theo số câu, thứ tự câu hai file như nhau). Câu chung: slice có ≥ 2 câu có **≥ 1 câu chung** (κ phủ mọi slice, kể cả out_of_catalog), phần còn lại theo tỷ lệ slice (largest remainder, hoà → tên slice; chỉ số nguyên); trong slice lấy **mẫu hệ thống theo cỡ pool** (điểm đầu ngẫu nhiên, mỗi slice một luồng RNG). Câu riêng: cân theo **số cặp** — mỗi slice và tổng lệch ≤ 1 câu, rồi đổi chéo A↔B trong cùng slice tới khi không một lần đổi nào thu hẹp được \|cặp A − cặp B\| (thường ≤ 1, không bảo đảm); không dựa vào nội dung câu. Thứ tự câu: mỗi slice một **khối liền**; A đi các slice theo thứ tự pool, **B bắt đầu từ slice ở khoảng giữa** (lệch nửa vòng); trong khối, câu riêng xáo riêng từng người (giữ thứ tự `case_id` thì câu chung chen vào sẽ lộ) và câu chung đặt cách đều với điểm lệch riêng từng người → thứ tự câu không cho biết câu nào là câu chung, và mỗi câu chung được hai người gán ở hai thời điểm xa nhau (cần không slice nào quá nửa số câu; lệnh cảnh báo nếu không đạt) (`gold-guide.md` mục Gán độc lập). Ứng viên trong câu: mỗi người một thứ tự xáo riêng (seed + qid + người gán). Kiểm sha `pool.csv` với `pool.build.json`; đã có `gold/labels/*.csv` thì không ghi đè meta trừ khi `--force`. In: số câu / cặp mỗi file, số câu / cặp chung, lệch số cặp, câu chung theo slice (k/n), slice bắt đầu của A và B; **không in qid câu chung** trừ khi `--show-shared` (người chạy lệnh có thể là người gán) |
| `sb gold kappa LABELS_A LABELS_B [--meta] [--min]` | chỉ trên các cặp của `overlap_qids`; câu chung còn thiếu nhãn → exit 1. In ma trận nhầm (A theo hàng), **κ linear** (quyết định, ngưỡng `gold.kappa_min`), κ không trọng số và quadratic để tham khảo, các cặp lệch 2 bậc |
| `sb gold merge LABELS_A LABELS_B [-o gold/labels/merged.csv]` | mọi cặp của pool phải có nhãn, nhãn hợp lệ với dòng pool (thiếu / thừa / sai → exit 1). Cặp một người gán: lấy nhãn đó (`source` A/B). Cặp chung: bằng nhau giữ; lệch 1 bậc → nhãn thấp hơn; lệch 2 bậc → `needs_discussion=true`; cả hai gán 2 thì `children_ok` = phần giao, rỗng ở parent_child → `needs_discussion`. Note của người gán nối sau dạng ` \| A: …`. Người gán sửa dòng `needs_discussion` ngay trong `merged.csv` (`gold-guide.md`) |
| `sb gold import MERGED [--catalog] [-o gold/gold.jsonl] [--provenance pool@gold_v1] [--overwrite]` | → `GoldRecord` (`{qid, text, slice, filter, child_filter, expected_no_result, judgments, provenance, expected_children, status}`, ghi bằng `write_gold_jsonl`). Từ chối (exit 1) nếu còn `needs_discussion`, thiếu / thừa cặp so với pool, `product_id` không có trong catalog snapshot hoặc là sản phẩm con, `children_ok` không phải con của sản phẩm đó, `validate_label_against_pool` báo lỗi; sha pool lệch meta → exit 2. `-o` đã có mà khác nội dung → exit 2 trừ khi `--overwrite` (Part 11: gold chỉ thêm). **`--append` (05/10, gold_v4+):** nối các câu mới của pool vào **cuối** gold đang có thay vì ghi file mới — qid đã có (kể cả retired) → exit 1; provenance từng nhãn theo `labels/provenance_<X>.csv` cạnh `pool_meta.json` (người / máy bị sửa → `pool@<version>`, máy được duyệt giữ nguyên → `pool:machine@<version>`); nhãn máy chưa duyệt → exit 1 trừ khi `--accept-unreviewed` (`pool:machine_unreviewed@…`); `verify-append` với gold cũ phải xanh; changelog `action: import_append` kèm `new_queries`, `new_labels_by_source`. `--provenance` mặc định `pool@<version>` |
| `sb gold check [GOLD] [--min-per-slice N]` | trên câu `active`: câu thường ≥ 1 nhãn 2; out_of_catalog không có nhãn 2 và có `expected_no_result`; nhãn 2 ở parent_child có `expected_children`; slice thuộc danh sách, qid không trùng; mỗi slice **có mặt** ≥ N câu (mặc định `gold.min_per_slice`; slice cấu hình mà vắng chỉ cảnh báo). In bảng số câu / số nhãn 0-1-2 theo slice; xanh thì nhắc `git tag gold_v1` |

**Done khi:** `sb gold pool` + `split` trên 10 draft fixture (`--qid line`) ra pool đọc được bằng `read_pool_csv`, sha trong meta khớp file; trên `tests/fixtures/gold_small/`: `kappa` ra κ linear = `expected.json`, `merge` trùng từng byte `merged_expected.csv`, `import merged_expected.csv` bị từ chối và `import merged_resolved.csv --catalog catalog_small.jsonl` trùng từng byte `gold_expected.jsonl`, `check --min-per-slice 1` xanh / mặc định đỏ (`tests/test_gold_cli.py`). *(Bản trước: `import` + `check` xanh trên `tests/fixtures/gold_small.jsonl` — fixture cũ của metrics, dùng config riêng cho test `tests/fixtures/config_test_overrides.yaml` — `gold.min_per_slice: 1`, vì fixture chỉ có 10 query trải 9 slice; `config/sbench.yaml` giữ 10.)* Fixture đó vẫn dùng cho metrics (Part 8).

---

## Part 6 — Query understanding, alias, SymSpell

`qu(q) -> QU{semantic_text, destination?, taxonomy?, price_max?, star_min?, pax?, amenity_must[], amenity_nice[], amenity_not[], ticketed?, applied_aliases[], corrections[]}`.

Thứ tự: NFC → lower bản phụ → alias (`config/aliases.yaml`: `KS→khách sạn, NT→Nha Trang, PQ→Phú Quốc, ĐN→Đà Nẵng, VW→VinWonders, KDL→khu nghỉ dưỡng, tr/triệu…`) → SymSpell (từ điển = `vocab.json` bỏ dấu, max edit 2, chỉ sửa token không có trong từ điển tiếng Việt thường dùng) → gazetteer destination / tên sản phẩm (match dài nhất, cả bản có dấu và không dấu) → taxonomy cue (`vé máy bay, chuyến bay → flight_route`; `vé, tham quan → attraction`; `combo, trọn gói → combo`; `resort, khách sạn, villa → hotel_property`) → số: giá (`dưới 3 triệu`, `< 3tr`), sao (`5 sao`), khách (`4 người`, `2 người lớn 1 trẻ`) → amenity: `phải có / bắt buộc / cần` → must; `không / không có / không cần` trước amenity → not; còn lại → nice; amenity không map được taxonomy → giữ trong `semantic_text`.

`semantic_text` = query gốc bỏ phần đã thành filter số/giá (giữ tên địa danh và amenity trong text để dense vẫn có tín hiệu).

`sb qu test gold/qu_cases.yaml` (≥ 30 case tay: input → QU mong đợi) → in exact-match rate theo trường.

**Done khi:** exact-match ≥ 90% trên `qu_cases.yaml` cho destination/taxonomy, ≥ 80% cho amenity must/not; "resort PQ có kids club dưới 3tr cho 4 người" → destination Phú Quốc, taxonomy hotel_property, price_max 3.000.000, pax 4, amenity_nice [kids_club].

---

## Part 7 — Synthetic query → named vector `query_vec`

1. `sb synth generate`: LLM sinh `per_unit` query / search unit theo `strata` (mỗi tầng ít nhất 1), ràng buộc dùng đúng destination/amenity của item; 20% query viết không dấu, 15% dùng viết tắt từ `aliases.yaml` → `synth_raw.jsonl {product_id, query, stratum}`. Cache theo `sha1(item_text)`.
2. `sb synth filter`: embed query (`cohere-v3`, `input_type=query`) → dense top-20 trên collection `T3+R` → cross-encoder `bge-reranker-v2-m3` chấm 20 cặp → giữ query nếu `product_id` gốc ở rank ≤ `keep_if_rank_le` → `synth_kept.jsonl`; in tỷ lệ giữ theo stratum (kỳ vọng 50–70%). CPU: ~7k query × 20 cặp, 1–2 giờ; `--limit` để thử.
3. `sb synth load --variant V --model M --mode doc|qry`: collection `queries__<variant>__<model>__<mode>` với object `{product_id, query, stratum}` và vector `query_vec` = embed(query, `input_type` = `document` khi `--mode doc`, `query` khi `--mode qry`). Chưa có bằng chứng chế độ nào tốt hơn cho vector phụ → arm **E5.doc** và **E5.qry** chạy cả hai; cổng E5 (Part 12) chọn chế độ, cổng P quyết định có dùng vector phụ hay không (P2 vs P3). Cache khoá theo `input_type` nên hai chế độ là hai lần embed riêng, mỗi lần ~$0,02.

Arm E5.doc / E5.qry retrieve: dense `content` top-50 ∪ `query_vec` top-50 của collection đúng `--mode` (gộp max theo `product_id`) → RRF k=60.

**Done khi:** `generate --limit 20` ra 160 query; `filter --limit 20` in tỷ lệ giữ; `load` count đúng.

---

## Part 8 — Arm runner, metric, so cặp

**Chiếu rubric v4 lúc chấm (06/10, người dùng chốt phương án b).** `runner.load_env` sau khi gắn chú giải: với câu có `allowed_variants` (query_annotations.yaml — variant catalog không vi phạm loại cốt lõi, kể cả phương án thay thế rubric cho 1 như combo cho câu hỏi vé / vé máy bay), nhãn ≥ 1 của sản phẩm có `variant` ngoài danh sách tính là 0 (`metrics.project_rubric_v4`); gold.jsonl không đổi, nên 161 nhãn 1 cũ "đúng nơi sai loại" của câu v3 không còn được gain. Tắt bằng `metrics.rubric_v4_projection: false`. results.json ghi `rubric_v4_projection {enabled, pairs, queries, annotated_queries}`, per_query ghi `v4_projected_n`. Số chạy trước 06/10 (chưa chiếu) không so trực tiếp với số sau — rescore.

**Arm YAML** (`arms/<id>.yaml`):

```yaml
id: S2.ranked
stage: S2
parent: "@S1"                     # tham chiếu arm được promote ở cổng S1
description: hybrid RRF k=60 (RANKED)
inherit: "@S1"                    # lấy mọi trường của arm cha, chỉ ghi đè trường dưới
retrieval: hybrid                 # dense | bm25 | hybrid | dense+query_vec
fusion: {type: ranked, alpha: 0.5}    # alpha chỉ dùng với relative_score
```

Trường đầy đủ sau khi giải (`sb list-arms --resolved`):

```yaml
text_variant: T3+R                # hoặc "@E1a+R" — giải thành chuỗi variant chuẩn
model: cohere-v3
embedding_types: float            # E6: int8
query_input_type: query           # E3: document
retrieval: dense
query_vec: null                   # {mode: doc|qry} cho E5.*, P3
fusion: null
bm25: {tokenization: word, k1: 1.2, b: 0.75}
filters: {qu: false, amenity_must: none}   # none | filter | boost
boost: {amenity_nice_w: 0.0, amenity_must_w: 0.0}
dedupe_parent: false
query_preproc: {alias: false, symspell: false}
cutoff: {max_vector_distance: null}
csls: null                        # S9: {k: 10, top: 50}
rerank: null                      # S8, P6: {model: rerank-v3.5, top_n: 25}
fallback_bm25_only: false         # F1
phase: 1                          # S10 = 3; runner từ chối phase > 1 trừ khi --allow-phase3
```

**Tham chiếu `@`.** `@<stage>` = arm được promote ở cổng đó (đọc `state/promotions.yaml`, Part 12); `@<stage>+R` chỉ dùng trong `text_variant` = variant của arm đó ghép thêm modifier. `arms.py` từ chối chạy arm có tham chiếu tới cổng chưa promote, và in rõ cổng còn thiếu. `resolved_config_hash` = sha1 của YAML sau khi giải — đổi promotion thì hash đổi và kết quả cũ thành `stale`.

`arms.py` so arm với arm cha đã giải: cấm khác > 1 **nhóm trường** (danh sách nhóm ở Phụ lục A; trừ arm `P*`, ghi `composite: true`, và arm sweep sinh nhiều cấu hình như `S1.k1b`, `S7`).

**Bẫy `bm25.k1/b` (S1.k1b).** `k1`, `b` là cấu hình của collection. Runner **không** sửa collection dùng chung; nó tạo collection clone `…__k1_<k1>_b_<b>` từ vector đã cache (không tốn API) rồi chạy trên clone.

**CSLS (S9).** Tính trước một lần cho mỗi collection: `r_d` = cosine trung bình của `d` tới `k` láng giềng gần nhất trong catalog (numpy, exact). Lúc query: lấy dense top-`top`, `score' = 2·cos(q, d) − r_d`, xếp lại rồi mới fusion.

**Runner** với mỗi query gold: `qu` (nếu bật) → preproc → embed query (cache) → retrieval theo arm → boost/rerank/dedupe ở app → top-10 → ghi `per_query`. `expected_no_result` query: đúng khi top-1 distance > cutoff hoặc không có kết quả.

**Metric** (`metrics.py`, k=10):

- `recall@10` = |{d ∈ top10 : rel(d) ≥ 1}| / |{d : rel(d) ≥ 1}|; query không có rel ≥ 1 bị loại khỏi trung bình (báo số).
- `ndcg@10` = DCG/IDCG, gain `2^rel − 1`, chưa gán nhãn = 0.
- `mrr@10` = 1/rank của rel = 2 đầu tiên, 0 nếu không có.
- `judged@10` = tỷ lệ top-10 có nhãn.
- `constraint_precision` = trên query có `filter` (slice `multi_constraint`, amenity must/not): tỷ lệ kết quả thoả filter theo evaluator tham chiếu pandas; phủ định: tỷ lệ kết quả **không** chứa amenity bị phủ định.
- `filter_recall_loss` = số (qid, product) có rel ≥ 1 nhưng bị filter cứng loại — chỉ arm có `amenity_must: filter`.
- `parent_dup_rate` = trung bình số kết quả cùng `parent_product_id` vượt 1 trong top-10.
- `zero_result_in_catalog` / `zero_result_out_of_catalog`.
- `hub_score_max`: 500 query ngẫu nhiên (lấy từ `synth_kept` hoặc gold nếu chưa có synth) → đếm số lần mỗi product lọt top-20 / kỳ vọng (= 500 × 20 / n_items) → max.
- `vs_parent`: paired bootstrap `bootstrap` lần trên vector per-query Δrecall và Δndcg → mean, CI95, p một phía = P(Δ ≤ 0).

`sb compare A B` in bảng overall + by_slice + Δ + CI + p, và **kết luận theo win_rule**: `WIN` (Δrecall ≥ 2, p < 0,05, không slice thua > 3), `TIE` (|Δndcg| < 2), `LOSE`. Kết luận cặp này để đọc report; **chọn arm thắng ở cổng dùng `select()`** của Part 10 (Part 12).

**Done khi:** trên `gold_small.jsonl` + `--model fake`, mọi metric ra số và bằng tính tay cho 3 query; `compare` giữa một arm và chính nó cho Δ = 0, p = 0,5.

---

## Part 9 — Latency đường nóng

| Lệnh | Đo |
|---|---|
| `sb latency http --base-url URL` | **(đã làm 30/09)** `GET /api/v1/search?q=…&limit=10` thật (Cloud `https://v-ota.duckdns.org` qua BFF, hoặc backend local) trên hai nhóm câu của `config/latency_queries.yaml`: `prewarmed` (25 câu gold active — nằm trong danh sách prewarm của backend) và `cold` (25 câu không có trong gold). `--runs 3`: mỗi lượt chạy hết 50 câu theo thứ tự; `--drop-first` bỏ lượt 1 khỏi bảng p50/p95 (làm nóng kết nối), nhưng lượt 1 vẫn là nguồn duy nhất của mẫu **miss** (`diagnostics.embedCache = miss`, contract 1.12.0; lần gặp đầu của mỗi câu). Ghi mỗi mẫu: `client_ms` (wall phía client, gồm mạng), `latencyMs` (route, server), `stageMs.*` (engine, contract 1.11.0), `embedCache`, `searchMode`, top-10 `productId` |
| `sb parity --mode http` | **(đã làm 30/09)** cùng 20 câu `config/parity_queries.yaml` (≥ 1 câu mỗi slice trong 13 slice + "VinWonders", "KS biển tại NT", "Vinpeal Resort Nha Trang giá tốt") gửi tới hai `/search` (A = Cloud, B = local): top-1 trùng và overlap@10 từng câu. Chỉ để chẩn đoán deployment: catalog local (snapshot bench) ≠ catalog VM nên lệch một phần là do dữ liệu |
| `sb parity --mode weaviate` | **(đã làm 30/09)** M4 đúng nghĩa "index Cloud = index local": cùng `SearchProducts` in-process (cổng APP) trên **catalog VM** (`PostgresCatalogReader` qua `SBENCH_VM_DATABASE_URL`), kho A = collection `Product` trên Weaviate Cloud, kho B = collection `ProductVM` trên Weaviate bench dựng từ **vector kéo về từ Cloud** (`WeaviateClient.fetch(include_vectors=True)`, 0 Cohere) — cùng vector, cùng text, chỉ khác Weaviate (phiên bản, hnsw). Trước khi Cloud có property BM25 (backfill C6) chỉ so dense; sau đó so hybrid + normalize như production |
| `sb latency embed --provider cohere\|bedrock --n 500 --no-cache` | *(chưa làm)* RTT một query cố định, p50/p95/p99, tỷ lệ lỗi/timeout; chạy tuần tự, không song song |
| `sb latency e2e --arm P2 --cache-hit 0 0.5 0.8` | *(chưa làm)* 200 query gold: với tỷ lệ hit h, h% query lấy vector từ cache, còn lại gọi API; p50/p95/p99 end-to-end = embed + Weaviate + app |
| `sb latency load --qps 50 --seconds 60` | *(chưa làm)* open-loop, ghi số 429/timeout theo giây; xác nhận `fallback_bm25_only` kích hoạt khi embed > `embed_timeout_ms` |
| `sb run --arm F1` | BM25-only trên gold — chất lượng của chế độ `degraded` |

Ghi `runs/<run_id>/latency.json` (`--label L` → `latency-L.json`; ví dụ `cache-off` trước PR cache, `cache-on` sau) và `runs/<run_id>/parity-<mode>.json`. Bảng của `latency http`: p50/p95 từng stage + tổng engine (`latencyMs`) + `client_ms` riêng; sau contract 1.12.0 tách **hit** / **miss** theo `embedCache`; `top10_stable` = số câu có top-10 giống nhau ở mọi lượt (miss vs hit phải giống 50/50 — cache chỉ đổi thời gian, không đổi kết quả). Cổng parity (`config/sbench.yaml` `latency.parity`): top-1 trùng ≥ 18/20 và overlap@10 ≥ 8/10 ở **mọi** câu có ≥ 8 kết quả
cả hai bên; câu ngắn hơn (out_of_catalog, tên riêng hiếm) phải cùng số kết quả và trùng hết (0 = 0 là trùng); in câu lệch.
Mode `weaviate` chờ shard `ProductVM` báo `READY` và hàng đợi index rỗng (`/v1/nodes?output=verbose`) sau khi nạp rồi mới
truy vấn — 01/10 truy vấn ngay sau khi nạp 3.183 object cho thứ tự sai (đúng tập ứng viên, sai thứ tự) và cổng FAIL 5/20 giả. Số đầu bảng lấy từ số server (`latencyMs` / `stageMs`); wall phía client báo riêng vì gồm RTT tới VM. Weaviate local không đại diện cho cloud; report ghi rõ. Biến môi trường (`.env.example`, chỉ nạp `SBENCH_*`): `SBENCH_CLOUD_BASE_URL`, `SBENCH_LOCAL_BASE_URL`, `SBENCH_CLOUD_WEAVIATE_URL`, `SBENCH_CLOUD_WEAVIATE_API_KEY`, `SBENCH_VM_DATABASE_URL`.

**Done khi:** `latency http` ra bảng trên Cloud với `stageMs` đủ khoá; `parity --mode weaviate` đạt cổng sau backfill C6; `embed --n 20` ra bảng; `e2e` với `--model fake` chạy; `load` ghi được ít nhất một 429 giả lập (fake provider có `--simulate-429-after N`).

---

## Part 10 — Report cuối và quy tắc chọn

`sb report final --run-id R` đọc `results.json` của các arm `P1…P6` (+ F1, latency.json, cost.jsonl) → `reports/R/FINAL.md`:

**Bảng 1 — 6 luồng:**

| Luồng | Recall@10 | nDCG@10 | MRR@10 | Slice yếu nhất (tên, Δ vs tốt nhất) | Constraint precision | Dup rate | Zero-result in/out | p95 cache-miss | p99 cache-miss | p95 cache 50% | $/1.000 query | Thành phần vận hành |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

"Thành phần vận hành" = đếm: Cohere embed, Weaviate, QU, alias/SymSpell, synth pipeline, rerank API, bge-m3 local — số càng nhỏ càng tốt.

**Bảng 2 —** nDCG@10 theo 13 slice × 6 luồng, tô đậm ô thua tốt nhất > 3 điểm.

**Bảng 3 —** chuỗi cổng theo `stages.yaml`, mỗi cổng một dòng: ứng viên, đề xuất của `select()`, arm được promote, override (kèm note), trạng thái sanity, `gold_version`; kèm Δ vs parent + WIN/TIE/LOSE của từng arm.

**Quy tắc chọn** — hàm `select(results, guards, order)` trong `report.py`, **dùng chung** cho bảng cuối và mọi cổng Part 12; in kèm lý do:

1. Loại luồng vi phạm guard: `constraint_precision < 0.95`, `parent_dup_max > 1`, `zero_result_in_catalog > 0.02`, `p95_cache_miss > 250 ms`, `zero_result_out_of_catalog < 1.0`.
2. Trong luồng còn lại: nDCG@10 cao nhất. Luồng khác chênh < `tie_delta_ndcg` **và** không slice nào thua > `max_slice_loss` → TIE → chọn theo `order`: ở bảng cuối là ít thành phần vận hành hơn, rồi rẻ hơn; ở cổng là thứ tự `candidates` trong `stages.yaml` (đơn giản trước).
3. P6 (rerank) chỉ được chọn nếu Δ nDCG ≥ `rerank_keep_if_delta_ndcg` so với luồng thắng không rerank và vẫn qua guard p95.
4. Nếu P5 (bge-m3) hơn luồng Cohere thắng ≥ 2 điểm ở slice `no_diacritics` hoặc `audience_style` → in **cảnh báo** "model mở thắng trên tiếng Việt của mình" — report không tự đổi quyết định.

Decision record template `reports/R/DECISION.md`: luồng, model, `model_version`, YAML luồng, bảng 1, 3 rủi ro (rate limit 33 QPS, API trên đường nóng, không fine-tune), việc tuần sau, người ký.

**Done khi:** trên run `--model fake` với 6 arm P giả, `report final` ra FINAL.md đầy đủ 3 bảng và một dòng "CHỌN: P2 vì …".

---

## Part 11 — Gold append-only: `gold holes`, `retire`, `rescore`

**Vấn đề.** Arm mới (T3, E5, S6…) kéo lên top-10 những sản phẩm chưa có trong pool gán nhãn ban đầu. Metric tính chúng là 0 → arm tìm ra thứ mới bị chấm thấp oan, và `judged@10` tụt. Part này lấp các "lỗ" đó mà không phá tính so sánh được của gold.

**Nguyên tắc append-only.** Gold chỉ được **thêm**: thêm query, thêm nhãn cho cặp (qid, product) chưa có nhãn, hoặc chuyển query `active → retired`. Không bao giờ sửa nhãn đã có. Mỗi lần thêm là một version mới (`gold_v2`, `gold_v3`…) có tag git và một mục trong `gold/changelog.yaml` (danh sách YAML; mỗi mục `version, at, action` (`import` | `retire` | `holes_import`), `n_queries_active, n_queries_retired, n_labels`, kèm `source` / `retired: [{qid, reason}]` / số nhãn mới theo nguồn tuỳ lệnh). `version` của một mục = tag `gold_v*` mới nhất + 1 (chưa có tag → `gold_v1`), hoặc `--version` nếu người chạy chỉ định; nhiều mục có thể cùng version khi chưa tag (ví dụ `import` rồi `retire` trước `gold_v1`). Version của `gold.jsonl` hiện tại xác định bằng git: file khớp blob `gold_vN:src/evaluation/search_bench/gold/gold.jsonl` → `gold_vN`, không khớp tag nào → chưa có version (`holes.gold_version_of`).

| Lệnh | Việc |
|---|---|
| `sb gold holes --arms A,B [--tag T] [--k] [--cap N] [--split] [--gold] [--out-dir] [--qids q1,q2] [--new-since TAG]` (05/10: `--qids` / `--new-since` chỉ quét các câu được chọn, hoặc câu chưa có trong TAG — để cap không bị loãng bởi câu cũ; `--stage S` khi có Part 12; `--run-id` toàn cục, mặc định run mới nhất) | Quét `per_query.parquet` của các arm → tập (qid, product_id) nằm trong top-`holes.k` mà chưa có nhãn. `--cap N` chọn tối đa N cặp theo round-robin giữa slice/query với seed cố định, trong mỗi query ưu tiên cặp do nhiều arm cùng kéo lên rồi hạng tốt hơn; `holes.json` vẫn ghi pool đã chọn → **thư mục** `gold/holes/<gold_version>__<tag>/` (30/09, thay cho một csv): `pool_A.csv` [+ `pool_B.csv` khi `--split`: chia câu xen kẽ hai người, không câu chung] đúng `POOL_COLUMNS` (`snippet` = 40 từ đầu text B0, `from`/`rank_dense` = hạng tốt nhất — app ẩn hai cột này; **xáo thứ tự trong mỗi qid, không ghi arm nào kéo lên**), `pool_meta.json` để app gán nhãn mở như pool thường (nhãn ghi `<thư mục>/labels/labels_X.csv`), `meta.csv` (arm, hạng tốt nhất, số arm thấy, người gán — nội bộ), `auto_ooc.csv`, `holes.json` (run, arm, k, gold_version, số cặp). Câu sắp theo số arm thấy giảm dần. Không có hole → exit 1 |
| — | Query `expected_no_result=true` (slice out_of_catalog): mọi hole tự gán 0 với nguồn `auto_ooc` (người gán đã khẳng định catalog không có sản phẩm đúng) — không đưa vào file gán |
| `sb gold holes import <thư mục> [--gold] [--version] [--partial]` | Thêm nhãn của `labels/labels_X.csv` vào `gold.jsonl` với `provenance = "holes:<tag>@<version>"` và hole out_of_catalog với `"auto_ooc:<tag>@<version>"` (nhãn 0); nhãn 2 kèm `children_ok` → `expected_children`. Từ chối (exit 1) nếu một cặp đã có nhãn, nhãn sai luật với dòng pool, nhãn gắn pool khác sha, hoặc còn cặp chưa gán (trừ `--partial`); ghi mục `holes_import` vào `changelog.yaml` (`new_labels_by_source: {human, auto_ooc, queries}`); in lệnh `git tag gold_vN+1` cần chạy. **05/10:** thư mục hole có `labels/provenance_<X>.csv` (nhãn máy qua `gold machine-import`) thì nhãn máy chưa duyệt → exit 1 trừ `--accept-unreviewed`; nhãn máy được duyệt giữ nguyên → provenance `holes:<tag>:machine@<version>`, `new_labels_by_source` thêm `machine`, `machine_unreviewed` |
| `sb gold retire <qid> --reason "…" [--gold] [--version]` | `status: retired` — query bị loại khỏi metric từ version này, nhãn đã gán giữ nguyên; ghi mục `retire` vào `changelog.yaml`. Dùng khi catalog đổi làm query mất nghĩa (ví dụ query out_of_catalog "resort ở Sapa" mà catalog vừa có Sapa), và **trước tag `gold_v1`** khi pool bỏ sót sản phẩm đúng nên câu không thể có nhãn 2 (`pool_miss`, chốt 30/09 — c0463; câu có thể thêm lại ở version sau bằng qid mới). Câu không có hoặc đã retired → exit 1. Sau `retire` không chạy lại `import --overwrite` (import đặt lại mọi câu thành `active`) |
| `sb gold check --catalog` | Ngoài kiểm tra Part 5: cảnh báo query out_of_catalog mà destination / tên trong câu nay đã có trong `vocab.json` |
| `sb gold verify-append <old> [<new>]` | `old` / `new` là tag hoặc commit (`git show <ref>:gold/gold.jsonl`) hoặc đường dẫn file; `new` mặc định là `gold/gold.jsonl` đang có. Mọi qid của bản cũ còn trong bản mới; câu cũ giữ nguyên `text` / `slice` / `filter` / `expected_no_result`; mọi nhãn cũ giữ nguyên giá trị **và provenance**; `expected_children` cũ còn nguyên; `status` chỉ đổi `active → retired`. Sai → exit 1, in từng vi phạm. Chạy trong CI và trước mọi `promote` |
| `sb rescore [--arms A,B] [--gold PATH] [--allow-untagged]` (`--run-id` toàn cục, mặc định run mới nhất) | Tính lại metric của các arm trong run từ `top_ids` (và `applied_filter`) đã lưu trên gold hiện tại → `results@<gold_version>.json` + `per_query@<gold_version>.parquet` cạnh bản gốc (tên file dùng version đã làm sạch: `fixture:ab12` → `fixture_ab12`, vì dấu `:` là NTFS stream trên Windows; `gold_version` thật đọc trong JSON; ghi `rescored_from`, `rescored_at`, `queries_missing_in_run`). **Không gọi lại Weaviate hay Cohere.** Latency, embed, cost chép nguyên; câu retired rời khỏi metric, câu mới thêm mà run chưa có bị bỏ qua và đếm. `sb compare` mặc định chọn version cao nhất hiện có trong hai arm, yêu cầu cả hai có bản đó; `--gold gold_vN` chọn version cụ thể, đọc cả bản rescore, thiếu bản thì báo chạy `sb rescore` |

**Ai gán:** `holes.labeler` (Người A — không dựng arm). Kỳ vọng vài chục cặp mỗi cổng, 15–30 phút *(ước lượng, chưa đo)*.

**Done khi:** trên fixture có 3 cặp chưa gán trong top-10 (1 thuộc query out_of_catalog): `holes` ra file 2 dòng + 1 nhãn `auto_ooc`; `holes import` tăng version và `verify-append` xanh; sửa tay một nhãn cũ → `verify-append` đỏ; `rescore` đưa `judged@10` về 1,0 và metric khớp với chạy lại từ đầu.

---

## Part 12 — Chạy theo cổng: `stages.yaml`, `run --stage`, `promote`, `status`

**Mục tiêu.** Chạy 43 arm theo chuỗi có phụ thuộc mà không ai phải nhớ "arm này lấy text nào, model nào": mỗi cổng chạy hết arm của nó, `select()` đề xuất arm thắng, người (hoặc `--auto-promote`) promote, cổng sau tự lấy cấu hình qua tham chiếu `@<stage>`.

### 12.1 `config/stages.yaml`

Thứ tự trong file = thứ tự chạy. `candidates` xếp **đơn giản trước** — đây là `order` của `select()` khi TIE. `guards` = guard của Part 10 áp dụng từ cổng đó.

```yaml
stages:
  - {id: B0,  arms: [B0], gate: reference}

  - id: SAN                                   # chạy ngay sau B0: eval hỏng thì biết sớm
    arms: [E3, E1.T6, E1.T7]
    gate: sanity
    hard: [input_type_vectors_differ, cache_recheck, collection_counts, gold_append_ok]
    soft:
      - {arm: E3,    expect: must_lose,     vs: B0}
      - {arm: E1.T6, expect: must_lose,     vs: B0}
      - {arm: E1.T7, expect: must_not_win,  vs: B0}

  - {id: E1a, arms: [E1.T0, E1.T1, E1.T2, E1.T3], candidates: [E1.T0, E1.T1, E1.T2, E1.T3], promotes: text}
  - {id: E1b, arms: [E1.T4, E1.T5], candidates: ["@E1a", E1.T4, E1.T5], promotes: text}
  - id: E4
    arms: [E4.w30, E4.w150, E4.full]
    candidates: ["@E1b", E4.w30, E4.w150, E4.full]
    skip_if: {base_of: "@E1b", in: [T1]}      # T1 không có description
    promotes: text
  - id: E2
    arms: [E2.v4, E2.bge, E2.gte]
    optional: [E2.gte]
    candidates: ["@E4", E2.v4, E2.bge, E2.gte]
    promotes: model
    gate: model                               # đề xuất ≠ stages.default_model → DECISION_NEEDED
  - {id: E6, arms: [E6], run_if: {provider_of: "@E2", is: cohere}, gate: info}
  - {id: E5, arms: [E5.doc, E5.qry], candidates: [E5.doc, E5.qry], promotes: query_vec_mode}

  - {id: S0, arms: [S0], gate: reference}
  - id: S1
    arms: [S1.word, S1.whitespace, S1.k1b]
    optional: [S1.k1b]
    candidates: [S1.word, S1.whitespace, S1.k1b]
    promotes: bm25
  - id: S2
    arms: [S2.ranked, S2.rs_a03, S2.rs_a05, S2.rs_a07]
    candidates: ["@S0", S2.ranked, S2.rs_a05, S2.rs_a03, S2.rs_a07]
    promotes: retrieval
  - {id: S3, arms: [S3], candidates: ["@S2", S3], guards: [constraint_precision], promotes: filters}
  - {id: S4, arms: [S4a, S4b], candidates: ["@S3", S4b, S4a], guards: [constraint_precision], promotes: filters}
  - {id: S5, arms: [S5], candidates: ["@S4", S5], guards: [constraint_precision, parent_dup], promotes: dedupe}
  - {id: S6, arms: [S6], candidates: ["@S5", S6], guards: [constraint_precision, parent_dup], promotes: preproc}
  - id: S7
    arms: [S7]                                # arm sweep → S7.d030 … S7.d060
    candidates: ["@S6", "S7.*"]
    guards: [constraint_precision, parent_dup, zero_result_in, zero_result_out]
    select: cutoff                            # thoả guard → nDCG cao nhất → TIE thì cutoff lỏng hơn
    promotes: cutoff
  - id: S9
    arms: [S9]
    run_if: {metric_of: "@S7", metric: hub_score_max, gt: 3.0}
    candidates: ["@S7", S9]
    guards: [constraint_precision, parent_dup, zero_result_in, zero_result_out, hub]
    promotes: csls                            # bị skip → promote kế thừa @S7
  - {id: S8, arms: [S8], gate: info}          # thông tin sớm; quyết định rerank nằm ở P6
  - {id: F1, arms: [F1], gate: info}
  - {id: S10, arms: [S10], disabled: phase3}

  - id: Pa                                    # luồng Cohere mặc định
    arms: [P1, P2, P3]
    candidates: [P2, P3]                      # P1 chỉ để báo cáo
    guards: [constraint_precision, parent_dup, zero_result_in, zero_result_out]
    promotes: flow
  - id: Pb                                    # model thay thế trên đúng cấu hình @Pa
    arms: [P4, P5]
    recalibrate: [S7]                         # cutoff phụ thuộc model → sweep lại cho từng model
    gate: info
  - {id: Pc, arms: [P6], gate: info}          # luồng tốt nhất của Pa/Pb + rerank
  - id: FINAL
    candidates: [P1, P2, P3, P4, P5, P6]
    select: final                             # đủ 4 quy tắc Part 10, gồm guard p95 từ Part 9
    gate: human                               # luôn cần người ký, kể cả --auto-promote
    promotes: flow
```

Định nghĩa arm P (ghi trong `arms/P*.yaml`): P1 = `inherit: "@S0"` (text + model đã chốt, dense-only) · P2 = `inherit: "@S9"` (đủ pipeline, không vector phụ, không rerank) · P3 = P2 + `query_vec: {mode: "@E5"}` · P4 = `@Pa` với `model: cohere-v4` · P5 = `@Pa` với `model: bge-m3` (nếu `@Pa` đã dùng đúng model đó thì arm tương ứng bị skip vì trùng) · P6 = `@best(Pa, Pb)` + `rerank: {model: rerank-v3.5, top_n: 25}`. Collection còn thiếu cho P4/P5 (ví dụ `queries__…__bge_m3__qry`) được runner tự dựng từ cache, ghi chi phí.

### 12.2 Sanity cứng và mềm

| Loại | Kiểm tra | Hỏng thì |
|---|---|---|
| Cứng | `input_type_vectors_differ`: embed 200 query gold hai lần (`query` và `document`) bằng model của B0; trung bình `1 − cos` phải > `input_type_min_cos_gap` | `SANITY_FAIL` — `input_type` không tới API; mọi số sau đều vô nghĩa |
| Cứng | `cache_recheck`: embed lại `cache_recheck_n` text ngẫu nhiên không qua cache; cos với vector trong cache ≥ 0,999 | `SANITY_FAIL` — cache trả vector cũ / sai model |
| Cứng | `collection_counts`: mọi collection dùng trong cổng có `count == n_items` | `SANITY_FAIL` |
| Cứng | `gold_append_ok`: `verify-append` từ `gold_v1` tới bản hiện tại | `SANITY_FAIL` |
| Mềm | `must_lose`: Δ nDCG (arm − `vs`) trung bình < 0 **và** cận trên CI95 < 0 | `SANITY_WARN` — có thể dữ liệu thật khác tài liệu (ví dụ Cohere v3 ít nhạy với `input_type`); cần `sb ack SAN --note "…"` |
| Mềm | `must_not_win`: không đồng thời Δ nDCG ≥ `tie_delta_ndcg` và p < `p_max` | `SANITY_WARN` như trên |

Kiểm tra cứng chạy lại ở **mọi** cổng (rẻ), không chỉ SAN. Khi chưa có máy trạng thái cổng, `sb sanity --arms A,B` chạy bốn kiểm tra cứng rời (`sanity.py`, 30/09): số câu cho `input_type_vectors_differ` = min(200, số câu active của gold — gold_v1 có 131); `cache_recheck` tốn một lượt embed không qua cache cho mỗi model; `gold_append_ok` bỏ qua khi chưa có tag; model local e5 kiểm bằng cùng hàm (prefix khác → vector khác). Với `gte-mb` và `bge-m3` cấu hình `input_type_mode: symmetric`, dùng `input_type_vectors_match`: cùng text ở query/document phải cho cùng vector (max sai khác tuyệt đối ≤ 1e-5); model card [GTE](https://huggingface.co/Alibaba-NLP/gte-multilingual-base) và [BGE-M3](https://huggingface.co/BAAI/bge-m3) dùng chung encoder, không yêu cầu prefix. Các model asymmetric vẫn giữ cổng khác biệt > 0,005.

### 12.3 Trạng thái cổng

| Trạng thái | Nghĩa | Cách đi tiếp |
|---|---|---|
| `PENDING` | cổng phía trước chưa promote | chạy cổng trước |
| `SANITY_FAIL` | kiểm tra cứng hỏng | sửa pipeline, `sb run --stage S --force` |
| `NEEDS_LABELS` | có ứng viên `judged@10 < judged_at_10_min` hoặc slice `< judged_at_10_slice_min` | `sb gold holes --stage S` → gán → `holes import` → tag → `sb rescore` → cổng tự tính lại |
| `SANITY_WARN` | kiểm tra mềm hỏng | `sb ack <stage> --note` |
| `NO_CANDIDATE` | mọi ứng viên vi phạm guard | người xem; `sb promote <arm> --override-guard --note` |
| `DECISION_NEEDED` | cổng `model` đề xuất khác `default_model`, hoặc cổng `FINAL` | người `sb promote` |
| `READY` | có đề xuất | `sb promote <arm>` hoặc `--auto-promote` |
| `SKIPPED` | `skip_if` / `run_if` | tự promote arm kế thừa (`@` cổng trước), ghi lý do |
| `INFO_DONE` | cổng `info` / `reference` đã chạy | không cần promote |
| `PROMOTED` | xong | — |

### 12.4 Lệnh

- `sb run --stage S [--until T] [--auto-promote] [--force]`: chạy các arm của S (bỏ qua arm đã có kết quả cùng `resolved_config_hash` + `gold_version`, trừ `--force`) → kiểm tra cứng → metric → `select()` → ghi `runs/<run_id>/stages/S.json` (ứng viên, guard, bảng tie, đề xuất, lý do, trạng thái). Có `--until`: đi tiếp các cổng sau khi cổng hiện tại `PROMOTED`/`SKIPPED`/`INFO_DONE`; gặp trạng thái khác thì dừng và in việc cần làm.
- `--auto-promote`: chỉ promote khi `READY`. Không bao giờ vượt `SANITY_WARN`, `DECISION_NEEDED`, `NO_CANDIDATE`, `NEEDS_LABELS`; ghi `by: auto`. Dùng khi chạy qua đêm, sáng đọc `sb status`.
- `sb compare --stage S`: in bảng của `select()` — ứng viên, guard đạt/không, nDCG@10, Δ so với dẫn đầu + CI95, slice thua nhiều nhất, tập TIE, đề xuất.
- `sb promote <arm> [--stage S] [--note "…"] [--ack] [--override-guard]`: arm phải thuộc `candidates` của S. Khác đề xuất → bắt buộc `--note`. Ghi thêm một mục vào `state/promotions.yaml` (append-only):

```yaml
- stage: E1a
  arm: E1.T3
  proposed: E1.T3
  override: false
  note: ""
  gold_version: gold_v1
  run_id: 20260926-0930-ab12cd3
  resolved_config_hash: 9f2c…
  by: auto                    # hoặc git user.name
  at: 2026-09-26T09:41:00+07:00
```

- `sb ack <stage> --note "…"`: xác nhận `SANITY_WARN`, ghi vào `promotions.yaml` với `arm: null`.
- `sb unpromote <stage>`: thêm mục `arm: null`; mọi cổng phụ thuộc (qua `@`) thành `stale`, kết quả của chúng không được đọc cho tới khi chạy lại.
- `sb status`: bảng cổng theo thứ tự — trạng thái, đề xuất, arm promote, `by`, `gold_version`, số arm stale, chi phí API luỹ kế. Mục promote mới nhất của mỗi cổng là mục có hiệu lực.

### 12.5 Ví dụ một ngày

```bash
sb run --stage B0 --until E1b --auto-promote
# B0 INFO_DONE → SAN SANITY_WARN (E1.T7 không thua B0) → dừng
sb compare --stage SAN            # xem: T7 thêm giá nhưng Δ = +0,4, p = 0,31 → ngang, chấp nhận được
sb ack SAN --note "T7 ngang B0; giá không giúp cũng không hại trên gold_v1"
sb run --stage E1a --until E4 --auto-promote
# E1a NEEDS_LABELS (slice audience_style judged 0,64) → dừng
sb gold holes --stage E1a         # 38 cặp → Người A gán 20 phút
sb gold holes import gold/holes/gold_v1__E1a.csv && git tag gold_v2 && sb rescore
sb run --stage E1a --until E4 --auto-promote
# E1a READY → promote E1.T3 → E1b READY → promote E1.T4 → E4 READY → promote @E1b (w60 ngang w150, đơn giản hơn)
sb status
```

**Done khi:** với `--model fake` và `stages` rút gọn (B0 → SAN → E1a → E1b): `run --stage B0 --until E1b --auto-promote` chạy hết và ghi `promotions.yaml`; `--fake-ignore-input-type` làm SAN `SANITY_FAIL` và chuỗi dừng; `promote` arm khác đề xuất mà thiếu `--note` → lỗi; `unpromote E1a` làm E1b `stale`; `arms check` bắt được một arm có trong `stages.yaml` mà thiếu YAML.

---

## Part 13 — Regression sau khi chốt

> **Bản gọn đang dùng (Day 5, 05/10 — người dùng chốt làm trước bản đầy đủ dưới đây).** `sb gold devtest [--seed 42]` chia gold đã tag thành
> dev / test phân tầng theo slice → `gold/splits/devtest@<gold_version>.json` (`devtest.py`; dev để chỉnh tham số, test chỉ để báo cáo).
> `sb --run-id R regress baseline --arm A --note "…" [--force]` ghi `regression/baseline_v1.json` (metric overall / slice / từng câu + top_ids,
> gold_version, sha catalog, commit); `sb --run-id R regress check [--arm A] [--split dev|test]` so trên tập câu chung: FAIL (mã 1) khi
> nDCG@10 hoặc Recall@10 tụt > `max_drop_overall` (1,0) điểm tổng hoặc > `max_drop_slice` (3,0) điểm một slice (`regression.regress_v1`),
> mã 2 khi khác gold / arm hoặc thiếu baseline. Chưa có: dựng lại collection `__reg_<date>`, canary B0, p-value, INCONCLUSIVE, CI.

**Mục tiêu.** Sau khi ký cổng FINAL, mỗi thay đổi có thể làm tụt chất lượng search (text builder, QU, alias, crawl lại catalog, version Weaviate, model string, gold mới) phải chạy lại luồng đã chọn trên gold và báo **PASS / FAIL / INCONCLUSIVE** trước khi merge.

**Baseline** — `sb regression baseline set --flow <P*> --note "…"`: chỉ chạy được khi cổng FINAL đã promote và working tree sạch. Ghi `regression/baseline.json`: flow id, YAML đã giải đầy đủ, model string, image Weaviate, `sha256` + số search unit của catalog, `gold_version`, git commit, metric overall / by_slice / guard, `top_ids` từng query, `note`, `by`, `at`. Arm **B0** được lưu kèm làm **canary**: cấu hình B0 không đổi, nên nếu B0 lệch thì nguyên nhân là môi trường (catalog, Weaviate, API) chứ không phải thay đổi trong PR.

**Chạy** — `sb regression run [--reason "…"] [--latency] [--rescore-only <run_id>]`:

1. Tiền kiểm: `doctor`, `arms check`, `gold verify-append <baseline gold> HEAD`, kiểm tra cứng Part 12.
2. Dựng lại items → text → embed (cache: chỉ text đổi mới gọi API) → nạp vào collection mới hậu tố `__reg_<date>`; không đụng collection của bench.
3. Chạy flow + B0 trên gold hiện tại. Nếu gold đã lên version mới hơn baseline: `rescore` `top_ids` của baseline trên gold hiện tại trước khi so.
4. So cặp (paired bootstrap) trên các qid `active` có ở cả hai.

| Kết quả | Điều kiện | Exit |
|---|---|---|
| **FAIL** | Δ nDCG@10 overall ≤ −`max_drop_ndcg` với p < `p_max`; **hoặc** slice nào (n ≥ `min_per_slice`) giảm > `max_slice_drop`; **hoặc** vi phạm guard bất kỳ | 1 |
| **INCONCLUSIVE** | `judged@10` của flow dưới ngưỡng (thay đổi kéo lên sản phẩm chưa gán) | 3 — chạy `sb gold holes --arms <flow> --run-id <run>`, gán, tag, rồi `sb regression run --rescore-only <run>` (không dựng lại) |
| **PASS** | không thuộc hai dòng trên | 0 |
| WARN (kèm PASS) | p95 Weaviate local tăng > `latency_warn_ratio`; hoặc B0 canary lệch ≥ 2 điểm nDCG trong khi flow không FAIL | 0, in cảnh báo |
| lỗi cấu hình / tiền kiểm | | 2 |

**Report** `reports/regression/<date>.md`: kết luận + exit code; bảng Δ overall và theo slice; guard; 10 query giảm nhiều nhất kèm top-5 tên sản phẩm trước/sau; đầu vào đã đổi so với baseline (file trong `watch_paths` đổi theo `git diff --name-only`, số search unit thêm/bớt, `gold_version` cũ → mới, model/image nếu khác).

**Khi nào chạy:** PR đụng bất kỳ đường dẫn nào trong `regression.watch_paths`; sau mỗi lần crawler chạy `seed`; khi nâng image Weaviate hoặc SDK. Không chạy theo lịch nếu không có thay đổi.

**CI (nếu repo dùng GitHub Actions)** — `.github/workflows/search-regression.yml`: trigger `pull_request` với `paths` = `watch_paths`; service container Weaviate đúng image trong config; secret `COHERE_API_KEY`; `actions/cache` cho `bench_out/search/cache/embeddings.sqlite` khoá theo `gold_version` + hash `textbuild.py` để không embed lại toàn bộ; chạy `sb regression run --reason "PR #${{ github.event.number }}"`; upload report làm artifact; exit 1 → job fail; exit 3 → job fail kèm lời nhắn "cần gán holes, không phải lỗi code". CI **không** có quyền `baseline set`.

**Khi nào đặt lại baseline** (luôn bằng tay, có `--note`): sau một thay đổi cố ý cải thiện đã merge (PASS và Δ ≥ +2 có ý nghĩa) — để lần sau so với mức mới; sau khi catalog thêm nhiều sản phẩm và đã gán holes; sau khi đổi model hoặc luồng — trường hợp này **không phải regression** mà là quyết định mới, phải chạy lại cổng Pa → FINAL trước.

**Done khi:** với `--model fake`: đặt baseline từ một FINAL giả; không đổi gì → exit 0; sửa `textbuild.py` để bỏ amenity khỏi text → exit 1 và report liệt kê query giảm; thêm sản phẩm mới vào catalog fake làm top-10 có cặp chưa gán → exit 3; `--rescore-only` sau khi gán → exit 0 hoặc 1 mà không gọi embed.

---

## Phụ lục A — Arm và cổng

Nguồn duy nhất: `arms.md` (mô tả, ví dụ, kỳ vọng) và `config/stages.yaml` (Part 12, thứ tự + cổng, máy đọc). Không chép danh sách arm vào spec này để tránh lệch.

`sb arms check` phải xanh trước mọi `run --stage`:

1. Mọi id trong cột đầu bảng §1 của `arms.md` (chữ đậm) có `arms/<id>.yaml`, và ngược lại.
2. Mọi arm trong `stages.yaml` có YAML, và mọi YAML thuộc đúng một cổng (trừ arm `disabled`).
3. Mọi `@<stage>` trong `parent` / `inherit` / `text_variant` trỏ tới cổng **đứng trước** trong `stages.yaml`.
4. Mỗi arm khác arm cha (sau khi giải) đúng **một nhóm trường**, trừ arm `P*` và arm sweep (`S1.k1b`, `S7`). Nhóm: `text` (text_variant) · `model` (model, embedding_types) · `query_embed` (query_input_type) · `retrieval` (retrieval, fusion, query_vec) · `bm25` · `filters` (filters, boost) · `dedupe_parent` · `query_preproc` · `cutoff` · `csls` · `rerank` · `fallback`.

Lệch ở bất kỳ điểm nào → exit 2, in danh sách.

## Phụ lục B — Bẫy đã biết

- `input_type` sai không báo lỗi; E3 tồn tại để chứng minh eval nhìn thấy nó.
- Weaviate hybrid: mặc định `fusion_type` là `RELATIVE_SCORE` từ 1.24 — luôn đặt tường minh; `alpha` mặc định của client có thể khác server.
- BM25 với query có dấu trên property fold dấu: nếu `shadow`, phải fold **cả query**; nếu `analyzer`, Weaviate tự fold — kiểm bằng test "nha trang" ở Part 4.
- Flat index + filter chọn lọc: Weaviate flat scan là exact; không có `ef`. Khi lên `dynamic`/HNSW (> 10k) recall thay đổi — ngoài phạm vi bench này.
- `max_vector_distance` là **khoảng cách** (1 − cosine), không phải cosine; sweep theo distance.
- Cohere trial key: 1.000 lượt gọi/tháng — `sb cost` in cả số lượt đã gọi.
- Bootstrap trên query có `recall` undefined (không có rel ≥ 1): loại khỏi cặp, ghi n.
- Không xoá collection thua trước khi `FINAL.md` commit.
- `max_vector_distance` phụ thuộc model (phân bố cosine khác nhau): P4, P5 phải sweep lại cutoff cho model của chúng (`recalibrate: [S7]` ở cổng Pb), không dùng cutoff của Cohere v3.
- `rescore` chỉ tính lại metric dựa trên nhãn. `constraint_precision`, `parent_dup_rate`, zero-result, hub, latency không đổi khi gold thêm nhãn — không cần chạy lại retrieval.
- Đổi promotion ở một cổng → mọi cổng phía sau `stale`. Đừng đọc report của cổng stale; `sb status` in rõ.
- Chạy `--auto-promote` qua đêm xong: đọc `sb status` trước khi làm việc khác — chuỗi có thể đã dừng ở `NEEDS_LABELS` từ tối hôm trước.
