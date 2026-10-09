# /search 1.18.0: thời lượng (F7), địa danh gazetteer → F1, entity gate cứng — backend, contract, tài liệu

- Ngày: 2026-10-07
- Tác giả: tqanh123 (người dùng chốt) / Claude (Fable 5.1, orchestrator + 6 agent)
- Nhánh: fix/search-production
- Trạng thái: hoàn thành (code + contract + test + docs; bench/gold ghi ở `history/2026-10-07-search-bench-arms-slices-duration-poi-entity.md`)
- Phạm vi: backend, contract, docs, frontend (chỉ regen `api.gen.ts`)

## Mục tiêu

Thực hiện P0 của plan `docs/plan/2026-10-07-search-duration-entity-poi.md` theo spec
`docs/spec/bench/tong-hop-chinh-sua-luong-search-ota.md` (history spec: `2026-10-07-spec-tong-hop-chinh-sua-luong-search-ota.md`):
chặn ba lỗi production — `vinwonder 3 ngay 2 dem` lẫn hotel "Chợ Đêm" (BM25 vớt theo `ngay`/`dem` trong tên), `khách sạn gần Hồ
Hoàn Kiếm` không lọc điểm đến (gazetteer không có landmark), và gate cứng điểm vui chơi. Mọi họ mới sau cờ **mặc định tắt**; tắt
thì không parse, không khai → response byte-identical 1.17.0. Phục vụ FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01; NFR-PERF-01.
Không lệch PRD (filter suy từ câu sau cờ, tiền lệ 05/10; không tham số request mới, không DDL, không re-embed).

## File thay đổi

Contract (trước code, AGENTS §3)
- `src/shared/contracts/schemas/search.yaml` — sửa: 1.18.0 additive — `queryPlan.duration` {days, nights, source}, `queryPlan.entity`
  {keys, role gate|location}, `queryPlan.location` {key, name, kind, destination}; `applied` += duration, entity; `emptyReason` +=
  entity, duration (duration không bao giờ phát — test contract ép mọi `APPLIED_*` vào cả hai enum); mô tả `appliedFilters.hard`
  (entity, destinationSource = poi), `derivedDestinations`, `destinationFilter`, `lexicalText`, ghi chú "chỉ khai khi cờ bật".
- `src/shared/contracts/openapi.yaml` — sửa: version 1.18.0. `src/frontend/src/types/api.gen.ts` — regen (`npm run generate:api-types`;
  hấp thụ luôn drift 1.17.0 `queryPlan.llm` chưa regen trước đó). FE không đọc khối mới → không sửa component.

Backend
- `src/backend/app/domain/search/gazetteer.py` — thêm: bảng `PLACES` (52 entry: thương hiệu nhiều site `vinwonders`/`safari`/
  `grand_world`/`aquafield` destination None; venue một site; site của thương hiệu từ `collectors/venues.csv` chép làm seed; landmark /
  khu vực / quận / sân bay cho 12 điểm đến catalog), `place_table(destinations)`, `entity_table()`, `entities_of_name()`,
  `ENTITY_TAXONOMIES`, `MAX_ALIAS_TOKENS`; stdlib, không I/O (pattern `amenities.py`).
- `src/backend/app/domain/search/constraints.py` — sửa: `parse_duration` / `DurationParse` (N ngày M đêm, 3N2Đ, N ngày, M đêm, days/
  nights; chữ số 1–30; bỏ span giá / số khách; không nhận "3 tiếng", "chợ đêm", "qua đêm").
- `src/backend/app/domain/search/query_plan.py` — sửa: `APPLIED_DURATION`, `APPLIED_ENTITY`, `ROLE_GATE/LOCATION`; `PlanFlags`
  duration/poi/entity; `PlanGazetteers.entities/places` + `entity_keys()` / `place_hits()`; `QueryPlan` field mới + `destination_via_poi`
  (so với `poi_destinations`, không phải "không có trong nq.destinations" — đích IATA "HAN DAD" không phải POI); parse ba họ CHỈ khi
  cờ bật: duration sau party (tiêu span khỏi `lexical_text`), entity sau F4 (vai trò: cue loại khác kể cả yếu / ≥ 2 loại → location,
  còn lại gate; không tiêu cụm), POI trước F1 (thêm điểm đến vào `nq.destinations` rồi `decide_destination` như cũ — giữ FR-SRC-04
  fallback, `drop_tokens`, enum `destinationFilter.source`); `mask_kwargs` require_entities; `families_in_order` bước entity ngay sau
  loại suy từ câu; `as_diagnostics` / `applied_filters` khối mới; `_fallback_reasons` vẫn nhận `nq` gốc (confidence, LLM trigger không đổi).
