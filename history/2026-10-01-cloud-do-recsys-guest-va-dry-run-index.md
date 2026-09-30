# Cloud 01/10: p95 `/recommendations` guest path, dry-run index job trên catalog VM, chuẩn bị parity weaviate

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: dang dở (tunnel SSH rớt giữa chừng; `/search` trên VM đang 500; chưa ghi gì lên Weaviate Cloud)
- Phạm vi: docs spec/plan, evaluation (requirements của search bench), số đo

## Mục tiêu

Plan Day 3 (`docs/plan/2026-09-30-plan-day3.md`) C6 (đồng bộ index Cloud từ DB VM), C4 (parity), C7 (p95 recsys Cloud) sau khi
người dùng mở tunnel SSH tới Postgres VM và mở PR1/PR2. Phục vụ NFR-PERF-01, M4 lịch 10 ngày.

## File thay đổi

- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: ô Day 2 C "p95 /recommendations trên cloud" điền số guest path.
- `docs/spec/bench/recsys-offline-eval.md` — sửa: thêm §4.5 (bảng guest path + ghi chú không phải 60 khách + hiện tượng `/search` 500).
- `src/evaluation/search_bench/requirements.txt` — sửa: thêm `psycopg[binary]>=3.2,<4` (cùng pin backend) cho `sb parity --mode weaviate`
  (dùng `PostgresCatalogReader` của backend đọc catalog VM); đã `pip install` vào `.venv-sbench`.

## Số đo và phát hiện (không ghi gì lên Cloud)

- **DB VM** (`127.0.0.1:15432/vota` qua tunnel, chỉ đọc): 13.414 products, **3.293 search unit** (hotel 2.361, attraction 642, combo 171,
  flight 113, golf 6), 2.404 recommendable, combo_items 417, events 7.131, profiles 2.000, `available_from` 2026-09-30 → loader đã chạy
  lại `--as-of 2026-09-30`; `app.search_logs` 0 dòng. Khác số 30/09 (3.008 unit): catalog VM tăng.
- **Weaviate Cloud `Product`** (chỉ đọc): 3.183 object, **3.183/3.183 đã có property BM25** (`lexical=True`), stopwords preset đã
  `none`, hfresh/cosine, uuid tất định 3.183/3.183, modelVersion đồng nhất `embed-multilingual-v3.0:catalog-text-v2`. Schema lưu
  ngoài repo (scratchpad). → Bước "backfill BM25" của C6 **không còn cần**; PUT stopwords cũng không cần.
- **Dry-run `embed_products`** (worktree `feat/search-embed-cache`, `DATABASE_URL` = tunnel VM, Weaviate Cloud): `searchUnits 3293 ·
  unchanged 3136 · embedded 157 · deletedOrphans 0 · missingLexical 0` → ghi thật chỉ embed 157 unit mới/đổi text (~2 lượt Cohere), không
  xoá gì. Chờ người dùng xác nhận trước khi chạy ghi (quy tắc plan C6).
- **`/recommendations` Cloud guest path**: server p50 9 / p95 10 ms, client 141 / 391 ms (§4.5 spec recsys).
- **`/search` Cloud**: treo rồi **500 sau ~64 s** (= chuỗi backoff Cohere 2+4+8+16+32 s, 6 lần), thân "Internal Server Error";
  `/similar` 1,5 s và `/recommendations`, `/products` bình thường; khoá Cohere trong `.env` local vẫn 200 → lỗi ở bước embed trên VM
  (khoá khác / egress), cần ops xem log container. C5 (`sb latency http`) chưa đo được.
- **Parity weaviate** chưa chạy được: lần 1 thiếu `psycopg` trong `.venv-sbench` (đã thêm), lần 2 tunnel SSH đã rớt (cổng 15432 không
  còn lắng nghe).

## Quyết định

- Không ghi lên Cloud khi chưa có xác nhận số dry-run; không PUT schema vì stopwords đã `none`.
- Mật khẩu SSH/DB chỉ đặt qua biến môi trường trong shell (file tạm ngoài repo, xoá sau C6); mọi log chỉ in `host:port/db`.

## Kiểm tra

- Dry-run không gọi Cohere, không ghi Weaviate (chỉ `ensure_collection` no-op vì property đã đủ).
- `pytest evaluation/search_bench/tests` không đổi (chỉ thêm dependency).

## Còn lại / rủi ro

- Người dùng: mở lại tunnel (thêm `-o ServerAliveInterval=30`), xác nhận "embed 157 / xoá 0", cho ops kiểm `/search` 500 trên VM,
  cho biết PR1 đã merge chưa.
- Sau đó: chạy ghi index (157), `sb parity --mode weaviate --arm APP.hybrid_norm` (cần `--recreate` nếu ProductVM đã nạp), `sb latency http --label cache-off`.
