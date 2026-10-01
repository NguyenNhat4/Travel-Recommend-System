# /search: cache vector truy vấn + prewarm (contract 1.12.0 `diagnostics.embedCache`), job `--lexical-only`

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/search-embed-cache (xếp trên `feat/search-stage-timing-v2` @ 391a00f, tách từ `origin/release-mvp-v2`)
- Trạng thái: hoàn thành (code + test; số hit/miss trên Cloud đo sau khi deploy — plan Day 3 C3)
- Phạm vi: contract, backend, frontend (types), docs

## Mục tiêu

Lịch 10 ngày Day 2–3 phần C và plan `docs/plan/2026-09-30-plan-day3.md` (C1 cache, C2 prewarm, C6 guard): Cohere chiếm
0,4–0,6 s mỗi truy vấn `/search` (plan 28/09 §1.5) trong khi PRD NFR-PERF-01 đặt p95 ≤ 250 ms; NFR-PERF-03 nói rõ "nếu
vượt thì phải cache vector của truy vấn lặp lại" → **không lệch PRD**. FR-SRC-01/02.

## File thay đổi

- `src/shared/contracts/schemas/search.yaml` — sửa: `EngineDiagnostics.embedCache` (enum `hit | miss`, tuỳ chọn, chỉ `/search`).
- `src/shared/contracts/openapi.yaml` — sửa: `info.version` 1.11.0 → **1.12.0**. `src/backend/app/main.py` — `FastAPI(version="1.12.0")`.
- `src/frontend/src/types/api.gen.ts` — sinh lại (`openapi-typescript@7.13.0`): thêm `embedCache?: "hit" | "miss"`.
- `src/backend/app/application/search/query_cache.py` — thêm: `QueryEmbeddingCache` (LRU `OrderedDict` + `threading.Lock`,
  single-flight bằng `threading.Event`, vector float32 chỉ đọc, counters `hits/misses/coalesced/evictions`, `stats()`),
  `CachingQueryEmbedder` (`EmbedderPort`; `embed_query_status` → (vector, hit|miss); `embed_queries` chỉ câu chưa có,
  dùng `inner.embed_queries` theo lô; `embed_docs` đi thẳng; log `search.embed_cache …` mỗi `log_every` lượt, không log câu).
- `src/backend/app/application/search/use_cases.py` — sửa: `canonical_query` (gộp khoảng trắng) áp cho chuỗi đi embed/BM25;
  `_embed` dùng `embed_query_status` khi có → `diagnostics.embedCache`; `query_text(q)` public cho prewarm.
- `src/backend/app/application/search/prewarm.py` — thêm: `prewarm(search, embedder, queries, batch=96, inputs_per_minute, stop, sleep)`
  → `PrewarmReport`; `read_query_file`.
- `src/backend/app/application/ports/embedder.py` — sửa docstring: hai method tuỳ chọn (`embed_query_status`, `embed_queries`).
- `src/backend/app/application/ports/search_logs.py` — thêm port `SearchLogReader.head_queries(days, limit)`; re-export ở `ports/__init__.py`.
- `src/backend/app/infrastructure/persistence/postgres_search_logs.py` — thêm adapter `PostgresSearchLogReader` (psycopg,
  `DATABASE_URL`; lỗi → `[]` + warning; hôm nay bảng `app.search_logs` chưa có code ghi nên trả rỗng).
- `src/backend/app/infrastructure/embeddings/cohere_embedder.py` — sửa: `embed_queries(texts)` chunk 96 với `search_query`.
- `src/backend/app/core/config.py` — sửa: `search_embed_cache` (True), `search_embed_cache_size` (10000),
  `search_embed_cache_log_every` (500), `search_prewarm` (True), `search_prewarm_file`, `search_prewarm_head_queries` (200),
  `search_prewarm_head_days` (30), `search_prewarm_inputs_per_minute` (2000).
- `src/backend/app/main.py` — sửa: `build_recsys` bọc `CohereEmbedder` bằng `CachingQueryEmbedder` khi bật (object là
  `recsys_embedder` → sống qua reload); `RecsysRefresher(prewarm=)`: sau lần publish đầu `asyncio.create_task(to_thread(prewarm))`,
  lỗi → `search.prewarm.failed` (warning), log `search.prewarm.done …`; `stop()` bật `threading.Event` cho prewarm;
  `wait_prewarm()` (shield + timeout 10 s) gọi trong `lifespan` **trước** `recsys.close()`; log `search.embed_cache` stats sau
  mỗi lần nạp lại; `prewarm_from_settings` đọc file + head query.
- `src/backend/data/search_prewarm_queries.txt` — thêm: 131 câu gold active, header `# gold_v1 e47b0d6a… 2026-09-30`
  (Docker chỉ COPY `src/backend` nên file nằm đây; test đối chiếu gold ở phía evaluation).
- `src/backend/jobs/prewarm_query_cache.py` — thêm: làm nóng backend đang chạy qua `GET /api/v1/search?q=&limit=1`, đếm
  hit/miss/noCache/lỗi; `--dry-run`, `--file`.
