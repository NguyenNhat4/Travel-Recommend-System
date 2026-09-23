# Chọn vector database bằng số đo — landscape 2026, gate, metric, protocol benchmark

Bản 22/09/2026 · thay thế phần "lý do" ở `VECTOR_STORE_AND_ROBUSTNESS.md` §1 bằng một **quy trình chọn đo được**: liệt kê đầy đủ hệ thống hiện có → loại bằng gate pass/fail → đo ứng viên còn lại trên cùng dữ liệu, cùng phần cứng → chấm điểm có trọng số → quyết định theo quy tắc viết sẵn. Kết quả đo điền vào bảng §6 (đang để trống — đây là **khung**, không phải kết luận). Nguồn §10. Spec để sinh code benchmark chạy từng phần: `VECTOR_DB_BENCH_SPEC.md`.

Nguyên tắc: mọi metric phải có **công thức**, **cách đo**, **đơn vị**, **ngưỡng**; số của vendor chỉ dùng để chọn ứng viên, không dùng để chấm điểm.

---

## 1. Landscape — có những gì (09/2026)

Nhóm theo cách triển khai. Cột "Gate" ghi trước gate nào **có khả năng** loại (xác nhận bằng smoke test 1 giờ ở §3, không phải kết luận). License lấy từ bảng Wikipedia "Vector database" và trang dự án; phiên bản chỉ ghi khi đã xác minh trong `VECTOR_STORE_AND_ROBUSTNESS.md` §1.2.

### 1.1 Extension / tính năng trong RDBMS đang có

| Hệ thống | License | Triển khai | Điểm mạnh với V-OTA | Gate có thể loại |
|---|---|---|---|---|
| **PostgreSQL + pgvector** 0.8.6 | PostgreSQL | Cùng DB nghiệp vụ | Filter/count/facet trong một SQL; đang dùng; migrate = 0 | — (baseline) |
| pgvectorscale 0.9.1 (Timescale) | PostgreSQL | Extension thêm | StreamingDiskANN, label filter `smallint[]` (ANY-of) | — |
| VectorChord 1.1.1 | AGPL-3 / ELv2 | Extension thêm | RaBitQ, build nhanh | G2 (review license) |
| ParadeDB `pg_search` / Timescale `pg_textsearch` | AGPL-3 / PostgreSQL | Extension | BM25 thật cho kênh lexical, không phải vector | Bổ trợ, không thay thế |
| AlloyDB AI / Aurora pgvector / Neon / Supabase | Managed | Cloud | pgvector managed | G1 nếu bắt buộc self-host |
| MariaDB Vector (11.7+) | GPL-2 | Self-host | HNSW trong MariaDB | G3 (filter mảng), G5 (client) — chưa kiểm |
| MySQL HeatWave / Oracle 23ai AI Vector Search / SQL Server 2025 | Proprietary | Cloud / license | Nếu đã dùng stack đó | G1/G2 |
| SingleStore / TiDB / CockroachDB / OceanBase | Proprietary / Apache-2 / … | Distributed SQL | Vector trong SQL phân tán | Quá nặng cho 100k dòng |
| ClickHouse (vector similarity index) / DuckDB `vss` / `sqlite-vec` | Apache-2 / MIT | Analytics / embedded | DuckDB, sqlite-vec tốt cho **offline eval** | Không phải serving |

### 1.2 Vector DB chuyên dụng (open source, self-host được)

| Hệ thống | License | Triển khai | Điểm mạnh | Gate có thể loại |
|---|---|---|---|---|
| **Qdrant** 1.19 | Apache-2 | 1 container | Filterable HNSW + ACORN, sparse, multivector, facet, Query API RRF | — |
| **Milvus** 3.0.1 | Apache-2 | standalone 1–3 container (+ etcd/MinIO) hoặc Milvus Lite | `ARRAY_CONTAINS_ALL`, BM25 built-in, aggregate/facet server-side | D1 (số thành phần) |
| **Weaviate** 1.37 | BSD-3 | 1 container | Hybrid built-in, ACORN, MMR native | — |
| Chroma (1.x, lõi Rust) | Apache-2 | 1 process | Đơn giản, embedded | G3/G4 — filter/facet hạn chế, chưa kiểm |
| LanceDB | Apache-2 | Embedded / cloud | Multivector, FTS trên mảng; tốt cho eval offline | G6 (freshness), serving đa tiến trình |
| Vald / Marqo / Zvec | Apache-2 | K8s / container | Niche | D1, hệ sinh thái nhỏ |
| Redis 8 (Vector Sets + Query Engine) | AGPL-3 / RSALv2 / SSPL (chọn một) | 1 container | Rất nhanh, filter theo attribute | G2 review; RAM-bound ở 1M |

