# Bench: `sb latency http`, `sb parity` (Cloud vs local) và `recsys_bench http-latency`

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành (công cụ + test; số đo trên Cloud chờ PR stage-timing deploy và tunnel VM — xem "Còn lại")
- Phạm vi: evaluation (search_bench, recsys_bench), docs spec bench, `.env.example`

## Mục tiêu

Lịch 10 ngày Day 2 phần C (`docs/plan/2026-09-28-lich-10-ngay-3-engine.md`): parity Cloud vs local trên 20 câu cố định
(cổng M4), latency breakdown `/search` trên Cloud 50 câu × 3 lượt theo `diagnostics.stageMs`, p95 `/recommendations`
trên Cloud. Plan chốt 30/09 (`docs/plan/2026-09-30-plan-day3.md`, kế hoạch C4/C5/C7): viết công cụ đo trước, chạy khi
Cloud có `stageMs` (PR `feat/search-stage-timing-v2`, contract 1.11.0) và property BM25 (backfill C6). Phục vụ NFR-PERF-01/03,
FR-SRC-01/02.

## File thay đổi

- `docs/spec/bench/search-eval-local-spec.md` — sửa: §1.3 dòng Part 9 thêm `sb latency http`, `sb parity`; Part 9 viết lại
  bảng: ba lệnh mới (đã làm) + ba lệnh cũ `embed`/`e2e`/`load` ghi rõ *chưa làm*; định dạng `latency[-label].json`,
  `parity-<mode>.json`; cổng parity; biến `SBENCH_CLOUD_*`, `SBENCH_VM_DATABASE_URL` (spec trước code).
- `src/evaluation/search_bench/config/sbench.yaml` — sửa: `latency.http` (queries, runs 3, drop_first, limit 10, timeout 30 s,
  percentiles) và `latency.parity` (queries, k 10, top1_min 18, overlap_min 8, `vm_collection: ProductVM`).
- `src/evaluation/search_bench/config/latency_queries.yaml` — thêm: 25 câu `prewarmed` (gold active, trải 13 slice) + 25 câu
  `cold` (ngoài gold).
- `src/evaluation/search_bench/config/parity_queries.yaml` — thêm: 20 câu (13 slice × ≥ 1 + "VinWonders", "KS biển tại NT",
  "Vinpeal Resort Nha Trang giá tốt").
- `src/evaluation/search_bench/latency.py` — thêm: `load_queries`, `canonical` (gộp khoảng trắng = khoá cache backend),
  `measure` (GET `/api/v1/search` tuần tự, mỗi mẫu `client_ms` / `latencyMs` / `stageMs` / `embedCache` / `searchMode` / top-10),
  `summarize` (p50/p95 theo nhóm và stage, bỏ lượt 1 khi `drop_first`, tách hit/miss — miss = lần gặp đầu của câu,
  `top10_stable`), `write_latency`.
- `src/evaluation/search_bench/parity.py` — thêm: `load_parity_queries`, `ParityRow` (top-1, overlap@k; hai bên rỗng = trùng),
  `verdict` (cổng + danh sách câu lệch), `parity_http` (A/B qua HTTP), `parity_engines` (hai `AppSearch`), `write_parity`.
- `src/evaluation/search_bench/app_adapter.py` — sửa: tách `load_collection(cfg, cat, ids, vecs, collection, drop_first)` dùng
  chung cho `ProductBench` (vector B0) và `ProductVM`; thêm `build_vm_catalog(database_url)` (`PostgresCatalogReader` thật →
  `UnitIndex` + text như production), `fetch_cloud_vectors` (`WeaviateClient.fetch(include_vectors=True)`), `parity_contexts`
  (A = collection Cloud đọc trực tiếp, B = `ProductVM` trên Weaviate bench nạp từ vector Cloud; thống kê object Cloud / unit VM
  có–không vector / mồ côi / thiếu BM25 / text cũ); `AppContext` nhận `weaviate_url`, `api_key`, `grpc_port` (None → bench).
- `src/evaluation/search_bench/__main__.py` — sửa: nhóm lệnh `latency` (`http`), lệnh `parity` (`--mode http|weaviate`, tuỳ chọn
  đọc `SBENCH_CLOUD_BASE_URL` / `SBENCH_LOCAL_BASE_URL` / `SBENCH_CLOUD_WEAVIATE_URL` / `SBENCH_CLOUD_WEAVIATE_API_KEY` /
  `SBENCH_VM_DATABASE_URL`); DSN chỉ in `host:port/db`.
- `src/evaluation/search_bench/tests/test_latency_parity.py` — thêm: 9 test (bộ câu ⊂ / ∩ gold, phủ 13 slice và 3 câu bắt buộc,
  đo qua `httpx.MockTransport` với server giả miss→hit, tóm tắt drop_first / by_cache / top10_stable, CLI ghi file, parity http
  + verdict + câu lệch, `parity_engines` ghi lỗi, ngữ nghĩa top-1).
