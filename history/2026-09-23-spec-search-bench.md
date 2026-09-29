# Spec benchmark embedding + search: đổi tên, đối chiếu repo, p95 theo PRD

- Ngày: 2026-09-23
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Ba tài liệu của benchmark embedding + search (Weaviate + Cohere) vào repo ở commit `e8381d6` (chưa có entry lịch sử — entry này ghi cho cả lần thêm đó). Trước khi code ngày 1 (Người B), đối chiếu tài liệu với repo và sửa **chỉ những chỗ sai sự thật**, theo quyết định của người dùng; thêm chỉnh p95 theo PRD.

## File thay đổi

- `docs/spec/bench/SEARCH_EVAL_LOCAL_SPEC.md` → `docs/spec/bench/search-eval-local-spec.md` — đổi tên + sửa:
  - dòng "Phục vụ" (FR-SRC-01/02/03, NFR-PERF-01/03; test-plan §2.5) và khối "Đối chiếu repo": ba tài liệu nguồn không có trong repo, tên thật của `SCHEMA.md`, `VECTOR_DB_BENCH_SPEC.md`, `ARCHITECTURE.md`; index `flat` và collection nhiều property chỉ dùng trong bench.
  - §1.1: `build_embed_text` → `build_text` (`src/backend/app/domain/catalog/text_builder.py`); module vbench thật (`dataset/amenities.py`, không có `gold.py`); amenity seed dùng chung với vbench; thư mục `data/_sample/`, `data/_fake/`; `cache/` chung; `gold/GUIDE.md` → `docs/spec/bench/gold-guide.md`, `CHANGELOG.md` → `changelog.yaml`, prompt `.txt`.
  - §1.2: `products_path` + `snapshot_path` (đường dẫn cũ không tồn tại); `search_unit_taxonomies` → `search_unit_variants`; `amenity_seed_path`, `amenity_fuzzy_min`; Weaviate `127.0.0.1:58080/55051`; `max_inputs_per_min`, `load_batch_size`, mục `doctor` (ghi *đề xuất*); `p95_cache_miss_ms_max` 300 → **250**; `watch_paths` trỏ snapshot.
  - §1.4, Part 10: thêm `weaviate_p99` và cột "p99 cache-miss" (chỉ báo cáo, không ngưỡng); quy tắc chọn 1 dùng 250 ms.
  - §1.6: `weaviate-client>=4.23`, `tokenizers`; tách `requirements-extra.txt`.
  - Part 0: compose `name: sbench`, cổng loopback 58080/55051, `CLUSTER_HOSTNAME`; `doctor` kiểm ascii_fold, cổng, tag gold chỉ thông tin.
  - Part 1: quy tắc search unit theo `variant`; tự bung snapshot; trigram kiểu pg_trgm thay `rapidfuzz`; khoá amenity trong filter + chặn đổi id; `filter_fields`; sample = 26 search unit, jsonl = 2.897.
  - Part 2: `sb tokens` đếm offline, không fallback API.
  - Part 3: file `vec_<V>_<M>.ids.json` / `.meta.json`; khoá cache `@int8`/`@d<dim>`/`@noit`; pacer.
  - Part 4: tên collection logic ↔ vật lý (Weaviate cấm `+`); property `field` không searchable; `load` so với số id; test fold dùng "da nang".
  - Part 11: changelog dạng `gold/changelog.yaml`.
- `docs/spec/bench/SEARCH_EVAL_CHECKLIST.md` → `docs/spec/bench/search-eval-checklist.md` — đổi tên + sửa: dòng "Phục vụ"; đường dẫn catalog; nhánh `bench/embed-search`; `gold/prompts/draft.txt`; filter ghi khoá amenity; lệnh compose; mẫu = 26 search unit và cờ `--dataset sample`; `gold-guide.md`.
- `docs/spec/bench/ARMS.md` → `docs/spec/bench/arms.md` — đổi tên + sửa: dòng "Phục vụ"; B0 "`embed_text` T4" → `T3+R`; S8 "p95 < 300 ms" → "≤ 250 ms (NFR-PERF-01)".
- `history/2026-09-23-spec-search-bench.md` — thêm: entry này.

## Quyết định

- Người dùng chốt (23/09): sửa tối thiểu phần sai sự thật; guard p95 theo PRD NFR-PERF-01 (**250 ms**) thay 300 ms, và **thêm p99** vào metric (chỉ báo cáo — PRD không đặt ngưỡng p99, không tự đặt); đổi tên file theo `AGENTS.md` §7 (chữ thường, gạch nối — tiền lệ `2026-09-23-chuyen-tai-lieu-vao-docs-spec.md` đổi `SCHEMA.md` → `schema.md`).
- Trigram thay `rapidfuzz`: kiểm trên snapshot, ratio > 0,6 map sai 141 chuỗi amenity (`ban công → bữa sáng`, `phòng tắm riêng → phòng gia đình`…); trigram Jaccard > 0,6 chỉ khớp vài chuỗi. Ngưỡng 0,6 giữ nguyên (spec §1.7).
- Cổng Weaviate 58080/55051: `docker-compose.yml` gốc giữ 8080/50051 cho Weaviate 1.27 của app; bench cần ≥ 1.37 (`text_analyzer`).
- Không đổi: quota slice, ngưỡng metric khác, danh sách arm, quy tắc chọn.

## Kiểm tra

- `grep -n "SEARCH_EVAL\|ARMS\.md" docs/spec/bench/*.md`: không còn tên cũ.
- `git ls-files --eol docs/spec/bench`: giữ LF, diff chỉ ở dòng sửa.
- `weaviate-client 4.23.1`: có `Configure.text_analyzer(ascii_fold=…)`, `Configure.Vectors.self_provided` (kiểm bằng `inspect` trong `.venv-sbench`).

## Còn lại / rủi ro

- Hợp đồng Search (`docs/spec/hop-dong-tich-hop-backend.md` §5.3 mục 9) vẫn ghi p95 300 ms, lệch PRD 250 ms — PRD thắng; chưa sửa hợp đồng.
- `docs/prd/test-plan.md` §2.5 có Recall@5; spec chỉ có Recall@10 — việc của Người A (metrics, ngày 2).
- S3 lọc cứng `star_rating` trong khi hợp đồng Search §2.5 coi `starRatingMin` là soft filter — cần Người A / mentor xem trước ngày 7.
- Đưa luồng thắng vào backend (ngày 8: property giàu, flat vs HNSW, Weaviate ≥ 1.37 vs 1.27 ở compose gốc) cần đề xuất ở `docs/prd/update/`.