### 1.3 Search engine có vector (lexical là hạng nhất)

| Hệ thống | License | Điểm mạnh | Gate có thể loại |
|---|---|---|---|
| **Elasticsearch** 9.4 | AGPL-3 / SSPL / ELv2 | BM25 + kNN + RRF; BBQ; ACORN-1; **plugin tách từ tiếng Việt CocCoc** | G2 review; D1 (JVM, RAM) |
| **OpenSearch** 3.x | Apache-2 | Như ES, Apache; neural sparse (không có tiếng Việt) | D1 |
| Vespa | Apache-2 | ColBERT native, grouping exact, ranking expression | D1 (vận hành nặng nhất bảng) |
| Apache Solr 9 | Apache-2 | Dense vector + BM25 | Hệ sinh thái vector mỏng |
| Typesense / Meilisearch | GPL-3 / MIT | Nhanh, dễ; hybrid | G3 (ALL-of, facet exact) — chưa kiểm |
| Manticore Search | GPL-3 | **Có hỗ trợ tiếng Việt** (charset/folding) + vector | G3/G4 — chưa kiểm |

### 1.4 Managed / serverless (không self-host)

| Hệ thống | Ghi chú | Gate |
|---|---|---|
| Pinecone | Serverless, metadata filter | G1 nếu bắt buộc self-host; đo RTT SG |
| Turbopuffer | BM25 + vector trên object storage; không `ContainsAll`; `limit.total` ≤ 10k | G1 |
| Amazon S3 Vectors (GA 02/12/2025) | 2 tỷ vector/index, 50 metadata key, "~100 ms hoặc thấp hơn" khi query thường xuyên, dưới 1 s khi hiếm; ghi 1.000 vector/s | G1; latency không đạt B1 cho search online |
| Zilliz Cloud / Qdrant Cloud / Weaviate Cloud / Elastic Cloud | Managed của 1.2–1.3 | G1; đo RTT |
| MongoDB Atlas Vector Search / Azure AI Search / Vertex AI Vector Search / Databricks / Cloudflare Vectorize / Upstash / DataStax Astra / Couchbase | Gắn với cloud riêng | G1 |

### 1.5 Thư viện (không phải DB — chỉ cho eval và ground truth)

FAISS, hnswlib, usearch, Voyager (Spotify), ScaNN, DiskANN, Annoy. Dùng **FAISS `IndexFlatIP`** hoặc numpy làm **ground truth** cho mọi phép đo recall ở §4.

---

## 2. Yêu cầu của V-OTA — dịch thành số

| Yêu cầu | Số cụ thể | Nguồn |
|---|---|---|
| Quy mô hiện tại / chuẩn bị / sau | 10.000 sản phẩm (22/09) → **~5.000 vector**: chỉ embed search unit (property, route, attraction, combo, golf); phòng và chuyến bay dùng vector cha; `profiles`/`events` không embed. ~5.000 là ước theo tỷ lệ 51% của bản crawl 16/09 (1.125/2.216) — số thật: `SELECT count(*) FROM catalog.product_meta WHERE is_search_unit` / 100k / 1M vector, 1024-d halfvec | PRODUCT_SCHEMA §4, §8; EMBEDDING_AND_ENGINES §0 #1; RECSYS_METHODS §2; số 10.000: team 22/09 |
| Filter điển hình | destination × taxonomy × `available` × amenities ALL-of × giá × sao; selectivity thường **< 1%**, đôi khi 10–30% (chỉ destination) | SCHEMA.md; VECTOR_STORE §1.3 |
| Latency ngân sách `/search` | **P99** ≤ 300 ms end-to-end *(đề xuất 22/09: ưu tiên P99 thay p95 — ARCHITECTURE đang ghi p95 < 300 ms, cần team xác nhận)*; phần DB P99 ≤ 50 ms (≤ 100k vector) / ≤ 100 ms (1M) ở tải 100 QPS; embed query tính riêng (cache hit ~0, miss 15–60 ms int8) | EMBEDDING_AND_ENGINES §3.3; §9 bên dưới |
| QPS | Demo: 10 QPS; thiết kế: 100 QPS; sau: 500 QPS | *(đề xuất — chưa có số traffic thật)* |
| `total`/`facets` | Chính xác khi tập lọc nhỏ (≤ ngưỡng exact, đếm luôn trong cùng câu query); tập lọc lớn → ước lượng + `totalExact=false` *(đề xuất 22/09 vì ưu tiên P99 — §9)* | EMBEDDING_AND_ENGINES §4.5 |
| Freshness | Giá/availability đổi hằng ngày (crawl daily) → visible ≤ 60 s; booking event → user vector đổi ngay (application) | Memory 21/09; EMBEDDING §6.6 |
| Hạ tầng | Docker Compose trên máy/VPS; Python 3.11 + FastAPI + asyncpg | ARCHITECTURE; MOCK_DATA_SPEC §1 |
| Team | 3 nhóm, không có SRE riêng → **ít thành phần** là yêu cầu, không phải sở thích | Memory dự án |

