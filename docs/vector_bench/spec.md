# spec.md — `vbench`: benchmark chọn vector database cho V-OTA

Bản 22/09/2026 · để Claude Code sinh code ở local, **mỗi Part chạy thử được độc lập** · nguồn yêu cầu: `docs/VECTOR_DB_SELECTION.md` (gate, metric, trọng số, quy tắc quyết định) · `docs/EMBEDDING_AND_ENGINES.md` (model, text builder, pgvector) · `docs/VECTOR_STORE_AND_ROBUSTNESS.md` (filter amenities, hybrid) · `SCHEMA.md` (contract `products.jsonl`) · `ARCHITECTURE.md` (vị trí code).

Cần chốt nhanh: dùng `spec-fasttrack.md` (`VECTOR_DB_FASTTRACK_SPEC.md`) — 3 engine, 2 giờ máy, quy tắc chốt viết sẵn. **P99 là chỉ số latency chính** (đo open-loop, Part 11).

Spec này **không đặt ra con số mới** cho việc chọn DB: ngưỡng, trọng số, số query, bucket đều chép từ VECTOR_DB_SELECTION.md vào **một** file config (§1.2). Tham số kỹ thuật do spec thêm (giới hạn CPU, sweep `ef`, dung sai…) được ghi *(đề xuất)*.

---

## 0. Tóm tắt

**Làm gì.** Một CLI Python (`vbench`) nạp **cùng** một bộ vector + metadata vào 6 engine (pgvector, pgvectorscale, Qdrant, Milvus, Weaviate, OpenSearch). CLI chạy cùng bộ query có filter trên mọi engine và so với ground truth tính brute-force. Sau đó đo gate G1–G7 và metric A1–E, chấm điểm, áp quy tắc quyết định, xuất report có bảng §6 đã điền.

**Không làm.**

- Không ghi vào database `vota` của app; chỉ đọc khi dùng `--source db`.
- Không đo managed cloud.
- Không chọn model embedding: dùng model ghi trong config, mặc định `BAAI/bge-m3`.
- Không xây taxonomy amenity chính thức: Data team làm; bench chỉ có fallback.

**Ba quy mô dữ liệu.**

| Scale | Vector | Query | Đo gì |
|---|---|---|---|
| `catalog` | Search unit thật từ 10.000 sản phẩm (~5.000; Part 1 in số thật), embed bằng model trong config | 1.000 text query (gold nếu có + template) → embed cùng model | Gate G1–G7, A1–A5 (A2 chỉ ở đây), B1 để tham khảo |
| `100k` | 100.000 vector passage Wikipedia tiếng Việt công khai (Cohere embed-multilingual-v3, 1024-d), metadata sinh theo phân bố catalog | 1.000 vector giữ lại từ cùng dataset | A1, A3–A5, B1–B6, C1–C2 |
| `1m` | như trên, 1.000.000 vector | như trên | như trên; chỉ chạy ở profile `full` (VM 8 vCPU / 32 GB) |

Vì sao scale lớn không dùng text template embed bằng model của mình: văn bản template sinh ra vector gần trùng nhau hàng loạt, làm ANN dễ hoặc khó một cách giả tạo. Passage Wikipedia là văn bản tiếng Việt thật, cùng số chiều 1024. Query ở scale lớn lấy từ **cùng** dataset (không trộn không gian vector của hai model khác nhau).

**Các Part** — làm theo thứ tự; Part sau dùng đầu ra của Part trước. `vb` = `python -m evaluation.vector_bench` chạy từ `src/` (giống `python -m data_collection.seed`).

| Part | Nội dung | Lệnh chạy thử | Cần trước |
|---|---|---|---|
| 0 | Khung package, config, docker compose 6 engine, `doctor` | `vb doctor` · `vb engine up pgvector` | — |
| 1 | Dataset catalog → `items.parquet` + thống kê (in số search unit thật) | `vb dataset catalog --source fake` rồi `--source jsonl` | 0 |
| 2 | Embedding + cache (thật / fake) | `vb embed --scale catalog --backend fake` | 1 |
| 3 | Filter AST, evaluator tham chiếu, sinh query theo bucket selectivity | `vb queries --scale catalog` | 1, 2 |
| 4 | Ground truth brute-force + count/facet | `vb gt --scale catalog` | 3 |
| 5 | Interface engine, adapter **pgvector**, load, smoke | `vb load pgvector` · `vb smoke pgvector` | 4 |
| 6 | Quality runner A1, A3, A4, A5 · 6b: A2 + công cụ gán nhãn gold | `vb quality pgvector` | 5 |
| 7 | Adapter **Qdrant** | `vb load qdrant` · `vb quality qdrant` | 6 |
| 8a–8d | Adapter pgvectorscale · Milvus · Weaviate · OpenSearch (độc lập nhau) | như Part 7 | 6 |
| 9 | Gate G1–G7 | `vb gate qdrant` | 5 + adapter |
| 10 | Dataset scale 100k / 1M | `vb scale-data 100k` | 3, 4 |
| 11 | Perf B1–B6, tài nguyên C1–C2, D1–D3 | `vb perf pgvector --scale 100k` | 6, 10 |
| 12 | Số nhập tay, chấm điểm, quy tắc quyết định, report | `vb score` · `vb decide` · `vb report` | 6, 9, 11 |

**Thứ tự làm ≠ thứ tự chạy thật.** Làm theo Part để sớm có một lát cắt chạy được (pgvector + A1 sau Part 6, so với Qdrant sau Part 7). Khi chọn DB thật: `vb run-all` chạy từng engine theo gate → quality → perf, rồi score → decide → report (Phụ lục C).

Mọi Part chạy được với `--source fake` / `--backend fake` / `--vectors fake`, không cần dữ liệu thật, model hay mạng. Dùng để thử khung trước; số đo thật chỉ lấy từ dữ liệu thật.

---

## 1. Quy ước chung

### 1.1 Vị trí code và dữ liệu

Bench thuộc workstream Evaluation (`ARCHITECTURE.md` §4, §11: `src/evaluation/` = "benchmark và report offline").

```
src/evaluation/vector_bench/
├── __main__.py            # CLI (typer) — mọi lệnh ở §1.3
├── config.py              # nạp config/vbench.yaml + docker/.env, validate bằng pydantic
├── paths.py               # VBENCH_HOME, run dir, tên file chuẩn
├── doctor.py              # Part 0
├── lifecycle.py           # compose up/down/restart, health, danh sách container, docker stats
├── dataset/
│   ├── catalog.py         # Part 1: jsonl | db | fake → items.parquet
│   ├── amenities.py       # fallback chuẩn hoá amenity
│   ├── textbuild.py       # fallback text builder (chỉ khi repo chưa có text builder của Search)
│   ├── fake.py            # catalog giả lập để chạy thử
│   └── scale.py           # Part 10
├── embed.py               # Part 2
├── filters.py             # Part 3: AST, validate, evaluator tham chiếu
├── querygen.py            # Part 3: sinh filter theo bucket + text query
├── lexical.py             # tokenizer fold dấu dùng chung; BM25 sparse cho Qdrant
├── groundtruth.py         # Part 4
├── engines/
│   ├── base.py            # Protocol VectorStore, Capabilities, lỗi Unsupported*
│   ├── registry.py        # tên engine → class
│   ├── pgvector.py        # Part 5
│   ├── qdrant.py          # Part 7
│   ├── pgvectorscale.py   # Part 8a
│   ├── milvus.py          # Part 8b
│   ├── weaviate.py        # Part 8c
│   └── opensearch.py      # Part 8d
├── runners/
│   ├── load.py            # create → upsert → index → wait_ready (ghi số liệu B3)
│   ├── quality.py         # Part 6
│   ├── gold.py            # Part 6b
│   ├── gates.py           # Part 9
│   ├── perf.py            # Part 11
│   └── resources.py       # sampler docker stats, dung lượng disk
├── scoring.py · decide.py · report.py   # Part 12
├── config/
│   ├── vbench.yaml        # MỌI con số (§1.2)
│   ├── amenity_seed.yaml  # alias amenity tối thiểu (Part 1)
│   └── query_templates.yaml  # mẫu câu query + bảng viết tắt (Part 3)
├── docker/
│   ├── compose.yml        # 6 profile engine (Part 0)
│   └── .env.example
├── manual/<engine>.yaml   # số nhập tay (Part 12) — commit
├── gold/                  # drafts.txt, pool.csv, gold.jsonl — commit
├── requirements.txt
└── tests/                 # unit (không cần engine) · integration (pytest -m integration)

bench_out/                 # VBENCH_HOME, ở gốc repo, thêm vào .gitignore
├── data/<scale>/          # items.parquet, vectors.npy, queries.jsonl, query_vectors.npy, gt.npz, …
├── backups/<engine>/
└── runs/<run_id>/<engine>/<scale>/*.json · runs/<run_id>/report.md
```

- Gốc repo là thư mục chứa `.git`. `VBENCH_HOME` mặc định `<repo>/bench_out`; không phụ thuộc thư mục đang đứng.
- Nếu repo đã có text builder của Search: tìm `text_builder` / `build_embed_text` trong `src/backend/app/`. Có thì import dùng lại để vector bench giống vector production. Không có thì dùng `dataset/textbuild.py`, và ghi `text_builder: fallback` vào `stats.json`.
- Không tạo folder `utils` chung (ARCHITECTURE §12).

### 1.2 Config — `config/vbench.yaml`

File duy nhất chứa con số. Code chỉ đọc, không có hằng số ngưỡng/trọng số trong logic. Chỗ ghi *(đề xuất)* là tham số spec thêm vào, chưa có trong VECTOR_DB_SELECTION.md.

