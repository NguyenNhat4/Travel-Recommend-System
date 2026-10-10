# Kế hoạch `/search` 1.18.0: thời lượng (F7), gazetteer địa danh → F1, entity gate cứng (P0) · geo (P1)

- **Phục vụ:** **FR-SRC-01**, **FR-SRC-03**, **FR-SRC-04**, **AC-SRC-01**; **NFR-PERF-01** (docs/prd/requirements.md).
  - FR-SRC-01: tìm bằng tiếng Việt tự nhiên — "vinwonder 3 ngay 2 dem" là một cách nói tự nhiên, phải không lẫn hotel "Chợ Đêm".
  - FR-SRC-03: "Địa điểm: điểm đến, thành phố, khu vực" suy từ câu — địa danh (Hồ Hoàn Kiếm, Cầu Rồng) phải quy về điểm đến catalog.
  - FR-SRC-04: F rỗng do filter suy ra → `emptyReason`, không nới (tiền lệ F3–F6, `history/2026-10-05-search-dest-filter-no-diacritics.md` L12–14).
  - AC-SRC-01; NFR-PERF-01 (p95 không tăng; không re-embed, không gọi thêm dịch vụ ngoài).
- **Phạm vi:** backend `/search` (domain → catalog/mask → application → config), contract OpenAPI **1.18.0 additive**, bench search + gold_v6, tài liệu spec. **Không** đổi DDL, **không** re-embed, **không** thêm tham số request, **không** sửa frontend component (chỉ regen `api.gen.ts`). Mọi cờ mới mặc định **tắt**.
- **Đầu vào:**
  - Đề xuất `docs/spec/bench/tong-hop-chinh-sua-luong-search-ota.md` (đổi tên từ `tong_hop_chinh_sua_luong_search_ota.md` ngày 07/10, Bước 1). Plan này thay cho §10 (lộ trình) của đề xuất; các mục thiết kế của đề xuất bị sửa theo bảng ở §4 Bước 1.
  - Kiến trúc đích: `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` §17 (pipeline đã có ~80 % — F1–F6, filter-first, consume span, RRF, revalidate, LLM fallback).
  - Hợp đồng: `src/shared/contracts/schemas/search.yaml`; `docs/spec/hop-dong-tich-hop-search-recommendation.md` §2.2/§2.4/§2.5/§10.
  - Số đo catalog bench: `bench_out/search/data/items.parquet` (snapshot 2026-09-23, 3.183 search unit).
- **Lịch:** 07/10 Bước 0–2 (đã xong Bước 0); 07–08/10 Bước 3–7 (contract, backend, test); 08/10 Bước 8 (bench, probe); gold_v6 phụ thuộc lịch gán nhãn của QAnh; rollout sau report.
- **Người đọc:**
  - Lead: người dùng — chốt §9, duyệt rollout, `git tag gold_v6`.
  - Gán nhãn: QAnh (tqanh123) — gold v6a (§5).
  - Web: xác nhận `SEARCH_ENTITY_FILTER` (tab Lưu trú có thể về 0) trước khi bật ở prod.
  - Dev: phiên Claude — viết code, chạy test/bench, viết report; không gán nhãn.
- **Trạng thái:** **đã chốt 9 quyết định (07/10)** — xem mục ngay dưới; Bước 0 đã xong, đang làm Bước 1–2. Chỗ nào bên dưới mâu thuẫn với "Quyết định đã chốt" thì mục đó thắng.

---

## Quyết định đã chốt (07/10) — thắng các mục bên dưới khi mâu thuẫn

| # | Người dùng chốt | Ảnh hưởng tới plan |
|---|---|---|
| Q1 | Entity gate **cứng** (HARD) | Câu chỉ nêu entity (VinWonders, Safari, Grand World…) → chỉ giữ unit `attraction`/`combo` có tên chứa entity; F rỗng → `emptyReason: entity`, **không nới** (FR-SRC-04, tiền lệ F3–F6). |
| Q2 | Gazetteer POI là **file trong repo** | Module `src/backend/app/domain/search/gazetteer.py` (tuple frozen dataclass, stdlib, không I/O); **không** tạo bảng `location_entities` như đề xuất §4.1. `venues.csv` chỉ chép làm seed. |
| Q3 | Facets **giữ contract**: tính trên R sau mask | Chẩn đoán "facet trước filter" của đề xuất §3.9 sai; bỏ `facetMeta`/`globalDiscovery`; `locationResolution` → `diagnostics.queryPlan.location`. |
| Q4 | Geo (bán kính, haversine, xếp hạng theo khoảng cách) là **P1** | Phác thảo ở §7, contract 1.19.0; P0 chỉ map địa danh → điểm đến. |
| Q5 | **Sửa tài liệu trước** → plan `docs/plan/` → code | Thứ tự Bước 1 → 2 → 3 (contract) → 4–7 (code) → 8 (bench) → 9 (đồng bộ). |
| Q6 | **Khôi phục regression merge `21d72ae` trước** | Bước 0 đã xong 07/10 (`history/2026-10-07-restore-search-prod-defaults-llm-fallback.md`), vì cùng chạm `config.py`/`main.py`. |
| Q7 | Entity + cue mạnh loại khác → **vai trò POI** (`location`); brand hotel **không** phải entity | "khách sạn ở Grand World" giữ hotel; "khách sạn Vinpearl" không có khoá entity (`vinpearl` là `BRAND_CUES`). Luật vai trò ở §3.3. |
| Q8 | Khối mới **ẩn trừ khi cờ bật** (quy ước 1.16) | Parse **chỉ khi cờ bật** → cờ tắt ⇒ response byte-identical 1.17.0; contract ghi "chỉ khai khi … bật" (tiền lệ `party`). |
| Q9 | **Probe fixture trước, gold_v6 sau** | 21 câu c0736–c0756 chạy dưới dạng fixture không nhãn (`fixture:<sha8>`, không trích dẫn) để kiểm parse/forbidden trước khi QAnh gán nhãn. |

**Đã thực hiện (07/10):** Bước 0 — khôi phục mặc định prod F1/F3/F5/F6, `no_diacritics_mode = relax`, 7 setting `search_llm_fallback*`, `search_hypothesizer` + 4 kwargs trong `build_recsys`, đoạn "Hiểu câu truy vấn (query plan)" PRD §5 (kèm cụm "bảng địa danh / điểm vui chơi giữ trong repo (`domain/search/gazetteer.py`…)"), dòng `SEARCH_LLM_FALLBACK*` deployment-plan §2; test `test_production_defaults_restored`; 157 passed.

---

## 0. Tóm tắt một đoạn

Ba lỗi production của `/search` (lẫn hotel "Chợ Đêm" với "3 ngày 2 đêm"; "khách sạn gần Hồ Hoàn Kiếm" trả nhiều điểm đến; landmark không quy về thành phố) đều là **thiếu parser**, không phải lỗi kiến trúc: pipeline đã có filter-first, consume span, RRF, revalidate và facet trên R. Plan thêm ba họ nhỏ sau cờ mặc định tắt — **F7 duration** (parse + bỏ cụm khỏi `lexicalText`, chưa lọc), **gazetteer địa danh → F1** (landmark/area/district/airport/venue → điểm đến catalog, đi qua `decide_destination` hiện có), **entity gate cứng** (unit `attraction`/`combo` tên chứa entity) — kèm contract **1.18.0 additive**, 4 arm bench, 2 slice gold nối cuối, probe fixture 21 câu rồi gold_v6. Cờ tắt thì không có đường code mới chạy; bật từng cờ ở VM sau khi bench WIN/TIE, `forbidden_at_10 = 0` và guards xanh; riêng entity gate chờ Web ký. Geo (bán kính, khoảng cách) để P1 với contract 1.19.0. **Không lệch PRD.**

