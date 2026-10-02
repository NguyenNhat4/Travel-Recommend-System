# Kết quả search bench trên Cloud — parity, breakdown latency, hit/miss cache

Phục vụ: NFR-PERF-01/03, FR-SRC-01/02; lịch 10 ngày Day 2 C (`docs/plan/2026-09-28-lich-10-ngay-3-engine.md`), plan Day 3
C3–C5 (`docs/plan/2026-09-30-plan-day3.md`). Công cụ: spec bench Part 9 (`docs/spec/bench/search-eval-local-spec.md`).
Cập nhật lần cuối: 2026-10-01 (§2–3 breakdown + hit/miss trên VM sau PR 1.12.0).

## 1. Parity Cloud vs local (M4) — `sb parity --mode weaviate`, 01/10

Cùng `SearchProducts` production (arm `APP.hybrid_norm`: hybrid + chuẩn hoá, cutoff 0,62) trên **catalog VM** đọc qua
`PostgresCatalogReader` (tunnel SSH, 3.304 search unit lúc chạy); kho A = collection `Product` trên Weaviate Cloud (hfresh),
kho B = `ProductVM` trên Weaviate bench 1.37.3 (hnsw) nạp từ **vector kéo về từ Cloud** (3.183 vector, 0 Cohere). 121 unit VM
chưa có vector trên Cloud (catalog VM lớn hơn index 3.183 — xem C6) nên vắng ở cả hai bên như nhau; 47 object Cloud còn text
cũ (vector cũ dùng chung hai bên). 20 câu `config/parity_queries.yaml` (13 slice + "VinWonders", "KS biển tại NT",
"Vinpeal Resort Nha Trang giá tốt"), k = 10.

| Chỉ số | Kết quả | Cổng |
|---|---|---|
| Top-1 trùng | **20/20** | ≥ 18/20 |
| Overlap@10 trên 16 câu có ≥ 8 kết quả cả hai bên | min **8**, 13 câu 10/10, 2 câu 9/10 (`amenity_negation`, `amenity_offtaxonomy`), 1 câu 8/10 (`VinWonders`) | ≥ 8/10 mọi câu |
| 4 câu ngắn (`out_of_catalog` ×2, "Chợ nổi Cái Răng", "khach san o ha long co ho boi co tam nhin") | cùng số kết quả, trùng hết (2/2, 0/0, 1/1, 1/1) | trùng hết |
| **Kết luận** | **PASS** — index Cloud = index local trên cùng vector, cùng text; lệch còn lại là nhiễu ANN (hfresh vs hnsw) và BM25 hoà điểm | |

Run: `bench_out/search/runs/20261001-cloud/parity-weaviate.json`.

Ghi chú: lần chạy đầu 01/10 (ngay sau khi nạp 3.183 object vào `ProductVM`) cho top-1 5/20, overlap min 0 dù dense / BM25
gọi rời trả **cùng tập, cùng điểm** hai bên — thứ tự ứng viên sai trong lúc HNSW còn dựng. Từ đó `load_collection` chờ shard
`READY` và hàng đợi index rỗng (`/v1/nodes?output=verbose`) rồi mới trả về; cổng overlap cũng sửa để câu ít kết quả không
bị tính FAIL giả (spec Part 9).

## 2. Breakdown `/search` trên Cloud — `sb latency http` (C5), 01/10

