# spec-fasttrack.md — chốt vector database trong 2 giờ chạy máy

Bản 22/09/2026 · rút gọn từ `spec.md` (`VECTOR_DB_BENCH_SPEC.md`) để **chốt trong chiều nay** · Claude Code chỉ cài những Part và tuỳ chọn liệt kê ở §4; mọi chi tiết không nhắc lại ở đây thì theo `spec.md`.

**Phạm vi:**

- Chạy thật **3 engine**: pgvector, Qdrant, pgvectorscale.
- Hai engine còn lại trong top 5 (Milvus, Weaviate) đánh giá trên giấy (§1).
- Đo ở hai quy mô: catalog thật (10.000 sản phẩm → ~5.000 search unit) và **1M vector khuếch đại từ chính catalog** (§3).
- Chỉ đo các metric có thể lật quyết định. **P99 là chỉ số latency chính**, đo bằng tải open-loop (§6).
- Quy tắc chốt viết sẵn ở §6 **trước khi** chạy.

---

## 1. Top 5 — bằng chứng

Loại trừ từ landscape ~40 hệ thống (`VECTOR_DB_SELECTION.md` §1) theo gate trên giấy (G1 ≤ 3 container, G2 license, G3 ngữ nghĩa filter), rồi xếp theo mức phù hợp với V-OTA. Ký hiệu nguồn: **[paper]**, **[docs]**, **[vendor]** = số do chính hãng / đối thủ công bố, không dùng để chấm.

| # | Engine | Bằng chứng ủng hộ | Rủi ro có bằng chứng | Hôm nay |
|---|---|---|---|---|
| 1 | **pgvector 0.8.x** (PostgreSQL License) | AWS, 10M sản phẩm, 384-d, db.r8g.4xlarge: iterative scan của 0.8.0 đưa recall truy vấn lọc theo category từ 10% → 100%, filter phức tạp 1% → 100%, query top-10 nhanh 9,4× **[vendor-host]** · Build song song (0.6.0): 1M × 1536-d, m=16, ef_construction=200, 16 core → ~9,5 phút (trước đó ~1 giờ 27 phút) **[vendor-host]** · Quét exact 10k × 960-d ~36 ms **[vendor-host]** · Cùng DB nghiệp vụ: count/facet/join chính xác, chi phí migrate = 0 | Iterative scan ở selectivity 0,5% mất 4,2 s (dbi-services 03/2026) → phải lọc trước rồi quét exact khi tập nhỏ · Issue #700: QPS 2.110 → 102 khi index HNSW vượt `shared_buffers` → phải đủ RAM · Không có đồ thị nhận biết filter (ACORN) | **Chạy** |
| 2 | **Qdrant 1.19** (Apache-2) | Paper ACORN (SIGMOD 2024): throughput 2–1.000× ở cùng recall so với pre/post-filter **[paper]** · Qdrant, 1M vector: selectivity 1% HNSW thường recall 0,1% → ACORN 67,7% (4,7 ms); hai filter 4%: ACORN 95,2% vs filterable HNSW 63,7%; 0,012% planner chuyển exact 100% / 1,3 ms **[vendor]** · Đối thủ Tiger Data đo Qdrant p95 37 ms ở 50M **[vendor]** · Count exact, facet API, lưu fp16, 1 container | Hệ thống thứ hai → cần job đồng bộ + độ trễ, chi phí migrate > 0 · Ngay số của chính Qdrant cho thấy filter chọn lọc vẫn phải tune | **Chạy** |
| 3 | **pgvectorscale 0.9.x** (PostgreSQL License) | Tiger Data, 50M × 768-d: 471 QPS ở recall 99% (Qdrant 41 QPS cùng bài) **[vendor]** · README: p95 thấp hơn 28×, QPS cao hơn 16× so với Pinecone s1 **[vendor]** · Label filter (StreamingDiskANN) · Vẫn trong Postgres | Bằng chứng gần như chỉ từ vendor · Label filter là ANY-of, ALL-of phải lọc lại · Không có trên một số Postgres managed | **Chạy** |
| 4 | **Milvus 3.0.1** (Apache-2) | `ARRAY_CONTAINS_ALL/ANY`, BM25 tích hợp (Block-Max WAND ở 3.0), aggregate + facet phía server **[docs]** · 2.6: JSON path index 140 ms → 1,5 ms; RaBitQ 1-bit giảm 72% bộ nhớ **[vendor]** | Standalone cần 3 container (etcd, MinIO, Milvus) · Lợi thế chủ yếu ở quy mô > 10M | Giấy |
| 5 | **Weaviate 1.37** (BSD-3) | ACORN (1.27): throughput ~2× so với sweeping ở selectivity 20% tương quan thấp, ~10× khi tương quan rất thấp **[vendor]** · 1.33 thêm `ContainsNone` và `Not` → đủ ngữ nghĩa filter **[docs]** · Hybrid BM25 tích hợp, 1 container | Vector lưu float32 (nén bằng SQ/BQ/PQ) → RAM ở 1M cao hơn · BM25 không tách từ tiếng Việt | Giấy |