---

## 3. Gate — pass/fail, kiểm bằng smoke test 1 giờ / engine

Engine trượt bất kỳ gate nào thì **không đo tiếp**; ghi gate trượt vào §6 làm bằng chứng loại.

| # | Gate | Cách kiểm | Pass khi |
|---|---|---|---|
| G1 | Triển khai được trong `docker-compose` của dự án, hoặc managed có region SG/HCM | Chạy `docker compose up`; với managed: `ping`/HTTP RTT từ VPS 100 lần | Self-host: lên trong ≤ 15 phút, ≤ 3 container. Managed: RTT p95 ≤ 40 ms |
| G2 | License cho phép dùng thương mại self-host không phí, không lây nhiễm mã V-OTA | Đọc LICENSE; AGPL/SSPL/BSL/ELv2 → ghi "cần pháp chế" | Apache/MIT/BSD/PostgreSQL: pass. Nhóm còn lại: pass **có điều kiện**, V-OTA quyết |
| G3 | Filter đủ ngữ nghĩa: AND/OR/NOT, mảng **ALL-of** và ANY-of, range số/ngày, geo radius, kết hợp với vector | 200 query filter sinh từ catalog thật (50 ALL-of 2–3 amenity, 50 NOT, 50 range giá/sao, 50 geo); so kết quả với brute-force numpy | Precision ràng buộc = **100%** (không có kết quả vi phạm filter) |
| G4 | `count` và facet **chính xác** trên tập filter, hoặc trả cờ exact/approx | 50 filter, so `count` với SQL/numpy | Sai số = 0, hoặc có cờ để contract báo `totalExact=false` |
| G5 | Client Python async chính thức; dim ≥ 1024; lưu fp16/int8 | Chạy upsert + search toàn bộ search unit (~5.000 vector) bằng client | Pass/fail |
| G6 | Read-after-write: cập nhật `available=false` cho 1 sản phẩm → search có filter không trả sản phẩm đó | Đo thời gian tới khi biến mất, 20 lần | p95 ≤ 5 s (batch daily) — ngưỡng *(đề xuất)* |
| G7 | Backup/restore có tài liệu và chạy được | Backup → xoá → restore toàn bộ vector (~5.000) | Restore đúng 100%, ≤ 10 phút |

Dự kiến qua gate để vào vòng đo *(giả thiết, phải xác nhận bằng smoke test)*: **pgvector (baseline), pgvectorscale, Qdrant, Milvus standalone, Weaviate, OpenSearch hoặc Elasticsearch (+ plugin CocCoc)**. Giữ tối đa 6 ứng viên để vòng đo xong trong 3–4 ngày công.

---

## 4. Metric định lượng — công thức, cách đo, ngưỡng, trọng số

Ký hiệu: GT = ground truth brute-force cosine (numpy/FAISS Flat) trên **đúng tập đã filter**; k = 10 cho recall, 20 cho latency; S = selectivity = |tập thoả filter| / N.

### 4.1 Nhóm A — Đúng và đủ (trọng số 35)

