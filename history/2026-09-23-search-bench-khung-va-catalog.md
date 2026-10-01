# sbench ngày 1 (Người B) — khung, compose Weaviate, doctor, catalog + vocab

- Ngày: 2026-09-23
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Ngày 1, vai Người B trong `docs/spec/bench/search-eval-checklist.md`: Weaviate chạy + `sb doctor` xanh, và Part 1 (catalog → `items.parquet`, `sb catalog vocab`) để Người A xuất danh sách điểm đến / tên / amenity cho draft gold ngay trong ngày. Commit này là mốc giữa ngày (Part 0–1) và được push để A kéo về; Part 2–4 (text `T3+R`, embed Cohere + cache, collection Weaviate, `sb query`) ở commit sau.

Phục vụ FR-SRC-02 (Cohere v3 1024 chiều, chỉ search unit), FR-SRC-01/03 (BM25, trường lọc), NFR-SEC-01 (key không vào log/commit); độ đo theo `docs/prd/test-plan.md` §2.5.

## File thay đổi

- `src/evaluation/search_bench/__init__.py`, `__main__.py` — thêm: CLI typer `sb` (`doctor`, `catalog build|vocab`, `cost`), tuỳ chọn chung `--run-id --config --dataset -v`.
- `src/evaluation/search_bench/config.py` — thêm: pydantic cho `run, catalog, text, embedding, weaviate, doctor` (chặt), các mục Part sau để mở; nạp `.env` gốc repo theo danh sách cho phép.
- `src/evaluation/search_bench/config/sbench.yaml` — thêm: toàn bộ §1.2 của spec (đã sửa ở `2026-09-23-spec-search-bench.md`) + `catalog.fake_n` (đề xuất).
- `src/evaluation/search_bench/paths.py` — thêm: `SBENCH_HOME`, `data_dir(dataset)` (`data/`, `data/_sample/`, `data/_fake/`), `cache_dir()` chung.
- `src/evaluation/search_bench/logsetup.py` — thêm: structlog; hạ log httpx; tắt cảnh báo deprecation của authlib.
- `src/evaluation/search_bench/costlog.py` — thêm: ghi/tổng hợp `cache/cost.jsonl`.
- `src/evaluation/search_bench/doctor.py` — thêm: Part 0.
- `src/evaluation/search_bench/docker/compose.yml` — thêm: Weaviate 1.37.3, project `sbench`, `127.0.0.1:58080/55051`.
- `src/evaluation/search_bench/amenities.py` — thêm: bọc `vector_bench` `AmenityMatcher` + bước trigram kiểu pg_trgm; so id cũ/mới.
- `src/evaluation/search_bench/catalog.py` — thêm: Part 1 (`build_catalog`, `build_vocab_file`, `reload_records` có kiểm sha).
- `src/evaluation/search_bench/requirements.txt`, `requirements-extra.txt` — thêm.
- `src/evaluation/search_bench/tests/{__init__,conftest,test_config,test_amenities,test_catalog,test_doctor}.py` — thêm: 43 unit test.
- `history/2026-09-23-search-bench-khung-va-catalog.md` — thêm: entry này.

## Quyết định

- **Dùng lại vbench, không chép** (spec §1.1): `vector_bench.paths.repo_root/resolve_repo_path`, `config.read_env_file`, `lexical.fold`, `dataset.amenities` (`AmenityMatcher`, `build_vocab`, `load_seed`, seed yaml), `dataset.catalog.variant_of/read_jsonl`, `dataset.fake.generate_products`, `results.dump_json/sha256_file`. Bung snapshot bằng `data_collection.seed.snapshot.materialize_snapshot` (kiểm checksum manifest).
- **Search unit theo `variant`** (như `catalog.product_meta`), không theo `taxonomy`: snapshot 2026-09-21 cho 2.897 unit (quy tắc cũ của spec bỏ sót 111 tuyến bay).
- **Trigram thay rapidfuzz** cho bước fuzzy amenity; mọi lần khớp ghi `amenity_fuzzy_hits.csv`. Chặn build khi id amenity của khoá cũ bị đổi (`--allow-id-drift` để chấp nhận) — filter trong gold ghi khoá, không ghi id.
- **Dataset tách thư mục**: `--dataset sample|fake` ghi `data/_sample/`, `data/_fake/`, không đè catalog thật; cache + `cost.jsonl` dùng chung.
- `ticketed`: snapshot không có `ticketed: false`; điểm tham quan có `unitPrice = null` được suy `ticketed = false` theo `docs/spec/data-collection/schema.md` §2 (đếm ở `stats.ticketed_inferred_false`).
- `unit_price_min` = min giá không null của unit và con (vbench bỏ giá của chính property khi có phòng — spec ghi min của cả hai).
- `review_score` quy về thang 10 (`reviewScore/reviewScoreScale`, fallback `rating/ratingScale`).
- Venv riêng `.venv-sbench` (Python 3.13, venv tự có `.gitignore`); `weaviate-client 4.23.1`, `cohere 5.21.1`.
- `sb doctor` gọi `tokenize(offline=False)` một lượt để kiểm key (mặc định của SDK đếm offline nên không kiểm được key), ghi `cost.jsonl`; `--skip-api` bỏ bước này.