**Ngoài top 5:**

- **Elasticsearch / OpenSearch:** JVM nặng; ES là AGPL/SSPL/ELv2 → G2 có điều kiện. Giữ làm phương án **sidecar lexical** (plugin tách từ tiếng Việt CocCoc bản 9.3.0, 03/2026), theo quy tắc 4 của VECTOR_DB_SELECTION §7.
- **VectorChord:** AGPL/ELv2.
- **Chroma, LanceDB:** hạn chế filter/facet hoặc serving.
- **Redis 8:** giới hạn bởi RAM, license.
- **Vespa:** vận hành nặng nhất.
- **Managed:** yêu cầu self-host; S3 Vectors ~100 ms–1 s.

**Vì sao chỉ chạy 3:**

- **Thời gian.** Mỗi engine ở 1M tốn ~20–30 phút (build index chiếm phần lớn), 5 engine thì hết 2 giờ, không còn dư.
- **Logic quyết định** (VECTOR_DB_SELECTION §7 quy tắc 3): chỉ khi **cả** pgvector lẫn pgvectorscale trượt ở 1M mới chọn engine ngoài Postgres. Qdrant là engine ngoài có bằng chứng filtered search sâu nhất nên đại diện nhóm này. Milvus/Weaviate chỉ làm thay đổi quyết định nếu Qdrant cũng trượt — khi đó chạy tiếp (§7).

---

## 2. Có làm loạn project không — không, nếu giữ 7 điều sau

| # | Rủi ro | Cách cô lập |
|---|---|---|
| 1 | Code lẫn vào app | Branch riêng `bench/vector-db`. Code chỉ nằm dưới `src/evaluation/vector_bench/`. Ngoài thư mục này chỉ sửa **một dòng** `.gitignore` (`bench_out/`) |
| 2 | Thư viện xung đột với backend | venv riêng `.venv-vbench` + `requirements.txt` riêng. **Không** thêm gì vào requirements hay lockfile của backend. torch, pymilvus… chỉ nằm trong venv này |
| 3 | Đụng container / DB của app | Compose project riêng `vbench`: network và volume riêng, port 55432 / 55433 / 56333. DB `vota` không bị ghi. Hôm nay dùng `--source jsonl`, không đọc DB luôn |
| 4 | Xoá nhầm volume của app | **Không** chạy `docker system prune` hay `docker volume prune`. Chỉ dọn bằng `vb engine down <engine> --volumes` (chỉ tác động project `vbench`) |
| 5 | Hết disk | Đỉnh ~15–20 GB *(ước)*: image ~3 GB, 1M fp16 2 GB + GT, volume mỗi engine ở 1M vài GB (xoá ngay sau engine đó), cache model bge-m3 ~2,3 GB |
| 6 | Tranh RAM/CPU, số đo nhiễu | Tắt stack app khi đo. Giới hạn engine `cpus: 6, mem: 12g` (máy 8 vCPU / 32 GB) hoặc `4 / 8g` (laptop 16 GB). Windows + Docker Desktop (WSL2): RAM cho Docker đặt trong `%UserProfile%\.wslconfig` (`[wsl2]` → `memory=16GB`), rồi chạy `wsl --shutdown` để áp dụng |
| 7 | Kết quả lẫn vào git | `bench_out/` bị gitignore. Chỉ commit code, `config/` và `fast_report.md` nếu muốn lưu |