| # | Metric | Công thức | Cách đo | Ngưỡng | w |
|---|---|---|---|---|---|
| A1 | **Filtered Recall@10** | `|top10_engine ∩ top10_GT| / 10`, trung bình trên 1.000 query; báo **theo bucket S ∈ {100%, 10%, 1%, 0.1%}** và theo loại filter (ALL-of / range / geo); ở mỗi quy mô N ∈ {hiện tại ~5k, 100k, 1M} | Query = 300 gold + 700 sinh; filter gán theo phân bố amenities thật (Zipf); engine chạy với cấu hình "khuyến nghị cho recall ≥ 0.95" của chính nó (ví dụ `ef_search`, `iterative_scan`); điểm = **min** trên các bucket | ≥ 0,95 mọi bucket; < 0,90 ở bucket nào → A1 = 0 | 15 |
| A2 | **Hybrid nDCG@10 trên bộ gold** | nDCG@10 chuẩn với nhãn 0/1/2 | Chạy 3 cấu hình: dense-only, lexical-only (kênh lexical **của engine**: tsvector/BM25/…), fused (RRF k=60 ở application nếu engine không có). Điểm lấy fused | ≥ nDCG của pgvector − 0,01; thắng ≥ +0,02 mới tính là hơn (paired bootstrap p < 0,05) | 10 |
| A3 | **Precision ràng buộc** | tỷ lệ kết quả thoả toàn bộ filter cứng | Cùng 1.000 query của A1 | = 1,0 (đã là G3; giữ để phát hiện lỗi khi scale) | 3 |
| A4 | **Sai số count/facet** | `|count_engine − count_GT| / count_GT`, trung bình trên 200 filter; facet: L1 giữa hai phân bố | Cùng bộ filter | = 0 → 10 điểm; xấp xỉ có cờ → 5; không có → 0 | 4 |
| A5 | **Ổn định thứ hạng** | Jaccard top-10 giữa 3 lần chạy cùng query (sau upsert lại toàn bộ) | 200 query × 3 lần build | ≥ 0,9 | 3 |

### 4.2 Nhóm B — Hiệu năng (trọng số 25)

| # | Metric | Công thức / đơn vị | Cách đo | Ngưỡng | w |
|---|---|---|---|---|---|
| B1 | **P99 latency search có filter** | ms, **không** tính embed query | Tải **open-loop** 100 QPS × 120 s (≥ 12.000 request), latency tính từ thời điểm lẽ ra gửi, timeout tính vào phân vị; đo ở 100k và 1M; báo P50/P95/P99/P99.9 + CI của P99 | 100k: ≤ 50 ms; 1M: ≤ 100 ms *(đề xuất)* | 8 |
| B2 | **Tải tối đa giữ P99** | QPS lớn nhất (thang 25 → 400, open-loop) mà P99 ≤ ngưỡng B1, với cấu hình đạt A1 ≥ 0,95 | Cùng bộ query; ghi cấu hình index dùng | ≥ 100 QPS ở 100k; ≥ 100 ở 1M | 7 |
| B3 | **Thời gian build index** | phút để nạp + index N vector; và vector/s khi upsert batch 1.000 | 100k và 1M, 8 vCPU | 1M ≤ 30 phút | 3 |
| B4 | **Time-to-visible (freshness)** | giây từ upsert tới khi search thấy | 100 upsert đơn lẻ + 10 batch 1.000 | p95 ≤ 1 s đơn lẻ; ≤ 60 s batch | 3 |
| B5 | **Tăng P99 khi ghi đồng thời** | `P99_khi_ghi / P99_tĩnh − 1` ở 100 QPS, ghi nền 100 vector/s (VectorDBBench "insertion-under-load") | 5 phút | ≤ 30% | 2 |
| B6 | **Cold start** | P99 trong 60 s đầu sau restart container (50 QPS) / P99 ấm | 3 lần restart | ≤ 3× | 2 |

### 4.3 Nhóm C — Tài nguyên & chi phí (trọng số 20)

| # | Metric | Đơn vị | Cách đo | Ngưỡng | w |
|---|---|---|---|---|---|
| C1 | RAM đỉnh khi phục vụ B2 | GB ở 100k / 1M | `docker stats` trong lúc chạy B2 | 1M: ≤ 8 GB *(đề xuất)* | 5 |
| C2 | Disk | GB ở 1M (index + data) | `du` volume | ≤ 3× kích thước vector thô | 2 |
| C3 | Chi phí hạ tầng/tháng | VND, VM nhỏ nhất đạt B1+B2 ở 1M | Bảng giá VPS đang dùng | Thấp hơn = tốt | 5 |
| C4 | **Chi phí migrate** | người-ngày: adapter `SearchClient` + job sync `product_vectors` + backup/monitoring + viết lại test; pgvector = 0 | Ước lượng theo LOC adapter đã viết trong benchmark (thực đo) | ≤ 10 người-ngày | 5 |
| C5 | Chi phí vận hành thường xuyên | giờ/tháng: upgrade, backup, alert | Ước lượng từ D1–D4 | — | 3 |

### 4.4 Nhóm D — Vận hành (trọng số 12)

| # | Metric | Cách đo | Điểm |
|---|---|---|---|
| D1 | Số container/process phải chạy | Đếm trong compose | 1 → 10; 2–3 → 6; > 3 → 2 |
| D2 | Thời gian restore backup 1M | Đo | ≤ 10 phút → 10; ≤ 30 → 6; hơn → 2 |
| D3 | Observability | Có endpoint Prometheus + log JSON | Có cả hai → 10; một → 5; không → 0 |
| D4 | Upgrade & bảo trì | Số release trong 12 tháng (GitHub); có rolling/in-place upgrade không phải rebuild index | ≥ 6 release và in-place → 10 |
| D5 | Nhất quán với dữ liệu nghiệp vụ | Cùng DB (join trong một transaction) → 10; cần sync với lag đo ở B4 → 5; sync tay → 0 | — |