```yaml
run:
  seed: 42
  profile: local              # local | full
  scales: {local: [catalog, 100k], full: [catalog, 100k, 1m]}
  engines: [pgvector, qdrant, pgvectorscale, milvus, weaviate, opensearch]
  engine_limits:              # (đề xuất) chừa CPU cho client load test chạy cùng máy
    local: {cpus: 4, mem: 8g}
    full:  {cpus: 6, mem: 16g} # 16 GB theo VECTOR_DB_SELECTION §5
  default_run_id: dev         # run-all dùng <YYYYMMDD-HHMM>-<git short sha>

dataset:
  catalog:
    source: jsonl             # jsonl | db | fake
    products_path: src/data_collection/products.jsonl   # hoặc output/products.jsonl của crawler
    database_url_env: DATABASE_URL
    fake_n: 5000
    amenity_scope: property_plus_rooms  # property_only | property_plus_rooms
    amenity_min_freq: 5       # chuỗi amenity chưa map, xuất hiện ≥ 5 lần → id riêng "raw:<slug>"
    max_amenities_in_text: 12
    max_room_names_in_text: 8
    max_description_words: 60
  scale:
    vectors: cohere-vi        # cohere-vi | fake
    hf_dataset: CohereLabs/wikipedia-2023-11-embed-multilingual-v3
    hf_config: vi
    sizes: {100k: 100000, 1m: 1000000}
    n_queries: 1000
    n_reserve: 20000          # vector dự trữ cho B4/B5 (upsert mới)
    correlation: none         # none | cluster  (metadata tương quan với vector hay không)
    geo_jitter_m: 1000

embedding:
  backend: st                 # st (sentence-transformers) | fake
  model: BAAI/bge-m3
  dim: 1024
  normalize: true
  max_seq_length: 512
  batch_size: 32
  device: cpu                 # cpu | cuda
  query_prefix: ""            # e5: "query: "
  passage_prefix: ""          # e5: "passage: "

queries:
  n_total: 1000
  gold_max: 300               # tối đa 300 gold + phần còn lại sinh
  buckets:                    # selectivity S = |tập thoả filter| / N
    b100: {range: null, quota: 250}                              # không filter
    b10:  {range: [0.05, 0.20], quota: 250}
    b1:   {range: [0.005, 0.02], quota: 250}
    b01:  {range: [0.0005, 0.002], quota: 250, min_matches: 3}
  filter_type_weights: {dest_tax: 0.25, all_amenity: 0.25, not_amenity: 0.15, range: 0.15, geo: 0.10, combo: 0.10}
  available_true_rate: 0.5
  geo_radius_m: [1000, 3000, 5000, 10000, 20000, 50000]
  price_quantiles: [0.1, 0.25, 0.5, 0.75, 0.9]
  star_min_values: [3, 4, 5]
  max_attempts: 200000
  text_slices: {normal: 0.7, khong_dau: 0.15, viet_tat: 0.15}

groundtruth:
  k: 100
  tie_eps: 0.001              # (đề xuất) dung sai điểm khi so recall (fp16)
  chunk_rows: 100000
  geo_boundary_tol: 0.005     # (đề xuất) ±0,5% bán kính = vùng biên, không tính vi phạm

engines:                      # chi tiết từng engine ở Part 5, 7, 8
  # default_query = cấu hình (a): tham số mặc định của engine ({mode: ann} không kèm tham số = để engine tự chọn)
  # query_sweep   = các cấu hình thử để tìm (b) — Part 6
  pgvector:
    dsn: postgresql://postgres:vbench@localhost:55432/vbench
    index_configs:            # thử theo thứ tự; cái đầu = index mặc định
      - {name: hnsw_m16_efc128, params: {m: 16, ef_construction: 128}}
      - {name: hnsw_m32_efc256, params: {m: 32, ef_construction: 256}}
    default_query: {mode: ann, ef_search: 40, iterative_scan: "off"}   # mặc định của pgvector; "off" phải có nháy (YAML)
    query_sweep:
      - {mode: exact}
      - {mode: ann, ef_search: [40, 64, 100, 200, 400], iterative_scan: relaxed_order, max_scan_tuples: 20000}
      - {mode: auto, auto_exact_max: 10000, ef_search: 100, iterative_scan: relaxed_order}
  pgvectorscale:
    dsn: postgresql://postgres:vbench@localhost:55433/vbench
    index_configs:
      - {name: diskann, params: {}}
      - {name: diskann_labels, params: {labels: true}}
    default_query: {mode: ann}
    query_sweep:
      - {mode: exact}
      - {mode: ann, query_search_list_size: [50, 100, 200, 400], query_rescore: 50}
  qdrant:
    url: http://localhost:56333
    grpc_port: 56334
    index_configs:
      - {name: default, params: {m: 16, ef_construct: 128}}
      - {name: forced_hnsw, params: {m: 16, ef_construct: 128, indexing_threshold_kb: 1, full_scan_threshold_kb: 1}}
    default_query: {mode: ann}
    query_sweep:
      - {mode: exact}
      - {mode: ann, hnsw_ef: [40, 64, 100, 200, 400]}
      - {mode: ann_acorn, hnsw_ef: [64, 128]}     # chỉ khi Capabilities báo có ACORN
  milvus:
    uri: http://localhost:59530
    consistency_level: Bounded                    # B4 đo thêm với Strong
    index_configs:
      - {name: hnsw_m16_efc128, params: {M: 16, efConstruction: 128}}
    default_query: {mode: ann}
    query_sweep:
      - {mode: ann, ef: [40, 64, 100, 200, 400]}
  weaviate:
    http_port: 58080
    grpc_port: 55051
    index_configs:
      - {name: hnsw_sweeping, params: {max_connections: 16, ef_construction: 128, filter_strategy: sweeping}}
      - {name: hnsw_acorn,    params: {max_connections: 16, ef_construction: 128, filter_strategy: acorn}}
    default_query: {mode: ann}
    query_sweep:
      - {mode: ann, ef: [40, 64, 100, 200, 400]}
  opensearch:
    url: http://localhost:59200
    force_merge: true         # (đề xuất) thông lệ benchmark; ghi vào kết quả
    index_configs:
      - {name: faiss_hnsw_sqfp16, params: {engine: faiss, space_type: innerproduct, m: 16, ef_construction: 128, encoder: sq_fp16}}
      - {name: lucene_hnsw, params: {engine: lucene, space_type: cosinesimil, m: 16, ef_construction: 128}}
    default_query: {mode: ann}
    query_sweep:
      - {mode: exact}
      - {mode: ann, ef_search: [40, 64, 100, 200, 400]}

load:
  batch_size: 1000
  shuffle: true

quality:
  k: 10
  a1_pass: 0.95
  a1_floor: 0.90
  exact_max_rows: 200000      # (đề xuất) bỏ mode exact ở scale lớn hơn — quét 1M dòng mỗi query không phục vụ quyết định
  a4_n_filters: 200
  a5: {rebuilds: 3, n_queries: 200, scales: [catalog, 100k]}
  a2: {rrf_k: 60, depth: 50, bootstrap: 1000, min_gold: 50}

gates:
  g1: {max_up_s: 900, max_containers: 3}
  g3: {per_type: 50, types: [all_amenity, not_amenity, range, geo]}
  g4: {n_filters: 50}
  g6: {n: 20, poll_ms: 100, pass_p95_s: 5}
  g7: {n_check_queries: 50, pass_restore_s: 600}

perf:
  k: 20
  load_model: open_loop       # tải tốc độ cố định; latency tính từ thời điểm LẼ RA gửi (tránh coordinated omission)
  rates_qps: [25, 50, 100, 200, 400]
  duration_s: 120             # ≥ 12.000 request ở 100 QPS — đủ mẫu cho P99 (1.000 request chỉ có 10 mẫu trên P99)
  warmup_s: 30
  timeout_ms: 1000            # timeout tính vào phân vị với giá trị = timeout, và vào tỷ lệ lỗi
  b1_rate_qps: 100            # B1 = P99 ở mức tải này
  reps: 3
  harness_max_p99_ms: 2       # engine giả "null": P99 của harness phải dưới mức này
  b4: {n_single: 100, n_batches: 10, batch_size: 1000, poll_ms: 100, timeout_s: 120}
  b5: {write_rate_per_s: 100, duration_s: 300, rate_qps: 100}
  b6: {restarts: 3, rate_qps: 50, duration_s: 60}
  sampler_interval_s: 1

scoring:
  weights: {A1: 15, A2: 10, A3: 3, A4: 4, A5: 3,
            B1: 8, B2: 7, B3: 3, B4: 3, B5: 2, B6: 2,
            C1: 5, C2: 2, C3: 5, C4: 5, C5: 3,
            D1: 2.4, D2: 2.4, D3: 2.4, D4: 2.4, D5: 2.4,   # D = 12, chia đều (đề xuất)
            E: 8}
  groups: {A: [A1, A2, A3, A4, A5], B: [B1, B2, B3, B4, B5, B6], C: [C1, C2, C3, C4, C5], D: [D1, D2, D3, D4, D5], E: [E]}
  metrics:                    # dir: higher | lower · pass = ngưỡng đạt · floor = tệ nhất còn điểm
    A1: {dir: higher, pass: 0.95, floor: 0.90}
    A2: {dir: higher, pass_vs_baseline: -0.01, floor_vs_baseline: -0.05}   # floor (đề xuất)
    A3: {dir: higher, pass: 1.0, floor: 0.99}                               # floor (đề xuất)
    A5: {dir: higher, pass: 0.90, floor: 0.80}                              # floor (đề xuất)
    B1: {dir: lower, pass: {100k: 50, 1m: 100}, floor_factor: 2.0}          # P99 ms ở b1_rate_qps; floor (đề xuất)
    B2: {dir: higher, pass: 100, floor: 50}                                 # QPS lớn nhất giữ P99 ≤ ngưỡng B1; floor (đề xuất)
    B3: {dir: lower, pass: {1m: 30}, floor_factor: 2.0}                     # phút
    B4: {dir: lower, single: {pass: 1, floor: 5}, batch: {pass: 60, floor: 300}}   # giây; floor (đề xuất)
    B5: {dir: lower, pass: 0.30, floor: 0.50}                               # P99 khi ghi / P99 tĩnh − 1
    B6: {dir: lower, pass: 3.0, floor: 6.0}                                 # P99 lạnh / P99 ấm
    C1: {dir: lower, pass: {1m: 8}, floor_factor: 2.0}                      # GB
    C2: {dir: lower, pass: 3.0, floor: 6.0}                                 # disk / byte vector thô
    C3: {dir: lower, method: minmax}                                        # VND/tháng
    C4: {dir: lower, pass: 10, floor: 20}                                   # người-ngày; floor (đề xuất)
    C5: {dir: lower, method: minmax}                                        # giờ/tháng
  discrete:
    A4: {exact: 10, approx_flagged: 5, none: 0}
    D1: {"1": 10, "2": 6, "3": 6, more: 2}
    D2: [{max_s: 600, score: 10}, {max_s: 1800, score: 6}, {max_s: null, score: 2}]
    D3: {both: 10, one: 5, none: 0}
    D4: {releases_and_inplace: 10, one_of_two: 5, none: 0}                  # one_of_two (đề xuất)
    D5: {same_db: 10, sync_measured: 5, manual_sync: 0}
  e_checklist:
    items: [sparse, multivector, bm25_native, vi_tokenizer, geo, facet_server, quantization, hybrid_server, mmr_server, multitenancy]
    planned_use_double: [sparse, facet_server]
  sensitivity:
    - {name: A45_B15, groups: {A: 45, B: 15}}
    - {name: C30_A25, groups: {C: 30, A: 25}}

decision:
  baseline: pgvector
  min_total_margin: 1.5       # đề xuất — chốt với team trước khi đo
  lexical_rule: {candidate: opensearch, min_ndcg_gain: 0.03, slices: [ten_rieng, amenity]}
```

### 1.3 CLI

| Lệnh | Part | Việc |
|---|---|---|
| `vb doctor` | 0 | Kiểm tra môi trường, in bảng |
| `vb engine up\|down\|restart\|status <engine> [--volumes]` | 0 | Điều khiển container theo profile |
| `vb dataset catalog [--source jsonl\|db\|fake] [--products PATH] [--n N]` | 1 | Dựng `items.parquet` |
| `vb embed --scale S [--target items\|queries] [--backend st\|fake]` | 2 | Embedding + cache |
| `vb queries --scale S` | 3 | Sinh filter + query |
| `vb gt --scale S` | 4 | Ground truth |
| `vb load <engine> --scale S [--index NAME]` | 5 | Nạp dữ liệu + build index |
| `vb smoke <engine> [--scale S]` | 5 | 10 query, in kết quả cạnh GT |
| `vb quality <engine> --scale S [--only A1,A3,A4,A5,A2] [--gold PATH] [--min-gold N]` | 6 | Metric nhóm A |
| `vb gold pool\|import …` | 6b | Công cụ gán nhãn gold |
| `vb gate <engine> [--only g1,…]` | 9 | Gate |
| `vb scale-data 100k\|1m [--vectors cohere-vi\|fake]` | 10 | Dataset lớn (+ tự gọi queries, gt) |
| `vb perf <engine> --scale S [--only B1,…]` | 11 | Metric nhóm B, C1–C2, D1–D3 |
| `vb score` · `vb decide` · `vb report` | 12 | Chấm điểm, quyết định, report |
| `vb run-all [--engines …] [--scales …] [--keep]` | C | Chạy trọn quy trình |

Tuỳ chọn chung: `--run RUN_ID` (mặc định `dev`), `--config PATH`, `--profile local|full`, `-v`. Mã thoát: `0` ok · `1` lỗi · `2` gate trượt / metric không đạt (khi lệnh có kiểm tra ngưỡng).

### 1.4 Định dạng kết quả

Mỗi lệnh đo ghi một file JSON `bench_out/runs/<run_id>/<engine>/<scale>/<step>.json` với phong bì chung:

```json
{
  "run_id": "dev", "engine": "qdrant", "scale": "catalog", "step": "quality",
  "status": "ok",              "error": null,
  "engine_version": "1.19.1",  "client_version": "1.19.x",
  "index_config": {"name": "default", "params": {}},
  "dataset": {"n": 5123, "dim": 1024, "embed_model": "BAAI/bge-m3", "vectors_sha256": "…"},
  "host": {"cpu": "…", "vcpus": 8, "ram_gb": 32, "os": "…", "docker": "…"},
  "engine_limits": {"cpus": 6, "mem": "16g"},
  "git_commit": "abc1234", "started_at": "…", "finished_at": "…",
  "metrics": {}
}
```

`status` ∈ `ok | error | skipped | unsupported | fail` (fail = chạy xong nhưng không đạt gate). Số liệu từng query (để bootstrap, debug) ghi ra `<step>_queries.parquet` cạnh file JSON.

### 1.5 Quy ước khác

- **Tất định.** Mọi random dùng `numpy.random.default_rng(seed)` với seed từ config cộng offset theo bước. Cùng seed + cùng input → cùng `queries.jsonl` (kiểm bằng sha256).
- **ID.** Bên ngoài dùng `productId` UUID dạng chuỗi; mọi engine dùng làm primary key. Bên trong (GT, evaluator) dùng số thứ tự dòng của `items.parquet`. Dataset scale dùng `uuid5(NAMESPACE_URL, f"vbench:{scale}:{i}")`.
- **Vector chuẩn.** `vectors.npy` là float16 **sau khi** L2-normalize. Mọi engine nạp đúng giá trị này (engine không có fp16 thì cast lên fp32). GT tính bằng fp32 trên chính các giá trị này, nên không lệch do precision giữa GT và engine.
- **Đo thời gian:** `time.perf_counter_ns`. Đơn vị: ms cho latency, s cho thời gian thao tác, phút cho build 1M, GB cho RAM/disk.
- **Log:** `rich` ra console + `bench_out/runs/<run_id>/vbench.log`.
- **Lỗi:** không nuốt lỗi. Một query lỗi thì ghi vào `errors` của file kết quả. Tỷ lệ lỗi > 1% thì step có `status: error`.
- **Windows:** `multiprocessing` dùng spawn, nên worker tự tạo adapter từ config (truyền tên engine + đường dẫn config, không truyền object đã kết nối).

### 1.6 Thư viện — `requirements.txt`

```
numpy>=1.26
pandas>=2.2
pyarrow>=15
scipy>=1.12
pyyaml>=6
pydantic>=2.6
typer>=0.12
rich>=13
psycopg[binary]>=3.2
pgvector>=0.3
qdrant-client          # cùng minor với server (1.19.x) — pin sau khi doctor xác nhận
pymilvus               # cùng major.minor với server (3.0.x) — pin sau khi doctor xác nhận
weaviate-client>=4.10
opensearch-py>=2.6
docker>=7
mmh3>=4
pytest>=8
# --- tuỳ chọn: tách ra requirements-extra.txt ---
# sentence-transformers>=3.0 và torch   (Part 2, backend st)
# datasets>=2.19                        (Part 10, cohere-vi)
# scikit-learn>=1.4                     (Part 10, correlation=cluster)
# matplotlib>=3.8                       (biểu đồ trong report)
```

`vb doctor` in version thật của từng thư viện. Phiên bản client phải khớp server theo khuyến nghị của từng vendor.

### 1.7 Việc Claude Code KHÔNG được tự quyết