- `src/backend/app/domain/search/__init__.py` — sửa: export tên mới.
- `src/backend/app/domain/catalog/unit_attributes.py` — sửa: `entities` (khoá entity trong TÊN, chỉ attraction/combo); loader không đổi.
- `src/backend/app/application/ports/unit_index.py` — sửa: `mask(require_entities=())` (gate: unit không có khoá bị loại).
- `src/backend/app/application/search/use_cases.py` — sửa: field `duration_filter` / `poi_resolve` / `entity_filter` (theo `derive_plan`);
  `_plan_gazetteers(units, *, entities, destinations)` — bảng entity chỉ khoá có unit, bảng địa danh chỉ điểm đến catalog;
  `derivedDestinations` = `plan.destination.candidates`.
- `src/backend/app/core/config.py` — sửa: `search_duration_filter`, `search_poi_resolve`, `search_entity_filter` (False).
- `src/backend/app/main.py` — sửa: truyền 3 cờ, log startup; `version="1.18.0"`. `.env.example` — sửa: 3 biến mới (comment).
- Test thêm: `tests/unit/domain/test_gazetteer.py`, `tests/unit/application/test_search_v118_families.py`; sửa:
  `tests/unit/domain/{test_constraints,test_query_plan,test_unit_attributes}.py`, `tests/unit/application/{test_unit_index_mask,
  test_search_v116_defaults,test_search_log}.py`, `tests/unit/api/test_search_settings_wiring.py`,
  `tests/contract/{test_search_contract,test_search_llm_contract}.py` (ghim 1.18.0, ALL_ON + CASES + khoá phải thấy).

Tài liệu
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §2.2 khối 2026-10-07 (ba họ), hoà cue yếu VinWonders/Safari/Grand
  World với gate, sửa chữ cũ "LLM fallback chờ chốt"; §2.4 knob (+ `llmFallback` thiếu); §2.5 hàng entity, `poi`; §9 10d–10f; §10 S18.
- `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` — sửa: §17 ba dòng mới, contract 1.18.0, link spec/plan.
- `docs/spec/product.md` — sửa: §4.2.3 ghi chú `SEARCH_ENTITY_FILTER` (tab Lưu trú có thể 0, cần Web xác nhận như F4).

## Quyết định

- Ba họ mới **tắt thì không parse** (khác F3–F6 "tắt vẫn khai"): giữ response mặc định y hệt 1.17.0 và `test_search_v116_defaults`;
  độ chính xác parse đo trên arm bật cờ. Ghi ở contract (block comment queryPlan) và spec §3.
- Entity chỉ từ **tên** unit; `combo_items.label` / `item_product_id` để P1 (đo trên catalog bench: +2 / +10 trong 133 combo).
- `safari` ở mức thương hiệu (destination None): catalog có 44 unit Phú Quốc, 6 Hội An, 1 Rạch Giá.
- Bảng entity thu hẹp theo catalog đang phục vụ: entity không có sản phẩm không bao giờ gate (tránh F rỗng vô cớ).
- `place_hits` bỏ cụm chồng span điểm đến normalizer đã nhận → "homestay phố cổ Hội An" không có khối `location` (điểm đến vẫn
  Hội An từ normalizer); câu ≥ 2 POI khác thành phố → `skipped = multi`, khối `location` vẫn là POI đầu tiên.
- LLM hypothesis không mở rộng (không `F_*` mới, không đổi prompt/`PROMPT_VERSION`).

## Kiểm tra

- `PYTHONUTF8=1 python -m pytest src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract -q`:
  **2305 passed, 9 failed, 3 skipped** — 9 lỗi đều `ModuleNotFoundError: weaviate` ở `test_weaviate_store.py` (env python hiện tại
  thiếu client; `.venv-sbench` có weaviate nhưng thiếu `pydantic_settings`) — có sẵn trước thay đổi, không liên quan.
- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py`: **PASS** (109 schema).
- `npm run generate:api-types` → `api.gen.ts` đổi 62 +/10 −; `npx tsc --noEmit`: 1 lỗi TS1149 có sẵn (`widgetProgress.test.ts` import khác hoa thường), không liên quan.
- Chạy tay `build_query_plan` cờ bật/tắt trên 14 câu mẫu (spec §3.7): đúng bảng; cờ tắt không phát khối mới.
- Test v118: BM25 vớt hotel "Khách sạn Ngay Chợ Đêm Đà Lạt" tái hiện offline (engine chỉ vớt) — cờ tắt vớt, cờ bật không.

## Còn lại / rủi ro

- Bật ở production: chỉ sau bench (entry bench) WIN/TIE + Forbidden@10 = 0; `SEARCH_ENTITY_FILTER` cần Web xác nhận (tab 0).
- Agent tool không truyền `derive_plan` → gate áp cả Agent khi bật env; chạy `test_itinerary_engine_tools.py` với cờ bật trước rollout.
- Câu không dấu "vinwonder 3 ngay 2 dem" trên fixture nhỏ ra 0 kết quả khi bật duration (normalizer fixture không có từ vựng sửa
  "vinwonder"); catalog thật sửa được (`vinwonder → VinWonders`) — kiểm trên bench slice `duration_false_positive`.
- 9 test Weaviate cần env có `weaviate-client` (không cài vào env người dùng trong phiên này).