## Kiểm tra

- `PYTHONUTF8=1 ../.venv-sbench/Scripts/python -m pytest evaluation/search_bench/tests` (từ `src/`): **43 passed**.
- `docker compose -f evaluation/search_bench/docker/compose.yml up -d --wait weaviate`: `sbench-weaviate-1` healthy, `semitechnologies/weaviate:1.37.3`, `127.0.0.1:58080->8080`, `127.0.0.1:55051->50051`.
- `sb doctor`: exit 0 — ✔ docker 29.7.2 · ✔ weaviate 1.37.3 · ✔ gRPC · ✔ ascii_fold analyzer · ✔ COHERE_API_KEY (tokenize "xin chào" = 2 token) · ✔ products.jsonl 10.320 dòng · ✔ sample 50 dòng · ! bge-m3 (sentence-transformers chưa cài, chỉ cần cho E2/P5) · ✔ disk · · chưa có tag gold.
- `sb catalog build --source jsonl` (9,5 s): 2.897 search unit / 10.320 bản ghi — hotel_property 2.116, attraction 571, flight_route 111, combo 93, golf 6; con mồ côi 0; 35 điểm đến; description derived 17,8%; amenity phủ 72,8%, id seed 23 + raw 482, khớp trigram 6, raw bỏ 1.061.
- `sb catalog vocab`: 35 điểm đến · 2.897 sản phẩm · 505 amenity · 1.909 hạng phòng · 5 hãng bay · 19 mã IATA.
- 6 khớp trigram trên snapshot: `dich vu giat la` → laundry (439 lần), `dich vu ui do` → laundry (339), `khong co khu vuc hut thuoc…` → non_smoking (99), `le tan 24 7` → front_desk_24h (13) — đúng; `bai bien` → private_beach (28), `phong tam` → fitness (1) — **sai / đáng ngờ**.
- `pytest src/evaluation/vector_bench/tests` vẫn 60 passed, 3 skipped (ở commit merge).

## Còn lại / rủi ro

- **Người A**: soát `bench_out/search/data/amenity_fuzzy_hits.csv` (2 khớp sai ở trên). Ngưỡng 0,6 là của spec (§1.7) — muốn đổi thì A/mentor quyết; hoặc thêm alias vào `vector_bench/config/amenity_seed.yaml`.
- **Người A**: `bench_out/` không commit — sau khi pull, chạy `sb catalog build --source jsonl && sb catalog vocab` để có `vocab.json`; filter JSON ghi khoá amenity (`filter_fields.amenity_keys`).
- `nights` luôn null trên snapshot hiện tại (loader chưa gán); `ticketed = false` chỉ có dạng suy từ giá null.
- Cảnh báo `AuthlibDeprecationWarning` còn hiện một lần trong pytest (authlib tự đặt filter "always" khi được import giữa test) — không ảnh hưởng kết quả.
- Việc tiếp theo trong ngày (commit sau): Part 2 (`T3+R` = `build_text` backend, `sb text`, bộ đếm token offline), Part 3 (Cohere + cache + pacer + `sb embed`), Part 4 (collection, load, dense/bm25, `sb query --arm B0`), chạy thử 26 unit mẫu với Cohere thật.