1. Không đổi ngưỡng, trọng số, bucket, số query, số lần lặp trong code — chỉ đọc từ `vbench.yaml`.
2. Không ghi vào database `vota`. `--source db` chỉ `SELECT`.
3. Không thêm engine ngoài 6 engine trên; không dùng dịch vụ cloud.
4. Không dùng số benchmark của vendor để chấm; không "làm đẹp" kết quả.
5. Filter mà engine không biểu diễn được thì raise `UnsupportedFilter`, **không** tự lọc phía client để giả vờ hỗ trợ. Ngoại lệ duy nhất: geo có thể giả lập (bbox + haversine phía client), khi đó phải gắn `capabilities.geo = "emulated"` và gate ghi `pass_emulated`.
6. Tham số API chưa chắc chắn (đánh dấu **VERIFY** trong spec) phải kiểm bằng docs của đúng phiên bản đang chạy. Có thì dùng và ghi vào `capabilities`; không có thì báo unsupported — không đoán tên tham số.
7. Spec thiếu hoặc mâu thuẫn thì dừng và hỏi, không tự bịa cách làm.
8. Không commit `bench_out/`. Có commit `manual/`, `gold/`, `config/`.

---

## Part 0 — Khung package, docker compose, `doctor`

**Mục tiêu:** có CLI chạy được, bật/tắt từng engine bằng một lệnh, và kiểm tra máy trước khi đo.

**File:** `__main__.py`, `config.py`, `paths.py`, `lifecycle.py`, `doctor.py`, `docker/compose.yml`, `docker/.env.example`, `config/*.yaml`, `requirements.txt`, thêm `bench_out/` vào `.gitignore`.

### P0.1 `docker/compose.yml`

Mỗi lần chỉ bật **một** profile để các engine không tranh tài nguyên. Project name `vbench`, port lệch khỏi port của app (`5432` vẫn là DB `vota`).

```yaml
name: vbench
x-limits: &limits
  cpus: ${ENGINE_CPUS:-4}
  mem_limit: ${ENGINE_MEM:-8g}

services:
  pgvector:
    profiles: [pgvector]
    image: ${PGVECTOR_IMAGE:-pgvector/pgvector:0.8.6-pg16}   # VERIFY tag; fallback pgvector/pgvector:pg16 rồi kiểm extversion
    <<: *limits
    shm_size: 2g        # build HNSW song song cần /dev/shm lớn hơn 64 MB mặc định của Docker
    environment: {POSTGRES_PASSWORD: vbench, POSTGRES_DB: vbench}
    command: >
      postgres -c shared_buffers=${PG_SHARED_BUFFERS:-2GB}
               -c maintenance_work_mem=${PG_MAINT_MEM:-1GB}
               -c max_parallel_maintenance_workers=${PG_PAR_MAINT:-2}
               -c work_mem=64MB -c jit=off
    ports: ["${PGVECTOR_PORT:-55432}:5432"]
    volumes: [pgvector_data:/var/lib/postgresql/data, "${VBENCH_HOME}/backups/pgvector:/backup"]

  pgvectorscale:
    profiles: [pgvectorscale]
    image: ${PGVS_IMAGE:-timescale/timescaledb-ha:pg16}      # VERIFY: có extension vectorscale; data dir
    <<: *limits
    shm_size: 2g
    environment: {POSTGRES_PASSWORD: vbench, POSTGRES_DB: vbench}
    command: >
      postgres -c shared_buffers=${PG_SHARED_BUFFERS:-2GB}
               -c maintenance_work_mem=${PG_MAINT_MEM:-1GB}
               -c max_parallel_maintenance_workers=${PG_PAR_MAINT:-2}
               -c work_mem=64MB -c jit=off
    ports: ["${PGVS_PORT:-55433}:5432"]
    volumes: [pgvs_data:/home/postgres/pgdata, "${VBENCH_HOME}/backups/pgvectorscale:/backup"]

  qdrant:
    profiles: [qdrant]
    image: qdrant/qdrant:${QDRANT_TAG:-v1.19.1}
    <<: *limits
    ports: ["${QDRANT_HTTP_PORT:-56333}:6333", "${QDRANT_GRPC_PORT:-56334}:6334"]
    volumes: [qdrant_data:/qdrant/storage, "${VBENCH_HOME}/backups/qdrant:/qdrant/snapshots"]

  weaviate:
    profiles: [weaviate]
    image: cr.weaviate.io/semitechnologies/weaviate:${WEAVIATE_TAG}
    <<: *limits
    command: ["--host", "0.0.0.0", "--port", "8080", "--scheme", "http"]
    environment:
      PERSISTENCE_DATA_PATH: /var/lib/weaviate
      DEFAULT_VECTORIZER_MODULE: none
      ENABLE_MODULES: backup-filesystem
      BACKUP_FILESYSTEM_PATH: /var/lib/weaviate-backups
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: "true"
      CLUSTER_HOSTNAME: node1
      PROMETHEUS_MONITORING_ENABLED: "true"
    ports: ["${WEAVIATE_HTTP_PORT:-58080}:8080", "${WEAVIATE_GRPC_PORT:-55051}:50051", "${WEAVIATE_METRICS_PORT:-52112}:2112"]
    volumes: [weaviate_data:/var/lib/weaviate, "${VBENCH_HOME}/backups/weaviate:/var/lib/weaviate-backups"]

  opensearch:
    profiles: [opensearch]
    image: opensearchproject/opensearch:${OPENSEARCH_TAG}
    <<: *limits
    environment:
      discovery.type: single-node
      DISABLE_SECURITY_PLUGIN: "true"
      DISABLE_INSTALL_DEMO_CONFIG: "true"
      bootstrap.memory_lock: "true"
      path.repo: /usr/share/opensearch/backups
      OPENSEARCH_JAVA_OPTS: "-Xms${OS_HEAP:-4g} -Xmx${OS_HEAP:-4g}"
    ulimits: {memlock: {soft: -1, hard: -1}, nofile: {soft: 65536, hard: 65536}}
    ports: ["${OPENSEARCH_PORT:-59200}:9200"]
    volumes: [os_data:/usr/share/opensearch/data, "${VBENCH_HOME}/backups/opensearch:/usr/share/opensearch/backups"]

  # milvus: KHÔNG tự viết. Lấy file milvus-standalone-docker-compose.yml trong release v3.0.1 của Milvus,
  # chép 3 service (etcd, minio, standalone) vào đây, gắn profiles: [milvus] cho cả 3, áp <<: *limits cho
  # standalone, đổi port 19530 → ${MILVUS_PORT:-59530}, 9091 → ${MILVUS_HTTP_PORT:-59091}, volume thành named volume.
  # D1 (số container) của Milvus tính theo đúng file chính thức này.

volumes: {pgvector_data: {}, pgvs_data: {}, qdrant_data: {}, weaviate_data: {}, os_data: {}}
```

`docker/.env.example`: `VBENCH_HOME` (đường dẫn tuyệt đối, `doctor` tự điền), image tag từng engine (`WEAVIATE_TAG=<<TỰ ĐIỀN 1.37.x>>`, `OPENSEARCH_TAG=<<TỰ ĐIỀN 3.x>>`, `MILVUS_TAG=v3.0.1`), port ở trên, `ENGINE_CPUS`/`ENGINE_MEM`/`PG_*`/`OS_HEAP`. Lệnh `vb` ghi đè `ENGINE_CPUS`/`ENGINE_MEM` theo `run.profile`. Profile `full` gợi ý: `PG_SHARED_BUFFERS=4GB`, `PG_MAINT_MEM=4GB`, `PG_PAR_MAINT=4`.

### P0.2 `lifecycle.py`

`up(engine)` · `down(engine, volumes=False)` · `restart(engine)` · `wait_healthy(engine, timeout_s) -> float` · `containers(engine) -> list[Container]` · `stats(engine) -> {mem_bytes, cpu_pct}` (docker SDK, lọc theo label `com.docker.compose.project=vbench` và service thuộc profile).

Health check chạy từ phía host (image không chắc có `curl`):

| Engine | Healthy khi |
|---|---|
| pgvector, pgvectorscale | `psycopg.connect(dsn)` + `SELECT 1` |
| qdrant | `GET /readyz` → 200 |
| milvus | `GET http://localhost:59091/healthz` → 200 |
| weaviate | `GET /v1/.well-known/ready` → 200 |
| opensearch | `GET /_cluster/health` → `green` hoặc `yellow` |

### P0.3 `doctor`

In một bảng OK / WARN / FAIL:

- Python ≥ 3.11 và version từng thư viện ở §1.6 (import thử).
- Docker daemon và Compose v2 ≥ 2.20.
- CPU, RAM, disk trống ở `VBENCH_HOME`. WARN nếu profile `full` mà RAM < 32 GB hoặc disk < 60 GB; profile `local` mà RAM < 16 GB.
- Image của từng engine có sẵn hoặc pull được (`docker image inspect`, không có thì `docker manifest inspect`).
- Port trống.
- `vm.max_map_count ≥ 262144`, bắt buộc cho OpenSearch. Linux: `sysctl`. Windows/WSL2: `wsl -d docker-desktop sysctl -w vm.max_map_count=262144`.
- `VBENCH_HOME` tuyệt đối, ghi được; tự điền vào `docker/.env` nếu thiếu.
- Tuỳ chọn: cache model HF, import `datasets`.

**Chạy thử:**

```bash
cd src && pip install -r evaluation/vector_bench/requirements.txt
python -m evaluation.vector_bench doctor
python -m evaluation.vector_bench engine up pgvector && python -m evaluation.vector_bench engine status pgvector
python -m evaluation.vector_bench engine down pgvector --volumes
```

**Done khi:**

- `doctor` thoát mã 0 (được có WARN).
- `engine up pgvector` healthy trong ≤ 60 s.
- `engine status` in container, image, `SELECT extversion FROM pg_extension WHERE extname='vector'`.
- `down --volumes` xoá sạch volume.

---

## Part 1 — Dataset catalog → `items.parquet`

**Mục tiêu:** một bảng phẳng các **search unit** kèm metadata để lọc, văn bản để embed, và thống kê — trong đó có **số vector thật** thay cho con số ước ~5.000.

**File:** `dataset/catalog.py`, `dataset/amenities.py`, `dataset/textbuild.py`, `dataset/fake.py`, `config/amenity_seed.yaml`.

### P1.1 Nguồn

| `--source` | Đọc | Ghi chú |
|---|---|---|
| `jsonl` | `products.jsonl` 13 trường (`SCHEMA.md`) | Mặc định. Crawler xuất ở `output/products.jsonl` |
| `db` | `cdp.products` JOIN `catalog.product_meta` qua `DATABASE_URL` | Chỉ `SELECT`. Nếu có bảng `catalog.product_amenities` thì lấy amenity từ đó |
| `fake` | Sinh `--n` search unit (mặc định 5.000) | Chạy thử không cần dữ liệu (P1.5) |

### P1.2 Search unit và cột

`variant` suy giống view `catalog.product_meta`: `hotel`+`level=property` → `hotel_property`; `hotel`+`room` → `hotel_room`; `flight`+`route` → `flight_route`; `flight`+`flight` → `flight`; `attraction`, `combo`, `golf` giữ nguyên. **Search unit** = `variant ∉ {hotel_room, flight}`. Phòng và chuyến bay không thành dòng riêng; chúng góp giá, amenity và tên hạng phòng vào dòng cha qua `attributes.parentProductId`.

| Cột | Kiểu | Cách tính |
|---|---|---|
| `row` | int32 | thứ tự dòng, bắt đầu 0 |
| `id` | string (UUID) | `productId` |
| `variant`, `taxonomy`, `destination`, `province`, `name` | string | `province` từ `attributes.province` |
| `available` | bool | `available` |
| `amenity_ids` | list<int16> | P1.3 |
| `unit_price` | float64, null được | property: min giá các phòng con; route: min giá các chuyến con; còn lại: `unitPrice` |
| `star_rating` | float32, null được | `attributes.starRating` |
| `lat`, `lon` | float64 | `attributes.latitude/longitude` |
| `embed_text` | string | P1.4 |
| `lex_text` | string | = `embed_text` (tên đã đứng đầu) |
| `text_hash` | string | sha256 của `embed_text` |
| `description_derived` | bool | `attributes.descriptionSource` có giá trị |
| `n_children` | int16 | số phòng / chuyến con |

### P1.3 Amenity → `amenity_ids`

Ưu tiên bảng của Data team (`catalog.product_amenities`, dòng `state = true`) khi `--source db` và bảng tồn tại. Không có thì dùng fallback — đây **không** phải taxonomy chính thức, chỉ để filter trong bench có phân bố thật:

1. `fold(s)`: NFC → lower → bỏ dấu (NFD, xoá combining mark) → `đ→d` → ký tự ngoài `[a-z0-9]` thành khoảng trắng → gộp khoảng trắng.
2. Khớp alias trong `amenity_seed.yaml`: exact trước, sau đó theo cụm từ nguyên token (alias dài nhất thắng). Không khớp → chuỗi raw.
3. Raw xuất hiện ≥ `amenity_min_freq` lần trên các search unit → id riêng `raw:<slug>`; ít hơn → bỏ, đếm vào `stats.amenity.dropped`.
4. Đánh id int16 từ 1: seed key theo thứ tự alphabet, rồi raw theo tần suất giảm dần. Ghi `amenity_vocab.json` = `{id: {key, label, source: seed|raw|catalog, freq}}`.
5. `amenity_scope: property_plus_rooms` → property nhận hợp amenity của nó và các phòng con.

`config/amenity_seed.yaml` (khởi đầu, Data team sửa thoải mái):

