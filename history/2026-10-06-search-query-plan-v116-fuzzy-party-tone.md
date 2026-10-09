# Search: hoàn thiện phần còn thiếu của kiến trúc Phase A/B (contract 1.16.0) — loại trừ loại sản phẩm, số khách, dấu thanh, kênh fuzzy, RRF trọng số, độ tin cậy router, ghi `app.search_logs`

- Ngày: 2026-10-06
- Tác giả: người dùng ("hoàn thành các phần còn thiếu và chưa làm" của `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md`) /
  Claude (Opus 5.5, orchestrator + 4 agent backend)
- Nhánh: fix/search-gold-v4
- Trạng thái: hoàn thành (mọi phần mới sau cờ, mặc định tắt; bật cờ nào là quyết định của người dùng — xem report)
- Phạm vi: backend, contract, docs

## Mục tiêu

Sau F1–F6 (05/10) kiến trúc còn thiếu: loại trừ loại sản phẩm / thành phần combo, lọc số khách (occupancy) + phòng con thoả
ràng buộc, chuẩn hoá vị trí dấu thanh, kênh fuzzy tên (5C), RRF có trọng số, router confidence (không LLM), ghi log truy vấn thật
(§11). LLM fallback là lệch PRD → chỉ đề xuất (`docs/prd/update/2026-10-06-search-llm-fallback-query-plan.md`, chờ chốt, không code).
Phục vụ FR-SRC-01, FR-SRC-03, FR-SRC-04; NFR-PERF-01.

## File thay đổi

- `src/shared/contracts/openapi.yaml` — sửa: version 1.16.0.
- `src/shared/contracts/schemas/search.yaml` — sửa (additive): `queryPlan.taxonomy.strength`, `mustNot.taxonomies` / `mustNot.flags`,
  `party {adults, children, total, source}`, `confidence`, `fallbackReasons[]`; enum `applied` / `emptyReason` += `party` (và `star`
  cho `emptyReason` — lỗ 1.15.0); `diagnostics.fuzzyCount`, `stageMs.fuzzy`; mô tả `AppliedFilters.hard`, `TravelContext.guests`.
- `src/shared/contracts/schemas/catalog.yaml` — sửa: `ScoredProduct.matchedChildren` (≤ 5 id phòng con).
- `src/shared/contracts/paths/search.yaml` — sửa: mô tả POST (occupancy).
- `src/backend/app/domain/search/tone.py` — thêm: `detect_style`, `normalize_tone` (oà/òa, oé/óe, uý/úy theo kiểu đa số catalog).
- `src/backend/app/domain/search/fuzzy.py` — thêm: `FuzzyIndex` trigram kiểu pg_trgm trong tiến trình (cửa sổ token ±1 độ dài tên,
  shortlist 200 theo cận trên, p50 1,6 ms / p95 3,8 ms trên 3.183 tên).
