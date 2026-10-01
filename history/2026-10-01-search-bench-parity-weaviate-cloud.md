# Bench: parity Cloud vs local (M4) đạt 20/20 — guard index READY, sửa cổng overlap cho câu ngắn, kết quả

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation (search_bench), docs spec/plan

## Mục tiêu

Lịch 10 ngày Day 2 C "parity cloud vs local 20 câu, overlap ≥ 8/10, top-1 ≥ 18/20" (M4) bằng `sb parity --mode weaviate`
(history `2026-09-30-search-bench-latency-parity-cloud.md`), chạy được sau khi người dùng mở lại tunnel SSH và `.venv-sbench`
có `psycopg`. Phục vụ NFR-PERF-01, FR-SRC-01.

## File thay đổi

- `src/evaluation/search_bench/app_adapter.py` — sửa: `index_status`, `wait_index_ready` (poll `/v1/nodes?output=verbose` tới
  khi shard `READY` và `vectorQueueLength == 0`, timeout 300 s → `AppAdapterError`); `load_collection` gọi sau khi nạp.
- `src/evaluation/search_bench/parity.py` — sửa: `ParityRow.overlap_need` / `overlap_ok` (ngưỡng = min(8, độ dài hai bên); câu
  ngắn phải cùng số kết quả và trùng hết); `verdict` thêm `overlap_min_full`, `n_full`, `need` trong `mismatch`.
- `src/evaluation/search_bench/__main__.py` — sửa: bảng `parity` thêm cột "cần", tô đỏ câu không đạt, tiêu đề nêu số câu đủ dài.
- `src/evaluation/search_bench/tests/test_latency_parity.py` — thêm 2 test: `wait_index_ready` (poll → READY, timeout, collection
  không có), cổng overlap theo độ dài (câu ngắn trùng hết → PASS; lệch câu ngắn / một bên rỗng / 7/10 → FAIL).
- `docs/spec/bench/search-eval-local-spec.md` — sửa: Part 9 quy tắc cổng cho câu ngắn + guard READY và sự cố 01/10.
- `docs/spec/bench/search-eval-results.md` — thêm: §1 bảng parity (PASS), §2–§4 chỗ cho breakdown / hit-miss / recsys Cloud.
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: tick ô parity Day 2 C với số.
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §4.6 p95 theo run cuối (máy đang chạy song song) + ghi chú.

## Quyết định

- **Sự cố lần chạy đầu** (top-1 5/20, overlap min 0): đo rời từng adapter (`near_vector` limit 200 có filter, `bm25` 50 có filter,
  `with_vectors`) cho **cùng tập, cùng điểm, cùng thứ tự** trên Cloud và `ProductVM` → khác biệt chỉ có thể sinh trong lượt
  parity chạy ngay sau khi nạp 3.183 object: thứ tự ứng viên dense sai (đúng tập, thứ tự theo uuid) trong lúc HNSW còn dựng.
  Không tìm thêm bằng chứng trong log Weaviate; xử lý bằng guard READY (rẻ, đúng cho mọi collection nạp lớn) và ghi vào spec.
- Cổng overlap 8/10 "ở mọi câu" là sai cho câu ít kết quả (`out_of_catalog` 0–2 kết quả, tên riêng hiếm 1 kết quả): ngưỡng
  theo độ dài, hai bên phải cùng số kết quả. Không nới cho câu đủ dài.
- Kết luận M4 **PASS**: top-1 20/20; overlap@10 min 8 trên 16 câu đủ dài (13 câu 10/10). Lệch còn lại là nhiễu ANN hfresh vs
  hnsw và BM25 hoà điểm (thứ tự khác giữa phiên bản Weaviate).

## Kiểm tra

- `pytest evaluation/search_bench/tests/test_latency_parity.py` → 11 passed; bộ đầy đủ search bench → **338 passed, 12 skipped**.
- `sb parity --mode weaviate --arm APP.hybrid_norm` (run `20261001-cloud`) lần 3 → **PASS**, `parity-weaviate.json`.

## Còn lại / rủi ro

- Catalog VM tăng liên tục (3.293 → 3.304 unit trong 1 giờ; crawler): số "không vector" tăng cho tới khi chạy index job
  (C6, chờ xác nhận embed ~157+).
- Lượt parity đầu tiên còn để lại bench process treo khi thoát (pipe `| tail` không kết thúc) — chạy với output ra file.
