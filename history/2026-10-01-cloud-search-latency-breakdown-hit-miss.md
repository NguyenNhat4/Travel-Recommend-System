# Cloud 01/10 (trưa): CI/CD release-mvp-v2 đã xanh, đo breakdown `/search` và hit/miss cache trên VM (C5, C3)

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/m6-trip-ended (sau `8842c3a`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation (report), docs spec bench, docs spec search, docs plan

## Mục tiêu

Người dùng hỏi sửa lỗi CI/CD frontend trên nhánh nào để `release-mvp-v2` deploy được (Frontend CI #64/#68/#76 fail ở
`RUN npm run build:web`). Kiểm qua GitHub API: PR #67 (`khoa/type-check-frontend-in-ci`, merge `98cd680`) đã sửa — Frontend CI #83
xanh cả 5 job, Backend CI/CD #114 (`fe7e04d`, sau PR #68 gold) deploy xong; `/api/v1/search` công khai đã trả `stageMs` +
`embedCache` (contract 1.12.0). Không cần sửa gì; xoá nhánh rỗng `fix/web-build-v2` ở worktree TRP-v2. Việc còn lại của plan
Track C: C5 breakdown và C3 hit/miss trên Cloud (NFR-PERF-01/03, FR-SRC-01/02; plan Day 4–5 §0 ô "Cache `/search` trên cloud",
lịch 10 ngày Day 2 C).

## File thay đổi

- `src/evaluation/reports/eval-2026-10-01-search-cloud-latency.md` — thêm: report theo AGENTS.md §7 (bảng nguyên văn `sb latency http`
  run `20261001-1059-8842c3a`, theo lượt, thí nghiệm mask id trên API công khai, đối chiếu Weaviate local, caveat, lệnh tái sinh).
- `docs/spec/bench/search-eval-results.md` — sửa: §2 breakdown (bảng stage p50/p95, ba nguyên nhân đã đo, đầu vào M3 / tuần
  performance), §3 hit/miss (cache tiết kiệm 0,3–0,45 s; prewarm đã chạy; top-10 50/50; trả lời câu 3 checkpoint); dòng cập nhật.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §7.1 thêm đoạn số đo thật 01/10 dưới bảng ngân sách (p95 4,0 s,
  nguyên nhân vùng), trỏ tới spec bench và report.
- `docs/plan/2026-10-01-plan-day4-5.md` — sửa: ô "Cache `/search` trên cloud" (p95 hit 4.003 / miss 3.216 ms, top-10 không đổi).
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: tick Day 2 C "latency breakdown" + bảng stage, tick "thiết kế cache"
  (PR2 đã deploy), checkpoint Day 2, log "Day 4 (C, tiếp — 01/10 trưa)".
- `history/2026-10-01-cloud-search-latency-breakdown-hit-miss.md` — entry này.

## Quyết định

- Không còn mốc "cache-off" (cache bật mặc định từ 1.12.0, cả PR1/PR2 đã deploy) → chỉ có run `--label cache-on`; so hit/miss đọc
  cột `embed` (hit 0 / miss 281 p50, 437 p95 ms), vì `latencyMs` bị nhiễu bởi Cloud chậm dần trong run.
- `/search` p95 **4,0 s** trên VM gần như toàn bộ là hai lượt gọi Weaviate Cloud nối tiếp (dense 1,8 s, BM25 2,1 s): cluster ở
  `eu-central-1` (AWS Frankfurt, geo-IP) còn VM ở `asia-southeast1`; `SearchProducts` gửi mask 3.146 id (`contains_any`) mỗi lượt
  gọi — thu mask bằng `destination`/`taxonomy` công khai cho dense 1.827 → 701 → 354 ms; local cùng adapter 20 / 11 ms (87 / 81 ms với
  mọi id). BM25 có sàn ~1,4 s bất kể mask.
- **Không sửa engine tuần này** (plan Day 4–5 §0: chỉ đo và so; tuần sau là tuần performance). Ghi ba đòn bẩy làm đầu vào M3:
  kho vector cùng vùng, bỏ mask id khi mask ≈ toàn bộ collection (lọc lại phía Python), dense ∥ BM25 — không cái nào đổi contract.
- Số client (p50 7 s / p95 14 s) chỉ tham khảo: mạng máy dev lúc đo rất xấu (TLS tới Cloud 5–17 s); số đầu bảng là số server.
- Lịch sử/report của phiên trước ghi ngày 02/10 cho M6 (`history/2026-10-02-…`, `ENGINE_RULES_VERSION 2026-10-02-trip-ended`,
  report v5) trong khi việc đó làm ngày 01/10 (dấu thời gian CI, run id) — giữ nguyên tên đã commit, không đổi.

## Kiểm tra

- GitHub API (token từ `git credential`, không in): runs `release-mvp-v2` — Frontend CI #83 success @ `98cd680`, Backend CI/CD #114
  success @ `fe7e04d` (4 job, kể cả "Deploy application VM in place").
- `GET https://v-ota.duckdns.org/api/v1/search?q=VinWonders&limit=3` ×4: 200, `embedCache` miss → hit, `stageMs` có đủ 6 stage.
- `sb latency http --base-url https://v-ota.duckdns.org --runs 3 --drop-first --limit 10 --label cache-on`: 150/150 OK, exit 0,
  bảng trong report; `top-10 giống nhau ở mọi lượt 50/50`.
- Thí nghiệm mask id: 4 URL × 4 lượt (bỏ lượt 1) — bảng §3 report. Micro-benchmark Weaviate local bằng `WeaviateVectorSearch`
  production, 5 lượt — bảng §4 report (phần đo tới Cloud từ laptop bỏ vì nhiễu).
- Không chạy test code (chỉ docs + report).

## Còn lại / rủi ro

- Chạy `python -m src.backend.jobs.prewarm_query_cache --base-url … ` lần hai để kiểm `miss 0` (plan C2) — chưa làm (131 request).
- Sàn BM25 1,4 s trên cluster Cloud chưa tách nguyên nhân (query_properties, kích thước `searchTextAscii`, sandbox).
- Đề xuất engine (bỏ mask id khi mask ≈ toàn bộ, dense ∥ BM25) là việc tuần performance; nếu làm thì đọc AGENTS.md §1 cho
  `src/backend/app/application/search/use_cases.py`, giữ top-k không đổi (test parity).
- PR M6 `feat/recsys-trip-ended` → `release-mvp-v2` vẫn chờ người dùng mở; sau đó merge `release-mvp-v2` về `bench/embed-search`.