---

## 1. Mục tiêu và mã FR/NFR

| # | Mục tiêu | Đo bằng | Mã |
|---|---|---|---|
| M1 | "vinwonder 3 ngay 2 dem" không còn vớt hotel có "ngay"/"đêm" trong tên; cụm thời lượng không vào BM25 | `queryPlan.duration = {3, 2}`, `"3 ngay 2 dem" ∉ lexicalText`; slice `duration_false_positive` `forbidden_at_10 = 0` | FR-SRC-01 |
| M2 | Địa danh trong câu quy về điểm đến catalog và lọc như F1 (duy nhất → lọc, ≥ 2 → multi, F rỗng → `emptyReason`) | `hard.destinationSource == "poi"`, `derivedDestinations`; slice `poi_resolution` `dest_share10`, `forbidden_at_10 = 0` | FR-SRC-03, FR-SRC-04 |
| M3 | Câu chỉ nêu entity vui chơi trả đúng vé/combo của entity đó; câu "khách sạn gần <entity>" vẫn giữ hotel | `entity.role` gate/location; c0697 vs c0700 không tệ hơn; `taxonomy=hotel` + gate → `emptyReason: entity` | FR-SRC-01, FR-SRC-04, AC-SRC-01 |
| M4 | Không làm hỏng số đã báo cáo và không đổi hành vi khi cờ tắt | `topids-diff` identity rỗng; `test_search_v116_defaults` 157+ câu; `validate_contract.py` PASS; p95 không tăng > 30 % | NFR-PERF-01, test-plan §2.5 |

**Không làm ở P0:** lọc theo thời lượng (catalog không có trường `nights`); bán kính/khoảng cách (P1); tham số request mới (P2, cần `docs/prd/update/`); sửa F4; sửa `normalize.py`, `destination.py`, `hybrid.py`, `scoring.py`, `hypothesis.py`, loader `postgres_store.py`; đổi facet contract; re-embed; DDL.

---

## 2. Chẩn đoán (đã xác minh bằng code và catalog bench)

| Lỗi | Root cause thật | Bằng chứng |
|---|---|---|
| L1 "vinwonder 3 ngay 2 dem" lẫn hotel "Chợ Đêm" | **Không có duration parser** → `ngay`/`dem` ở lại `lexical_text`. Hai hotel `HOTEL THU NGUYEN - ngay BẾN NINH KIỀU & CHỢ ĐÊM` và `December Hotel Dalat - Ngay Trung Tâm & Chợ Đêm` có **cả** `ngay` lẫn `dem` trong tên → coverage 2/3 ≥ 0,6 → BM25 vớt. F4 tắt ở prod; `vinwonders` là cue **yếu** nên không khoá loại | Chạy parser trên câu gốc; `hybrid.min_coverage = 0.6` |
| L2 "khách sạn gần Hồ Hoàn Kiếm" facet nhiều điểm đến | Gazetteer chỉ có điểm đến catalog + 17 viết tắt → F1 **không kích hoạt** → R = top-200 dense toàn quốc. Facets **đã** tính trên R sau mask (contract [C4]) → chẩn đoán "facet trước filter" của đề xuất **sai** | `derivedDestinations = []` trên câu này; `hybrid_filter_score` |
| L3 landmark không map về thành phố | Cùng nguyên nhân L2. Tên **chứa sẵn** city (Phố cổ Hội An, Dragon Bridge Da Nang) đã resolve đúng nhờ `DESTINATION_ALIASES` | `normalize.py` |

**Số đo catalog** (items.parquet, 3.183 unit: hotel_property 2.321 · attraction 610 · combo 133 · flight_route 113 · golf 6):

- `attributes.latitude/longitude` 100 %; `locationPrecision` ∈ {exact, venue, airport, poi, destination}; `city` 88 % (có cả "Quận Hoàn Kiếm") → đủ cho geo P1 mà không cần DDL.
- `nights` = 0 unit; "N ngày" nằm trong **tên vé** 31 unit (20 attraction + 11 combo), 0 hotel, 0 tên có "N đêm", 0 tên có `3n2d` → consume cụm duration chỉ mất bằng chứng BM25 "ngay" trên tên vé; dense vẫn thấy câu đầy đủ.
- VinWonders trong 141 tên; `brand` chỉ có Vinpearl (26 KS) → brand hotel không làm entity (Q7).
- Safari: 51 unit tên có "safari" = Phú Quốc 44, Hội An 6 (River Safari, VinWonders Nam Hội An), Rạch Giá 1 → `safari` phải ở **mức brand** (destination None), không khoá về Phú Quốc.
- Grand World: Hà Nội 2 + Phú Quốc 31; Aquafield: Hà Nội 17 + Nha Trang 15 → cũng mức brand.
- Combo: 133 combo / 306 dòng `catalog.combo_items`, `item_product_id` NULL 168/306. Lấy entity từ `label` thêm **+2** combo (chỉ vinwonders); từ tên sản phẩm được `item_product_id` trỏ tới thêm **+10** (vinpearl harbour 5, vinpearl aquarium 2, vinwonders 2, safari 1). 12/145 không đáng 3 chỗ sửa loader → P0 lấy entity **chỉ từ tên unit**, `combo_items` → P1 (§7).

---

## 3. Thiết kế P0

### 3.1 F7 duration — `constraints.parse_duration`

- Nối sau phần party của `domain/search/constraints.py`; tái dùng `_toks`, `_overlaps`, `_gap_has`, `_INT`, `Span`; chép vòng ghép span của `parse_party`.
- `DurationParse(days, nights, spans)`; luật: bỏ token chồng `protected` (= `numeric.spans + party.spans`); (a) token compact `^(\d{1,2})n(\d{1,2})d$` (`fold("3N2Đ") == "3n2d"`) → cả hai; (b) `_INT` 1..30 + token **ngay sau** là `{ngay, day, days}` / `{dem, night, nights}` → ghi; giá trị đầu mỗi loại thắng; mọi span khớp đều consume; span kề ghép qua `va` / `,` / `-` / `/`. Chỉ chữ số (như party). Không suy phần thiếu.
- Vì sao `protected` đủ: "2 triệu/đêm", "tầm 1.5 triệu một đêm", "1 triệu 1 đêm" bị `_absorb_unit_tail` nuốt vào `numeric.spans`; "dưới 2 triệu 2 đêm", "3 sao 2 đêm", "500k 2 đêm" để "2 đêm" tự do → nights = 2 (đúng).
- Bảng bảo đảm (test parametrize): "VinWonders 3 ngày 2 đêm" → (3, 2); "3 ngay 2 dem" → (3, 2); "3N2Đ"/"3n2d" → (3, 2); "2 ngày" → (2, None); "phòng cho 2 người 3 đêm" → (None, 3), party giữ "2 người"; "resort 2 triệu/đêm Phú Quốc" → None; "tầm 1.5 triệu một đêm" → None; "(3 tiếng)" (c0372) → None; "qua đêm" / "ban đêm" / "chợ đêm" / "ngay trung tâm" → None; "2 đêm 3 ngày", "3 ngày, 2 đêm", "3 days 2 nights" → cả hai, một span; "khách sạn 3 sao 2 đêm" → (None, 2); "45 ngày", "0 đêm" → None; "ngày 15/10 đến 17/10" → None; "vé máy bay Hà Nội Đà Nẵng 3 ngày 2 đêm" → (3, 2), route không đổi.
- Trong `build_query_plan`: chỉ khi `flags.duration`; có giá trị → `applied += "duration"`, `consumed += spans`. **Không** mask, **không** bước trong `families_in_order` → `emptyReason: duration` không bao giờ phát (khai trong contract cho đủ họ vì `test_contract_declares_every_domain_constant`). Câu chỉ có duration → `applied_filters()` trả None → **không có** `appliedFilters`; `lexicalText`/`applied` vẫn phát.
- Dự phòng một dòng (ghi trong spec): nếu arm `_dur` tụt slice `named_entity` thì "N ngày" trần chỉ khai, không consume.