- `src/backend/app/domain/search/constraints.py` — sửa: cue cứng "không lấy/không muốn"; `must_not_taxonomies` ("vé lẻ", "không lấy
  combo", "không phải khách sạn") + `must_not_flags` (includesFlight/includesHotel); combo đứng đầu; `WEAK_VERTICAL_CUES` /
  `VERTICAL_CUE_STRENGTH` (chốt theo dữ liệu nhãn dev/test 06/10) + `VerticalParse.strength`; `parse_party`; `POI_BRAND_CUES` công khai;
  cue mới "hotel", "điểm vui chơi"; cue trong tên sản phẩm tính khi đúng loại của chính unit (`brand_taxonomy`); "có <cue> nào" là câu
  hỏi tồn tại.
- `src/backend/app/domain/search/query_plan.py` — sửa: `PlanParams.adults/children`, `PlanFlags.taxonomy_strong_only/party`,
  `QueryPlan` (+ taxonomy_strength, must_not_taxonomies/flags, party_*, confidence, fallback_reasons, `party_active`), mask kwargs
  `min_occupancy`/`exclude_taxonomies`/`exclude_flags`, `as_diagnostics(extended=)`; câu có một loại khác flight không là câu vé máy
  bay (c0706); tên điểm vui chơi giữ trong `lexical_text`; `PlanGazetteers.brand_taxonomy`.
- `src/backend/app/domain/search/destination.py` — sửa: `decide_destination(..., flight=)` nhận quyết định "câu bay" của query plan.
- `src/backend/app/domain/search/normalize.py` — sửa: `QueryNormalizer(tone=)`, `tone_style`.
- `src/backend/app/domain/search/hybrid.py` — sửa: `HybridConfig` fuzzy_k / fuzzy_candidate_k / fuzzy_min_sim / dense_weight /
  lexical_weight / fuzzy_weight; `rrf` có trọng số + danh sách thứ ba; `hybrid_filter_score(fuzzy_rank, fuzzy_admissible)`.
- `src/backend/app/domain/search/amenities.py` — sửa: bỏ khớp nhầm "Bồn tắm spa"/"Ghế, giường mát-xa" (→ spa), "Phòng tập thể"
  (dorm → gym; `exclude_re`), "Nhà hàng / phòng chờ phù hợp cho người khuyết tật" (→ restaurant).
- `src/backend/app/domain/search/__init__.py` — sửa: export.
- `src/backend/app/domain/catalog/unit_attributes.py` — sửa: `flags` (includesFlight/includesHotel từ `combo_items.item_kind`,
  ticketed), `max_occupancy`, `children` (id, giá, sức chứa).
- `src/backend/app/application/ports/unit_index.py` — sửa: `mask(exclude_taxonomies, exclude_flags, min_occupancy)`,
  `matched_children(...)`.
- `src/backend/app/application/search/use_cases.py` — sửa: field `tone_normalize`, `taxonomy_strong_only`, `party_filter`; kênh
  fuzzy (lấy vector cho unit chỉ-fuzzy; danh sách kênh lọc theo `fuzzy_min_sim` — xem Quyết định); `adults/children`; kiểm chung giá +
  số khách bằng phòng con; `matchedChildren`; `_plan_diagnostics`; gazetteer `brand_taxonomy`.
- `src/backend/app/application/search/search_log.py` — thêm: `search_log_entry`, `SearchLogRecorder` (hàng đợi 1.000, một luồng).
- `src/backend/app/application/ports/search_logs.py` — sửa: `SearchLogEntry`, `SearchLogWriter`.
- `src/backend/app/infrastructure/persistence/postgres_search_logs.py` — sửa: `PostgresSearchLogWriter` (INSERT `app.search_logs`).
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: `_COMBO_QUERY` lấy `item_kind` (cột có sẵn, không DDL).
- `src/backend/app/api/v1/routes/search.py` — sửa: `travelContext.guests` → adults/children; ghi log sau cờ; GET dùng `Annotated`
  (sửa test agent hỏng sẵn ở HEAD khi gọi route trực tiếp).
- `src/backend/app/core/config.py`, `src/backend/app/main.py`, `.env.example` — sửa: SEARCH_TONE_NORMALIZE, SEARCH_TAXONOMY_STRONG_ONLY,
  SEARCH_PARTY_FILTER, SEARCH_FUZZY_K/_CANDIDATE_K/_MIN_SIM, SEARCH_RRF_*_WEIGHT, SEARCH_LOG_QUERIES; version 1.16.0.
- `src/backend/tests/fakes/in_memory_vector_store.py` — sửa: đọc `combo_items.jsonl` nếu có, attrs mới.
- Test — thêm: `unit/domain/test_tone.py`, `test_party.py`, `test_fuzzy.py`; `unit/application/test_search_v116_knobs.py`,
  `test_search_v116_defaults.py`, `test_search_log.py`; `unit/infrastructure/test_postgres_search_logs.py`;
  `unit/api/test_search_settings_wiring.py`; `contract/test_search_contract.py`. Sửa: `unit/domain/test_constraints.py`,
  `test_query_plan.py`, `test_normalize.py`, `test_hybrid.py`, `test_unit_attributes.py`, `test_amenities.py`;
  `unit/application/test_unit_index_mask.py`; `unit/api/test_search_route.py`.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §2.2 (phần 1.16.0 của QUERY PLAN, kênh fuzzy + RRF trọng số), §2.4
  knob, §2.5 hai hàng hard mới, §7.3 ghi `app.search_logs`, §10 S12–S14 cập nhật số + S15–S17.
- `docs/prd/update/2026-10-06-search-llm-fallback-query-plan.md` — thêm: đề xuất LLM fallback (chờ chốt).

## Quyết định

- **Mọi phần mới sau cờ, mặc định tắt** (như F1–F6); tham số request tường minh (`travelContext.guests`) áp không cờ — tuân thủ contract.
- **Chốt bảng cue yếu bằng dữ liệu** (task 3 của yêu cầu): trên dev/test của `devtest@gold_v4`, danh từ chỗ nghỉ giữ 99–100 % item
  nhãn 2 cùng loại → mạnh; tên điểm vui chơi (safari 73 % dev, vinwonders 50 % test — combo chứa vé được nhãn 2) → yếu và không cắt
  khỏi BM25.
- **Kênh fuzzy: chỉ khớp ≥ `fuzzy_min_sim` vào danh sách kênh.** Bản đầu đưa cả top-50 vào RRF (ngưỡng chỉ chặn phần vớt): bench
  −7,6 điểm nDCG@10 và hai ngưỡng 0,6 / 0,75 cho kết quả y hệt. Sau sửa: −0,5 (TIE). Mặc định `SEARCH_FUZZY_MIN_SIM=0.75`.
- **Diagnostics 1.16.0 chỉ phát khoá của núm đang dùng** (`strength` khi strong-only bật, `party` khi có guests/cờ, `mustNot` mở
  rộng khi cờ phủ định bật) — response hôm nay không đổi ngoài `queryPlan.confidence` / `fallbackReasons`.
- **Không LLM** trong request path (lệch PRD) — chỉ khai `confidence` / `fallbackReasons`, đề xuất chờ chốt.
- **Ghi log**: không DDL (bảng có sẵn), ngoài đường request, lỗi không lên response, `cdp_user_id` chỉ khi đã xác thực.

## Kiểm tra

- `pytest src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract` (.venv): xanh (1.422 passed, 1 skipped —
  test Postgres thật cần `RUN_POSTGRES_INTEGRATION=1`); sau sửa cue/brand: domain + application + architecture 967 passed.
- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py`: PASS (102 schemas, 70 fixture);
  pyc tracked `bundle_openapi.cpython-313.pyc` đã `git checkout --`.
- Identity cờ tắt: 6 cấu hình engine × 171 câu × 8 bộ tham số so `use_cases.py` HEAD — results/total/facets/topScore/appliedFilters
  trùng; bench: arm mốc `APP.e5s.hybrid_norm_nocut` và `APP.e5s.dense_nocut` trùng top-10 154/154 với run vòng 1.
- Bench đầy đủ: `src/evaluation/reports/eval-2026-10-06-search-query-plan-gold-v4.md`.

## Còn lại / rủi ro

- Bật cờ production (F1, F3–F6; F4 cần ý kiến Web vì số đếm tab) là quyết định người dùng — đề xuất cụ thể ở report.
- `SEARCH_PARTY_FILTER`, `SEARCH_TONE_NORMALIZE`, kênh fuzzy, RRF trọng số: trung tính trên gold (gold gần như không có câu dấu thanh
  lệch / số khách) — giữ tắt; cần gold riêng nếu muốn bật.
- Danh sách tiện ích catalog của một số khách sạn dừng ở đúng 60 chuỗi → tiện ích bị loại trừ có thể vắng trong dữ liệu (F3 không
  thấy) — việc của Data.
- Test Postgres thật cho writer chưa chạy (không có DB local).
- `release-mvp-v2`: chưa cherry-pick (không sửa nhánh đó).