```yaml
# alias viết ở dạng đã fold
pool:             {label: hồ bơi,            aliases: [ho boi, be boi, swimming pool, pool, outdoor pool, indoor pool, infinity pool, ho boi vo cuc, ho boi ngoai troi]}
private_beach:    {label: bãi biển riêng,    aliases: [bai bien rieng, private beach]}
spa:              {label: spa,               aliases: [spa, massage, xong hoi, sauna]}
fitness:          {label: phòng gym,         aliases: [phong gym, gym, fitness, fitness center, trung tam the duc, phong tap]}
kids_club:        {label: câu lạc bộ trẻ em, aliases: [kids club, kid club, cau lac bo tre em, khu vui choi tre em, san choi tre em]}
restaurant:       {label: nhà hàng,          aliases: [nha hang, restaurant]}
bar:              {label: quầy bar,          aliases: [quay bar, bar, lounge, pool bar]}
breakfast:        {label: bữa sáng,          aliases: [bua sang, an sang, breakfast, buffet sang]}
wifi:             {label: wifi,              aliases: [wifi, wi fi, wifi mien phi, free wifi, internet]}
parking:          {label: chỗ đỗ xe,         aliases: [cho do xe, bai do xe, parking, free parking]}
airport_shuttle:  {label: đưa đón sân bay,   aliases: [dua don san bay, xe dua don san bay, airport shuttle, shuttle]}
room_service:     {label: dịch vụ phòng,     aliases: [dich vu phong, room service]}
front_desk_24h:   {label: lễ tân 24 giờ,     aliases: [le tan 24 gio, le tan 24 24, 24 hour front desk]}
laundry:          {label: giặt ủi,           aliases: [giat ui, dich vu giat ui, laundry]}
water_park:       {label: công viên nước,    aliases: [cong vien nuoc, water park]}
golf:             {label: sân golf,          aliases: [san golf, golf course]}
tennis:           {label: sân tennis,        aliases: [san tennis, tennis]}
family_room:      {label: phòng gia đình,    aliases: [phong gia dinh, family room, family rooms]}
non_smoking:      {label: không hút thuốc,   aliases: [khong hut thuoc, phong khong hut thuoc, non smoking]}
air_conditioning: {label: điều hòa,          aliases: [dieu hoa, may lanh, air conditioning]}
elevator:         {label: thang máy,         aliases: [thang may, elevator, lift]}
accessible:       {label: tiện nghi người khuyết tật, aliases: [nguoi khuyet tat, xe lan, wheelchair accessible]}
pet_friendly:     {label: cho phép thú cưng, aliases: [cho phep vat nuoi, thu cung, pets allowed, pet friendly]}
```

### P1.4 `embed_text`

Nếu repo đã có text builder của Search thì dùng nó (§1.1). Fallback theo EMBEDDING_AND_ENGINES §2.6, rút gọn. Không đưa giá, ngày, toạ độ, mã, review; sao viết "5 sao".

| Variant | Mẫu |
|---|---|
| `hotel_property` | `{name} — {propertyType or "khách sạn"} {sao} sao tại {destination} ({province}). Tiện ích nổi bật: {≤12 label amenity}. Loại phòng: {≤8 roomName khác nhau của phòng con}. {≤60 từ description nếu không derived}` |
| `flight_route` | `Vé máy bay {originCity} – {destinationCity}. Chuyến bay đến {destination}, {province}; hãng: {airline các chuyến con}.` |
| `attraction` | `{name} — {venue} tại {destination} ({province}). {"Điểm tham quan công cộng, không cần vé" nếu ticketed=false}. Phù hợp: {audience}. Nổi bật: {≤5 highlights}. {≤60 từ description}` |
| `combo` | `{name} — combo tại {destination} ({province}). {≤60 từ description}` |
| `golf` | `{name} — sân golf tại {destination} ({province}). {≤60 từ description}` |

### P1.5 Catalog giả lập (`--source fake`)

Mục đích duy nhất là chạy thử khung. `n` search unit, tỷ lệ variant như bản crawl 16/09: property 50%, attraction 36%, combo 8%, route 5%, golf 1%.

- **Điểm đến:** 12 destination (Nha Trang, Phú Quốc, Đà Nẵng, Hội An, Hạ Long, Hà Nội, TP.HCM, Sa Pa, Đà Lạt, Quy Nhơn, Cửa Hội, Tây Ninh), trọng số Zipf s = 1,1. Toạ độ = tâm điểm đến (xấp xỉ) + nhiễu σ = 3 km.
- **Amenity:** lấy từ seed với tần suất Zipf; 35% property không có amenity nào, mô phỏng coverage 65%.
- **Giá:** lognormal theo taxonomy. 34% attraction là điểm công cộng (`ticketed=false`, `unit_price = null`), như bản 16/09 (139/407).
- **Sao:** 3–5 cho property; khoảng 49% null, theo độ phủ `starRating` 51% của bản 16/09.
- **Văn bản:** sinh bằng template ở P1.4.

`stats.source = fake`.

### P1.6 Đầu ra

Ghi vào `bench_out/data/catalog/`:

- `items.parquet`
- `amenity_vocab.json`
- `stats.json`:
  - số sản phẩm theo variant; `n_search_units` và tỷ lệ; nguồn và text builder đã dùng;
  - amenity: coverage của `hotel_property`, số id (seed / raw), số raw bị bỏ, top 30;
  - số destination; tỷ lệ null của giá và sao;
  - số từ của `embed_text` (p50 / p95); tỷ lệ `description_derived`.

In bảng tóm tắt ra console.

**Chạy thử:**

```bash
python -m evaluation.vector_bench dataset catalog --source fake --n 5000
python -m evaluation.vector_bench dataset catalog --source jsonl --products <đường dẫn products.jsonl 10.000 dòng>
```

**Done khi:**

- `id` duy nhất, không `embed_text` rỗng, mọi dòng có `lat/lon`.
- Với `--source db`: `n_search_units` = `SELECT count(*) FROM catalog.product_meta WHERE is_search_unit`.
- Unit test: 7 bản ghi mẫu, một cho mỗi variant (có attraction `ticketed=false`, property không có phòng) cho đúng variant, đúng min giá, đúng hợp amenity.
- `stats.json` in ra số vector thật. Cập nhật con số "~5.000" ở VECTOR_DB_SELECTION.md §2 bằng số này.

**Ước lượng chạy:** < 1 phút cho 10.000 sản phẩm.

---

## Part 2 — Embedding + cache

**Mục tiêu:** một ma trận vector chuẩn dùng chung cho mọi engine; chạy lại chỉ embed phần văn bản đã đổi.

**File:** `embed.py`.

- `--target items` (mặc định): embed `passage_prefix + embed_text` theo thứ tự `row` → L2-normalize fp32 → cast **float16** → `vectors.npy` (N × D).
  - `embed_meta.json` ghi: model, revision (commit hash HF nếu có), dim, backend, normalize, `max_seq_length`, prefix, device, n, số giây, items/s, version `sentence-transformers` và `torch`, sha256 của `vectors.npy`.
  - Mảng `text_hash` đã embed lưu kèm để chạy **tăng dần**: cùng model/backend/dim và cùng hash thì dùng lại vector cũ.
- `--target queries`: embed `query_prefix + text` của `queries.jsonl` → `query_vectors.npy`. Chỉ dùng cho scale `catalog`; scale lớn lấy query vector từ dataset (Part 10).
- `--backend fake`: không cần model.
  - Tâm cụm ngẫu nhiên (theo seed) cho từng destination và variant.
  - `v = normalize(c_dest + 0.7·c_variant + 0.6·ε)`, với ε lấy seed theo `hash(id)`.
  - Query fake: `normalize(v_item_ngẫu_nhiên + 0.8·ε)`.
  - Dùng để chạy thử khung. **Không** dùng số recall từ vector fake để kết luận.

**Chạy thử:**

```bash
python -m evaluation.vector_bench embed --scale catalog --backend fake
python -m evaluation.vector_bench embed --scale catalog                  # bge-m3, lần đầu tải ~2,3 GB
```

**Done khi:**

- `vectors.npy` có shape (N, D).
- Mọi norm nằm trong 1 ± 0,01 (sau fp16).
- Chạy lại lần hai báo `re-embedded: 0`.
- Backend fake chạy offline < 10 s với 5.000 dòng.

**Ước lượng chạy:** ~5.000 search unit với bge-m3 trên CPU dưới 5 phút (ngoại suy từ "1.125 dưới 1 phút" ở EMBEDDING_AND_ENGINES §3.2).

---

## Part 3 — Filter AST, evaluator tham chiếu, sinh query

**Mục tiêu:** một ngôn ngữ filter duy nhất; một evaluator numpy là "sự thật"; mỗi engine chỉ dịch AST sang cú pháp của nó. Đây là lõi của G3, A1, A3, A4.

**File:** `filters.py`, `querygen.py`, `lexical.py`, `config/query_templates.yaml`.

### P3.1 AST (JSON)

```
Filter := null
        | {"and": [Filter, …]} | {"or": [Filter, …]} | {"not": Filter}
        | {"eq":    [field, value]}
        | {"in":    [field, [value, …]]}
        | {"range": [field, {"gte"|"gt"|"lte"|"lt": number, …}]}
        | {"all":   ["amenity_ids", [int, …]]}        # chứa TẤT CẢ
        | {"any":   ["amenity_ids", [int, …]]}        # chứa ÍT NHẤT MỘT
        | {"geo":   {"lat": float, "lon": float, "radius_m": float}}
        | {"id_in": [uuid, …]}                        # chỉ dùng cho probe G6/B4
```

| Field | Kiểu | Null | Toán tử |
|---|---|---|---|
| `taxonomy`, `destination`, `variant` | keyword | không | `eq`, `in` |
| `available` | bool | không | `eq` |
| `amenity_ids` | int16[] | không (có thể rỗng) | `all`, `any` |
| `unit_price`, `star_rating` | float | **có** | `range` |
| `lat`/`lon` | geo | không | `geo` |

**Ngữ nghĩa bắt buộc giống nhau ở mọi engine:**

1. NULL không bao giờ khớp `range`.
2. `all`/`any` với danh sách rỗng là AST không hợp lệ.
3. `not` chỉ được bọc `eq` trên trường không null, hoặc `any` trên `amenity_ids`. Validator từ chối mọi dạng khác, vì `NOT` trên trường nullable cho kết quả khác nhau giữa SQL (NULL → loại) và các engine khác. Mảng rỗng thoả `not any` — đúng nghĩa "không có dữ liệu ≠ có".
4. `geo`: khoảng cách haversine, R = 6.371.008,8 m, khớp khi d ≤ r. Item có |d − r| ≤ `geo_boundary_tol`·r là **vùng biên**: không tính vi phạm nếu engine trả, không tính miss nếu engine không trả. Lý do: mỗi engine tính khoảng cách hơi khác nhau.

**Evaluator:** `mask(ast, table) -> np.ndarray[bool]` và `boundary(ast, table) -> np.ndarray[bool]`, vector hoá toàn bộ. `amenity_ids` dựng một lần thành `scipy.sparse.csr_matrix` (N × A): `all` = AND các cột, `any` = OR. Chạy 1.000 filter trên 1M dòng trong vài phút.

### P3.2 Sinh filter theo bucket selectivity

| Loại | Cấu trúc | Tham số lấy từ dữ liệu |
|---|---|---|
| `dest_tax` | `and(eq destination, eq taxonomy)` | destination theo tỷ lệ số item; taxonomy theo tỷ lệ trong destination |
| `all_amenity` | `and(eq taxonomy "hotel", all(amenity_ids, 2–3 id))`, 50% thêm `eq destination` | id theo tần suất trong `hotel_property` |
| `not_amenity` | `and(eq destination, eq taxonomy "hotel", not(any(amenity_ids, [id])))` | id theo tần suất |
| `range` | `and(eq destination, range(unit_price, lte = quantile p) \| range(star_rating, gte = s))` | p ∈ `price_quantiles` của destination × taxonomy; s ∈ `star_min_values` |
| `geo` | `geo(toạ độ một item ngẫu nhiên, r ∈ geo_radius_m)`, 50% thêm `eq taxonomy` | — |
| `combo` | `and(eq destination, eq taxonomy, all(amenity_ids, 1–2 id), range(unit_price, lte))` | — |

- Mỗi filter có xác suất `available_true_rate` được thêm `eq available true`.
- Bucket `b100` = không filter (`null`).
- Các bucket còn lại: chọn loại theo `filter_type_weights`, sinh tham số, tính S = `mask.mean()`. Giữ filter nếu S nằm trong khoảng của một bucket còn quota và `n_match ≥ min_matches`; không thì bỏ, thử lại. Dừng khi đủ quota hoặc hết `max_attempts`; bucket thiếu thì ghi `shortfall`.

### P3.3 Text query (scale `catalog`)

`config/query_templates.yaml` chứa mẫu câu theo variant và bảng viết tắt; team sửa file này, không sửa code:

```yaml
templates:
  hotel_property: ["{loai} {sao} sao ở {destination}", "khách sạn {destination} có {amenity}", "resort {destination} có {amenity} cho gia đình", "{name}"]
  attraction:     ["vé {name}", "chỗ vui chơi ở {destination} cho trẻ em", "{name}"]
  combo:          ["combo nghỉ dưỡng {destination}", "{name}"]
  flight_route:   ["vé máy bay đi {destination}"]
  golf:           ["sân golf {destination}"]
abbreviations: {"khách sạn": "ks", "khu nghỉ dưỡng": "resort", "Phú Quốc": "PQ", "Nha Trang": "NT", "Đà Nẵng": "ĐN", "VinWonders": "VW"}
```

- Mỗi query điền từ một item ngẫu nhiên, variant chọn theo tỷ lệ search unit.
- Slice theo `text_slices`: `normal`; `khong_dau` (bỏ dấu, dùng `lexical.fold`, giữ hoa/thường); `viet_tat` (thay theo bảng). Câu không có gì để viết tắt thì ghi `normal`.
- Query ghép **độc lập** với filter. A1 đo recall của engine, không đo độ liên quan, nên ghép ngẫu nhiên là đủ.
- Nếu có `gold/gold.jsonl`: lấy tối đa `gold_max` câu gold trước (có `slice` riêng). Gold vẫn nhận filter sinh ngẫu nhiên cho A1; filter của chính gold giữ ở `gold_filter` để dùng cho A2.

