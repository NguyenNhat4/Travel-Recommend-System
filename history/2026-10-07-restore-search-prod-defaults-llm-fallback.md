# Khôi phục mặc định production của /search và wiring LLM fallback bị merge `21d72ae` làm mất

- Ngày: 2026-10-07
- Tác giả: tqanh123 (người dùng chốt) / Claude (Fable 5.1)
- Nhánh: fix/search-production
- Trạng thái: hoàn thành
- Phạm vi: backend, docs

## Mục tiêu

Khi review luồng search (đề xuất `docs/spec/bench/tong-hop-chinh-sua-luong-search-ota.md`), phát hiện merge `21d72ae` ("merge code",
07/10) đã đưa `core/config.py` và `main.py` về trạng thái trước commit `1eb7624` (06/10, entry
`history/2026-10-06-search-e5-production-f12356-llm-fallback.md`): mặc định production F1/F3/F5/F6 lật về tắt, câu không dấu về
`off`, mất 7 setting `search_llm_fallback*` (nên `SEARCH_LLM_FALLBACK*` trong `.env.example` không có tác dụng — `Settings` có
`extra="ignore"`), mất `main.search_hypothesizer` và 4 kwargs truyền vào `SearchProducts`; PRD mất đoạn "Hiểu câu truy vấn (query
plan)" ở `architecture.md` §5 (đề xuất đã chốt 06/10) và dòng `SEARCH_LLM_FALLBACK*` ở `deployment-plan.md` §2. Người dùng chốt
07/10: khôi phục **trước** khi làm F7 / POI / entity (cùng chạm các file này). Phục vụ FR-SRC-01, FR-SRC-03, NFR-PERF-01.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: `search_no_diacritics_cutoff` vào `_OPTIONAL_BLANK_IS_NONE`; mặc định
  `search_dest_filter` / `search_negation_filter` / `search_route_filter` / `search_numeric_filter` = True (F4 giữ False),
  `search_no_diacritics_mode = "relax"`, `search_no_diacritics_cutoff = 0.80`; thêm lại khối `search_llm_fallback*` (off, 0,75,
  1.500 ms, gpt-4o-mini, cache 10.000, cache_path "", cache_only False).
- `src/backend/app/main.py` — sửa: thêm lại `_SEARCH_HYPOTHESIZERS` + `search_hypothesizer(settings)`; `build_recsys` truyền
  `llm_fallback`, `llm_min_confidence`, `llm_timeout_ms`, `hypothesizer` vào `SearchProducts`.
- `docs/prd/architecture.md` — sửa: cạnh `HybridSearch -.-> LLM` trong sơ đồ; §5 mục 5 thêm lại đoạn "Hiểu câu truy vấn (query
  plan)" và chữ "câu đã chuẩn hoá" ở mục Truy vấn.
- `docs/prd/deployment-plan.md` — sửa: dòng `SEARCH_CUTOFF` ghi thêm `SEARCH_NO_DIACRITICS_CUTOFF` 0,80; thêm lại dòng
  `SEARCH_LLM_FALLBACK*`.
- `src/backend/tests/unit/api/test_search_settings_wiring.py` — sửa: thêm `test_production_defaults_restored`.

## Quyết định

- Chỉ khôi phục đúng các hunk bị mất; **không** khôi phục khối Cohere / `EMBED_PROVIDER` / `PROVIDER_DEFAULTS` — HEAD bỏ có chủ
  đích theo `docs/prd/update-archive/2026-10-06-bo-duong-lui-cohere.md`; giữ `vector_collection = ProductE5Small`
  (`history/2026-10-06-vector-collection-dung-san-truoc-deploy.md`).
- Đoạn query plan ở PRD §5 khôi phục nguyên văn đề xuất đã chốt 06/10, **thêm một cụm** "và bảng địa danh / điểm vui chơi giữ trong
  repo (`domain/search/gazetteer.py`…)" để mô tả gazetteer POI sắp làm (plan `docs/plan/2026-10-07-search-duration-entity-poi.md`).
  Cụm này chỉ diễn giải "gazetteer" đã có trong đoạn, không đổi phạm vi / hành vi; người dùng soát khi review — nếu coi là lệch
  thì tách thành đề xuất `docs/prd/update/` không đổi hành vi.
- Production = mặc định `core/config.py` (env thật ở VM ngoài repo) — giữ nguyên quyết định 06/10.

## Kiểm tra

- `PYTHONUTF8=1 python -m pytest src/backend/tests/unit/api/test_search_settings_wiring.py …test_search_route.py
  …test_search_llm_fallback.py …test_dest_filter.py …test_query_plan_filters.py …test_search_v116_defaults.py
  …test_backend_wiring.py src/backend/tests/contract`: 157 passed.
- Toàn bộ `src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract`: xem entry
  `history/2026-10-07-search-duration-poi-entity-contract-1-18-0.md` (chạy chung sau các thay đổi tiếp theo) — kết quả chạy riêng tại
  thời điểm này ghi ở mục dưới khi có.
- Lưu ý Windows: pytest cần `PYTHONUTF8=1`, nếu không test đọc contract lỗi cp1252.

## Còn lại / rủi ro

- Deploy VM vẫn chờ quyền (như entry 06/10); env thật trên VM không bị ảnh hưởng bởi merge này, chỉ mặc định trong repo.
- Nên rà các merge "merge code" khác trên nhánh (`git diff 1eb7624 HEAD --stat`) để chắc không còn hunk nào bị mất ngoài phạm vi
  search; entry này chỉ soát `config.py`, `main.py`, hai file PRD.
