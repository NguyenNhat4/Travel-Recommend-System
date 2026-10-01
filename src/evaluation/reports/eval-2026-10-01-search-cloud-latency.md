# Search bench — latency `/search` trên Cloud (VM) sau PR cache 1.12.0: breakdown stage, hit/miss, ảnh hưởng mask id

- Công cụ: `sb latency http` trên nhánh `bench/m6-trip-ended @ 8842c3a` (spec bench Part 9). Backend đang chạy trên VM =
  `release-mvp-v2 @ fe7e04d` (Backend CI/CD #114, 01/10 10:31 giờ VN; contract **1.12.0**: `diagnostics.stageMs` + `embedCache`,
  cache vector truy vấn + prewarm bật mặc định). Index Weaviate Cloud = catalog VM (C6, 01/10).
- Run id: `20261001-1059-8842c3a`, label `cache-on` → `bench_out/search/runs/20261001-1059-8842c3a/latency-cache-on.json`.
- Câu hỏi: `config/latency_queries.yaml` — 25 câu **prewarmed** (gold_v1 active, nằm trong `src/backend/data/search_prewarm_queries.txt`,
  sha gold `e47b0d6a…`) + 25 câu **cold** (ngoài gold).
- Cấu hình: 50 câu × 3 lượt tuần tự, `limit 10`, `drop_first` (p50/p95 tính trên lượt 2–3; lượt 1 vẫn là nguồn mẫu `miss`),
  timeout 30 s. Client = máy dev (VN); server = VM GCP `asia-southeast1` (Singapore) → Weaviate Cloud `eu-central-1` (AWS, Frankfurt).
- Chạy lúc: 2026-10-01 10:59–11:19 (giờ VN). Phục vụ: NFR-PERF-01/03, FR-SRC-01/02; plan Day 4–5 §0 (ô "Cache `/search` trên cloud"),
  lịch 10 ngày Day 2 C.

## 1. Bảng nguyên văn `sb latency http` (ms server: `latencyMs`, `stageMs`; lượt ≥ 2)

| nhóm | n | latencyMs p50 | p95 | client p50 | p95 | normalize p50/p95 | embed p50/p95 | dense p50/p95 | lexical p50/p95 | fuse p50/p95 | hydrate p50/p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 100 | 3940 | 4007 | 7172 | 14390 | 0/0 | 0/0 | 1809/1830 | 2131/2181 | 1/1 | 0/0 |
| prewarmed | 50 | 2870 | 3969 | 6864 | 16718 | 0/0 | 0/0 | 1395/1822 | 1558/2150 | 1/1 | 0/0 |
| cold | 50 | 3972 | 4159 | 7610 | 13419 | 0/0 | 0/0 | 1819/1835 | 2148/2342 | 1/1 | 0/0 |

Theo `embedCache` (miss = lần gặp đầu của câu, mọi lượt):

| cache | n | latencyMs p50 | p95 | embed p50 | p95 | client p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| hit | 125 | 3929 | 4003 | 0 | 0 | 6805 | 13981 |
| miss | 25 | 3076 | 3216 | 281 | 437 | 7338 | 14268 |

`mẫu 150/150 OK · searchMode ['HYBRID_CANDIDATE_SCORE'] · embedCache ['hit', 'miss'] · top-10 giống nhau ở mọi lượt 50/50`

## 2. Theo lượt và theo nhóm (tính từ `samples` của JSON, p50 trừ khi ghi khác)

| Lượt | Nhóm | latencyMs p50 / p95 | dense | lexical | embed p50 / p95 | client p50 | hit |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | prewarmed | 2744 / 2822 | 1281 | 1477 | 0 / 0 | 4883 | **25/25** |
| 1 | cold | 3076 / 3231 | 1285 | 1503 | 281 / 463 | 7338 | 0/25 |
| 2 | prewarmed | 2798 / 2854 | 1288 | 1503 | 0 / 0 | 7287 | 25/25 |
| 2 | cold | 3971 / 4309 | 1816 | 2149 | 0 / 0 | 8112 | 25/25 |
| 3 | prewarmed | 3941 / 3979 | 1809 | 2130 | 0 / 0 | 6704 | 25/25 |
| 3 | cold | 3975 / 4007 | 1821 | 2147 | 0 / 0 | 6589 | 25/25 |

Lượt 1 nhóm prewarmed hit 25/25 → prewarm lúc khởi động trên VM đã chạy xong trước khi đo (không chạy job `prewarm_query_cache`
từ máy dev). Từ lượt 2 nhóm cold trở đi Cloud chậm hẳn (dense 1,28 → 1,82 s, lexical 1,50 → 2,15 s) — nhiễu phía Cloud/đường mạng,
không liên quan cache.

