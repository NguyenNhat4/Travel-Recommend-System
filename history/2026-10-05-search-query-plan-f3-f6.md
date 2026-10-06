# Search: query plan theo kiến trúc Phase A — phủ định tiện ích (F3), loại sản phẩm (F4), chiều bay (F5), giá/sao (F6) sau cờ; contract 1.15.0

- Ngày: 2026-10-05
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent; hai khối con do workflow agent triển khai, orchestrator kiểm và nối)
- Nhánh: `fix/search`
- Trạng thái: hoàn thành (backend + contract + spec; phần bench ghi ở `history/2026-10-05-search-bench-query-plan-guards.md`)
- Phạm vi: backend, contract, docs

## Mục tiêu

Theo `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` (Phase A): **hard constraint phải được parse và filter, vector chỉ xếp
hạng**. Bốn kiểu câu yếu còn lại của `/search` (phủ định, lẫn loại, chiều bay, giá/sao) đều là hard constraint chưa thành filter. Người
dùng chốt 05–05/10: làm cả bốn khối sau cờ mặc định tắt (hiện thực FR-SRC-01 + FR-SRC-03, không cần đề xuất PRD); tham số request
tường minh (`origin`, `priceMin/priceMax`, `starRatingMin`, `availableOnly` — contract đã khai nhưng route đang bỏ qua) áp ngay; F rỗng
do filter suy ra trả rỗng + `emptyReason`, không nới; sprint này không phụ thuộc gold mới. Phục vụ FR-SRC-01/03/04, AC-SRC-01, NFR-PERF-01.

## File thay đổi

- `src/backend/app/domain/search/amenities.py` — thêm: từ vựng tiện ích có kiểm soát (catalog phrase → khoá, cụm hỏi → khoá; loại POI kèm
  khoảng cách, chuỗi tự phủ định, `sân gôn nhỏ`/`trong vòng N km`); `amenity_keys`, `keys_of_string`, `QUERY_CUES`.
- `src/backend/app/domain/search/constraints.py` — thêm: `parse_numeric` (giá VND / sao, cue trần-sàn, `dropped`/`unresolved`),
  `parse_negation` (cue cứng/mềm, scope ≤ 4 token, không bịa khoá, `must_not_brands`), `parse_vertical` (cue loại → taxonomy, ≥ 2 loại →
  `multi`, bỏ cue trong scope phủ định / sau `có|kèm|gần` / trong tên thương hiệu), `parse_flight_roles` (vai trò nơi đi/đến theo toán tử,
  dấu `-`, IATA viết hoa; không bịa nơi đi), `remove_spans`.
- `src/backend/app/domain/search/query_plan.py` — thêm: `QueryPlan`, `PlanParams`, `PlanFlags`, `PlanGazetteers` (brand guard, IATA, thành
  phố bay), `build_query_plan` (thứ tự giá/sao → phủ định → loại → tuyến → điểm đến; param thắng câu; cờ tắt chỉ khai; `lexical_text`
  bỏ cụm đã thành filter; `as_diagnostics`, `applied_filters`, `mask_kwargs`, `families_in_order`).
- `src/backend/app/domain/search/normalize.py` — sửa: public `spans`/`find_phrases`; `NormalizedQuery.destination_spans` (additive).
- `src/backend/app/domain/search/scoring.py` — sửa: `soft_star_order` (unit không khai sao xếp sau), `revalidate` (kiểm lại mask sau fusion).
- `src/backend/app/domain/search/__init__.py` — sửa: export các module trên.
- `src/backend/app/domain/catalog/unit_attributes.py` — thêm: `UnitAttributes.build(units, children)` (amenities property ∪ phòng con,
  brand, star_rating, min_price, origin_city, destination_city). `src/backend/app/domain/catalog/__init__.py` — sửa: export.
- `src/backend/app/application/ports/unit_index.py` — sửa: `attrs: UnitAttributes | None = None` (field cuối, tự dựng khi None);
  `mask(..., origin_city, destination_city, price_min, price_max, star_min, exclude_amenities)` additive; `star_known_ok`.
- `src/backend/app/application/search/use_cases.py` — sửa: `SearchProducts` thêm `negation_filter/taxonomy_filter/route_filter/
  numeric_filter`, `_gaz` (`_plan_gazetteers`); `__call__` nhận `origin, price_min, price_max, star_min, available_only, derive_plan`;
  `_retrieve(plan, …)` dựng mask từ plan, BM25/độ phủ dùng `lexical_text`, re-validate + sao soft; `_empty_reason`; diagnostics
  `queryPlan` (phát khi chuẩn hoá bật, kể cả cờ tắt); `appliedFilters` khi F1 bật / có param lọc / có họ suy từ câu áp. Bỏ
  `_applied_filters` cũ (thay bằng `QueryPlan.applied_filters`, giữ khoá cũ).
