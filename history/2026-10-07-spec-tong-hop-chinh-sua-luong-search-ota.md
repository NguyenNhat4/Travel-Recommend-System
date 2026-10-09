# Spec "Tổng hợp chỉnh sửa luồng Search OTA" (duration · địa danh → F1 · entity gate) và plan triển khai

- Ngày: 2026-10-07
- Tác giả: tqanh123 (người dùng chốt) / Claude (Fable 5.1, orchestrator + 2 agent viết tài liệu)
- Nhánh: fix/search-production
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng đưa bản nháp `docs/spec/bench/tong_hop_chinh_sua_luong_search_ota.md` (3 lỗi production của `/search`: `vinwonder 3 ngay
2 dem` lẫn hotel "Chợ Đêm"; `khách sạn gần Hồ Hoàn Kiếm` facet nhiều điểm đến; landmark không map về thành phố) và yêu cầu
review với code, brainstorm, rồi chốt: sửa tài liệu trước khi coi là spec → lên plan → code. Review (có chạy parser và profile
catalog bench 3.183 unit) cho thấy pipeline đã có ~80 % kiến trúc đích; root cause thật: thiếu duration parser (hai hotel có cả
`ngay` lẫn `dem` trong TÊN → coverage 2/3 → vớt BM25), gazetteer chỉ có điểm đến catalog + 17 viết tắt (POI không resolve →
F1 không chạy); facets đã tính trên R sau mask nên chẩn đoán "facet trước filter" sai. Phục vụ FR-SRC-01, FR-SRC-03, FR-SRC-04,
AC-SRC-01; NFR-PERF-01.

## File thay đổi

- `docs/spec/bench/tong_hop_chinh_sua_luong_search_ota.md` — xoá (bản nháp untracked, tên gạch dưới sai AGENTS §7).
- `docs/spec/bench/tong-hop-chinh-sua-luong-search-ota.md` — thêm: spec đã sửa (511 dòng): dòng "Phục vụ FR…", §2.1 thành
  "gap so với kien_truc §17", luật P0 nguyên văn (gazetteer, parse_duration, query plan, mask, contract 1.18.0, gold/guard),
  bỏ fusion tuyến tính / rewrite dense text / `facetMeta` / `globalDiscovery` / tham số request mới / bảng DB `location_entities`
  / `[file:10]`, tên variant → enum taxonomy, lộ trình P0–P2.
- `docs/plan/2026-10-07-search-duration-entity-poi.md` — thêm: plan theo mẫu `2026-10-05-gold-v4a-mo-rong.md`: 9 quyết định đã
  chốt, chẩn đoán, thiết kế P0, thay đổi code theo thứ tự (Bước 0–9), bench/gold (slice mới nối cuối, probe fixture, 21 câu
  nháp c0736–c0756, 12 qid hồi quy), rollout, P1 geo, DoD, việc cần chốt, rủi ro, đánh giá lệch PRD (không lệch).

## Quyết định

Người dùng chốt 07/10 (ghi ở spec §1.2 và plan "Quyết định đã chốt"):
1. Entity gate **cứng**. 2. Gazetteer POI là **module Python trong repo** (`domain/search/gazetteer.py`), không bảng DB.
3. Facets **giữ contract** (tính trên R). 4. Geo vào **P1**. 5. Sửa tài liệu trước → plan → code.
6. Khôi phục regression merge `21d72ae` trước (`history/2026-10-07-restore-search-prod-defaults-llm-fallback.md`).
7. Entity + cue loại khác (kể cả cue yếu) → vai trò **location**; thương hiệu khách sạn (Vinpearl, Meliá) không phải entity.
8. Khối `queryPlan.duration/entity/location` **ẩn trừ khi cờ bật** (quy ước 1.16). 9. Probe fixture trước, gold_v6 sau.
- Không lệch PRD: filter suy từ câu sau cờ mặc định tắt (tiền lệ `history/2026-10-05-search-dest-filter-no-diacritics.md`);
  không thêm tham số request, không DDL. Mục cần tham số request (`locationEntityId`…) để P2, phải qua `docs/prd/update/`.
- Spec không ghi quy trình agent (AGENTS §8); chỉ luật nghiệp vụ / kỹ thuật.

## Kiểm tra

- `grep` spec mới: không còn `[file:`, `hotel_property`, `attraction_ticket`, công thức `final_score`; dòng 3 đúng mã FR.
- Không chạy test (chỉ tài liệu). Contract/code đi kèm ghi ở `history/2026-10-07-search-duration-poi-entity-contract-1-18-0.md`.

## Còn lại / rủi ro

- Plan §9: Web xác nhận trước khi bật `SEARCH_ENTITY_FILTER`; QAnh gán nhãn gold_v6; banner "kết quả yếu" FE lệch contract
  §3.4 (ngoài phạm vi); người dùng soát cụm "bảng địa danh … trong repo" thêm vào PRD `architecture.md` §5 ở Bước 0.
- Đề xuất đang chờ `docs/prd/update/2026-10-06-search-hybrid-min-coverage-rrf.md` (minCoverage 0,6 → 0,1) làm hotel "Chợ Đêm"
  dễ được vớt hơn nếu F7 chưa bật — bench lại cùng slice duration sau gold_v6.