### 3.2 Gazetteer địa danh → F1 — `domain/search/gazetteer.py` (mới)

- Pattern `amenities.py`: tuple `Place(key, name, kind, aliases, destination, entity)` frozen; `kind ∈ {landmark, area, district, airport, venue}`; `aliases` đã fold, duy nhất toàn `PLACES`; `destination` = giá trị catalog hoặc None (brand nhiều site); `entity` = khoá entity cho venue, None cho các kind khác. Chỉ import `.lexical.fold`, `.normalize.spans/find_phrases`; không I/O (Docker chỉ ship `src/backend`).
- API: `place_table(destinations=None)` (alias → Place cho entry **có** destination; khi truyền tập catalog thì bỏ entry có destination ∉ catalog — luật `normalize.py` L145); `entity_table()` (alias → khoá entity cho entry **có** entity); `entities_of_name(name, table)`; `MAX_ALIAS_TOKENS`; `ENTITY_TAXONOMIES = {attraction, combo}`.
- Seed (đã đối chiếu 38 destination bench): brand (destination None) `vinwonders` (vinwonders, vinwonder, vin wonders, vinpearl land), `safari` (safari, vinpearl safari), `grand_world` (grand world, mega grand world), `aquafield`; venue một site (destination + entity): `hon_tam` → Nha Trang, `vinpearl_harbour` → Nha Trang, `vinke` (vinke, vinpearl aquarium) → Hà Nội, `grand_park` → TP. Hồ Chí Minh, `wave_park` → Hà Nội, `horse_academy` → Hải Phòng; site entry chép từ `src/data_collection/collectors/venues.csv` (23 dòng) với `entity` = khoá brand (`vinwonders_nha_trang`, `_phu_quoc`, `_nam_hoi_an`, `_cua_hoi` → Nghệ An, `_vu_yen` → Hải Phòng, `safari_phu_quoc`, `grand_world_phu_quoc`, `grand_world_ha_noi`, `aquafield_nha_trang`, `aquafield_ocean_city`…); golf **không** là entity (là sản phẩm `golf`). Landmark/area/district/airport chỉ cho destination catalog: Hà Nội (`ho_hoan_kiem`: ho hoan kiem, ho guom, hoan kiem lake; `quan_hoan_kiem`; `pho_co_ha_noi` — không "pho co" trần; `ho_tay`; `times_city`; `ocean_city`; `noi_bai`), Đà Nẵng (`cau_rong`/dragon bridge, `my_khe`, `ba_na`: ba na, ba na hills, sun world ba na; `son_tra`; `ngu_hanh_son`), Hội An (`pho_co_hoi_an`, `an_bang`, `cua_dai`), Nha Trang (`hon_tre`, `bai_dai`, `cam_ranh`), Phú Quốc (`bai_sao`, `bai_truong`, `duong_dong`, `an_thoi`), TP.HCM (`quan_1`, `ben_thanh`, `tan_son_nhat`), Hạ Long (`bai_chay`, `tuan_chau`), Đà Lạt (`ho_xuan_huong`), Sa Pa (`fansipan`), Huế (`lang_co`), Phan Thiết (`mui_ne`), Ninh Bình (`trang_an`, `tam_coc`). Không Vũng Tàu (không phải destination catalog).
- Luật vệ sinh (docstring + test): alias không trùng khoá `DESTINATION_ALIASES`, destination đã fold, khoá `VERTICAL_CUES`, `BRAND_CUES` ("vinpearl"); không "thuy cung" trần (va "thuỷ cung hoà bình").
- Nối vào `build_query_plan` **trước F1, sau F5** (F5 vẫn dùng `nq.destination_spans` gốc): `hits = gaz.place_hits(text, nq.destination_spans, excluded=negation.spans)`; `location = hits[0].place`; `poi_destinations` = destination của hit chưa có trong `nq.destinations`; `nq_dest = replace(nq, destinations=(*nq.destinations, *poi_destinations))` → `decide_destination(nq_dest, …)` **không đổi**: một → lọc `source="query"` (giữ FR-SRC-04 fallback, `drop_tokens`, enum `destinationFilter.source` đóng); ≥ 2 → `skipped=multi` ("khách sạn Hà Nội gần Cầu Rồng"); câu bay → `skipped=flight`. `_fallback_reasons(text, nq, …)` giữ `nq` **gốc** → confidence và tập kích hoạt LLM không đổi.
- Nguồn gốc: `QueryPlan.poi_destinations`, `QueryPlan.location`, property `destination_via_poi = destination.source == "query" and destination.value in poi_destinations`. **Không** dùng `value not in nq.destinations` — sai với "vé máy bay HAN DAD" (route override cho `candidates=()` với `nq.destinations == ()`). `hard.destinationSource = "poi"` khi `destination_via_poi`. `derivedDestinations` ← `plan.destination.candidates` (≡ `nq.destinations` khi POI không thêm gì).

### 3.3 Entity gate cứng — luật vai trò