Scale `100k`/`1m`: không có text; `source = "dataset"`, query vector lấy từ Part 10.

### P3.4 `lexical.py`

`fold(s)` giống P1.3. `tokens(s) = [t for t in fold(s).split() if len(t) >= 2]` — âm tiết đã bỏ dấu, tương đương `to_tsvector('simple', unaccent(lower(…)))`. Engine nào có analyzer riêng thì cấu hình analyzer tương đương (Phụ lục A); tokenizer này dùng khi engine không có BM25 phía server (Qdrant).

### P3.5 Đầu ra

`bench_out/data/<scale>/queries.jsonl`, một dòng một query:

```json
{"qid": "c0001", "text": "khach san nha trang co ho boi", "slice": "khong_dau", "source": "gen",
 "filter": {"and": [{"eq": ["destination", "Nha Trang"]}, {"all": ["amenity_ids", [3, 17]]}]},
 "filter_type": "all_amenity", "bucket": "b1", "selectivity": 0.0123, "n_match": 63, "gold_filter": null}
```

Kèm `queries_stats.json`: số query theo bucket × loại, khoảng S đạt được, shortfall, sha256 của file.

**Chạy thử:**

```bash
python -m evaluation.vector_bench queries --scale catalog
python -m evaluation.vector_bench embed --scale catalog --target queries --backend fake
```

**Done khi:**

- 1.000 dòng; mỗi bucket đủ quota hoặc có `shortfall` ghi rõ.
- Tính lại `mask` cho từng filter ra đúng `n_match`.
- Unit test evaluator:
  - `range` trên giá null;
  - `not any` với mảng rỗng;
  - `all` 3 id;
  - `or` + `in`;
  - geo trong / ngoài / vùng biên.
- Validator từ chối `not(range(…))` và `all([])`.
- Cùng seed → cùng sha256.

---

## Part 4 — Ground truth

**Mục tiêu:** top-K chính xác cho từng query trên đúng tập đã lọc, cùng count và facet đúng.

**File:** `groundtruth.py`.

- Với mỗi query *i*: `m = mask & ~boundary` (tập chặt) → điểm cosine fp32 của `q_i` với `V[m]` → top-K (K = 100).
- Chạy theo khối `chunk_rows` dòng:
  - Mỗi khối tính ma trận điểm Q × chunk bằng một phép `matmul`.
  - Áp mask của khối (evaluator chạy trên lát metadata tương ứng).
  - Gộp top-K bằng `np.argpartition`.
  - `vectors.npy` mở bằng `np.load(mmap_mode="r")`.
- `gt.npz`:
  - `rows` (Q×K int32, −1 = trống);
  - `scores` (Q×K float32, NaN = trống);
  - `n_match` (Q, tập chặt);
  - `n_boundary` (Q);
  - `k`.
- `facets_gt.json`: `a4_n_filters` query có filter đầu tiên → `{qid: {count, count_boundary, taxonomy: {…}, destination: {…}}}`.
- Tự kiểm tra:
  - 50 item ngẫu nhiên làm query, không filter → top-1 là chính nó, điểm ≥ 0,999.
  - 20 query ngẫu nhiên tính lại bằng vòng lặp ngây thơ → trùng kết quả chạy theo khối.

**Chạy thử:** `python -m evaluation.vector_bench gt --scale catalog`

**Done khi:** tạo đủ file, hai tự kiểm tra pass, log thời gian chạy.

**Ước lượng chạy:** vài giây ở catalog; vài phút ở 1M trên 8 core.

---

## Part 5 — Interface engine + adapter pgvector + load + smoke

**Mục tiêu:** hợp đồng chung cho mọi engine, và bản cài đặt đầu tiên — pgvector, cũng là baseline.

**File:** `engines/base.py`, `engines/registry.py`, `engines/pgvector.py`, `runners/load.py`, lệnh `smoke`.

### P5.1 `engines/base.py`

```python
Hit = tuple[str, float]                     # (id, score) — score càng cao càng giống

@dataclass(frozen=True)
class Capabilities:
    exact_search: bool
    filter_ops: frozenset[str]              # eq in range all any not or geo id_in
    geo: Literal["native", "emulated", "none"]
    count_exact: bool
    facet: Literal["exact", "approx", "none"]
    lexical: Literal["bm25", "ts_rank", "sparse_bm25", "none"]
    vector_dtypes: frozenset[str]           # f32 f16 int8 binary
    async_client: bool
    backup: Literal["native", "tool", "none"]
    acorn: bool = False
    notes: tuple[str, ...] = ()

class UnsupportedFilter(Exception): op: str
class UnsupportedFeature(Exception): feature: str

class VectorStore(Protocol):
    name: str
    def __init__(self, cfg: "EngineConfig", dim: int) -> None: ...
    def connect(self) -> None: ...
    def close(self) -> None: ...
    def server_version(self) -> str: ...
    def client_version(self) -> str: ...
    def capabilities(self) -> Capabilities: ...
    def translate(self, filt: dict) -> Any: ...     # thuần, không I/O — để unit test
    def create(self, index: "IndexConfig") -> None: ...           # drop + tạo bảng/collection + payload index
    def upsert(self, ids: list[str], vecs: np.ndarray, payloads: list[dict]) -> None: ...
    def finalize(self) -> float: ...                # build/đợi index xong; trả số giây
    def search(self, q: np.ndarray, filt: dict | None, k: int, qp: "QueryParams") -> list[Hit]: ...
    def lexical_search(self, text: str, filt: dict | None, k: int) -> list[Hit]: ...
    def count(self, filt: dict | None) -> tuple[int, bool]: ...                   # (số, exact?)
    def facet(self, filt: dict | None, field: str) -> tuple[dict[str, int], bool]: ...
    def set_available(self, id: str, value: bool) -> None: ...
    def delete_ids(self, ids: list[str]) -> None: ...            # dọn vector thêm vào ở B4/B5
    def delete_all(self) -> None: ...
    def backup(self, dest: Path) -> None: ...
    def restore(self, src: Path) -> None: ...
```

- Payload chung: `{variant, taxonomy, destination, available, amenity_ids, unit_price, star_rating, lat, lon, lex_text}`.
- `QueryParams` = một phần tử đã khai triển của `query_sweep`, ví dụ `{mode: ann, ef_search: 100, iterative_scan: relaxed_order}`.

### P5.2 `runners/load.py`

`load(engine, scale, index_name)` chạy theo thứ tự:

1. `create(index)`.
2. `upsert` theo lô `load.batch_size`, thứ tự dòng xáo bằng seed.
3. `finalize()`.

Ghi `load.json` gồm `n`, `load_s`, `index_s`, `vectors_per_s`, `index_config`. Tổng `load_s + index_s` ở 1M chính là **B3**.

### P5.3 Adapter pgvector

DDL (database `vbench`, không phải `vota`; `{dim}` lấy từ config):

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;
-- unaccent() chỉ là STABLE nên không dùng được trong GENERATED column / index.
-- Wrapper IMMUTABLE, gọi kèm schema để pg_restore không lỗi search_path.
CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
  AS $$ SELECT public.unaccent('public.unaccent', $1) $$;
CREATE OR REPLACE FUNCTION haversine_m(lat1 float8, lon1 float8, lat2 float8, lon2 float8) RETURNS float8
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$
  SELECT 2 * 6371008.8 * asin(sqrt(
    power(sin(radians(lat2 - lat1) / 2), 2) +
    cos(radians(lat1)) * cos(radians(lat2)) * power(sin(radians(lon2 - lon1) / 2), 2))) $$;

DROP TABLE IF EXISTS items;
CREATE TABLE items (
  id uuid PRIMARY KEY,
  embedding halfvec({dim}) NOT NULL,
  variant text NOT NULL, taxonomy text NOT NULL, destination text NOT NULL,
  available boolean NOT NULL,
  amenity_ids smallint[] NOT NULL DEFAULT '{}',
  unit_price float8, star_rating float8,
  lat float8 NOT NULL, lon float8 NOT NULL,
  lex_text text NOT NULL,
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', f_unaccent(lower(lex_text)))) STORED
);
CREATE INDEX items_dest_tax ON items (destination, taxonomy);
CREATE INDEX items_amen     ON items USING gin (amenity_ids);
CREATE INDEX items_price    ON items (unit_price);
CREATE INDEX items_star     ON items (star_rating);
CREATE INDEX items_geo      ON items USING gist (point(lon, lat));
CREATE INDEX items_tsv      ON items USING gin (tsv);
-- finalize(): CREATE INDEX items_hnsw ON items USING hnsw (embedding halfvec_cosine_ops)
--             WITH (m = {m}, ef_construction = {ef_construction}); ANALYZE items;
```

> `EMBEDDING_AND_ENGINES.md` §4.2 đang dùng `unaccent()` trực tiếp trong GENERATED column — Postgres sẽ báo `generation expression is not immutable`. Sửa DDL đó theo wrapper `f_unaccent` ở trên.

- **Nạp:** `COPY … FROM STDIN WITH (FORMAT BINARY)` bằng psycopg 3 với `pgvector.psycopg.register_vector` và `copy.set_types([...,'halfvec',...])`. Tạo HNSW **sau** khi nạp. Ghi lẻ (B4, B5) dùng `INSERT … ON CONFLICT (id) DO UPDATE`. Query vector truyền dạng `HalfVector` hoặc cast `::halfvec` như dưới — không có toán tử `halfvec <=> vector`.
- **Search** (`score = 1 − distance`):

```sql
-- mode exact: CTE MATERIALIZED ngăn planner dùng HNSW → quét đúng tập đã lọc
WITH f AS MATERIALIZED (SELECT id, embedding FROM items WHERE {where})
SELECT id, 1 - (embedding <=> %(q)s::halfvec) AS score FROM f ORDER BY embedding <=> %(q)s::halfvec LIMIT %(k)s;

-- mode ann: trong MỘT transaction; SET LOCAL không nhận bind param → format số nguyên đã validate
BEGIN;
SET LOCAL hnsw.ef_search = {ef_search};
SET LOCAL hnsw.iterative_scan = {iterative_scan};      -- off | strict_order | relaxed_order
SET LOCAL hnsw.max_scan_tuples = {max_scan_tuples};
WITH r AS MATERIALIZED (
  SELECT id, embedding <=> %(q)s::halfvec AS d FROM items WHERE {where} ORDER BY embedding <=> %(q)s::halfvec LIMIT %(k)s)
SELECT id, 1 - d AS score FROM r ORDER BY d;           -- relaxed_order có thể lệch thứ tự → sắp lại
COMMIT;