- `src/backend/app/infrastructure/vectors/postgres_store.py`, `src/backend/tests/fakes/in_memory_vector_store.py`,
  `src/evaluation/search_bench/app_adapter.py` — sửa: truyền `attrs` dựng từ `children` đã có (không SQL mới, không DDL).
- `src/backend/app/core/config.py` — sửa: 4 cờ `search_negation_filter / search_taxonomy_filter / search_route_filter /
  search_numeric_filter` = False. `.env.example` — sửa: khối comment. `src/backend/app/main.py` — sửa: nối 4 cờ, log, `version="1.15.0"`.
- `src/backend/app/api/v1/routes/search.py` — sửa: payload/GET nhận `origin, priceMin, priceMax, starRatingMin, availableOnly` và truyền
  xuống engine; `priceMin > priceMax` → 400 `VALIDATION_ERROR`; nhánh câu rỗng lấy `cutoff` của engine thay hard-code 0.62.
- `src/shared/contracts/openapi.yaml` — sửa: `version: 1.15.0`. `src/shared/contracts/paths/search.yaml` — sửa: GET thêm `origin, priceMin,
  priceMax, starRatingMin, availableOnly`. `src/shared/contracts/schemas/search.yaml` — sửa: `SearchRequest.origin`; `EngineDiagnostics.
  queryPlan` (object đóng); mô tả `AppliedFilters.hard/soft` khoá mới.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §2.2 bước QUERY PLAN, §2.4 knob, §2.5 hàng hard/soft suy từ câu + đoạn
  `appliedFilters` 1.15.0, §10 S12–S14. `docs/spec/product.md` — sửa: ghi chú số đếm tab khi bật F4.
- Test thêm: `src/backend/tests/unit/domain/test_amenities.py`, `test_constraints.py`, `test_query_plan.py`, `test_unit_attributes.py`;
  `src/backend/tests/unit/application/test_query_plan_filters.py`, `test_unit_index_mask.py`; `src/backend/tests/unit/api/
  test_search_route.py`; sửa `src/backend/tests/unit/domain/test_normalize.py` (thêm test `destination_spans`).

## Quyết định

- **Filter-first trong RAM**: mọi họ mới là mask numpy trên `UnitIndex` (3.183 unit), id gửi Weaviate như cũ — không đụng adapter, không
  SQL mới, không DDL; loader đã tải phòng con nên giữ lại để tính giá tối thiểu và tiện ích cấp phòng (gold phủ định có "ban công",
  "bếp riêng").