## 3. Ảnh hưởng kích thước mask id (`Filter.by_id().contains_any`, một lượt gọi dense + một lượt BM25)

`GET /api/v1/search` công khai trên VM, 4 lượt mỗi ca, bỏ lượt 1 (embed miss), p50 của 3 lượt còn lại; `filteredCount` = số id
trong mask gửi sang Weaviate:

| Ca | filteredCount | total | dense p50 | lexical p50 | latencyMs p50 |
|---|---:|---:|---:|---:|---:|
| `q=khách sạn có hồ bơi` (không lọc, mask = mọi unit) | 3146 | 232 | 1827 | 2147 | 3974 |
| + `destination=Hạ Long` | 140 | 65 | 701 | 1396 | 2099 |
| + `destination=Côn Đảo` | 64 | 37 | 354 | 1395 | 1752 |
| `q=vé máy bay Hà Nội&taxonomy=flight` | 113 | 89 | 701 | 1395 | 2098 |

## 4. Đối chiếu Weaviate local (máy dev, collection `Product` 2.897 object, adapter production `WeaviateVectorSearch`, 5 lượt)

| Mask | dense p50 (min) | bm25 p50 (min) |
|---|---:|---:|
| không lọc | 20 (19) | 11 (10) |
| 50 id | 11 (9) | 14 (13) |
| 500 id | 32 (26) | 28 (23) |
| mọi id (2.897) | 87 (73) | 81 (78) |

Cùng script đo tới Cloud từ laptop cho dense 1,0–5,1 s không theo quy luật (TLS tới Cloud từ laptop 5–17 s lúc đo) — **không dùng**;
số Cloud tin cậy là số server trên VM ở §1–§3.

## 5. Caveat khi trích dẫn

- So hit/miss chỉ đọc cột `embed` (hit 0 / 0, miss 281 / 437 ms). `latencyMs` nhóm hit (3.929) cao hơn nhóm miss (3.076) vì mẫu
  miss toàn ở lượt 1 lúc Cloud còn nhanh, không phải vì cache làm chậm.
- `client` p50/p95 (6,8–7,3 s / 14–17 s) nhiễu bởi mạng máy dev lúc đo; số đầu bảng là số server (`latencyMs`, `stageMs`).
- Mỗi request tuần tự, không tải đồng thời; không phải số p95 dưới tải.
- `stageMs` làm tròn xuống nên tổng stage ≤ `latencyMs`; `hydrate` 0 vì catalog nằm trong RAM.
- Chưa chạy `python -m src.backend.jobs.prewarm_query_cache --base-url …` lần hai để kiểm `miss 0` (plan C2) — prewarm đã được
  xác nhận gián tiếp qua lượt 1 nhóm prewarmed.

## 6. Lệnh tái sinh

```bash
# từ src/, venv bench
PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 ../.venv-sbench/Scripts/python.exe -m evaluation.search_bench latency http \
    --base-url https://v-ota.duckdns.org --runs 3 --drop-first --limit 10 --label cache-on
# §3: 4 lượt mỗi URL, đọc diagnostics.stageMs / filteredCount
curl -s 'https://v-ota.duckdns.org/api/v1/search?q=kh%C3%A1ch+s%E1%BA%A1n+c%C3%B3+h%E1%BB%93+b%C6%A1i&limit=10'
curl -s 'https://v-ota.duckdns.org/api/v1/search?q=kh%C3%A1ch+s%E1%BA%A1n+c%C3%B3+h%E1%BB%93+b%C6%A1i&limit=10&destination=H%E1%BA%A1+Long'
curl -s 'https://v-ota.duckdns.org/api/v1/search?q=kh%C3%A1ch+s%E1%BA%A1n+c%C3%B3+h%E1%BB%93+b%C6%A1i&limit=10&destination=C%C3%B4n+%C4%90%E1%BA%A3o'
curl -s 'https://v-ota.duckdns.org/api/v1/search?q=v%C3%A9+m%C3%A1y+bay+H%C3%A0+N%E1%BB%99i&limit=10&taxonomy=flight'
# §4: WeaviateVectorSearch(connect_weaviate("http://127.0.0.1:8080")).near_vector(vec, allowed, 200) / .bm25("vinwonders phu quoc", allowed, 50)
#     với allowed = None / 50 / 500 / mọi productId của collection, 5 lượt, lấy p50
```