Chạy **toàn bộ** `spec.md` (6 engine × 3 quy mô × mọi metric) mất 1–2 ngày máy, lại cần bộ gold và số nhập tay. Vì vậy hôm nay chạy fast-track này.

---

## 3. Có 1M vector từ catalog 10.000 sản phẩm — khuếch đại có kiểm tra

**Chọn cách:**

| Cách | Ưu | Nhược | Hôm nay |
|---|---|---|---|
| **A. Khuếch đại từ vector thật** (nội suy giữa item với láng giềng + nhiễu nhỏ, metadata kế thừa) | 1–2 phút, không tải gì; **cùng không gian bge-m3** nên dùng lại đúng 1.000 text query thật; giữ tương quan metadata ↔ vector (khách sạn Nha Trang nằm cạnh nhau) — sát cách filter chạy thật | Dữ liệu tổng hợp: chỉ dùng cho hiệu năng và hành vi filter, **không** cho chất lượng tìm kiếm | **Dùng** |
| B. Wikipedia tiếng Việt thật (`CohereLabs/wikipedia-2023-11-embed-multilingual-v3`, subset `vi` ~2,84 triệu passage, 1024-d) | Phân bố thật | Tải ~5 GB; model khác → query phải lấy từ dataset; metadata không tương quan | Đối chứng sau (`spec.md` Part 10) |
| C. Nhân bản nguyên 100 lần | — | 100 vector trùng → GT hoà điểm hàng loạt, ANN dễ một cách giả tạo | Không |
| D. Vector ngẫu nhiên | — | Local intrinsic dimensionality (LID) gần bằng số chiều → khó bất thường so với embedding thật | Không |

Căn cứ để bắt buộc kiểm LID: Aumüller & Ceccarello (SISAP 2019) cho thấy LID quyết định độ khó của truy vấn kNN và dùng được để chọn bộ truy vấn theo độ khó **[paper]**. Không có paper nào chuẩn hoá riêng cách khuếch đại A, nên số 1M chỉ được dùng khi qua kiểm tra dưới đây.

**Thuật toán** (`dataset/scale.py`, tuỳ chọn mới `--vectors amplify`):

```
Vào:  V0 (N0 × d, fp32, đã chuẩn hoá) = vector search unit của catalog thật; meta0 = items.parquet
Tham số (đề xuất, trong config fast.amplify):
      N = 1_000_000 · k_nn = 10 · alpha ~ U(0.1, 0.5) · sigma ∈ {0.05, 0.1, 0.2, 0.3} (hiệu chỉnh ở bước 2)
      geo_jitter_m = 2000 · amenity_drop = 0.1 · amenity_add = 0.1 · price_log_sd = 0.2

1. Láng giềng: k_nn láng giềng cosine của mỗi seed, ưu tiên cùng destination (đủ k_nn seed), không thì toàn cục.
2. Hiệu chỉnh sigma: c1 = median cosine của cặp 1-NN thật trong V0. Với mỗi sigma: sinh 20k mẫu,
   đo median cos(v, seed); chọn sigma có median gần c1 nhất (con sinh ra cách seed xa như láng giềng thật).
3. Sinh (theo khối 100k, ghi memmap fp16):
   i = t mod N0 (mỗi seed ~N/N0 con) · j = láng giềng ngẫu nhiên của i · g ~ N(0, I_d)
   v = normalize((1 − alpha)·V0[i] + alpha·V0[j] + sigma·g/√d)
4. Metadata kế thừa từ i:
   - variant, taxonomy, destination, star_rating giữ nguyên;
   - available ~ Bernoulli(tỷ lệ available của variant);
   - amenity_ids: mỗi id bỏ với xác suất 0,1; thêm 1 id phổ biến với xác suất 0,1;
   - unit_price × exp(N(0, 0.2));
   - lat/lon + N(0, 2 km).
5. Kiểm tra — ghi vào stats.json. Trượt thì đổi sigma và sinh lại (1–2 phút):
   a. LID (MLE Levina–Bickel, k = 20, khoảng cách Euclid trên vector chuẩn hoá):
      median LID của mẫu N0 điểm tổng hợp / median LID của V0 ∈ [0.75, 1.33]   (đề xuất)
      LID(x) = −[ (1/k) Σ_{i=1..k} ln(d_i / d_k) ]⁻¹
   b. Gần trùng: tỷ lệ điểm có cos(v, seed) ≥ 0.999 < 1%.
   c. Thông tin: phân bố cosine top-10 của 200 query thật trên V0 so với trên 1M (1M sẽ dày hơn — bình thường).
```