-- mode auto: ƯỚC LƯỢNG n từ thống kê cache (đếm theo destination × taxonomy × available, tần suất amenity, giả định độc lập),
--            KHÔNG chạy COUNT trước (thêm một round trip = cộng thẳng vào P99). n ≤ auto_exact_max → exact; ngược lại → ann,
--            max_scan_tuples là trần công việc. Nhánh exact đếm luôn total trong cùng CTE (gần như miễn phí).
```

- **Dịch filter** (whitelist tên cột, luôn bind param):
  - `eq` → `col = %s`; `in` → `col = ANY(%s)`; `range` → `col >= %s` …;
  - `all` → `amenity_ids @> %s::smallint[]`; `any` → `amenity_ids && %s::smallint[]`;
  - `not` → `NOT (…)`; `and`/`or` → ngoặc;
  - `id_in` → `id = ANY(%s::uuid[])`;
  - `geo` → `point(lon,lat) <@ box(point(%s,%s), point(%s,%s)) AND haversine_m(lat, lon, %s, %s) <= %s`, trong đó bbox: Δlat = r/111.320, Δlon = r/(111.320·cos lat).
- **Lexical:** tsquery OR từ `lexical.tokens(text)` (`to_tsquery('simple', 'a | b | …')`, escape từng token) + `ts_rank(tsv, q)`, AND với `{where}`.
- **count / facet:** `SELECT count(*)`, `SELECT {field}, count(*) … GROUP BY 1` (field ∈ taxonomy, destination, variant) → exact.
- **backup/restore:**
  - `docker exec <container> pg_dump -U postgres -Fc -d vbench -f /backup/items.dump`;
  - `pg_restore -U postgres --clean --if-exists -d vbench /backup/items.dump`.
- **Capabilities:** exact ✓, mọi filter op ✓, geo native, count exact, facet exact, lexical `ts_rank`, dtypes {f32, f16, binary}, async ✓ (asyncpg/psycopg async), backup native, acorn ✗.

### P5.4 `vb smoke <engine>`

Chạy 10 query (2–3 query mỗi bucket) với cấu hình đầu tiên của `query_sweep`. In bảng: `qid · bucket · filter_type · n_match · recall@10 · vi_phạm · top-3 tên (engine | GT)`.

Thoát mã 2 nếu có vi phạm filter, hoặc nếu `mode=exact` mà recall < 1.

**Chạy thử:**

```bash
python -m evaluation.vector_bench engine up pgvector
python -m evaluation.vector_bench load pgvector --scale catalog
python -m evaluation.vector_bench smoke pgvector
pytest src/evaluation/vector_bench/tests/test_translate_pgvector.py
pytest -m integration -k pgvector        # catalog fake N=2.000, mọi loại filter
```

**Done khi:**

- Test dịch filter (AST → SQL, so chuỗi mẫu) pass.
- `load` in `load_s` và `index_s`.
- `smoke` ở mode exact: recall@10 = 1,0 cho cả 10 query, 0 vi phạm.
- Integration test:
  - mọi loại filter có precision = 1,0;
  - `count` = evaluator (lệch tối đa bằng `n_boundary` với geo);
  - `backup` → `delete_all` → `restore` ra đúng số dòng.

---

## Part 6 — Quality runner: A1, A3, A4, A5 · 6b: A2 + công cụ gold

**Mục tiêu:** đo nhóm A và chọn cấu hình (b) — cấu hình rẻ nhất đạt A1 ≥ 0,95 — để Part 11 đo hiệu năng đúng cấu hình đó.

**File:** `runners/quality.py`, `runners/gold.py`.

### P6.1 Recall có dung sai (dùng cho A1, smoke, G7)

Với query *i*, k = 10:

- `G` = `min(k, n_match_i)` dòng đầu của GT (tập chặt); `s_last` = điểm của phần tử cuối trong `G`.
- Kết quả engine → đổi id sang `row`, bỏ các dòng vùng biên. Với mỗi dòng còn lại:
  - **vi phạm** nếu `mask[row] = False`;
  - ngược lại **trúng** nếu `row ∈ G` hoặc cosine thật (tính lại fp32 từ `vectors.npy`) ≥ `s_last − tie_eps`.
- `recall_i = min(trúng, |G|) / |G|`.
- `n_match_i = 0`: không tính recall; engine phải trả 0 kết quả, trả gì cũng là vi phạm.
- Ghi thêm `short_i` = engine trả ít hơn `|G|` kết quả. Đây là dấu hiệu post-filter mất kết quả, ví dụ pgvector khi tắt iterative scan.

### P6.2 Quy trình `vb quality <engine> --scale S`

1. Engine phải đã `load` ở scale S với index config đang xét. Chạy lần lượt từng `index_configs`.
2. Khai triển `default_query` + `query_sweep` thành danh sách cấu hình (ví dụ `ann × ef ∈ {40…400}`). Với mỗi cấu hình, chạy 1.000 query **một client, tuần tự**, k = 10, và ghi latency. Bỏ mode `exact` ở scale có N > `quality.exact_max_rows` *(đề xuất 200.000)* vì quét 1M dòng cho mỗi query không phục vụ quyết định nào.
3. Mỗi cấu hình tính:
   - `a1_by_bucket` (trung bình recall theo bucket);
   - `a1_min` = min trên các bucket;
   - `a1_by_type`, `a1_by_slice`;
   - A3 = 1 − vi phạm / số kết quả (không tính vùng biên);
   - latency mean / p50 / p95 / p99;
   - `n_short`.
4. **Cấu hình (a)** = `default_query` (tham số mặc định của engine). **Cấu hình (b)** = cấu hình có **P99 một client** thấp nhất (hoà thì xét latency trung bình) trong số đạt `a1_min ≥ a1_pass`. Không cấu hình nào đạt thì chọn `a1_min` cao nhất và gắn `a1_fail: true`. Điểm A1 và A3 lấy theo (b).
5. **A4:** `a4_n_filters` query có filter đầu tiên.
   - `count` so với `n_match`, cho lệch tối đa `n_boundary`;
   - `facet` theo taxonomy và destination so với `facets_gt.json` (khoảng cách L1);
   - ghi `count_exact_rate`, `count_mae`, `facet_l1`, cùng `capabilities.count_exact` / `facet`.
6. **A5** (chỉ ở `quality.a5.scales`): rebuild `rebuilds` lần (`delete_all` → `load` với seed xáo khác) → chạy `n_queries` query với cấu hình (b) → Jaccard trung bình theo cặp của tập top-10.

Đầu ra: `quality.json` (các khoá `configs[]`, `config_a`, `config_b`, `a1_fail`, `A1`, `A3`, `A4{…}`, `A5{…}`) và `quality_queries.parquet` (kết quả từng query × cấu hình).

### P6.3 Part 6b — A2 và công cụ gold (chỉ scale `catalog`)

**Gán nhãn** — quy trình EMBEDDING_AND_ENGINES §9, người gán do team chốt:

1. `vb gold pool --drafts gold/drafts.txt --engine pgvector [--depth 20]`: mỗi dòng draft là một câu query (tuỳ chọn thêm `\t<slice>`).
   - Hợp dense top-20 (cấu hình b) với lexical top-20 → `gold/pool.csv`.
   - Cột: `qid, query, slice, product_id, name, variant, destination, from(dense|lexical|both), rank_dense, rank_lex, label`.
2. Người gán điền `label`:
   - 2 = đúng thứ khách tìm;
   - 1 = liên quan một phần (đúng loại hoặc đúng nơi nhưng thiếu điều kiện);
   - 0 = không liên quan;
   - để trống = chưa gán.
3. `vb gold import gold/pool_labeled.csv` → `gold/gold.jsonl`: `{qid, text, slice, filter (tuỳ chọn), judgments: {product_id: 0|1|2}}`. Cảnh báo query không có nhãn ≥ 1.

**Đo A2** (`vb quality <engine> --only A2`, cần ≥ `a2.min_gold` query):

- dense top-50 (cấu hình b, filter của gold) + lexical top-50 (kênh lexical **của engine**) → RRF k = 60 ở application (giống nhau cho mọi engine) → top-10.
- nDCG@10 với gain `2^rel − 1`; tài liệu chưa gán nhãn tính 0; báo thêm Judged@10.
- Báo ba cột dense-only / lexical-only / fused, theo slice. Engine không có lexical → `lexical: n/a`, fused = dense.
- Nếu run đã có kết quả A2 của pgvector: paired bootstrap (`a2.bootstrap` lần) cho Δ = fused(engine) − fused(pgvector) → trung bình, CI95, p một phía = P(Δ ≤ 0).
- Ở scale catalog, dense của mọi engine gần như trùng nhau (cùng vector, recall ~1). **A2 thực chất so kênh lexical của các engine** — ghi chú này vào report.

**Chạy thử:**

```bash
python -m evaluation.vector_bench quality pgvector --scale catalog
python -m evaluation.vector_bench quality pgvector --scale catalog --only A2 --gold tests/fixtures/gold_small.jsonl --min-gold 5
```

**Done khi:**

- pgvector ở catalog: `exact` có A1 = 1,0.
- Sweep ann: recall không giảm khi tăng `ef_search`. Nếu planner dùng HNSW cho query có filter chọn lọc thì `default_query` (`iterative_scan=off`) sẽ có `n_short > 0` ở `b01` — hành vi đúng của post-filter, không phải lỗi. Ở catalog nhỏ, planner có thể chọn quét B-tree/GIN + sort thay vì HNSW; adapter ghi `EXPLAIN (FORMAT JSON)` của 20 query mẫu mỗi cấu hình (`plan_uses_hnsw_rate`) để biết.
- Cấu hình (b) được ghi; A3 = 1,0; A4 exact; A5 ≥ 0,9.
- A2 chạy với fixture 10 query trên catalog fake và ra số.

**Ước lượng chạy:** 5–15 phút / engine ở catalog; 100k tuỳ số cấu hình sweep.

---

## Part 7 — Adapter Qdrant (ứng viên đầu tiên)

**File:** `engines/qdrant.py`, `tests/test_translate_qdrant.py`.

- **Collection** `items`:
  - named vector `dense` = `VectorParams(size=dim, distance=COSINE, datatype=FLOAT16, hnsw_config=HnswConfigDiff(m, ef_construct))`;
  - sparse vector `bm25` = `SparseVectorParams(modifier=Modifier.IDF)`.
  - Index config `forced_hnsw` thêm `optimizers_config.indexing_threshold` và `hnsw_config.full_scan_threshold` rất nhỏ. **VERIFY** ngữ nghĩa: ở nhiều bản, `indexing_threshold = 0` nghĩa là *tắt* index.
- **Payload index** tạo **trước** khi nạp: keyword (`taxonomy`, `destination`, `variant`), bool (`available`), integer (`amenity_ids`), float (`unit_price`, `star_rating`), geo (`location = {lat, lon}`).
- **Nạp:** `upsert(…, wait=True)` theo lô.
  - Vector `dense` là list fp32 lấy từ `vectors.npy`.
  - Vector `bm25` = BM25 phía client: `tf·(k1+1) / (tf + k1·(1 − b + b·dl/avgdl))`, k1 = 1,2, b = 0,75, index = `mmh3.hash(token, signed=False)`, token lấy từ `lexical.tokens`. IDF do server nhân qua `Modifier.IDF`.
- **finalize():** đợi collection `green`. Với `forced_hnsw` đợi thêm `indexed_vectors_count ≥ points_count`.
- **search:** `query_points(query=q, using="dense", query_filter=…, limit=k, search_params=SearchParams(hnsw_ef=…, exact=mode=="exact"))`.
  - `ann_acorn`: **VERIFY** tên tham số ACORN (1.16+). Không có → `capabilities.acorn=False` và bỏ mục sweep đó.
- **count:** `count(count_filter, exact=True)`.
- **facet:** `facet(key, facet_filter, exact=True, limit=1000)`.
- **lexical:** `query_points(query=SparseVector(indices, values=1.0), using="bm25", query_filter=…)`.
- **set_available:** `set_payload(…, wait=True)`.
- **backup:** `create_snapshot` (file nằm ở `bench_out/backups/qdrant`); restore bằng `recover_snapshot` từ file đó (**VERIFY** dạng URI `file://`).
- **Capabilities:** exact ✓, mọi filter op ✓, geo native, count exact, facet exact, lexical `sparse_bm25`, dtypes {f32, f16, int8, binary}, async ✓ (`AsyncQdrantClient`), backup native.

> Ở catalog (~5.000 × 1024 × 2 byte ≈ 10 MB), `indexing_threshold` mặc định (20.000 KB) khiến Qdrant **không** build HNSW mà quét toàn bộ. Đó là hành vi mặc định thật, nên là cấu hình (a). `forced_hnsw` đo hành vi ANN ở cùng quy mô. Báo cả hai.

**Chạy thử:**

```bash
python -m evaluation.vector_bench engine up qdrant
python -m evaluation.vector_bench load qdrant --scale catalog          # lần lượt index default, forced_hnsw
python -m evaluation.vector_bench smoke qdrant
python -m evaluation.vector_bench quality qdrant --scale catalog
```

**Done khi:** test dịch filter pass; `smoke` 0 vi phạm; `quality.json` có đủ hai index config; so được với pgvector trong cùng run.

---

## Part 8 — Bốn adapter còn lại (8a–8d, làm độc lập)

Mỗi adapter có cùng tiêu chí done như Part 7: test dịch filter, `load`, `smoke` 0 vi phạm, `quality` ra file. Chỗ **VERIFY** phải tra docs đúng phiên bản chạy; không có tính năng thì báo unsupported (§1.7).

### 8a — pgvectorscale

- Kế thừa adapter pgvector, cùng DDL và cùng cách dịch filter. Thêm `CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE`.
- Cột vector: `halfvec` nếu `diskann` hỗ trợ (**VERIFY** bằng tạo thử index trên bảng tạm trong `doctor`), không thì `vector({dim})` fp32.
- Index `diskann`: `USING diskann (embedding vector_cosine_ops)`.
- Index `diskann_labels`:
  - thêm cột `labels smallint[]` = `amenity_ids`;
  - `USING diskann (embedding vector_cosine_ops, labels)`;
  - query có `all`/`any` trên amenity thì thêm `labels && ARRAY[id_đầu]::smallint[]` để index lọc theo nhãn (ngữ nghĩa ANY-of), và giữ nguyên điều kiện đầy đủ trong WHERE.
- Query ann: `SET LOCAL diskann.query_search_list_size = {n}; SET LOCAL diskann.query_rescore = {r};` + mẫu CTE như pgvector.

### 8b — Milvus (standalone theo compose chính thức)

- **Schema:**
  - `id` VARCHAR(36) primary; `dense` FLOAT16_VECTOR(dim);
  - `lex_text` VARCHAR, `enable_analyzer=True`, `analyzer_params = {tokenizer: standard, filter: [lowercase, asciifolding]}` (**VERIFY** tên filter);
  - `sparse` SPARSE_FLOAT_VECTOR là đầu ra của `Function(type=BM25, input=lex_text)`;
  - `variant`, `taxonomy`, `destination` VARCHAR; `available` BOOL;
  - `amenity_ids` ARRAY(INT16, max_capacity 256);
  - `unit_price`, `star_rating` FLOAT `nullable=True`;
  - `lat`, `lon` FLOAT.
- **Index:**
  - `dense` HNSW (M, efConstruction, COSINE);
  - `sparse` SPARSE_INVERTED_INDEX (metric BM25);
  - index vô hướng (INVERTED / STL_SORT) theo khuyến nghị docs cho các trường lọc.
- **finalize():** flush → create_index → load collection → đợi index build xong.
- **search:** `search(data=[q], anns_field="dense", filter=expr, limit=k, search_params={"metric_type":"COSINE","params":{"ef":…}}, consistency_level=cfg)`. Không có mode exact.
- **Dịch filter** sang chuỗi biểu thức (escape nháy):
  - `destination == "…"`, `taxonomy in [...]`, `unit_price <= …`;
  - `ARRAY_CONTAINS_ALL(amenity_ids, [..])`, `ARRAY_CONTAINS_ANY(..)`;
  - `not (…)`, `id in [...]`;
  - `range` trên trường nullable phải loại NULL (**VERIFY**);
  - geo: dùng kiểu GEOMETRY + `ST_DWITHIN` nếu bản 3.0 có (**VERIFY**), không thì `emulated` (bbox trên `lat`/`lon` + haversine phía client) và gắn cờ.
- **count:** `query(filter=expr, output_fields=["count(*)"])` → exact.
- **facet:** API aggregate/group-by của 3.0 (**VERIFY**); không có → `UnsupportedFeature`.
- **lexical:** `search(data=[text], anns_field="sparse", search_params={"metric_type":"BM25"})`.
- **set_available:** upsert lại nguyên dòng.
- **backup:** công cụ `milvus-backup` → `capabilities.backup="tool"`; chưa cài thì G7 ghi `manual`.
- **B4:** đo cả `consistency_level` mặc định lẫn `Strong`.

