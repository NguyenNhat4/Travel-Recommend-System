# Search bench Part 8: `runner.py`, `sb run --arm`, `sb compare`, zero-result theo slice

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Kế hoạch 3 ngày (30/09 → 02/10), mục P2: có runner để chạy arm trên gold và so hai arm — điều kiện để có số search
(M2) ngay khi `gold_v1` được tag sáng 01/10. Trước đó `metrics.py` đã đủ metric nhưng chưa có gì sinh `per_query` từ
một arm (history `2026-09-24-search-bench-metrics-bootstrap.md`). Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5.

## File thay đổi

- `src/evaluation/search_bench/runner.py` — thêm: `RunEnv` + `load_env` (gold, items, amenity key index; version gold theo
  tag qua `holes.gold_version_of`, gold ngoài `gold/` → `fixture:<sha8>`, gold chưa tag → từ chối trừ `allow_untagged`),
  `new_run_id` (`<YYYYMMDD-HHMM>-<git sha>`), `config_hash` (sha1 các trường hành vi của arm, bỏ id / stage /
  description / parent), `retrieve` (embed cả lô câu qua cache; `dense` có `cutoff.max_vector_distance`, filter gold khi
  `filters.qu`; `bm25`; `hybrid` / preproc / rerank / csls / dedupe báo chưa cài), `score_arm`, `judged_gate`
  (NEEDS_LABELS theo `gold.judged_at_10_min` / `judged_at_10_slice_min`), `build_results` / `write_arm` / `read_results`
  / `read_rows` (`results.json` + `per_query.parquet`, luôn giữ `top_ids`), `vs_parent_of`, `compare`, `latest_run_id`.
- `src/evaluation/search_bench/metrics.py` — sửa: `aggregate.by_slice` thêm `zero_result` và `constraint_precision`
  (M2 cần zero-result theo slice; `judged@k` đã có trong rank metrics).
- `src/evaluation/search_bench/__main__.py` — sửa: thêm `sb run --arm … [--gold] [--allow-untagged] [--model] [--force]`
  (bỏ qua arm đã có kết quả cùng hash + gold_version trong run; in bảng theo slice, NEEDS_LABELS, vs_parent) và
  `sb compare A B` (`--run-id` hoặc run mới nhất; từ chối khác gold_version; bảng overall + slice + kết luận win_rule).
- `src/evaluation/search_bench/tests/test_runner.py` — thêm: 10 test với store / embedder giả (top-10 của arm A trong
  `run_small.json` → số trùng `test_aggregate_arm_a`; đọc lại parquet giữ `top_ids`; so với chính nó Δ = 0, p = 0,5;
  cutoff và filter; bm25; gold trong `gold/` phải có tag; hash bỏ id; CLI run / compare / bỏ qua khi trùng hash).
- `src/evaluation/search_bench/tests/test_metrics.py` — sửa: kiểm `zero_result` / `constraint_precision` theo slice.
- `docs/spec/bench/search-eval-local-spec.md` — sửa: §1.3 dòng Part 8 (tuỳ chọn của `run`), §1.4 (trường thêm trong
  `results.json`, cột thêm trong `per_query.parquet`, `by_slice` có `zero_result`, `constraint_precision`).

## Quyết định

- **`resolved_config_hash` chỉ tính trên trường hành vi** (text_variant, model, retrieval, filters, cutoff…), không tính
  id / stage / description / parent — để arm trùng cấu hình (S0 = B0 sau khi bỏ qua chuỗi E) dùng lại được kết quả.
- **Gold chưa tag:** `sb run` từ chối theo spec §1.5; `--allow-untagged` chỉ để chạy thử, kết quả ghi `gold_version: null`
  và in cảnh báo; gold ngoài `gold/` (fixture) ghi `fixture:<sha8>` để test và smoke không cần tag.
- **`--model` ghi đè** (vd `fake`) tạo arm hiệu lực; hash và `results.json` theo arm hiệu lực (lỗi phát hiện bởi test:
  hash so với arm gốc thì không bao giờ "bỏ qua" được).
- **`applied_filter` và `latency_ms` ghi vào per_query** để `rescore` (P4) tính lại `filter_recall_loss` và giữ latency.
- `cost_usd.embed_docs` để `null`: chi phí embed catalog đã nằm trong `cost.jsonl` (`sb cost`), không gán lại cho từng
  arm. `hub_score_max` để `null` cho tới khi có nguồn 500 câu (P7).
- `vs_parent` chỉ tính khi `parent` là id arm (không phải `@`) và arm cha đã chạy trong cùng run, cùng gold_version.

## Kiểm tra

- `pytest evaluation/search_bench/tests -q -p no:cacheprovider`: **307 passed, 10 skipped** (trước P1: 282).
- Smoke thật (Weaviate bench + Cohere, `--run-id smoke-fixture`): `sb run --arm B0 --gold tests/fixtures/gold_small.jsonl`
  trên collection `products__T3+R__cohere_v3` (3.183 item): chạy hết 10 câu, 8 câu embed mới / 2 từ cache, weaviate
  p50 12 ms · p95 67 ms, in bảng và cờ NEEDS_LABELS (đúng: fixture gán trên catalog mẫu 26 unit nên judged@10 = 0,04);
  `sb compare B0 B0` → TIE, Δ = +0,00, p = 0,500. Collection `sample` bị `check_ready` chặn vì dựng từ text builder cũ
  (đúng thiết kế; smoke đổi sang jsonl).

## Còn lại / rủi ro

- `hybrid`, `dense+query_vec`, query_preproc, rerank, csls, dedupe chưa cài trong runner (P5 adapter production, P7).
- `run --stage`, promote, `arms check` (Part 12) chưa có — số tuần này đọc từ `sb run --arm` + `sb compare`.
- Khi `gold_v1` được tag: chạy `sb run --arm B0` thật và kiểm 122 câu không filter có top-10 trùng `rank_dense` 1..10
  của `pool.csv` (kế hoạch mục 6).