### 4.5 Nhóm E — Tính năng (trọng số 8)

Checklist 10 mục, điểm = số mục có × 1: sparse vector · multivector/MaxSim · BM25 native · tokenizer tiếng Việt (tách từ, không chỉ folding) · geo filter · facet server-side · quantization int8/binary · hybrid fusion server-side · MMR/diversity server-side · multi-tenancy/namespace. Mục nào **đã có kế hoạch dùng** (sparse bge-m3, facet) nhân đôi.

### 4.6 Chuẩn hoá và tổng điểm

- Metric có ngưỡng: đạt ngưỡng và tốt nhất trong nhóm → 10; đạt ngưỡng → nội suy tuyến tính 6–10 giữa "vừa đạt" và "tốt nhất"; không đạt → 0–5 tuyến tính giữa "tệ nhất chấp nhận" và "vừa đạt"; dưới mức A1 < 0,90 hoặc trượt gate → 0.
- `Tổng = Σ_nhóm (w_nhóm × Σ_metric w_metric × điểm_metric / Σ w_metric) / 100`, thang 0–10.
- **Phân tích độ nhạy:** chạy lại tổng với trọng số nhóm ±10 điểm (ví dụ A 45 / B 15). Nếu thứ hạng #1 đổi → ghi rõ trong quyết định, không kết luận "thắng".

---

## 5. Protocol benchmark — để số so được với nhau

| Hạng mục | Quy định |
|---|---|
| Phần cứng | Một VM cố định 8 vCPU / 32 GB / SSD (cùng cấu hình Qdrant dùng cho benchmark công khai); engine chạy Docker, giới hạn 16 GB RAM; client cùng máy (ghi rõ) |
| Dữ liệu quality | Catalog thật: toàn bộ search unit của 10.000 sản phẩm (~5.000 vector) 1024-d (model thắng ở tuần 2) + `amenity_ids`, `destination`, `taxonomy`, `unit_price`, `star_rating`, toạ độ |
| Dữ liệu scale | 100k và 1M: vector passage Wikipedia tiếng Việt công khai (`CohereLabs/wikipedia-2023-11-embed-multilingual-v3`, subset `vi` ~2,84 triệu passage, 1024-d); query = 1.000 vector giữ lại từ cùng dataset; metadata sinh theo phân bố catalog. Không dùng text template embed bằng model của mình vì template sinh vector gần trùng hàng loạt → ANN không thực tế. A2 (gold) chỉ đo ở catalog. Chi tiết: `VECTOR_DB_BENCH_SPEC.md` Part 10 |
| Query | 300 gold (có slice amenity/không dấu/…) + 700 sinh; mỗi query kèm filter; 4 bucket selectivity; cùng bộ cho mọi engine; lưu `bench_out/data/<scale>/queries.jsonl` |
| Ground truth | numpy cosine trên tập đã filter; lưu `bench_out/data/<scale>/gt.npz`; tính một lần |
| Cấu hình engine | Mỗi engine 2 cấu hình: (a) mặc định, (b) tune tới A1 ≥ 0,95 (ghi rõ `ef_search`/`m`/`nprobe`/quantization); chấm điểm ở (b) |
| Lặp | Warm-up 200 query; 3 lần chạy; báo **median**; ghi phiên bản engine, client, ngày |
| Công cụ | **Harness riêng** `bench/` cho nhóm A và G3/G4 (VectorDBBench label-filter chỉ là `color == 'red'`, không phải ALL-of mảng); **VectorDBBench** (hỗ trợ pgvector, pgvectorscale, VectorChord, Qdrant, Milvus, Weaviate, ES, OpenSearch, Redis, Vespa…; filter rate 50–99,9%; streaming; full-text từ 2026) cho B3/B5 ở 1M để so chéo |
| Bias | Không dùng số vendor để chấm; nếu dùng để tham khảo, ghi "[vendor]" |
| Đầu ra | `bench_out/runs/<run_id>/<engine>/<scale>/*.json` + `report.md` có bảng §6 điền tự động (`VECTOR_DB_BENCH_SPEC.md` Part 12) |

---

## 6. Bảng điểm — khung để điền sau khi đo