### 8c — Weaviate

- **Kết nối:** `weaviate.connect_to_local(port=58080, grpc_port=55051)`. Client v4 cần cổng gRPC.
- **Collection** `Items`:
  - object uuid = `productId`; vector tự cung cấp (không vectorizer — **VERIFY** cú pháp theo version client);
  - `variant`, `taxonomy`, `destination`: TEXT `tokenization=field`;
  - `available` BOOL; `amenity_ids` INT_ARRAY; `unit_price`, `star_rating` NUMBER; `location` GEO_COORDINATES;
  - `lex_text` TEXT `tokenization=word` (+ accent folding nếu 1.37 hỗ trợ — **VERIFY**);
  - `inverted_index_config(index_null_state=True)`.
- **Index:** hai index config — HNSW `filter_strategy` = `sweeping` và `acorn`.
- **Nạp:** batch `fixed_size(1000)`; `failed_objects` phải rỗng.
- **search:** `query.near_vector(near_vector=q, filters=…, limit=k, return_metadata=MetadataQuery(distance=True))`. `ef` là tham số HNSW đổi được → `config.update(...)` trước mỗi cấu hình sweep. Không có mode exact.
- **Dịch filter:**
  - `by_property(f).equal(v)`, `contains_any` (cho `in`), `greater_or_equal` / `less_or_equal`;
  - `contains_all(ids)`, `contains_any(ids)`;
  - `not any`: `contains_none` (có từ Weaviate 1.33, cùng toán tử `Not`);
  - geo: `within_geo_range(GeoCoordinate(lat, lon), distance=r)`;
  - `Filter.all_of` / `any_of`; `id_in`: `Filter.by_id().contains_any`.
- **count:** `aggregate.over_all(filters=…, total_count=True)`.
- **facet:** `aggregate.over_all(group_by=GroupByAggregate(prop=field), filters=…)`. Tính exact hay không: **VERIFY** docs.
- **lexical:** `query.bm25(query=text, query_properties=["lex_text"], filters=…)`.
- **set_available:** `data.update(uuid, properties)`.
- **backup:** `backup.create(backend="filesystem", include_collections=["Items"], wait_for_completion=True)`; restore sau khi xoá collection.

### 8d — OpenSearch

- **Index** `items`: 1 shard, 0 replica.
  - Analyzer `vi_fold` = tokenizer `standard` + filter `lowercase`, `asciifolding`.
  - Mapping: `embedding` `knn_vector` (dim); `taxonomy`, `destination`, `variant` keyword; `available` boolean; `amenity_ids` short; `unit_price` double; `star_rating` float; `location` geo_point; `lex_text` text (`vi_fold`).
- **Index config:**
  - `faiss_hnsw_sqfp16` — engine faiss, `space_type: innerproduct` (vector đã chuẩn hoá nên bằng cosine), m, ef_construction, encoder `sq` fp16;
  - `lucene_hnsw` — `cosinesimil`.
- **Nạp:** `refresh_interval: -1` → bulk 1.000 → trả `1s` → `_refresh` → `_forcemerge?max_num_segments=1` nếu `force_merge: true` (ghi vào kết quả).
- **search ann:** `{"knn": {"embedding": {"vector": q, "k": k, "filter": {...}, "method_parameters": {"ef_search": ef}}}}` (**VERIFY** `method_parameters` theo version).
- **search exact:** `script_score` với script `knn_score` (lang `knn`, space_type của index) trên `bool.filter`.
- **Dịch filter:**
  - `eq` → `term`; `in` → `terms`; `range` → `range`;
  - `all` → `bool.filter` gồm các `term`; `any` → `terms`; `not` → `bool.must_not`;
  - `geo` → `geo_distance`; `or` → `bool.should` + `minimum_should_match: 1`;
  - `id_in` → `ids`.
- **count / facet:** `_count`; terms aggregation `size: 1000` (1 shard → exact).
- **lexical:** `match` với `operator: or` + filter.
- **set_available:** `update` không ép refresh — visible sau refresh interval, đúng hành vi production cho B4/G6.
- **backup:** repo `fs` (`path.repo`) → `_snapshot` → xoá index → restore.

---

## Part 9 — Gate G1–G7

**Mục tiêu:** loại sớm engine không đạt yêu cầu tối thiểu, trước khi tốn giờ đo hiệu năng. Chạy ở scale `catalog`.

**File:** `runners/gates.py`. Lệnh `vb gate <engine> [--only g1,g3]`. Đầu ra `gates.json`; thoát mã 2 nếu có gate `fail`.

| Gate | Cách chạy | Pass khi |
|---|---|---|
| G1 | `down --volumes` → `docker compose pull` (đo `pull_s`, không tính) → đo `up -d` + `wait_healthy` = `up_s`; đếm container của profile | `up_s ≤ 900` và `≤ 3` container |
| G2 | Đọc `manual/<engine>.yaml` → `license.verdict` | `pass`; `conditional` → được đo tiếp nhưng gắn cờ "cần pháp chế"; `null` → `pending` |
| G3 | `per_type` query cho mỗi loại `all_amenity`, `not_amenity`, `range`, `geo`. Lấy từ `queries.jsonl`; thiếu thì sinh thêm bằng cùng generator vào `gate_queries.jsonl`. Chạy với cấu hình (a), k = 20, đếm vi phạm (bỏ vùng biên) | 0 vi phạm và không có `UnsupportedFilter`. Geo giả lập → `pass_emulated` |
| G4 | `n_filters` query có filter: `count` và `facet` so với GT | Khớp (± `n_boundary`) và capability exact. Capability approx có cờ → `pass_flagged` |
| G5 | `capabilities()` + chạy thật một lệnh bằng async client (ví dụ count). Tạo collection 1024-d (nếu `embedding.dim` < 1024 thì tạo collection tạm 1024-d, nạp 10 vector). Có dtype f16 hoặc int8 | Đủ cả ba |
| G6 | 20 item `available=true`: query = vector của chính item, filter `available = true`, item phải nằm trong top-10 → `set_available(false)` → poll cùng query mỗi `poll_ms` tới khi item biến mất → thời gian `t` → trả lại `true` | p95(`t`) ≤ 5 s |
| G7 | 50 query → lưu top-10 (cấu hình a) → `backup` → `delete_all` → `restore` (đo `restore_s`) → đếm = N và top-10 của 50 query trùng khớp | Trùng 100% và `restore_s ≤ 600`. `backup = "tool"` mà chưa cài tool → `manual` |

**Chạy thử:** `python -m evaluation.vector_bench gate pgvector` rồi `gate qdrant`.

**Done khi:**

- pgvector pass G1, G3–G7; G2 `pending` cho tới khi điền `manual/pgvector.yaml`.
- Với một engine bị ép thiếu toán tử (test giả lập raise `UnsupportedFilter`), G3 ra `fail` kèm tên toán tử.

---

## Part 10 — Dataset scale 100k / 1M

**Mục tiêu:** vector tiếng Việt thật ở quy mô lớn, metadata theo phân bố catalog, cùng bộ filter và GT như catalog.

**File:** `dataset/scale.py`. Lệnh `vb scale-data 100k|1m [--vectors cohere-vi|fake] [--correlation none|cluster]`.

1. **Vector (`cohere-vi`):**
   - `datasets.load_dataset("CohereLabs/wikipedia-2023-11-embed-multilingual-v3", "vi", split="train", streaming=True)`: subset tiếng Việt ~2,84 triệu passage, trường `emb` 1024-d.
   - Đọc `size + n_queries + n_reserve` dòng đầu theo thứ tự dataset → xáo bằng seed rồi chia thành base / query / reserve (query không bị dồn vào vài bài viết liền nhau) → L2-normalize → fp16.
   - Ghi `vectors.npy` (memmap), `query_vectors.npy`, `reserve.npy` (vector chưa nạp, dùng cho B4/B5).
   - Dung lượng tải ước ~5 KB/dòng: 100k ≈ 0,5 GB, 1M ≈ 5 GB.
   - Dataset card không ghi license (kiểm 22/09) → chỉ dùng benchmark nội bộ, không phân phối lại vector.
2. **Metadata:**
   - Mỗi dòng lấy mẫu một search unit "khuôn" từ `catalog/items.parquet` (trọng số theo tỷ lệ variant) → chép `variant`, `taxonomy`, `destination`, `amenity_ids`, `unit_price`, `star_rating`, `available`.
   - `lat/lon` = khuôn + nhiễu N(0, `geo_jitter_m`).
   - `lex_text` = `title` của passage (không chấm A2 ở scale này).
   - `correlation=none` (mặc định): metadata không tương quan với vector — trường hợp khó nhất cho filtered ANN, nên A1 ở scale là **cận dưới bảo thủ**.
   - `correlation=cluster`: MiniBatchKMeans (K = số destination) trên mẫu 100k → gán destination theo cụm → filter destination tương quan với vùng vector, gần dữ liệu thật hơn.
3. Tự chạy `queries --scale S` (filter trên metadata tổng hợp, không có text) và `gt --scale S`.
4. `--vectors fake`: vector cụm ngẫu nhiên như Part 2, để chạy thử không tải gì.

Đầu ra: `bench_out/data/<scale>/{items.parquet, vectors.npy, query_vectors.npy, reserve.npy, queries.jsonl, gt.npz, facets_gt.json, stats.json}`. `stats.json` ghi nguồn, `correlation`, số byte đã tải, thời gian.

**Chạy thử:**

```bash
python -m evaluation.vector_bench scale-data 100k --vectors fake      # thử khung
python -m evaluation.vector_bench scale-data 100k                     # thật
```

**Done khi:**

- Đúng shape; norm ≈ 1.
- Bucket đủ quota (ở 1M, `b01` = 500–2.000 item).
- Tự kiểm tra GT pass.

**Ước lượng chạy:** 100k: 5–15 phút; 1M: tới ~1 giờ, phụ thuộc băng thông; GT vài phút.

---

## Part 11 — Hiệu năng B1–B6 + tài nguyên C1–C2, D1–D3

**Mục tiêu:** đo với **cấu hình (b)** lấy từ `quality.json` cùng scale (thiếu → báo "chạy quality trước"). Không tính thời gian embed query — query vector đã tính sẵn.

**File:** `runners/perf.py`, `runners/resources.py`. Lệnh `vb perf <engine> --scale S [--only B1,B2,…]`.

**Load generator — open-loop, vì P99 là chỉ số latency chính:**

- Một process lập lịch phát request theo tốc độ cố định (`rates_qps`, khoảng cách đều) vào hàng đợi. Pool worker đủ lớn (≥ 64 process, an toàn với spawn; mỗi worker tự tạo adapter từ config) để không thành nút cổ chai.
- **Latency = thời điểm nhận kết quả − thời điểm *lẽ ra* gửi theo lịch.** Request phải chờ vì engine chậm vẫn bị tính. Closed-loop (N client, gửi tiếp khi nhận xong) bỏ sót đuôi — ví dụ của wrk2: P99 đo sai 6,04 ms so với đo đúng 1,27 s.
- Warm-up `warmup_s`, bỏ khỏi số liệu. Timeout `timeout_ms` tính vào phân vị với giá trị = timeout, và vào tỷ lệ lỗi. k = `perf.k`.
- Ghi toàn bộ mẫu `(scheduled_ns, start_ns, end_ns, ok, n_results)`; báo P50/P95/**P99**/P99.9 và CI 95% của P99 (bootstrap).
- Hiệu chỉnh harness: `vb perf null` (engine giả trả ngay) phải có P99 < `harness_max_p99_ms`, không thì số đo không dùng được.
- Engine bị giới hạn CPU/RAM theo `engine_limits` để chừa tài nguyên cho client chạy cùng máy — ghi cả hai con số vào kết quả.

| Metric | Cách đo | Ghi |
|---|---|---|
| **B1** | Tải open-loop `b1_rate_qps` (100 QPS) trong `duration_s`, lặp `reps` lần | **P99** (median các lần) + CI; kèm P50/P95/P99.9 và tỷ lệ timeout |
| **B2** | Lần lượt các mức `rates_qps`, mỗi mức `duration_s`; dừng khi P99 vượt ngưỡng B1 của scale (vẫn ghi mức đó) | Đường cong (QPS, P50, P99); B2 = mức tải lớn nhất có P99 ≤ ngưỡng |
| **B3** | Lấy từ `load.json`: `load_s + index_s` | Phút; chấm ở 1M |
| **B4** | Đơn lẻ: upsert 1 vector từ `reserve` (payload chép từ một item) → poll `search(v, k=1)` mỗi `poll_ms` tới khi top-1 là id mới; `n_single` lần. Lô: `n_batches` lô × `batch_size` → poll tới khi phần tử cuối lô xuất hiện. Dọn bằng `delete_ids` | p95 đơn lẻ, p95 lô. Milvus đo cả consistency mặc định và `Strong`; chấm theo mặc định |
| **B5** | Chạy B1 hai lần: tĩnh, và cùng lúc với process ghi `write_rate_per_s` vector/s (lô 10 mỗi 0,1 s) | `P99_ghi / P99_tĩnh − 1`, kèm tỷ lệ timeout |
| **B6** | P99 ấm (tải `b6.rate_qps` trong `b6.duration_s`) → `restart` → `wait_healthy` (Milvus: đợi collection load) → cùng tải ngay → P99 lạnh; lặp 3 lần | Median của `P99 lạnh / P99 ấm`; `os_cache_dropped: false` (không xoá page cache của host) |
| **C1** | Sampler `docker stats` mỗi `sampler_interval_s` trong lúc B2 (và lúc load) | RAM đỉnh GB (cộng mọi container của profile), CPU trung bình |
| **C2** | Dung lượng named volume của profile sau khi load | GB và tỷ lệ so với byte vector thô (N × dim × 2) |
| **D1** | Số container trong profile | Số |
| **D2** | Quy trình G7 ở scale lớn nhất đã chạy | `restore_s` |
| **D3** | Probe endpoint Prometheus trong config (Qdrant `:56333/metrics`, Milvus `:59091/metrics`, Weaviate `:52112/metrics`; Postgres, OpenSearch mặc định không có) + `D3_json_logs` trong `manual/` | both / one / none |