- Query ở 1M = **đúng 1.000 query vector** của catalog (cùng không gian).
- Filter sinh lại trên metadata 1M để đủ 4 bucket selectivity (ở 1M, `b01` = 500–2.000 item).
- GT tính exact như `spec.md` Part 4: ~1 TFLOP, 1–3 phút trên 8 core.

---

## 4. Claude Code cài gì (theo thứ tự, lấy chi tiết từ `spec.md`)

| Part (`spec.md`) | Cài | Bỏ hôm nay |
|---|---|---|
| 0 | `compose.yml` chỉ 3 profile: `pgvector`, `pgvectorscale`, `qdrant`; `lifecycle`; `doctor` | Milvus, Weaviate, OpenSearch |
| 1 | `dataset catalog --source jsonl` (amenity fallback + text builder fallback) | `--source db` |
| 2 | `embed` backend `st` (bge-m3) cho items và queries | — |
| 3 | Filter AST + evaluator + generator; 1.000 query; 4 bucket; thêm `queries --scale 1m --reuse-query-vectors catalog` | Slice text chỉ cần `normal` + `khong_dau` |
| 4 | GT theo khối cho catalog và 1m | Facet GT |
| 5 | Adapter pgvector: `create/upsert(COPY)/finalize/search` (exact, ann, auto), `count` | lexical, facet, backup |
| 7 | Adapter Qdrant: `create/upsert/finalize/search`, `count(exact)`; index `default` | forced_hnsw, lexical, facet, snapshot |
| 8a | Adapter pgvectorscale (kế thừa pgvector): index `diskann` | `diskann_labels` |
| 6 (lite) | A1, A3 (+ count exact ở catalog) | A2, A5, facet |
| 9 (lite) | G3 ở catalog (ALL-of, NOT, range, geo) | G1, G2, G4–G7 |
| 10 | **Mới:** `scale-data 1m --vectors amplify` (§3) | cohere-vi |
| 11 (lite) | Tải **open-loop** 100 rồi 200 QPS, mỗi mức 90 s (≥ 9.000 request); latency tính từ thời điểm *lẽ ra* gửi; P50/P95/**P99**/P99.9 + CI bootstrap; timeout 1 s tính vào phân vị; `vb perf null` hiệu chỉnh harness; B3 từ `load.json`; C1 (sampler docker stats) | B4, B5, B6, C2, D |
| **Mới** | `vb fast` (điều phối, có chặn thời gian) + `vb fast-report` (bảng + quy tắc §6) | score/decide đầy đủ |

**Tham số index — giữ mặc định của engine để build nhanh và công bằng:**

- pgvector: HNSW `m=16, ef_construction=64` (mặc định của pgvector), `maintenance_work_mem=4–8GB`, `max_parallel_maintenance_workers = số CPU của engine − 1`, `shm_size: 2g`.
- Qdrant: `m=16, ef_construct=100` (mặc định).
- pgvectorscale: `diskann` mặc định.

**Sweep query — cấu hình (b) = cấu hình có P99 một client thấp nhất trong các cấu hình đạt A1 ≥ 0,95:**

- pgvector: `auto` (exact khi tập lọc ≤ 10.000, không thì HNSW + `iterative_scan=relaxed_order`) × `ef_search ∈ {40, 100, 200}`, và `ann` thuần `ef_search=100`. Kích thước tập lọc **ước lượng** từ thống kê cache (đếm theo destination × taxonomy, tần suất amenity), không chạy `COUNT` trước — thêm một round trip là cộng thẳng vào P99. Giữ `hnsw.max_scan_tuples = 20000` làm trần công việc mỗi query.
- Qdrant: `hnsw_ef ∈ {64, 128, 256}`.
- pgvectorscale: `query_search_list_size ∈ {100, 200, 400}`.