| Metric (w) | pgvector 0.8.6 | pgvectorscale | Qdrant | Milvus | Weaviate | OpenSearch/ES |
|---|---|---|---|---|---|---|
| Gate G1–G7 | pass (baseline) | | | | | |
| A1 Filtered Recall@10 — min bucket (15) | | | | | | |
| A2 Hybrid nDCG@10 gold (10) | | | | | | |
| A3 Precision ràng buộc (3) | | | | | | |
| A4 Sai số count/facet (4) | | | | | | |
| A5 Ổn định thứ hạng (3) | | | | | | |
| B1 P99 ms @100k / @1M (8) | | | | | | |
| B2 QPS tối đa giữ P99 (7) | | | | | | |
| B3 Build 1M phút (3) | | | | | | |
| B4 Time-to-visible (3) | | | | | | |
| B5 Tăng P99 khi ghi (2) | | | | | | |
| B6 Cold start (2) | | | | | | |
| C1 RAM GB @1M (5) | | | | | | |
| C2 Disk GB @1M (2) | | | | | | |
| C3 VND/tháng (5) | | | | | | |
| C4 Migrate người-ngày (5) | 0 | | | | | |
| C5 Vận hành giờ/tháng (3) | | | | | | |
| D1–D5 (12) | | | | | | |
| E checklist (8) | | | | | | |
| **Tổng (0–10)** | | | | | | |
| Tổng khi A=45/B=15 | | | | | | |
| Tổng khi C=30/A=25 | | | | | | |

---

## 7. Quy tắc quyết định — viết trước khi có số

1. Engine trượt gate → loại, không bàn thêm.
2. Ở quy mô **hiện tại (~5k vector) và 100k**: ở lại pgvector trừ khi ứng viên khác **thắng ≥ 1,5 điểm tổng** *(ngưỡng đề xuất — chốt với team trước khi đo)* *và* thắng ở nhóm A *và* thứ hạng không đổi khi phân tích độ nhạy. Lý do đưa vào quy tắc thay vì tranh luận: C4 = 0 và D5 = 10 của pgvector là số đo, không phải sở thích.
3. Ở quy mô **1M** (chạy lại benchmark khi catalog thật > 200k): nếu pgvector (kể cả pgvectorscale) không đạt B1/B2 ở cấu hình (b) → chọn ứng viên có tổng cao nhất trong số đạt A1 ≥ 0,95; ưu tiên ứng viên có D1 = 1 container.
4. Kênh lexical: nếu A2 của Elasticsearch + CocCoc thắng pgvector ≥ 0,03 nDCG trên slice "tên riêng / amenity term" → cân nhắc **chỉ** kênh lexical sang ES (sidecar), vector vẫn ở Postgres — quyết định riêng, không kéo theo vector.
5. Mọi quyết định ghi kèm: ngày, phiên bản engine, commit harness, file kết quả; benchmark lại khi đổi model embedding (đổi D hoặc phân bố vector) hoặc khi N tăng 10×.

---

## 8. Shortlist và fast-track (22/09/2026)

Top 5 theo gate trên giấy + bằng chứng (chi tiết và nguồn: `VECTOR_DB_FASTTRACK_SPEC.md` §1):

1. pgvector 0.8.x
2. Qdrant 1.19
3. pgvectorscale 0.9.x
4. Milvus 3.0.1
5. Weaviate 1.37

Elasticsearch/OpenSearch giữ làm phương án sidecar lexical, không nằm trong top 5 vector DB.