Đầu ra: `perf.json` (B1–B6 + đường cong) và `resources.json` (C1, C2, D1–D3).

**Chạy thử:**

```bash
python -m evaluation.vector_bench perf pgvector --scale catalog --only B1,B2      # thử nhanh
python -m evaluation.vector_bench perf pgvector --scale 100k
```

**Done khi:**

- Đủ file; `vb perf null` cho P99 harness < 2 ms.
- Đường B2: P99 tăng theo mức tải và có điểm gãy rõ khi engine bão hoà.
- C1 có mẫu trong suốt B2.
- Mọi vector thêm vào ở B4/B5 đã được xoá: count sau khi chạy = N.

**Ước lượng chạy:** 30–45 phút / engine / scale.

---

## Part 12 — Số nhập tay, chấm điểm, quy tắc quyết định, report

**File:** `manual/<engine>.yaml`, `scoring.py`, `decide.py`, `report.py`.

### P12.1 `manual/<engine>.yaml`

```yaml
engine: qdrant
license: {spdx: null, verdict: null, note: ""}   # G2 — verdict: pass | conditional | fail (V-OTA / pháp chế quyết)
C3_vnd_month: null               # VM nhỏ nhất đạt B1 + B2 ở scale lớn nhất đã đo, theo bảng giá VPS đang dùng
C4_migration_person_days: null   # adapter SearchClient + job sync product_vectors + backup/monitoring + test
C5_ops_hours_month: null
D3_json_logs: null               # true | false
D4: {releases_12m: null, in_place_upgrade: null}
D5: null                         # same_db | sync_measured | manual_sync
E: {sparse: null, multivector: null, bm25_native: null, vi_tokenizer: null, geo: null,
    facet_server: null, quantization: null, hybrid_server: null, mmr_server: null, multitenancy: null}
```

**Điền sẵn** — các giá trị suy trực tiếp từ kiến trúc hoặc đo được:

- pgvector: `C4 = 0`, `D5 = same_db`.
- pgvectorscale: `D5 = same_db`.
- Bốn engine riêng: `D5 = sync_measured`.
- Mục E tự điền từ `capabilities()`:
  - `sparse`: có kiểu sparse vector;
  - `geo`: `native`;
  - `facet_server`: facet ≠ none;
  - `quantization`: dtypes có int8/binary/f16;
  - `bm25_native`: server tự tính BM25 từ văn bản thô.
- Còn lại để `null` cho người điền.

`vb score` báo thiếu và dừng, trừ khi có `--allow-missing` (khi đó tính 0 điểm và gắn cờ).

### P12.2 Giá trị thô → điểm 0–10

**Giá trị thô:**

- A1, A3: min trên các scale đã chạy (cấu hình b).
- A5: min trên `a5.scales`.
- A2: fused nDCG@10 ở catalog.
- A4: rời rạc (exact / approx_flagged / none), lấy trường hợp xấu nhất.
- B1, B2: chấm từng scale có ngưỡng (100k, 1m), rồi lấy trung bình.
- B3, C1: chấm ở 1m. Không chạy 1m thì dùng minmax ở scale lớn nhất và gắn cờ `partial_scale`.
- B4 = min(điểm đơn lẻ, điểm lô).
- B5, B6, C2: ở scale lớn nhất.
- C3, C4, C5: từ `manual/`.
- D1–D5: rời rạc.
- E: điểm checklist.

**Chuẩn hoá** (VECTOR_DB_SELECTION §4.6):

```
higher-better, ngưỡng T, sàn F, B = giá trị tốt nhất trong các engine đạt T:
  raw ≥ T      → s = 10 nếu B = T, ngược lại 6 + 4·(raw − T)/(B − T)
  F ≤ raw < T  → s = 5·(raw − F)/(T − F)
  raw < F      → s = 0
lower-better: đối xứng (B = nhỏ nhất trong các engine đạt T; floor_factor → F = T × hệ số)
minmax (lower-better): s = 10·(max − raw)/(max − min); mọi engine bằng nhau → 10
A2: T = A2(pgvector) − 0,01 ; F = A2(pgvector) − 0,05
E:  s = 10 × điểm / điểm tối đa (mục trong planned_use_double tính 2)
Tổng = Σ w_m · s_m / 100   (Σ w = 100 → thang 0–10)
Độ nhạy: nhóm g đổi trọng số G → G' thì w'_m = w_m · G'/G cho mọi m ∈ g; tính lại tổng và thứ hạng
```

### P12.3 `vb decide` — quy tắc VECTOR_DB_SELECTION §7, cài thành code

1. Loại engine có gate `fail`. G2 `conditional` vẫn xét nhưng gắn cờ.
2. Scale lớn nhất đã chạy ≤ 100k: giữ `baseline` (pgvector). Chỉ đổi khi một ứng viên thoả **cả ba**:
   - tổng ≥ tổng baseline + `min_total_margin`;
   - điểm nhóm A > nhóm A của baseline;
   - đứng #1 ở cả hai biến thể độ nhạy.

   Nhiều ứng viên thoả thì chọn tổng cao nhất.
3. Có chạy 1m: nếu cả pgvector lẫn pgvectorscale trượt ngưỡng B1 hoặc B2 ở 1m (cấu hình b) → chọn tổng cao nhất trong các engine có A1 ≥ 0,95; hoà thì ưu tiên ít container hơn (D1). Không thì áp quy tắc 2.
4. Quy tắc lexical: nếu gold có slice `ten_rieng`/`amenity` và fused nDCG của `lexical_rule.candidate` hơn pgvector ≥ `min_ndcg_gain` với p < 0,05 → **khuyến nghị riêng** "cân nhắc sidecar lexical", không đổi engine vector.
5. Ghi `decision.json`: `winner`, `rule_applied`, `reasons[]` (câu tiếng Việt kèm số), `excluded{}`, `flags[]`, metadata (`run_id`, phiên bản engine/client, `git_commit`, sha dataset, model embed).

### P12.4 `vb report`

`bench_out/runs/<run_id>/report.md`:

- đầu trang: run, ngày, máy, profile, scale, model, sha dữ liệu;
- bảng gate;
- **bảng §6 đã điền** (mỗi ô: `giá trị thô · điểm`);
- tổng và hai biến thể độ nhạy;
- quyết định kèm lý do.

Phụ lục của report:

- A1 theo bucket × loại × scale;
- đường cong B2 (PNG nếu có matplotlib);
- A2 theo slice;
- ma trận capabilities;
- danh sách **VERIFY** đã xác minh ra sao (hỗ trợ / giả lập / không hỗ trợ);
- lỗi.

Kèm `scores.csv`.

**Chạy thử:**

```bash
python -m evaluation.vector_bench score --allow-missing && python -m evaluation.vector_bench decide && python -m evaluation.vector_bench report
```

**Done khi:**

- Unit test chuẩn hoá (ca tính tay: đạt, dưới ngưỡng, dưới sàn, minmax bằng nhau).
- Unit test đổi trọng số độ nhạy.
- Unit test quy tắc quyết định trên bảng điểm tổng hợp giả: baseline giữ khi ứng viên thắng < 1,5; đổi khi thoả cả ba điều kiện; quy tắc 1M.
- Report sinh được với pgvector + Qdrant trên dữ liệu fake.

---

## Phụ lục A — Dịch filter AST sang từng engine

| AST | pgvector / pgvectorscale | Qdrant | Milvus | Weaviate | OpenSearch |
|---|---|---|---|---|---|
| `eq(f, v)` | `f = %s` | `FieldCondition(key=f, match=MatchValue(value=v))` | `f == v` | `by_property(f).equal(v)` | `term` |
| `in(f, […])` | `f = ANY(%s)` | `MatchAny(any=[…])` | `f in […]` | `contains_any([…])` | `terms` |
| `range` | `f >= %s AND f <= %s` | `Range(gte, lte, …)` | `f >= v and f <= w` | `greater_or_equal` / `less_or_equal` | `range` |
| `all(amenity_ids, [a,b])` | `amenity_ids @> %s::smallint[]` | một `must` `MatchValue` cho mỗi id | `ARRAY_CONTAINS_ALL(amenity_ids, [a,b])` | `contains_all([a,b])` | `bool.filter: [term a, term b]` |
| `any(amenity_ids, […])` | `amenity_ids && %s::smallint[]` | `MatchAny` | `ARRAY_CONTAINS_ANY(…)` | `contains_any` | `terms` |
| `not(X)` | `NOT (X)` | `must_not: [X]` | `not (X)` | `contains_none` / `Not` (≥ 1.33) | `bool.must_not` |
| `and` / `or` | `(… AND …)` / `(… OR …)` | `must` / `should` | `and` / `or` | `Filter.all_of` / `any_of` | `bool.filter` / `bool.should` + `minimum_should_match: 1` |
| `geo` | `point(lon,lat) <@ box(…) AND haversine_m(…) <= r` | `GeoRadius(center, radius)` | GEOMETRY `ST_DWITHIN` (**VERIFY**) hoặc emulated | `within_geo_range` | `geo_distance` |
| `id_in` | `id = ANY(%s::uuid[])` | `HasIdCondition` | `id in […]` | `by_id().contains_any` | `ids` |

## Phụ lục B — Bẫy đã biết

1. **`unaccent()` là STABLE.** Không dùng được trong GENERATED column / index → wrapper `f_unaccent` (Part 5). Sửa luôn DDL ở EMBEDDING_AND_ENGINES §4.2.
2. **`SET LOCAL` chỉ có hiệu lực trong transaction.** asyncpg pool `RESET ALL` khi trả connection (EMBEDDING §4.6).
3. **Build HNSW song song của pgvector trong Docker cần `shm_size` lớn.** Không thì lỗi `could not resize shared memory segment`.
4. **pgvector `iterative_scan=off` + filter chọn lọc → trả ít hơn k kết quả.** Đây là hành vi post-filter (thể hiện ở `n_short`). `relaxed_order` cần sắp lại thứ tự.
5. **YAML đọc `off`/`on`/`yes` thành boolean** → luôn đặt trong nháy.
6. **Qdrant không build HNSW dưới `indexing_threshold`** (mặc định 20.000 KB); đặt `0` có thể là *tắt* index.
7. **Milvus:** phải `flush` trước khi tạo index và `load` collection trước khi search; consistency level ảnh hưởng B4.
8. **Weaviate v4:** cần cổng gRPC; lỗi batch nằm trong `failed_objects` chứ không raise.
9. **OpenSearch:**
   - `vm.max_map_count ≥ 262144`;
   - tắt security plugin cho bench;
   - `refresh_interval` quyết định B4;
   - `_forcemerge` làm search nhanh hơn — luôn ghi lại đã bật hay chưa.
10. **Windows:** multiprocessing spawn (worker tự tạo adapter); docker SDK qua npipe; `sysctl` chạy trong WSL2.
11. **Vector fp16 có norm lệch 1 một chút** → luôn tính cosine có chia norm ở GT và khi so dung sai.
12. **Công thức khoảng cách geo khác nhau giữa các engine** → vùng biên `geo_boundary_tol`.
13. **B6 không xoá page cache của host** → đo cold start của process engine, không phải cold start đĩa.
14. **Metadata tổng hợp không tương quan với vector** (`correlation=none`) → A1 ở scale là cận dưới; chạy thêm `correlation=cluster` nếu cần so sát thực tế.
15. **Dataset Cohere chưa ghi license** → chỉ dùng nội bộ, không commit vector.

## Phụ lục C — Chạy thật để chọn DB

```bash
# Máy đo: VM 8 vCPU / 32 GB / SSD → --profile full; laptop → --profile local (catalog + 100k)
vb doctor --profile full

# 1. Dữ liệu dùng chung — một lần, mọi engine dùng lại
vb dataset catalog --source jsonl --products <products.jsonl>
vb embed --scale catalog && vb queries --scale catalog && vb embed --scale catalog --target queries && vb gt --scale catalog
vb scale-data 100k && vb scale-data 1m                  # 1m chỉ ở profile full

# 2. Gold: ≥ 50 query đã gán nhãn trong gold/gold.jsonl (không có → A2 = skipped, ghi rõ trong report)
# 3. Điền manual/<engine>.yaml (license, C3, C4, C5, D3_json_logs, D4, phần E còn trống)

# 4. Chạy trọn quy trình, qua đêm
vb run-all --profile full --run <YYYYMMDD>
#   với mỗi engine: engine up → gate (catalog) → trượt gate thì dừng engine đó
#                   → load + quality ở mọi scale → perf ở 100k, 1m → engine down --volumes
#   chạy lại được: bỏ qua step đã có file kết quả status=ok (trừ khi --force)

# 5. Kết quả
vb score --run <id> && vb decide --run <id> && vb report --run <id>
```

**Ước lượng thời gian máy:** mỗi engine catalog + 100k ≈ 1–1,5 giờ; thêm 1m ≈ 2–3 giờ; cả 6 engine profile `full` ≈ 1–2 ngày máy.

**Definition of done của cả spec:**

1. Mọi unit test pass.
2. `run-all` chạy hết với ít nhất pgvector + Qdrant ở catalog + 100k.
3. `report.md` có bảng §6 đầy đủ (trừ ô nhập tay còn trống, được đánh dấu).
4. `decide` in lý do quyết định.
5. Con số search unit thật từ Part 1 đã được cập nhật vào VECTOR_DB_SELECTION.md.