- `src/evaluation/recsys_bench/http_latency.py` — thêm: `measure` guest path (`GET /api/v1/recommendations?k=`, không cookie,
  lặp k GET mỗi lượt) hoặc users path (`/internal/recommendations` + `X-Service-Token` từ biến môi trường, không in),
  `summarize`, `write`.
- `src/evaluation/recsys_bench/__main__.py` — sửa: lệnh `http-latency`; docstring module thêm ví dụ.
- `src/evaluation/recsys_bench/tests/test_http_latency.py` — thêm: 4 test (guest lặp k GET, users cần token ≥ 32 ký tự và ghi
  lỗi 500, users rỗng, CLI).
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §1 thêm lệnh `http-latency` và ghi chú guest path; §7 ghi rõ số Cloud chỉ là
  guest path cho tới khi ops mở IAP.
- `.env.example` — sửa: khối sbench thêm 5 biến `SBENCH_CLOUD_BASE_URL`, `SBENCH_LOCAL_BASE_URL`, `SBENCH_CLOUD_WEAVIATE_URL`,
  `SBENCH_CLOUD_WEAVIATE_API_KEY`, `SBENCH_VM_DATABASE_URL` (chú thích: DSN tunnel chỉ đặt trong shell).

## Quyết định

- **Số đầu bảng là số server** (`diagnostics.latencyMs`, `stageMs`); wall phía client báo riêng vì gồm RTT tới VM qua BFF.
  `drop_first` bỏ lượt 1 khỏi p50/p95 nhưng lượt 1 vẫn là nguồn mẫu **miss** (sau contract 1.12.0 `embedCache`): miss chỉ tính ở
  lần gặp đầu của mỗi câu, hit tính mọi lượt còn lại.
- Hai nhóm câu cố định trong config (spec §1.5: mọi con số vào config): `prewarmed` phải ⊂ gold active (test kiểm) để sau PR
  prewarm lượt 1 đã là hit; `cold` phải ∩ gold = ∅ để lượt 1 chắc chắn miss.
- Parity mode `weaviate` là cổng M4 đúng nghĩa: cùng `SearchProducts`, cùng catalog VM, cùng vector (kéo từ Cloud, 0 Cohere),
  chỉ khác Weaviate (Cloud vs bench 1.37.3, hnsw). Mode `http` chỉ chẩn đoán deployment vì catalog local ≠ catalog VM.
  Ba câu bắt buộc theo lịch 10 ngày; "Vinpeal" lấy nguyên câu gold c0456. Hai bên cùng rỗng (`out_of_catalog`) tính là top-1 trùng.
- `/recommendations` trên Cloud chỉ đo **guest path** (quyết định người dùng 30/09): `/internal/recommendations` cần
  `X-Service-Token` + `INTERNAL_API_ENABLED`, BFF không chuyển header. Nhánh `--users` viết sẵn cho khi ops mở IAP; token chỉ
  qua biến môi trường.
- Không sửa `runner.py`/`metrics.py`; `load_collection` tách từ `load_product_bench` giữ nguyên hành vi (test integration cũ
  không đổi).

## Kiểm tra

- `cd src && PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 ../.venv-sbench/Scripts/python -m pytest evaluation/search_bench/tests -q`
  → **336 passed, 11 skipped** (trước: 327 / 11; 9 test mới).
- `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q src/evaluation/recsys_bench/tests` → **35 passed** (trước 31; 4 test mới).
- Chưa chạy trên Cloud: `stageMs` chưa deploy (PR1 `feat/search-stage-timing-v2` mới commit local `391a00f`, chưa push), Cloud
  chưa có property BM25 (C6 cần tunnel VM).

## Còn lại / rủi ro

- Sau khi PR1 merge + CI deploy: `sb latency http --base-url https://v-ota.duckdns.org --label cache-off` (số "cache off" + top-10
  tham chiếu) → điền bảng Stage của lịch 10 ngày Day 2 C; sau PR2 (cache) chạy lại `--label cache-on` → hit/miss (C3).
- Sau C6 (backfill BM25 từ DB VM): `sb parity --mode weaviate` với `SBENCH_VM_DATABASE_URL` (tunnel), `SBENCH_CLOUD_WEAVIATE_*`
  → điền "overlap ____ / top-1 ____". Trước C6 chỉ so được dense (`--arm APP.dense`).
- `python -m src.evaluation.recsys_bench http-latency --base-url https://v-ota.duckdns.org` → điền "Cloud: p50 ____ / p95 ____"
  kèm chú thích guest path.
- `sb latency embed|e2e|load` (Part 9 gốc) vẫn chưa làm — spec ghi rõ.