**Fast-track (chạy thật #1–#3):**

- Đo G3 và A1/A3 ở catalog thật; A1, A3, B1 (P99 ở 100 QPS), B2, B3, C1 ở 1M vector khuếch đại từ catalog (có kiểm LID).
- Quy tắc chốt viết trước:
  1. pgvector đạt A1 ≥ 0,95 và P99 ≤ 100 ms ở tải 100 QPS (1M) → chốt pgvector.
  2. Không thì pgvectorscale đạt → chốt pgvectorscale.
  3. Không thì Qdrant đạt → chốt Qdrant.
  4. Không engine nào đạt → pgvector cho quy mô hiện tại; chạy bộ đầy đủ (thêm Milvus, Weaviate) trước khi vượt ~200k vector.
- Kết quả: `bench_out/runs/<run>/fast_report.md` — ghi số vào đây khi có.

## 9. Lựa chọn DB ảnh hưởng phương pháp search thế nào — khi ưu tiên P99

**Có.** DB quyết định năm phần của phương pháp search, và mỗi phần là một nguồn đuôi latency:

| Phần của phương pháp | pgvector / pgvectorscale | Qdrant (và engine riêng khác) | Ảnh hưởng tới P99 |
|---|---|---|---|
| **Kết hợp filter với vector** | HNSW không biết filter: post-filter + iterative scan. Ứng dụng phải tự định tuyến: exact trên tập lọc nhỏ, ANN có trần `max_scan_tuples` cho tập lớn. pgvectorscale: label filter ANY-of trong DiskANN | Engine tự định tuyến: payload index, filterable HNSW, ACORN, planner chuyển exact khi tập lọc rất nhỏ (Qdrant 1M: selectivity 0,012% → exact 1,3 ms) | Công việc mỗi query biến thiên theo selectivity → **nguồn P99 lớn nhất**. dbi-services: iterative scan ở selectivity 0,5% mất 4,2 s nếu không định tuyến |
| **Số round trip** (hybrid + dữ liệu hiển thị) | Một câu SQL (CTE) gồm dense + tsvector + filter, trả luôn giá / availability bằng JOIN → **1 round trip** | Query API prefetch + fusion phía server → 1 round trip tới Qdrant. Nhưng thêm 1 round trip **nối tiếp** về Postgres để lấy giá / availability, hoặc phải denormalize payload và đồng bộ hằng ngày | Mỗi round trip nối tiếp cộng thêm đuôi của nó. Gọi song song hai hệ (Postgres + sidecar ES) thì P99 ≈ P99,5 của hệ chậm hơn. Tail at Scale: 1/100 request chậm, fan-out 100 → 63% request chậm |
| **`total` và facet** | COUNT / GROUP BY exact, chi phí tỷ lệ với tập lọc: rẻ khi tập nhỏ (đếm luôn trong CTE), đắt với filter rộng ở 1M | `count(exact)` hoặc xấp xỉ; facet API. ES đếm có trần `track_total_hits` (10.000) | Đếm exact trên filter rộng là một query nặng mỗi request → trả `totalExact=false` (ước lượng) khi tập lọc lớn |
| **Index và bộ nhớ** | HNSW trong RAM; index vượt `shared_buffers` → QPS 2.110 → 102 (issue #700). DiskANN (pgvectorscale) đọc SSD | HNSW trong RAM (fp16); đưa vector xuống disk là tuỳ chọn | Đuôi tăng vọt khi phải đọc disk → định cỡ RAM để index nằm trọn; prewarm sau restart |
| **Cập nhật hằng ngày** | UPDATE sinh dead tuple, kéo theo autovacuum và WAL; HNSW cập nhật từng dòng | Optimizer gộp segment chạy nền; có alias để đổi collection | Đuôi tăng trong lúc ghi → đo P99 khi có ghi nền (B5); cập nhật theo lô ngoài giờ cao điểm; build lại toàn bộ theo kiểu blue/green (bảng mới + rename / alias) |

Hai engine còn lại cũng có nguồn đuôi riêng:

- **Milvus:** mức `Strong` bắt query node đợi dữ liệu mới nhất nên latency tăng; mặc định là `Bounded`.
- **Elasticsearch / OpenSearch:** GC của JVM và merge segment.

**Quy tắc thiết kế khi ưu tiên P99 — áp dụng dù chọn DB nào:**

1. **Thành phần nào chậm với hơn 1% request thì quyết định P99.** Ví dụ: LLM query understanding cho ~2% query khó (mẫu Instacart ở EMBEDDING §4.1, ~300 ms) mà chạy đồng bộ thì P99 ≥ 300 ms. Cách tránh: trả kết quả rule-based ngay và gọi LLM bất đồng bộ để cache cho lần sau, hoặc đặt timeout cứng.
2. **Một round trip** cho dense + lexical + filter + dữ liệu hiển thị. Không dùng sidecar trừ khi A2 chứng minh lợi ích lớn hơn chi phí đuôi.
3. **Chặn trần công việc mỗi query:**
   - định tuyến exact / ANN bằng ước lượng selectivity từ thống kê cache, không chạy `COUNT` trước;
   - cố định `ef_search` / `max_scan_tuples` / `hnsw_ef`;
   - đặt `statement_timeout` / timeout. Hết giờ thì trả kết quả "đủ tốt" (lexical, hoặc ANN chưa đủ k) và gắn cờ — kỹ thuật degraded responses trong Tail at Scale.
4. **`total` / facet exact chỉ khi tập lọc nhỏ.** Tập lớn thì ước lượng và trả `totalExact=false` — contract đã có trường này.
5. **Index và vector nằm trọn trong RAM.** Cache embedding query theo query đã chuẩn hoá; embed chạy trong pool thread riêng có hàng đợi giới hạn.
6. **Exact có công việc cố định nên P99 ≈ P50.** Ở ~5.000 vector hiện tại, exact nằm trong ngân sách (Neon 2023: 10k × 960-d ≈ 36 ms) và recall = 1. ANN nhanh hơn ở trung vị nhưng đuôi phụ thuộc filter — chỉ cần khi tập lọc vượt ngưỡng exact.

**Đo P99 cho đúng** (đã áp vào B1, B2, B5, B6 ở §4 và vào hai spec):

- Tải open-loop tốc độ cố định; latency tính từ thời điểm lẽ ra gửi. Closed-loop bỏ sót đuôi: ví dụ trong README của wrk2, P99 đo sai 6,04 ms, đo đúng 1,27 s.
- ≥ 10.000 request mỗi mức tải: 1.000 request chỉ có 10 mẫu nằm trên P99.
- Báo khoảng tin cậy của P99; timeout tính vào phân vị.

**Hệ quả cho lựa chọn:** ưu tiên P99 nghiêng về giữ vector chung DB với dữ liệu nghiệp vụ (ít round trip, không phải lấy dữ liệu hiển thị ở hệ khác), trừ khi thử ở 1M cho thấy đuôi của pgvector vượt ngưỡng. Qdrant mạnh hơn ở khâu tự định tuyến filter, nhưng phải trả thêm một round trip hoặc chi phí đồng bộ payload.

## 10. Nguồn

- Landscape & license: Wikipedia "Vector database" (bảng implementations) https://en.wikipedia.org/wiki/Vector_database · danh sách engine VectorDBBench hỗ trợ (40+) https://github.com/zilliztech/VectorDBBench
- Phiên bản/tính năng đã xác minh (pgvector 0.8.6, pgvectorscale 0.9.1, VectorChord 1.1.1, Qdrant 1.19, Milvus 3.0.1, Weaviate 1.37, Elasticsearch 9.4, Vespa, Turbopuffer, LanceDB, plugin CocCoc): xem `VECTOR_STORE_AND_ROBUSTNESS.md` §6
- Amazon S3 Vectors GA 02/12/2025 — 2 tỷ vector/index, 50 metadata key, ~100 ms/≤ 1 s, 1.000 vector/s [docs] https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-s3-vectors-generally-available/
- Redis 8 Vector Sets (mã nguồn `modules/vector-sets/hnsw.c` tại tag 8.2.3) [repo] https://github.com/redis/redis/blob/8.2.3/modules/vector-sets/hnsw.c · Redis vector indexes/hybrid [vendor] https://redis.io/blog/vector-indexes-in-redis/
- Dean & Barroso — The Tail at Scale, CACM 2013 (fan-out khuếch đại đuôi; hedged requests; degraded responses) [paper] https://cacm.acm.org/research/the-tail-at-scale/
- wrk2 — coordinated omission, đo latency từ thời điểm lẽ ra gửi [docs] https://github.com/giltene/wrk2
- Milvus consistency levels (Strong tăng latency, mặc định Bounded) [docs] https://milvus.io/docs/consistency.md
- VectorDBBench — metric (QPS, QP$, p50/p95/p99, load duration, recall, build time), label-filter 50–99,9%, streaming, full-text 2026, quantization int8/fp16/binary [docs] https://github.com/zilliztech/VectorDBBench
- Qdrant benchmarks — phương pháp (8 vCPU/32 GB server, 25 GB RAM cho engine, "so sánh chỉ khi cùng precision"), filtered benchmark 02/2023 [vendor] https://qdrant.tech/benchmarks/
- Qdrant filtered search ACORN — số recall theo selectivity [vendor blog] https://qdrant.tech/articles/filtered-vector-search-acorn/ · Big-ANN NeurIPS'23 filter track (ALL-of tag) [paper] https://arxiv.org/html/2409.17424v1 · ACORN SIGMOD 2024 [paper] https://arxiv.org/abs/2403.04871
- Các bài "best vector databases 2026" (firecrawl, encore, datacamp, effoma, salttechno…) chỉ dùng để **liệt kê tên**, không lấy số — chưa kiểm chứng phương pháp đo.

**Chưa xác minh:** license/tính năng hiện tại của MariaDB Vector, Chroma 1.x, Typesense, Meilisearch, Manticore (tiếng Việt), Solr, Marqo, Vald, Zvec, Redis 8 (điều khoản AGPL/RSAL); phiên bản OpenSearch 3.x; ngưỡng QPS/latency/RAM ở §2 và §4 là đề xuất cho tới khi có số traffic thật.