Đo sau khi `release-mvp-v2 @ fe7e04d` (contract 1.12.0: `stageMs` + cache + prewarm) lên VM — PR1 và PR2 đã merge và deploy
(Backend CI/CD #114); không còn mốc "cache-off" để đo riêng vì cache bật mặc định. 25 câu prewarmed + 25 câu cold × 3 lượt tuần tự,
bỏ lượt 1, `limit 10`, số server (`latencyMs`, `stageMs`), run `20261001-1059-8842c3a`. Bảng nguyên văn, theo lượt và thí nghiệm
mask id ở `src/evaluation/reports/eval-2026-10-01-search-cloud-latency.md`.

| Stage (ms server, 100 mẫu lượt 2–3) | p50 | p95 |
|---|---:|---:|
| normalize | 0 | 0 |
| embed (cache hit) | 0 | 0 |
| dense (`nearVector`, mask 3.146 id) | 1.809 | 1.830 |
| lexical (BM25, cùng mask) | 2.131 | 2.181 |
| fuse (RRF) | 1 | 1 |
| hydrate | 0 | 0 |
| **`latencyMs` tổng** | **3.940** | **4.007** |
| client qua BFF từ máy dev (nhiễu mạng dev, chỉ tham khảo) | 7.172 | 14.390 |

Đọc số: engine `/search` trên VM gần như chỉ là **hai lượt gọi Weaviate Cloud tuần tự**; mọi stage khác ≈ 0. Ba nguyên nhân đã
đo được:

1. **Khoảng cách vùng.** Cluster Weaviate Cloud của nhóm ở `eu-central-1` (AWS Frankfurt), VM ở `asia-southeast1` (Singapore) —
   mỗi lượt gọi gRPC đi ~10.000 km. Cùng adapter trên Weaviate local: dense 20 ms, BM25 11 ms không lọc.
2. **Mask id gửi kèm mỗi lượt gọi.** `SearchProducts` gửi toàn bộ id được phép (`Filter.by_id().contains_any`, 3.146 UUID khi không
   lọc) cho cả dense lẫn BM25. Thu mask bằng filter công khai: dense 1.827 ms (3.146 id) → 701 ms (140 id, `destination=Hạ Long`) →
   354 ms (64 id, `Côn Đảo`); local mọi id 87 ms so với 20 ms không lọc. BM25 có sàn ~1,4 s bất kể mask — cần xem riêng trên cluster.
3. **Dense và lexical chạy nối tiếp** trong `_hybrid` → tổng = cộng dồn.

Đầu vào cho M3 và tuần performance (plan Day 4–5 §0: tuần này chỉ đo, không tune; không cái nào đổi contract):
kho vector **cùng vùng** với backend (Weaviate trên VM/compose hoặc cluster Cloud châu Á) là đòn bẩy lớn nhất (≈ 3,9 s → vài chục ms
theo số local); bỏ mask id khi mask ≈ toàn bộ collection (lọc lại phía Python) tiết kiệm ~1,1–1,5 s/lượt dense ngay trên Cloud hiện
tại; chạy dense ∥ lexical chia đôi phần còn lại; sàn BM25 1,4 s trên cluster sandbox cần đo tách (có/không `query_properties`,
kích thước `searchTextAscii`).

## 3. Hit/miss cache vector truy vấn — sau PR 1.12.0 (C3), 01/10

| embedCache | n | embed p50 / p95 | latencyMs p50 / p95 |
|---|---:|---:|---:|
| hit | 125 | 0 / 0 | 3.929 / 4.003 |
| miss (lần gặp đầu của 25 câu cold) | 25 | 281 / 437 | 3.076 / 3.216 |

- Cache tiết kiệm **≈ 0,3–0,45 s mỗi truy vấn** (cột `embed`), tức ~10 % `latencyMs`; `latencyMs` nhóm hit cao hơn nhóm miss là do
  Cloud chậm dần trong run (lượt 1: dense 1,28 s / lexical 1,50 s; lượt 2–3: 1,82 / 2,15 s), không phải do cache.
- **Prewarm trên VM đã chạy**: lượt 1 nhóm prewarmed hit 25/25 (`search_prewarm_queries.txt`, 131 câu gold_v1 active); nhóm cold
  miss 25/25 ở lượt 1, hit 25/25 từ lượt 2.
- **Top-10 không đổi giữa miss và hit: 50/50 câu** ở cả 3 lượt.
- Câu hỏi 3 của checkpoint (p95 cache-hit < 250 ms?): **không** — 4,0 s. Phần còn lại không phải Cohere mà là hai lượt Weaviate Cloud
  (§2); NFR-PERF-01 chỉ có thể đạt khi kho vector cùng vùng.
- Chưa chạy job `prewarm_query_cache` lần hai để kiểm `miss 0` (cần chạy từ VM hoặc qua BFF; thêm 131 request).

## 4. `/recommendations` trên Cloud (C7)

Guest path 01/10: server p50 9 / p95 10 ms, client qua BFF 141 / 391 ms — chi tiết `docs/spec/bench/recsys-offline-eval.md` §4.5.