- **Ngữ nghĩa phủ định** = loại unit **có ghi nhận** tiện ích; vắng = không biết → qua ([C2], gold-guide #3/#7). Cụm ngoài từ vựng →
  `unresolved`, không bịa khoá. "không cần / không nhất thiết X" = bỏ điều kiện, không lọc.
- **Sao soft** theo contract [C6] (kiến trúc coi là hard — không theo): unit khai sao thấp hơn bị loại, không khai giữ và xếp sau (phân
  hoạch ổn định sau RRF). **Giá hard** trên giá thấp nhất của unit kể cả phòng con; giá null bị loại khi có lọc giá (contract).
- **F4** chỉ khi câu nêu đúng một loại và không có `taxonomy` request; ≥ 2 loại (cross-vertical) không lọc; cue trong tên thương hiệu
  (guard dựng từ catalog: tên chứa cue của taxonomy khác) không tính. Bật sẽ đổi số đếm tab của Web → ghi spec/product.md, cờ tắt.
- **F5** chỉ câu vé máy bay / `taxonomy = flight` / có `origin`; gazetteer thành phố bay dựng từ `originCity/destinationCity` của tuyến
  (nơi đi thường không phải điểm đến du lịch — "Hà Nội" chỉ là originCity nên normalizer không biết); IATA chỉ nhận token VIẾT HOA (fold
  "han" đụng âm tiết Việt). Đích tuyến parse được thay luật "câu bay bỏ lọc điểm đến" của F1. Lệch PRD tồn đọng (flight trong `/search`)
  không mở rộng: không có taxonomy/câu bay thì hành vi như cũ. `origin` trên `/search` phục vụ Agent/API/`type=flight`; trang `/flights`
  dùng `GET /products` (sửa dữ kiện tôi nêu sai trong plan ban đầu).
- **F rỗng**: filter suy từ câu không nới (kiến trúc §6) — `total 0` + `queryPlan.emptyReason` (họ đầu tiên làm F rỗng); chỉ điểm đến suy ra
  giữ fallback `dropped_empty` (FR-SRC-04, có thể suy sai địa danh). Filter param rỗng → rỗng.
- **Text embed không đổi** (khoá cache vector, prewarm, số bench so được); chỉ `lexical_text` (BM25 + độ phủ vớt) bỏ cụm đã thành filter.
  `queryPlan` phát kể cả khi cờ tắt để bench đo độ chính xác parse; `appliedFilters` giữ hình dạng 1.14.0 cho request web hôm nay (taxonomy
  param không thêm `taxonomySource`).
- Contract bump thẳng **1.15.0** (1.14.0 là nhánh này, `release-mvp-v2` dùng 1.13.0); sửa contract trước code (AGENTS §3); additive.
- Verifier độc lập (workflow) tìm 3 lỗi major trước khi đóng: "dưới 500 m" bị hiểu là 500 triệu, cue "trừ" bắn trên fold của "lưu trú",
  `UnitAttributes.build` mất ~9 s trên catalog thật (200k chuỗi tiện ích, 1.864 chuỗi khác nhau) → memo `keys_of_string` (0,04 s), sửa
  parser kèm test hồi quy; "không phải Vinpearl" từ chỗ chỉ khai nay lọc thật (`exclude_brands`, `appliedFilters.hard.mustNotBrands`).
- Kiểm identity trên bench (`sb topids-diff` với run det 05/10) bắt thêm một lỗi test đơn vị không thấy: cờ tắt vẫn xếp lại 7 câu
  `multi_constraint` vì `_retrieve` áp sắp xếp sao mềm khi plan *parse ra* sao thay vì khi sao *đang áp* → dùng `plan.star_active`, thêm test
  so thứ tự với engine không chuẩn hoá. Bài học: identity cờ tắt phải kiểm trên bench thật, không chỉ so hai engine cùng mã mới.
- Không sửa `text_builder._FEATURES` (regex `golf` bỏ sót "sân gôn" 128 khách sạn): đổi text = đổi vector toàn catalog. Từ vựng tiện ích
  là module riêng của filter.

## Kiểm tra

- `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q src/backend/tests/unit/domain src/backend/tests/unit/application src/backend/tests/unit/api
  src/backend/tests/architecture src/backend/tests/contract` → **871 passed** (lần cuối, sau sửa lỗi verifier; mốc trước sprint 579 + contract; thêm test từ vựng, parser (62 + 44 hồi quy),
  query plan, thuộc tính unit, mask, use case, route, normalize).
- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py` → PASS (102 schema).
- Cờ tắt ≡ hôm nay: `test_query_plan_filters.py::test_flags_off_is_todays_behaviour_and_declares_the_plan` so response của engine mặc định
  với engine có 4 cờ tắt trên 5 câu (chỉ khác khoá khai báo `queryPlan`); `test_dest_filter.py` (F1) giữ xanh không sửa.
- Độ phủ từ vựng trên catalog thật (items.parquet snapshot 2026-09-23, 2.321 property): wifi 2.154 · balcony 1.275 · parking 1.269 ·
  breakfast 1.248 · restaurant 1.092 · pool 976 · shuttle 904 · kitchen 743 · golf 128 · privatePool 120 · privateBeach 108.

## Còn lại / rủi ro

- Mọi cờ mặc định tắt; bật sau khi đo trên gold v4 (chờ người dùng push; tên slice/trường gold sẽ gửi sau). Số Sprint 1 là trong mẫu.
- Agent nhận cờ toàn cục; có `derive_plan` theo lượt nhưng `SEARCH_ENGINE_ARGUMENTS` của Agent chưa truyền `origin`/giá/sao (giữ nguyên).
- `has_golf` suy từ chuỗi "sân gôn" có nhiễu (city hotel ghi) — chỉ dùng chiều loại. Giá là một báo giá (1 đêm/2 người/một ngày); combo
  `per_person` vs `per_package` chưa phân biệt khi lọc giá.
- Cherry-pick sang `release-mvp-v2`: `use_cases.py` ở release có `scored()` (1.13.0) → giải conflict.
