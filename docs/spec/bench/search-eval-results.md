# Kết quả search bench trên Cloud — parity, breakdown latency, hit/miss cache

Phục vụ: NFR-PERF-01/03, FR-SRC-01/02; lịch 10 ngày Day 2 C (`docs/plan/2026-09-28-lich-10-ngay-3-engine.md`), plan Day 3
C3–C5 (`docs/plan/2026-09-30-plan-day3.md`). Công cụ: spec bench Part 9 (`docs/spec/bench/search-eval-local-spec.md`).
Cập nhật lần cuối: 2026-10-01.

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

## 2. Breakdown `/search` trên Cloud — `sb latency http` (C5)

Chưa đo: `/api/v1/search` công khai đang 500 sau ~64 s (bước embed Cohere trên VM, xem history 01/10) và PR `stageMs`
(1.11.0) chưa merge. Bảng dự kiến: p50/p95 `latencyMs` tổng + `stageMs.normalize/embed/dense/lexical/fuse/hydrate`, 25 câu
prewarmed + 25 câu cold × 3 lượt, bỏ lượt 1; `--label cache-off` trước PR cache, `cache-on` sau.

## 3. Hit/miss cache vector truy vấn — sau PR 1.12.0 (C3)

Chưa đo (chờ PR `feat/search-embed-cache` deploy): p50/p95 riêng cho `embedCache = hit` và `miss`; top-10 của lần miss và
lần hit phải trùng 50/50 câu; job `prewarm_query_cache` lần hai phải `miss 0`.

## 4. `/recommendations` trên Cloud (C7)

Guest path 01/10: server p50 9 / p95 10 ms, client qua BFF 141 / 391 ms — chi tiết `docs/spec/bench/recsys-offline-eval.md` §4.5.
