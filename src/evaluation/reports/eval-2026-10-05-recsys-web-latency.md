# Latency `/recommendations` trên Web — cloud (khách vãng lai, đã đăng nhập) và backend local (60 khách) (05/10)

- Phục vụ: NFR-PERF-01 (p95 `/recommendations` ≤ 250 ms), FR-REC-01; lịch 10 ngày Day 7 "latency p95 `/recommendations` trên cloud".
- Câu hỏi: người dùng Web chờ bao lâu để có khối gợi ý trên trang chủ.
- Quan trọng: trang chủ **chỉ gọi** `GET /api/v1/recommendations?k=4` khi đã đăng nhập (`src/frontend/src/components/home/HomeView.tsx`:
  khách vãng lai không gọi, không thấy khối gợi ý). Số khách vãng lai dưới đây chỉ là mốc API, không phải trải nghiệm Web.

## Kết quả

| # | Đường | Ở đâu | n | Server `latencyMs` p50 / p95 / max | Phía client p50 / p95 / max | Strategy |
|---|---|---|---:|---|---|---|
| 1 | **Web đã đăng nhập** (BFF + cookie phiên, như trang chủ) | Cloud `v-ota.duckdns.org`, trình duyệt | 50 | **35 / 37 / 39 ms** | **264 / 531 / 664 ms** | `popular` (cold start: tài khoản chưa có lịch sử, `eventsUsed 0`) |
| 1b | **Web đã đăng nhập, nhánh cá nhân hoá** (cùng tài khoản sau khi xem 1 sản phẩm Đà Lạt → `eventsUsed 1`) | Cloud, trình duyệt | 38 | **820 / 1.057 / 2.207 ms** (min 814) | **918 / 1.450 / 2.284 ms** | `cold_start_content` |
| 2 | Khách vãng lai (không cookie) | Cloud, qua BFF, Python `http-latency` | 50 | 9 / 12 ms | 251 / 625 ms | `popular` |
| 3 | 60 khách cá nhân hoá (`/internal/recommendations`, `X-Service-Token`) | Backend local, DB bench seed 09-23 | 120 | 72 / 86 ms | 77 / 92 ms | long_term 72 · dormant 57 · popular 45 · cross_vertical 3 · cold_start 3 (180 mẫu) |

- Dòng 1: 55 lượt tuần tự `fetch('/api/v1/recommendations?k=4', {cache:'no-store'})` trong tab đã đăng nhập (người dùng tự đăng nhập; phiên
  `authenticated`), bỏ 5 lượt đầu (client 318 / 207 / 219 / 241 / 218 ms); 55/55 trả 200, 4 món mỗi lượt. Client = `performance.now()` quanh
  `fetch` + parse JSON, đo từ máy dev ở Việt Nam qua Internet tới VM `asia-southeast1`.
- Dòng 2: `python -m src.evaluation.recsys_bench http-latency --base-url https://v-ota.duckdns.org --runs 11 --k 5 --run-id 20261005-cloud-guest`
  (11 lượt × 5 GET, bỏ lượt 1), 55/55 OK.
- Dòng 3: `http-latency --base-url http://127.0.0.1:8000 --users src/evaluation/recsys_bench/frozen/users60.json --token-env AUTH_SERVICE_TOKEN
  --runs 3 --k 5 --run-id 20261005-local-users60` (3 lượt × 60 khách, bỏ lượt 1), 180/180 OK. Backend local `uvicorn` (vsf2), Postgres bench
  cổng 55433 (snapshot 09-23, `as_of` 2026-09-24), Weaviate bench `ProductBench` (vector Cohere v3, 3.183 unit, 48 unit lệch textHash),
  `INTERNAL_API_ENABLED=true`. Ngày chạy 05/10 muộn hơn `as_of` 11 ngày nên nhiều khách rơi vào `dormant` / `popular` hơn lúc seed.

- Dòng 1b: 40 lượt (3 lô trong cùng tab), bỏ 2 lượt đầu; 40/40 trả 200, 4 món. Tài khoản tự có 1 event sau khi người dùng xem một sản phẩm.

## Đọc

- **Nhánh cá nhân hoá trên cloud KHÔNG đạt NFR-PERF-01:** server p50 820 ms, p95 1.057 ms (ngưỡng 250 ms); người dùng chờ ~0,9 s (p50),
  ~1,5 s (p95). Cùng nhánh ở local chỉ 72 / 86 ms (dòng 3) và nhánh `popular` trên cloud 35 / 37 ms (dòng 1) → phần chênh không nằm ở thuật toán
  mà ở các lượt gọi Weaviate Cloud mỗi request (lấy vector sản phẩm khách đã xem + `near_vector` top-K có mask). Sàn 814 ms ổn định giống `/search`
  (dense 1,8 s, 01/10: Weaviate Cloud `eu-central-1`, VM `asia-southeast1`, mask ~3.000 id mỗi lượt). Chưa có `stageMs` cho `/recommendations`
  để tách từng bước — nên thêm trước khi tối ưu.
- **Nhánh `popular` (khách mới đăng nhập, chưa có lịch sử) nhanh:** server p95 37 ms; người dùng chờ ~0,26 / 0,53 s, ~85 % là mạng + TLS + BFF.
- **Chưa đo `long_term` / `cross_vertical` trên cloud** (khách có lịch sử mua): kỳ vọng cùng sàn ~0,8 s vì cùng đi Weaviate Cloud; đo được khi
  đăng nhập persona P1 hoặc ops mở IAP + `X-Service-Token`.
- Hướng xử lý (đã ghi ở `search-eval-results.md` §2 cho `/search`, áp dụng chung): Weaviate cùng vùng với VM, bỏ mask id khi mask ≈ toàn
  catalog, gộp / song song các lượt gọi; cache vector sản phẩm trong RAM (3.183 × 1.024 float ≈ 13 MB).

## Không làm

- Web local có đăng nhập: bản web production cần Redis cho phiên; người dùng chọn không tải image Redis.
- Tải trang đầy đủ (LCP, render khối gợi ý): chỉ đo request gợi ý.