- `src/backend/jobs/embed_products.py` — sửa: `--lexical-only` (chỉ PATCH BM25; **từ chối**, mã thoát 2, khi có unit phải
  embed hoặc object mồ côi — chặn `DATABASE_URL` trỏ nhầm xoá vector production); tách `_patch_lexical`.
- Tests thêm/sửa: `tests/unit/application/test_search_embed_cache.py` (12: alias + dạng đầy đủ + khoảng trắng → 1 lượt Cohere,
  không cache → không có trường, top-10 trùng bật/tắt, contract nhận hit/miss và từ chối giá trị lạ, khoá theo tên model, LRU +
  vector chỉ đọc, single-flight `Barrier(8)` → 1 lượt & `coalesced 7`, leader lỗi không kẹt follower, `embed_queries` chỉ câu
  thiếu, fallback không có batch, log stats không lộ câu, passthrough/close); `test_search_prewarm.py` (5); 
  `tests/unit/infrastructure/test_prewarm_query_cache_job.py` (2); `test_cohere_embedder.py` (+1 `embed_queries` search_query
  chunk 96); `test_embed_products_job.py` (+3 lexical-only); `tests/unit/api/test_recsys_refresher.py` (+3 prewarm chạy một lần
  sau publish đầu, lỗi chỉ log, tắt khi settings không bật).
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §2.2 đoạn cache + prewarm; §7.1 dòng "Embed một truy vấn";
  tiêu chí 11 bổ sung hit/miss; §10 thêm S11.
- `src/backend/README.md` — sửa: đoạn Search thêm cache/prewarm/job/`--lexical-only`. `.env.example` — thêm khối `SEARCH_EMBED_CACHE*`,
  `SEARCH_PREWARM*`.

## Quyết định

- **Contract trước code**, tăng minor 1.12.0 (trường tuỳ chọn; `docs/prd/api-contract.md` §3.2). `embedCache` là khoá cấp 1 của
  `EngineDiagnostics` (object mở), không nhét vào `stageMs` (`additionalProperties: false`).
- Khoá cache = `(tên model, "search_query", câu sau chuẩn hoá + gộp khoảng trắng)`; canonical áp **cả vào chuỗi gửi Cohere**
  (một chỗ trong `SearchProducts`) để khoá và input luôn trùng. Không fold hoa/thường/dấu; không dùng `index.model_version`
  (đổi text builder không đổi vector truy vấn).
- Bọc cache quanh **embedder** chứ không quanh `SearchProducts`: `RecsysRefresher` truyền lại `recsys_embedder` mỗi 900 s nên
  cache sống qua reload mà không sửa refresher; test/bench tiêm `FakeEmbedder`/`BenchQueryEmbedder` không bị bọc (không có
  `embed_query_status`) → hành vi cũ, không có trường.
- Single-flight bằng thread (route `/search` sync trong threadpool, agent inprocess dùng `ThreadPoolExecutor`); follower nhận
  "hit" vì request đó không gọi Cohere; leader lỗi → follower tự gọi (không kẹt dây chuyền).
- Prewarm chạy nền sau lần nạp catalog đầu, không chặn startup; pacing tự tính theo câu/phút (không dùng `CallLimiter` của job
  vì runtime search `limiter=None`); shutdown chờ ≤ 10 s. Head query từ `app.search_logs` hôm nay = 0 (bảng chưa có code ghi).
- Job HTTP thay vì ghi thẳng cache: cache nằm trong tiến trình backend, tiến trình khác không chạm được.
- `--lexical-only` là guard cho các lần backfill sau (C6 lần đầu là re-index có chủ đích, chạy job đầy đủ với dry-run trước).

## Kiểm tra

- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py` → PASS.
- `npx --yes openapi-typescript@7.13.0 …` → `api.gen.ts` +5 dòng (`embedCache`).
- `pytest src/backend/tests -q` trong worktree → **928 passed, 21 skipped** (99 s; trước PR2: 902 / 21 — 26 test mới) (kể cả `tests/architecture`: application không import infrastructure).
- Trên nhánh bench: `search_bench/tests/test_prewarm_list.py` chạy với file này → 1 passed (131 câu = gold active `gold_v1`).

## Còn lại / rủi ro

- PR2 → `release-mvp-v2` **sau** PR1 (cùng chạm `use_cases.py`); push khi người dùng bảo. Sau deploy: `sb latency http --label
  cache-on` → hit/miss (C3), `python -m src.backend.jobs.prewarm_query_cache --base-url https://v-ota.duckdns.org` lần hai
  phải `miss 0`.
- Trial Cohere: prewarm 131 câu = 2 lượt gọi; mỗi lần backend khởi động lại (deploy) tốn 2 lượt.
- `app.search_logs` chưa có code ghi → head query luôn rỗng cho tới khi route `/search` ghi log (việc khác, chưa có FR).