**`vb fast`** — với mỗi engine lần lượt:

1. `up`, `wait_healthy`.
2. Load catalog → G3 → A1 / A3 / count ở catalog.
3. Load 1M (ghi B3) → sweep A1 / A3 ở 1M → chọn (b) → tải open-loop 100 rồi 200 QPS với (b) (B1, B2); sampler C1 chạy suốt.
4. `down --volumes`.

Chặn thời gian `fast.max_minutes_per_engine: 35`: vượt thì ghi kết quả dở dang (`status: partial`) và sang engine tiếp, để cả lượt không vượt 2 giờ.

---

## 5. Lịch 2 giờ máy (sau khi code đã chạy được với dữ liệu fake)

| Mốc | Việc | Lệnh | ~Phút |
|---|---|---|---|
| 0:00 | Kiểm máy, pull 3 image | `vb doctor` · `docker compose -p vbench --profile pgvector --profile qdrant --profile pgvectorscale pull` | 5–10 |
| 0:05 | Catalog → embed → query → GT | `vb dataset catalog --source jsonl --products <10k>` · `vb embed --scale catalog` · `vb queries --scale catalog` · `vb embed --scale catalog --target queries` · `vb gt --scale catalog` | 10–15 |
| 0:20 | Khuếch đại 1M + kiểm LID + query + GT | `vb scale-data 1m --vectors amplify` (tự gọi `queries` và `gt`) | 5–10 |
| 0:30 | pgvector | `vb fast --engines pgvector` | 25–30 |
| 1:00 | Qdrant | `vb fast --engines qdrant` | 20–25 |
| 1:25 | pgvectorscale | `vb fast --engines pgvectorscale` | 25–30 |
| 1:55 | Bảng + quyết định | `vb fast-report` | 2 |

Ước lượng build 1M × 1024-d halfvec trên 8 vCPU với `ef_construction=64` là 5–10 phút *(ngoại suy từ số của Supabase: 1M × 1536-d, efc 200, 16 core ≈ 9,5 phút)*. Nếu máy yếu hơn, chặn thời gian ở §4 giữ tổng không vượt 2 giờ.

**Thời gian sinh code** (Part 0–5, 7, 8a, bản lite + `amplify` + `fast`) là phần riêng, ước 1–2 giờ với Claude Code. Nên chạy song song: một người pull image và tải model bge-m3 trong lúc code đang sinh.

---

## 6. Metric và quy tắc chốt — viết trước khi chạy

| Metric | Đo ở | Ngưỡng (VECTOR_DB_SELECTION §4) |
|---|---|---|
| G3 — ngữ nghĩa filter (0 vi phạm ALL-of / NOT / range / geo) | catalog | bắt buộc |
| A3 — precision ràng buộc | catalog + 1M | = 1,0 |
| A1 — Filtered Recall@10, min trên 4 bucket, cấu hình (b) | 1M | ≥ 0,95 |
| B1 — **P99** latency ở tải open-loop 100 QPS, cấu hình (b), không tính embed query | 1M | ≤ 100 ms |
| B2 — P99 ở 200 QPS (dư địa gấp đôi) | 1M | ghi nhận, không loại |
| B3 — load + build index | 1M | ≤ 30 phút (ghi nhận, không loại) |
| C1 — RAM đỉnh của engine | 1M | ≤ 8 GB (ghi nhận, không loại) |

**Quy tắc** — `vb fast-report` in ra kết luận và lý do:

1. Trượt G3 hoặc A3 < 1 → loại.
2. **pgvector** đạt A1 và B1 (P99 ≤ 100 ms ở 100 QPS) ở 1M → **chốt pgvector**. Lý do: đáp ứng tới 1M mà chi phí migrate = 0, dữ liệu cùng DB. Khớp quy tắc 2–3 của VECTOR_DB_SELECTION §7.
3. Không thì, **pgvectorscale** đạt → **chốt pgvectorscale** (vẫn trong Postgres).
4. Không thì, **Qdrant** đạt → **chốt Qdrant**.
5. Không engine nào đạt ở 1M → **chốt pgvector cho quy mô hiện tại** (5k → 100k vector, dựa trên số ở catalog). Chạy `spec.md` đầy đủ, thêm Milvus và Weaviate, **trước khi** catalog vượt ~200k vector.