- Catalog: `UnitAttributes.entities: tuple[frozenset[str], ...]` nối sau `children`, điền trong `build()` từ **tên unit**, allow-list `taxonomy ∈ {attraction, combo}` áp lúc build → **không sửa loader** (`postgres_store.py`, `in_memory_vector_store.py`, `app_adapter.py`, prewarm đều gọi `build(units, children, kinds)`).
- Mask: `UnitIndex.mask(..., require_entities=())` — sau `min_occupancy`: `req = frozenset(k for k in require_entities if k); if req: m &= [bool(e & req) for e in entities]`. Không thêm `entity_taxonomies` (allow-list đã trong data; `taxonomy` param và F3 `exclude_taxonomies` AND qua kwargs sẵn có).
- Vai trò (trong `build_query_plan`, sau F4, trước F5, chỉ khi `flags.entity`): `entity_keys = gaz.entity_keys(text, excluded=negation.spans)` ("không lấy VinWonders, vé Safari" → chỉ safari); nếu có: `gate = vertical.skipped != multi and (vertical.taxonomy is None or vertical.taxonomy in ENTITY_TAXONOMIES)`; `role = gate ? "gate" : "location"`; gate → `applied += "entity"`. Entity token **không** consume (tên sản phẩm; tiền lệ `POI_BRAND_CUES`).
- Ma trận đã kiểm bằng `parse_vertical`: c0697 "khách sạn ở Grand World Phú Quốc" → hotel/strong → **location** (giữ KS); "phòng gần Grand World" → hotel/**weak** → location (luật "chỉ cue mạnh" sẽ gate sai → bác); "khách sạn gần biển và vé VinWonders" → multi → location; "combo VinWonders Phú Quốc" → combo → gate; "vé VinWonders và Safari" → attraction → gate với OR; "Grand World Phú Quốc" trần → attraction/weak → gate (ẩn 8 KS tên Grand World — chấp nhận, c0697/c0700 đo cả hai phía); c0709 "khách sạn Vinpearl ở Nha Trang" → không có khoá entity; c0703 "vé lẻ VinWonders, không lấy combo" → gate ∧ F3 `exclude_taxonomies=[combo]` → {attraction}.
- Tham số `taxonomy` của request **không đổi role** (tab Web fan-out): `taxonomy=hotel` + gate → bước `entity` trong `families_in_order` (ngay sau bước taxonomy-query) làm rỗng → `emptyReason: entity` (không phải `param`), total 0, tab Lưu trú hiện (0). Gate role không đưa destination vào F1.
- Chỉ khoá entity **có mặt** trong `attrs.entities` mới vào `PlanGazetteers.entities` (entity không có sản phẩm không bao giờ gate — gương `DESTINATION_ALIASES` validation).
- Không sửa F4: F4 tắt ở prod, cue yếu đã do `SEARCH_TAXONOMY_STRONG_ONLY` quản; tập taxonomy của gate ⊆ {attraction, combo} nên F4 không nới quá. Ghi "F4 bật + entity bật → AND" vào hop-dong §2.2 + 1 test.

### 3.4 Contract 1.18.0 (additive)

- Ba object đóng dưới `queryPlan`, sau `party`, trước `lexicalText`, tiền tố `(1.18.0)`: `duration {days, nights (int|null ≥ 1), source: [query]}`, `entity {keys: [string] minItems 1, role: [gate, location]}`, `location {key, name, kind: [landmark, area, district, airport, venue], destination}`.
- `applied` enum += `duration`, `entity`; `emptyReason` enum += `entity`, `duration` (duration không bao giờ phát). `appliedFilters.hard` += `entity` (list), `destinationSource = poi`. Mô tả `lexicalText` += "thời lượng"; `destinationFilter`: điểm đến suy từ POI vẫn `source = query`; `derivedDestinations` gồm điểm đến từ POI khi cờ bật; block comment "KỂ CẢ khi mọi cờ tắt" thêm ngoại lệ 3 khối 1.18.0 (tiền lệ `party`).
- **Không đổi**: enum `destinationFilter.source`, `stageMs`, `llm`, `paths/search.yaml`, mocks, request schema.
- Ghim version: `openapi.yaml`, `main.py`, `test_search_contract.py`, `test_search_llm_contract.py` → 1.18.0. Regen `src/frontend/src/types/api.gen.ts` (hấp thụ luôn drift 1.17 `queryPlan.llm`; FE chỉ đọc `facets/total/topScore/diagnostics.totalExact` → không sửa component).

### 3.5 Chính sách phát (emission) và bất biến

- **Parse chỉ khi cờ bật** (Q8): cờ tắt ⇒ `DurationParse()` / `()` / None, không có đường code mới chạy, không `hide` mới trong `_plan_diagnostics`, `test_search_v116_defaults` giữ nguyên → response **byte-identical 1.17.0**. Chi phí chấp nhận: parse accuracy trường mới chỉ đo được trên arm `_dur/_poi/_ent`.
- Dense text **không đổi** (khoá cache embed); chỉ `lexical_text` bỏ span.
- `confidence` / tập kích hoạt LLM **không đổi** (`_fallback_reasons` dùng `nq` gốc; không thêm `REASON_*`).
- Không re-embed, không DDL, không thêm tham số request, không đổi facet contract.
- Log: `search_log.py` chép `appliedFilters.hard` nguyên → `entity`, `destinationSource: poi` tự vào `app.search_logs.filters` (jsonb); khoá không được tên `confidence`/`llm`.

### 3.6 Thứ tự parse trong `build_query_plan` khi cả ba cờ bật

Thứ tự này ghi vào docstring module `query_plan.py` và vào spec (Bước 1); mỗi bước mới chỉ chạy khi cờ của nó bật, các bước cũ không đổi vị trí.

| # | Bước | Có sẵn? | Đầu vào bảo vệ / loại trừ | Ghi ra |
|---|---|---|---|---|
| 1 | Giá / sao (`parse_numeric`) | có (F6) | — | `numeric.spans` |
| 2 | **Thời lượng (`parse_duration`)** | **mới, F7** | `protected = numeric.spans + party.spans` | `duration`, consume span, `applied += duration` |
| 3 | Số khách (`parse_party`) | có | — | `party.spans` |
| 4 | Phủ định (`parse_negation`) | có (F3) | — | `negation.spans`, `exclude_taxonomies` |
| 5 | Loại sản phẩm (`parse_vertical`) | có (F4; tắt prod) | — | `vertical.taxonomy`, `strength`, `skipped` |
| 6 | **Vai trò entity (`gaz.entity_keys`)** | **mới** | `excluded = negation.spans`; chỉ khoá có trong `attrs.entities` | `entity_keys`, `entity_role`; gate → `applied += entity`; **không** consume |
| 7 | Tuyến bay / IATA (F5 `city_spans`) | có | `nq.destination_spans` gốc | `route`, `flight_context` |
| 8 | **Địa danh (`gaz.place_hits`)** | **mới** | `known = nq.destination_spans`, `excluded = negation.spans` | `location`, `poi_destinations`, `nq_dest` |
| 9 | Điểm đến (`decide_destination(nq_dest, …)`) | có (F1) | — | `destination` (`source = query`), `skipped ∈ {multi, flight, param}` |
| 10 | `_fallback_reasons(text, nq, …)` | có | `nq` **gốc** | `confidence`, lý do → LLM trigger **không đổi** |

Thứ tự dò họ làm F rỗng (`families_in_order`, quyết định `emptyReason`; hiện tại: taxonomy-query → route → price → star → party → mustNot): chèn **entity** ngay sau bước taxonomy-query. Duration không có bước. Điểm đến (F1) không nằm trong danh sách này — use case xử lý riêng bằng đường fallback FR-SRC-04 (`destinationFilter.fallback`), POI đi chung đường đó. Lưu ý docstring hiện ghi "cờ tắt thì vẫn parse để khai" cho F1–F6; ba họ mới theo Q8 **không** parse khi tắt — docstring Bước 4 phải ghi rõ hai chế độ.

### 3.7 Xác nhận trước khi code (AGENTS §1.3) — đăng trước commit Bước 3

- File đã đọc: `docs/prd/README.md`, `requirements.md` §1.1 (FR-SRC), §3 (AC-SRC-01), `architecture.md` §2/§5/§6, `api-contract.md` (nguyên tắc), `docs/spec/contracts-guide.md`, `search.yaml` + `paths/search.yaml` + `schemas/common.yaml`, `hop-dong-tich-hop-search-recommendation.md` §2.2/§2.4/§2.5/§9/§10, `kien_truc…` §6/§17, `src/backend/README.md`, `docs/prd/update/` (4 đề xuất chờ), `history/README.md`, 10 entry mới nhất và mọi entry `search-*` từ 2026-10-05.
- FR/AC: FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01; NFR-PERF-01.
- Ràng buộc: contract trước code (AGENTS §3); không xoá/đổi field v1; cờ mặc định tắt; dense text không đổi; không DDL; `domain` không import `application`/`infrastructure` (`tests/architecture`).
- Việc dang dở liên quan: Bước 0 đã xong; `history/2026-10-07-streamlit-search-pipeline-debugger.md` (debug app — Bước 8 sửa thêm 3 checkbox).
- Lệch PRD: **không** (§11). Điểm chưa rõ: §9 C1–C7.

---

## 4. Thay đổi code theo thứ tự phụ thuộc

| # | Bước | File chính | Cổng | History |
|---|---|---|---|---|
| 0 | **Đã xong 07/10** — khôi phục regression merge `21d72ae` (so với `1eb7624`): `config.py` (`_OPTIONAL_BLANK_IS_NONE`, mặc định prod F1/F3/F5/F6, `search_llm_fallback*`), `main.py` (`search_hypothesizer` + 4 kwargs), PRD §5 + deployment-plan §2; **không** khôi phục khối Cohere/`EMBED_PROVIDER` (HEAD bỏ có chủ đích, `update-archive/2026-10-06-bo-duong-lui-cohere.md`) | `src/backend/app/core/config.py`, `main.py`, `docs/prd/architecture.md`, `docs/prd/deployment-plan.md`, `tests/unit/api/test_search_settings_wiring.py` | pytest + `test_production_defaults_restored` (157 passed) | `history/2026-10-07-restore-search-prod-defaults-llm-fallback.md` |
| 1 | Đổi tên spec `tong_hop_…` → `tong-hop-chinh-sua-luong-search-ota.md` (AGENTS §7); sửa dòng 3 (FR, contract 1.18.0); §2.1 → "Gap so với §17"; §3.1 dense không đổi; §3.3 → module gazetteer; §3.4 variant → taxonomy, `city` → `destination`, geo gắn P1, thêm c0697; §3.6 bỏ rewrite dense; §3.7 bỏ công thức tuyến tính → kênh RRF có trọng số (P1); §3.9 giữ contract facets; §4.1 → module; §4.3/§4.4 → P1 (+2/+10); §5 bỏ `SearchRequest` mới (P2), `SearchResponse` = khối 1.18.0; §6 theo `SearchProducts._retrieve` thật; §7 log = `app.search_logs.filters`; §8 `forbidden_filter` theo AST `store/filters.py`, slice nối cuối, §8.1 `taxonomy: hotel`; §10 → plan này; §12 quyết định 07/10. Ghi luật P0 §3 **nguyên văn** vào spec. Link từ hop-dong §2.2 và kien_truc §17 (L877 "1.16.0" → 1.18.0) | `docs/spec/bench/tong-hop-chinh-sua-luong-search-ota.md` | — | `history/2026-10-07-spec-tong-hop-chinh-sua-luong-search-ota.md` |
| 2 | Plan này | `docs/plan/2026-10-07-search-duration-entity-poi.md` | — | cùng entry Bước 1 |
| 3 | Contract 1.18.0 (§3.4) **trước code** | `src/shared/contracts/schemas/search.yaml`, `openapi.yaml`, `src/frontend/src/types/api.gen.ts` | `validate_contract.py` PASS; `npm run generate:api-types`; `git checkout -- src/shared/contracts/tests/__pycache__/bundle_openapi.cpython-313.pyc` | gộp entry Bước 4 |
| 4 | Domain: `gazetteer.py` (mới, §3.2), `constraints.parse_duration` (§3.1), `query_plan.py` (`APPLIED_DURATION/ENTITY`, `ROLE_GATE/LOCATION`, `PlanFlags += duration/poi/entity`, `PlanGazetteers += entities/places` + `entity_keys`/`place_hits`, `QueryPlan` trường mới + `destination_via_poi`, wiring §3.1–3.3, `mask_kwargs`, `families_in_order`, `as_diagnostics`, `applied_filters`, docstring thứ tự parse), export `domain/search/__init__.py` | `src/backend/app/domain/search/{gazetteer,constraints,query_plan,__init__}.py` | `pytest src/backend/tests/unit/domain` | `history/2026-10-07-search-duration-poi-entity-contract-1-18-0.md` |
| 5 | Catalog + mask: `UnitAttributes.entities` (build từ tên, allow-list), `UnitIndex.mask(require_entities=())` | `src/backend/app/domain/catalog/unit_attributes.py`, `application/ports/unit_index.py` | `test_unit_attributes`, `test_unit_index_mask` | cùng entry Bước 4 |
| 6 | Application/config/main/env: `SearchProducts` += `duration_filter/poi_resolve/entity_filter` (theo `derive_plan`; docstring "năm cờ họ" → "tám"); `_plan_gazetteers(units, *, entities, destinations)`; `derivedDestinations` ← `candidates`; `config.py` 3 setting False (+ comment entity "đổi số đếm tab Web khi bật — cần Web xác nhận"); `main.py` 3 kwargs + log; `.env.example` khối "07/10 (contract 1.18.0): mặc định tắt" | `application/search/use_cases.py`, `core/config.py`, `main.py`, `.env.example` | `pytest src/backend/tests -q` | cùng entry Bước 4 |
| 7 | Tests backend: mới `unit/domain/test_gazetteer.py`, `unit/application/test_search_v118_families.py`; sửa `test_constraints` (bảng §3.1), `test_query_plan` (NEW_FEATURE_QUERIES += 3 câu; ma trận role; POI; **"vé máy bay HAN DAD" + poi → `destination_via_poi is False`**; `families_in_order`; reasons y hệt khi 3 cờ bật; F4 + entity AND), `test_unit_attributes`, `test_unit_index_mask` (`require_entities=()`/`[""]` identity), `test_search_v116_defaults` (EXTRA += "vinwonder 3 ngay 2 dem", "khách sạn gần Hồ Hoàn Kiếm", "khách sạn Nha Trang 2 đêm"; assert không có `duration/location/entity`), `test_search_log`, `test_search_settings_wiring`, `contract/test_search_contract.py` (ALL_ON += 3; CASES += "vé VinWonders 3 ngày 2 đêm", "khách sạn gần Hòn Tằm", "resort gần Bãi Sao", ("VinWonders Nha Trang", taxonomy=hotel); `seen` += 3 khối), `test_search_llm_contract.py`. Chạy không đổi: `test_dest_filter`, `test_query_plan_filters`, `test_itinerary_engine_tools` | `src/backend/tests/**` | `python -m pytest src/backend/tests -q` (gồm `architecture/test_import_rules.py`) | cùng entry Bước 4 |
| 8 | Bench + gold (§5) | `src/evaluation/search_bench/**`, `gold/v6a/**` | bench tests; `topids-diff` identity rỗng; probe guards | `history/2026-10-07-search-bench-arms-slices-duration-poi-entity.md`, `history/2026-10-07-gold-v6-duration-poi.md` |
| 9 | Đồng bộ docs + rollout (§6): hop-dong §2.2 (khối "Từ 2026-10-07 (contract 1.18.0, mặc định tắt)…", hoà L179–182 về cue yếu VinWonders/Safari/Grand World, L192 duration consume, L193–195 emptyReason entity, sửa L188–191 + §10 S17 về LLM fallback đã ship 1.17.0), §2.4 knob YAML += `durationFilter/poiResolve/entityFilter: false` (+ `llmFallback` đang thiếu), §2.5 Hard `entity` + `poi` ở destinationSource, §9 tiêu chí 10d/10e, §10 S18; kien_truc §17 3 dòng "chưa đo"; `product.md` §4.2.3 ghi chú `SEARCH_ENTITY_FILTER` như F4. **Không** thêm dòng F7/POI/entity vào `deployment-plan.md` (F1–F6 chưa từng có) | `docs/spec/hop-dong-tich-hop-search-recommendation.md`, `docs/spec/bench/kien_truc_…md`, `docs/spec/product.md` | — | trong entry Bước 4/8 |

Lệnh chạy trên Windows: `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest src/backend/tests -q -p no:cacheprovider` từ repo root.

---

## 5. Bench và gold

### 5.1 Bench wiring (`src/evaluation/search_bench`)

- `app_adapter.py`: khoá **tuỳ chọn** `V118_FLAG_KEYS = ("duration_filter", "poi_resolve", "entity_filter")` đọc trong `app_params` (`setdefault(k, False)` + kiểm bool), vào `NEUTRAL`, chuyển qua `supported_kwargs(SearchProducts, …, V118_FLAG_KEYS, bool)` ở `make_search` (backend cũ chỉ lỗi khi cờ True). **Không** vào `APP_DEFAULTS`: `config_hash` băm `arm.app` từ YAML → 55 YAML, hash và `regression/baseline_v1.json` giữ nguyên (tiền lệ `app.llm` "vắng ≡ off"). `applied_filter_of` không đổi (entity purity đo bằng Forbidden@10).
- `metrics.py`: `PARSE_FIELDS` += `duration_days`, `duration_nights` (INT), `entity` (LIST), `entity_role`, `location_entity` (STR); `plan_fields` đọc `queryPlan.duration.days/nights`, `sorted(entity.keys)`, `entity.role`, `location.key`.
- Arm: `APP.e5s.prod_f12356_dur`, `_poi`, `_ent`, `_dur_poi_ent` (chép `APP.e5s.prod_f12356.yaml` + khoá, `parent: APP.e5s.prod_f12356`, `composite: true` cho arm cuối); `docs/spec/bench/arms.md` thêm "Knob 07/10 (contract 1.18.0, tuỳ chọn như `app.llm`)".
- Slice: nối **cuối** `gold_schema.SLICES` → `duration_false_positive`, `poi_resolution` (`sb gold split` seed theo `SLICES.index`; golden `test_gold.py` không đổi); `config/sbench.yaml gold.slices` quota 9 + 12 → `target 232`, `minimum ≥ 51`; `tests/test_config.py`; `__main__.py` gold-scan `PlanFlags` += 3.
- `debug_search_app.py`: badge 1.18.0; 3 checkbox mục 4; `PlanFlags`; truyền `index.attrs.entities` vào `_plan_gazetteers`.
- Tests: `test_app_adapter.py` (vắng ≡ off; non-bool bị từ chối; True trên backend thiếu field → raise), `test_metrics_phase_a.py`, `test_config.py`.

### 5.2 Identity → probe → gold_v6 → đo

Chạy từ `src/` với `..\.venv-sbench\Scripts\python -m evaluation.search_bench`, `PYTHONUTF8=1`, `PYTHONPATH=<repo>/src`, option toàn cục trước subcommand.

1. **Identity:** `sb --run-id 2026-10-07-identity run --arm APP.e5s.prod_f12356` → `sb --run-id 2026-10-07-identity topids-diff 2026-10-06-gold-v4-r2 APP.e5s.prod_f12356 --run-b 2026-10-07-identity` phải **rỗng**.
2. **Probe fixture** (Q9): `gold/v6a/probe.jsonl` ngoài `gold/` → version `fixture:<sha8>`, run-id `2026-10-07-v6a-probe`, **không trích dẫn** trong report chính thức; 21 câu c0736–c0756 (bảng §5.3) → `sb --run-id 2026-10-07-v6a-probe run --gold … --arm APP.e5s.prod_f12356 --arm …_dur --arm …_poi --arm …_ent --arm …_dur_poi_ent` → `guards --arms …` (không `--recompute`): parse_accuracy trường mới ≥ 0,9, `forbidden_at_10 = 0`.
3. **Gold v6a:** `gold/v6a/drafts_raw.tsv` (case_id, query, slice, filter_json, expected_no_result, source_refs, review_note; khối 3 câu/ý định từ c0736) + `drafts.txt` → `sb gold pool --drafts … --raw … --out gold/v6a/pool.csv --arm E2.e5s` (cần `sb collection create --variant T3+R --model e5-small` + `sb load`) → `sb gold split --pool … --overlap 0 --out-dir gold/v6a` → QAnh gán nhãn (app) → `sb gold merge … -o gold/v6a/labels/merged.csv` → `sb gold import merged.csv --meta pool_meta.json --append --provenance pool@gold_v6` → **chỉ sau import** thêm c0736–c0756 vào `config/query_annotations.yaml` (expected_parse + forbidden_filter + allowed_variants) → `sb gold check`, `sb gold verify-append gold_v5` → holes (`sb --run-id <r> run … --allow-untagged`; `sb gold holes --arms … --new-since gold_v5 --tag D10a`) → người dùng `git tag gold_v6` → `sb gold devtest` (report ghi qid đổi bên dev/test).
4. **Run đo** `2026-10-07-dur-poi-ent` 5 arm → `compare` dev/test, `guards`, `rescore`, `regress check --arm APP.e5s.prod_f12356`.
5. **Guard hồi quy** (không tệ hơn trên `_ent`/`_dur_poi_ent`): c0697, c0709, c0703, c0700, c0472, c0372, c0316/c0321/c0324/c0332/c0336/c0338.
6. **Report** `src/evaluation/reports/eval-2026-10-07-search-duration-entity-poi.md` (header theo `eval-2026-10-06-search-query-plan-gold-v4.md`: commit, run id, gold tag, split, win rule, bảng nguyên văn, caveat HNSW, lệnh tái sinh).

### 5.3 Draft 21 câu (expected_parse chỉ trường cần so; `taxonomy` chỉ so khi F4 bật)

| qid | slice | câu | expected_parse | forbidden_filter |
|---|---|---|---|---|
| c0736–c0738 | duration_false_positive | vinwonder 3 ngay 2 dem · VinWonders 3 ngày 2 đêm · combo VinWonders 3N2Đ | duration 3/2, entity [vinwonders], role gate (c0738 taxonomy combo) | `{in:[taxonomy,[hotel,golf,flight]]}` |
| c0739–c0741 | duration_false_positive | khách sạn Đà Lạt 2 đêm · ks da lat 2 dem 3 ngay · Dalat hotel 3 days 2 nights | destination Đà Lạt, duration (None,2)/(3,2)/(3,2) | `{not:{eq:[destination,"Đà Lạt"]}}` |
| c0742 | duration_false_positive | khách sạn gần chợ đêm Đà Lạt | destination Đà Lạt, duration null | như trên |
| c0743 | duration_false_positive | tour VinWonders Phú Quốc 3 tiếng | duration null, entity [vinwonders] | `{in:[taxonomy,[hotel,golf,flight]]}` |
| c0744 | duration_false_positive | phòng dưới 2 triệu/đêm Nha Trang | price_max 2000000, duration_nights null | `{not:{eq:[destination,"Nha Trang"]}}` |
| c0745–c0747 | poi_resolution | khách sạn gần Hồ Hoàn Kiếm · ks gan ho guom · hotel near Hoan Kiem lake | destination Hà Nội, location_entity ho_hoan_kiem | `{not:{eq:[destination,"Hà Nội"]}}` |
| c0748–c0749 | poi_resolution | khách sạn gần Cầu Rồng · ks gan cau rong da nang | destination Đà Nẵng, location_entity cau_rong | `{not:{eq:[destination,"Đà Nẵng"]}}` |
| c0750–c0751 | poi_resolution | resort gần biển Mỹ Khê · vé Bà Nà Hills | destination Đà Nẵng, location my_khe / ba_na | như trên |
| c0752 | poi_resolution | homestay phố cổ Hội An | destination Hội An, location pho_co_hoi_an | `{not:{eq:[destination,"Hội An"]}}` |
| c0753 | poi_resolution | khach san gan san bay Noi Bai | destination Hà Nội, location noi_bai | `{not:{eq:[destination,"Hà Nội"]}}` |
| c0754 | poi_resolution | khách sạn gần VinWonders Nam Hội An | destination Hội An, entity [vinwonders], role location | `{or:[{not:{eq:[taxonomy,hotel]}},{not:{eq:[destination,"Hội An"]}}]}` |
| c0755 | poi_resolution | khách sạn gần Hồ Gươm hoặc Hồ Tây | destination Hà Nội (hai POI cùng city) | `{not:{eq:[destination,"Hà Nội"]}}` |
| c0756 | poi_resolution | khách sạn gần Hồ Gươm hoặc Cầu Rồng | destination null, location_entity null (multi) | — |

Quy ước: `forbidden_filter` theo AST `store/filters.py` (`{not:{eq:[…]}}`, `{in:[…]}`, `{or:[…]}`; không có `neq`); mỗi ý định một cách nói chính + biến thể không dấu/tiếng Anh trong cùng khối 3; probe không trùng ý định qid gold cũ (c0446 "vé VW Nha Trang", c0472 "vé Safari PQ" đã có nên không lặp).

---

## 6. Rollout

| Bước | Điều kiện | Hành động |
|---|---|---|
| R0 | Merge code với mọi cờ **tắt** | Response ≡ 1.17.0 (identity `topids-diff` rỗng; `test_search_v116_defaults`). Deploy bình thường, không đổi `.env` VM. |
| R1 | Bench trên gold_v6: `_dur`, `_poi` **WIN/TIE** trên test + `forbidden_at_10 = 0` ở slice mới + guards xanh + 12 qid hồi quy không tệ hơn + p95 không tăng > 30 % | Bật `SEARCH_DURATION_FILTER=true`, `SEARCH_POI_RESOLVE=true` trong `.env` VM (ngoài repo). |
| R2 | Như R1 cho `_ent` **và** Web ký xác nhận (ghi cạnh `docs/spec/product.md` §4.2.3 L281, như ghi chú F4 05/10): tab Lưu trú có thể (0) cho câu entity; FE không đọc `emptyReason` → empty state chung | Bật `SEARCH_ENTITY_FILTER=true`. Trước đó chạy `test_itinerary_engine_tools.py` với cờ bật (Agent không truyền `derive_plan` → gate áp cả tool Agent). |
| Smoke | Sau mỗi lần bật | `GET /api/v1/search?q=vinwonder%203%20ngay%202%20dem` không có hotel "Ngay Chợ Đêm"; `q=khách sạn gần Hồ Hoàn Kiếm` → `appliedFilters.hard.destinationSource == "poi"`, chỉ Hà Nội; `/health/ready` không đổi. |
| Theo dõi | 48 h sau bật | `app.search_logs.filters.entity` / `destinationSource = poi`: tỷ lệ zero-result theo giờ; so với 48 h trước. |
| Rollback | Bất kỳ lúc nào | Bỏ biến env → mặc định tắt → không parse, không khai. Không cần deploy lại code. |

---

## 7. P1 — Geo (phác thảo, contract 1.19.0)

- `Place` += `lat/lon/radius_m` (additive); `UnitAttributes.latitude/longitude` (float64, NaN) + `location_precision` (object "") từ `attributes` (100 % phủ).
- `UnitIndex.mask(near=(lat, lon, radius_m))` haversine numpy — precision `destination`/`airport` hoặc NaN = không biết → **giữ** ([C2]) và demote bằng `soft_geo_order` (partition ổn định như `soft_star_order`); F rỗng → radius ×2 → destination-only, khai bằng trường fallback **cấp location** (không tái dùng `destinationFilter.fallback`; kien_truc §6 cấm nới filter suy ra khác điểm đến).
- Xếp hạng = kênh thứ 4 trong `hybrid.rrf` (`legs`) với `HybridConfig.geo_weight` mặc định 0 (số y hệt khi tắt) — **không** fusion tuyến tính (bỏ §3.7 đề xuất).
- 1.19.0: `queryPlan.location.radiusM/fallback`, `emptyReason + geo`, `stageMs.geo`, `ScoredProduct.distanceKm`; `duration.source + param` (travelContext nights) + soft order theo `duration_days` parse từ tên unit; POI sân bay cấp cho F5 `city_spans`; entity combo qua `combo_items.item_product_id` (+10 combo đo ở §2; cần `_COMBO_QUERY` + 3 loader); bench cột RAM `entity_keys`/`distance_km` + `contains_any`/`lte`, slice `geo_radius` nối cuối, arm `_geo` (parent `_dur_poi_ent`); cờ `SEARCH_GEO_FILTER` tắt; tuỳ chọn `validate_hypothesis` bỏ chữ số trong span duration.
- Mở P1 chỉ sau khi P0 có report và người dùng chốt; mọi trường 1.19.0 là khối đóng → **không** khai trước ở 1.18.0.

---

## 8. Definition of Done / tiêu chí nghiệm thu

**Track contract + backend (Bước 3–7)**
1. `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py` PASS; `openapi.yaml` 1.18.0; `api.gen.ts` regen và `git diff --exit-code` sạch sau commit; `npm run build` FE xanh.
2. `python -m pytest src/backend/tests -q` toàn bộ xanh (unit domain/application/api, contract, architecture import rules); độ phủ `domain`/`application` ≥ 80 % (DoD implementation-plan §4).
3. Cờ tắt: `test_search_v116_defaults` (157+ câu, EXTRA += 3) và `test_new_kwargs_defaults_identical` không đổi; `Settings()` mặc định 3 cờ False.
4. Chạy tay `build_query_plan` trên 5 câu gốc của đề xuất với cờ bật/tắt, đối chiếu bảng §3.1/§3.3.

**Track bench + gold (Bước 8)**
5. `pytest src/evaluation/search_bench/tests -q` xanh; golden `gold_small` không đổi; `topids-diff` identity rỗng; 55 arm YAML + `baseline_v1.json` không đổi hash.
6. Probe fixture: parse_accuracy trường mới ≥ 0,9, `forbidden_at_10 = 0` trên `_dur_poi_ent`.
7. Tag `gold_v6`: `sb gold check` PASS (mỗi slice ≥ 3, câu trong catalog ≥ 1 nhãn 2), `verify-append gold_v5` PASS (+21 qid, 0 nhãn cũ đổi), annotations chỉ sau import; `devtest` report liệt kê qid dời dev/test.
8. Report `eval-2026-10-07-search-duration-entity-poi.md` đủ header, bảng nguyên văn, caveat, lệnh tái sinh; 12 qid hồi quy có bảng riêng.

**Chung**
9. Spec đã đổi tên và sửa theo Bước 1; hop-dong §2.2/§2.4/§2.5/§9/§10, kien_truc §17, `product.md` §4.2.3, `arms.md` đồng bộ trong cùng thay đổi (AGENTS §4).
10. Mỗi bước một entry `history/` theo bảng §4 (đối chiếu `git status`), nằm trong cùng commit.
11. Không chạm `db/` → không cần `verify.sql`. Không chạm mock → `validate_contract.py` chỉ vì contract.

---

## 9. Việc cần người dùng chốt

| # | Câu hỏi | Khuyến nghị |
|---|---|---|
| C1 | **Web sign-off** `SEARCH_ENTITY_FILTER`: chấp nhận tab Lưu trú (0) cho câu chỉ nêu entity; FE không đọc `emptyReason` nên empty state chung; gợi ý UX theo `product.md` §4.2.4 là việc FE sau. Ghi xác nhận cạnh `product.md` §4.2.3 L281 | Bật `_dur`/`_poi` trước, không chờ Web; `_ent` chờ Web ký |
| C2 | Người gán nhãn gold v6a: chỉ QAnh (`split --overlap 0`, không κ, như D5 05/10)? | Có; report ghi tỉ lệ nhãn máy được giữ/sửa thay cho κ |
| C3 | Banner "kết quả yếu" của FE (`topScore < 0.35`) lệch contract §3.4 (0,70 / margin) — **ngoài phạm vi** plan này, chỉ ghi nhận? | Ghi nhận; FE tự xử lý sau |
| C4 | Cụm "và bảng địa danh / điểm vui chơi giữ trong repo (`domain/search/gazetteer.py`…)" thêm vào PRD §5 ở Bước 0 (khôi phục): xác nhận là **diễn giải** chữ "gazetteer" đã có, không lệch PRD? | Xác nhận không lệch; nếu người dùng coi là lệch thì tách thành đề xuất `docs/prd/update/` "không đổi hành vi" |
| C5 | Agent tool (`engine_tools.py`, `itinerary_http_clients.py`) không truyền `derive_plan` → gate áp cả Agent khi bật env (tool `taxonomy=hotel` + "VinWonders" → NO_RESULTS). Chấp nhận, hay Agent truyền `derive_plan=False`? | Chấp nhận ở P0 (chạy `test_itinerary_engine_tools.py` với cờ bật trước rollout); ghi lại nếu Agent trả NO_RESULTS bất thường |
| C6 | Đề xuất đang chờ `docs/prd/update/2026-10-06-search-hybrid-min-coverage-rrf.md` (minCoverage 0,6 → 0,1) làm hotel "Chợ Đêm" dễ được vớt hơn nếu F7 chưa bật — bench lại arm đó với slice duration sau gold_v6? | Có, sau gold_v6; không chặn plan này |
| C7 | Quota slice mới 9 + 12 (`target 232`)? | Chấp nhận; chỉnh sau khi QAnh ước lượng pool |

---

## 10. Rủi ro và giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| Consume "N ngày" làm mất bằng chứng BM25 trên 31 tên vé | Dense vẫn thấy câu đầy đủ; đo bằng arm `_dur` trên `named_entity`; dự phòng một dòng: "N ngày" trần chỉ khai, không consume (§3.1) |
| Gate ẩn hotel tên "Grand World" khi câu trần ("Grand World Phú Quốc") | Chấp nhận có chủ đích (Q1); c0697/c0700 đo cả hai phía; role `location` khi có cue loại khác kể cả yếu (Q7) |
| Entity không có sản phẩm trong catalog → gate rỗng oan | Chỉ khoá có mặt trong `attrs.entities` vào `PlanGazetteers.entities` (§3.3) |
| POI alias trùng tên điểm đến / cue loại / brand → parse sai | Test vệ sinh gazetteer (alias ∉ `DESTINATION_ALIASES`/`VERTICAL_CUES`/`BRAND_CUES`/destination fold); `place_hits` bỏ hit chồng `nq.destination_spans` |
| `destinationSource = poi` phát sai cho tuyến IATA ("vé máy bay HAN DAD") | `destination_via_poi` suy từ `poi_destinations` của chính pass POI, không từ `nq.destinations`; test riêng |
| Entity/POI nằm trong cụm phủ định ("không gần Hồ Gươm") | `excluded=negation.spans` cho cả `entity_keys` và `place_hits` |
| Cờ tắt mà response vẫn đổi (vi phạm Q8) | Parse chỉ khi cờ bật; identity `topids-diff` rỗng; `test_search_v116_defaults` 157+ câu; không `hide` mới |
| Contract test ép khai `emptyReason: duration` dù không bao giờ phát | Khai với mô tả "không bao giờ phát ở 1.18.0"; không tạo bước mask cho duration |
| Bench: thêm khoá vào `APP_DEFAULTS` làm đổi hash 55 arm và baseline | Khoá tuỳ chọn qua `supported_kwargs` (tiền lệ `app.llm`); test adapter "vắng ≡ off" |
| Agent nhận gate khi bật env prod (C5) | Chạy `test_itinerary_engine_tools.py` với cờ bật trước rollout; rollback = bỏ env |
| `devtest@gold_v6` dời qid cũ giữa dev/test (per-slice permutation) | Report liệt kê qid dời; so sánh thêm trên split cũ |
| Nhiễu HNSW ở arm APP | Lật đơn lẻ phải lặp lại ở lần chạy thứ hai mới tính; caveat trong report |
| Hạ tầng test: `.env` trỏ tunnel VM + Weaviate Cloud làm pytest chậm/treo | Chạy test với env sạch (`PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1`), không chạy embed job với `.env` nguyên trạng |
| Windows: pytest đọc contract lỗi cp1252 | Luôn `PYTHONUTF8=1` |

---

## 11. Đánh giá lệch PRD

**Không lệch PRD; không cần đề xuất `docs/prd/update/`.**

- F7, POI → F1 và entity gate là **filter suy từ câu, sau cờ mặc định tắt** — cùng loại với F1–F6 đã làm 05/10 theo tiền lệ `history/2026-10-05-search-dest-filter-no-diacritics.md` L12–14: người dùng chốt "lọc điểm đến từ câu là hiện thực FR-SRC-03 ('điểm đến do câu truy vấn quyết định'), không cần đề xuất PRD; làm sau cờ mặc định tắt, chỉ bật sau khi bench xác nhận".
- FR-SRC-03 ghi "Địa điểm: điểm đến, thành phố, khu vực" → địa danh gazetteer quy về điểm đến catalog là hiện thực đúng chữ PRD. FR-SRC-04: F rỗng do filter suy ra → `emptyReason`, không nới — giữ nguyên hành vi đã có.
- PRD `architecture.md` §5 (đề xuất đã chốt 06/10, khôi phục Bước 0) đã mô tả "luật + gazetteer" và "bảng địa danh / điểm vui chơi giữ trong repo (`domain/search/gazetteer.py`)" → module gazetteer đúng PRD (xác nhận C4 ở §9).
- **Không** thêm tham số request, **không** bảng DB, **không** đổi facet contract, **không** đổi `destinationFilter.source` enum; contract 1.18.0 additive theo quy tắc versioning `api-contract.md`.
- Cấu hình bench (arm, slice, quota, ngưỡng guard) là cấu hình nội bộ do người dùng chọn (spec §1.5, §1.7 #1), không phải PRD.

**Sẽ lệch PRD nếu làm — cần đề xuất `docs/prd/update/` trước (P2, ngoài plan):**
- (a) Tham số request mới (`durationNights`, `near`, `radiusKm`, `entity`…) như đề xuất §5 `SearchRequest` — FR-SRC-03 chỉ định nghĩa bộ lọc điểm đến/loại/hạng sao.
- (b) Bảng `location_entities` trong DB (đề xuất §4.1) — data-model.md không có; Q2 chọn module trong repo.
- (c) Lọc theo thời lượng khi catalog có trường `nights` — cần cập nhật data-model.md §3 `attributes`.
- (d) Đổi `topScore`/banner "kết quả yếu" của FE (C3) — thuộc hop-dong §3.4 và product.md, không thuộc plan này.

Bốn đề xuất đang chờ trong `docs/prd/update/` (`2026-10-05-go-golden-dataset-cu.md`, `2026-10-05-tach-ket-noi-doc-replica.md`, `2026-10-06-recsys-trong-so-ngan-han-pho-bien.md`, `2026-10-06-search-hybrid-min-coverage-rrf.md`) không chạm phạm vi plan này; riêng đề xuất minCoverage có tương tác với F7 — mục C6 ghi cách phối hợp.