**Đọc số cho đúng:**

- Khoảng tin cậy 95% của P99 hai engine chồng nhau → coi là hoà.
- Hoà → pgvector.
- Mọi số 1M là trên dữ liệu khuếch đại: ghi rõ trong báo cáo, kèm kết quả kiểm LID.

**Vì sao đo P99 kiểu này:**

- Tải closed-loop (N client, nhận xong mới gửi tiếp) tự giảm tải đúng lúc engine chậm nên bỏ sót đuôi — coordinated omission. Ví dụ trong README của wrk2: P99 đo sai 6,04 ms, đo đúng 1,27 s.
- 1.000 request chỉ có 10 mẫu nằm trên P99, không đủ để so hai engine; ≥ 9.000 request mỗi mức tải thì có ≥ 90 mẫu.

---

## 7. Hoãn lại, và khi nào chạy tiếp

| Hoãn | Vì sao hôm nay không cần | Chạy khi |
|---|---|---|
| A2 hybrid nDCG | Cần bộ gold ≥ 50 query đã gán nhãn | Có gold (EMBEDDING §9) |
| Milvus, Weaviate | Chỉ đổi quyết định nếu Qdrant cũng trượt (§6 quy tắc 5) | Quy tắc 5 xảy ra, hoặc cần BM25/facet phía server |
| Elasticsearch làm sidecar lexical | Là quyết định riêng về kênh lexical | A2 cho thấy lexical của Postgres thiếu |
| B4–B6, G1, G2, G4–G7, C2, D, E | Không lật được quyết định giữa 3 engine | Trước khi lên production |
| 1M bằng Wikipedia-vi thật | Đối chứng dữ liệu khuếch đại | Tuần này, chạy nền |

---

## 8. Nguồn

- AWS — pgvector 0.8.0 trên Aurora: iterative scan, 10M × 384-d, recall 10% → 100%, 9,4× https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql
- Supabase — pgvector 0.6.0 build song song: 1M × 1536-d ~9,5 phút / 16 core https://supabase.com/blog/pgvector-fast-builds
- Aumüller & Ceccarello — The Role of Local Intrinsic Dimensionality in Benchmarking Nearest Neighbor Search (SISAP 2019) https://arxiv.org/abs/1907.07387
- Weaviate 1.33 — `ContainsNone`, `Not` https://weaviate.io/blog/weaviate-1-33-release
- Qdrant — filtered search với ACORN (số theo selectivity, 1M) https://qdrant.tech/articles/filtered-vector-search-acorn/
- ACORN, SIGMOD 2024 https://arxiv.org/abs/2403.04871
- Weaviate ACORN https://weaviate.io/blog/speed-up-filtered-vector-search
- Milvus release notes 3.0.x https://milvus.io/docs/release_notes.md · Milvus 2.6 https://milvus.io/blog/introduce-milvus-2-6-built-for-scale-designed-to-reduce-costs.md
- pgvectorscale README https://github.com/timescale/pgvectorscale · Tiger Data pgvector vs Qdrant https://www.tigerdata.com/blog/pgvector-vs-qdrant
- pgvector issue #700 https://github.com/pgvector/pgvector/issues/700 · dbi-services pgvector part 2 (03/2026) https://www.dbi-services.com/blog/pgvector-a-guide-for-dba-part-2-indexes-update-march-2026/ · Neon exact vs index https://neon.com/blog/optimizing-vector-search-performance-with-pgvector
- Plugin tiếng Việt cho Elasticsearch https://github.com/duydo/elasticsearch-analysis-vietnamese
- Dataset Wikipedia-vi 1024-d https://huggingface.co/datasets/CohereLabs/wikipedia-2023-11-embed-multilingual-v3
- Coordinated omission — wrk2 README (Gil Tene) https://github.com/giltene/wrk2
- Dean & Barroso — The Tail at Scale, CACM 2013 https://cacm.acm.org/research/the-tail-at-scale/
