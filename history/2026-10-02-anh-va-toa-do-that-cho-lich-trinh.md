# Lịch trình chỉ hiện ảnh, tag, toạ độ và điểm đánh giá thật

- Ngày: 2026-10-02
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend, backend, agent, docs

## Mục tiêu

Giai đoạn 1 của kế hoạch "thẻ thật trong khung chat + panel chi tiết" (desktop). Người dùng đưa ảnh tham chiếu một trợ lý
khác: lịch trình kể theo ngày, mỗi địa điểm có thẻ ảnh/điểm đánh giá/địa chỉ thật. Trước khi làm thẻ mới phải sửa chỗ widget
đang bịa dữ liệu (FR-AGT-04, NFR-REL-01, FR-AGT-03; PRD `architecture.md` §3: `imageUrl` phải lấy nguyên từ tool;
`hop-dong-tich-hop-frontend.md` §9.5: tên, ảnh, giá chỉ lấy từ `product`, không từ `note`/`title`):

1. `widgetVisuals.ts` chọn ảnh Unsplash theo từ khoá trong tên/ghi chú **trước** ảnh catalog (luật 12/13). Từ khoá `'hố'`
   khớp cả "phố", nên "thành phố", "phố cổ" ra ảnh sân golf. Khách sạn không phải biệt thự luôn có tag "Resort 5★ biển",
   chú thích "Phòng nghỉ tiện nghi 5 sao" và ảnh hồ bơi stock. Ghi chú mặc định "Khách sạn lưu trú 5 sao", "tiêu chuẩn cao cấp".
2. Bản đồ đặt mọi điểm ở tâm thành phố (hoặc Nha Trang): `SUMMARY_ATTRIBUTE_KEYS` cắt mất `latitude`/`longitude`/`address`
   dù catalog có cho 100% sản phẩm (snapshot 2026-09-30) và `services/catalog.ts` có đọc.
3. 178 điểm tham quan có `rating`/`ratingScale` (thang 5) nhưng API trả `rating: null`: code chỉ đọc `reviewScore`. Nguồn
   `tripAdvisorRating` của `schema.md` §8.1 cũng chưa được hiện thực. `reviewCount` trả khác null khi `rating` null, trái
   `hop-dong-tich-hop-backend.md` §2.2.
4. Nhãn đoàn khách luôn "Cặp đôi" (so object `Party` với chuỗi `'family_with_kids'`), "Gia đình" khi không biết.
   Slot không có sản phẩm hiện enum thô (`MEAL`) làm tiêu đề và có ảnh stock.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/widgetVisuals.ts` — sửa: bỏ toàn bộ ảnh stock theo từ khoá, chỉ còn
  `hotelTags` dựng tag từ `attributes` thật (`starRating`, `oceanView`, `privateBeach`, `pool`; nhãn theo backend §2.5).
- `src/frontend/src/features/itinerary/widget/WidgetDays.tsx` — sửa: ảnh = `product.imageUrl`, lỗi thì placeholder theo
  loại. Thẻ khách sạn bỏ ảnh thứ hai, tag và ghi chú bịa. Nhãn loại theo `taxonomyLabel` (§6.1). Slot không có sản phẩm
  không có ảnh, hiện icon theo `activityType`. Ẩn dòng địa điểm khi không có.
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — sửa: bỏ bảng toạ độ tâm thành phố và toạ độ mặc định. Thêm
  `partyLabel` từ `intent.party`. Bỏ ghi chú khách sạn bịa và điểm đến mặc định "Nha Trang". Tiêu đề slot không có sản
  phẩm theo `ACTIVITY_TYPE_LABEL`. `locationName` là địa chỉ thật.
- `src/frontend/src/features/itinerary/widget/widgetTypes.ts` — sửa: `WidgetPlan.partyLabel`.
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — sửa: hiện `partyLabel`, ẩn khi `null`.
- `src/frontend/src/components/assistant/ItineraryMap.tsx` — sửa: số thứ tự điểm đếm mọi slot (kể cả slot không có toạ
  độ) để id điểm vẫn khớp `WidgetDays` và `locateProduct`.
- `src/frontend/src/services/catalog.ts` — sửa: export `placeholderImage(taxonomy)`.
- `src/frontend/src/types/travel.ts` — sửa: `ItinerarySlot.activityType`.
- `src/frontend/tests/unit/widgetPlan.test.ts` — sửa: test toạ độ chỉ từ catalog, `partyLabel`, `hotelTags`, không bịa ghi chú.
- `src/frontend/tests/unit/widgetDays.test.tsx` — thêm: chỉ có ảnh catalog (tên/ghi chú có "phố", "show"), tag thật,
  slot ghi chú không có ảnh.
- `src/backend/app/domain/itinerary/planning.py` — sửa: `SUMMARY_ATTRIBUTE_KEYS` giữ thêm `starRating`, `latitude`,
  `longitude`, `address`.
- `src/backend/app/domain/catalog/models.py` — sửa: `RATING_SOURCES` theo thứ tự §8.1 (`reviewScore` → `tripAdvisorRating` →
  `rating/ratingScale`); `review_count` cùng nguồn với `rating`, `rating` null thì null.
- `src/backend/tests/unit/domain/test_itinerary_composition.py` — sửa: khoá giữ lại trong summary.
- `src/backend/tests/unit/domain/test_catalog_listing.py` — sửa: thứ tự nguồn điểm, `reviewCount` null khi không có điểm.
- `docs/spec/data-collection/schema.md` — sửa §8.1: thêm nguồn 3 `rating`/`ratingScale`, quy tắc "nguồn đầu tiên thắng".
- `docs/spec/agent/field-review.md` — sửa §2.1: ghi chú sửa ngày 2026-10-02 (FE có đọc toạ độ/địa chỉ nên giữ thêm khoá).
- `history/2026-10-02-anh-va-toa-do-that-cho-lich-trinh.md` — thêm: entry này.

## Quyết định

- **Không lệch PRD**, không cần đề xuất: chỉ hiện thực đúng PRD `architecture.md` §3 và spec frontend §5, §6.6, §9.5.
  Contract không đổi: `ProductAttributes` là `additionalProperties: true`.
- Quyết định field-review §2.1 (2026-09-28) cắt `attributes` còn 4 khoá dựa trên tiền đề "FE chỉ đọc 4 khoá". Tiền đề
  này sai vì `productFromApi` đọc toạ độ/địa chỉ. Theo đúng điều kiện của chính quyết định đó ("FE đọc thì giữ"), giữ thêm
  ba khoá này và `starRating` (nay tag khách sạn đọc). `description` vẫn bỏ.
- Entry `2026-09-29-man-mo-dau-widget-ai.md` giữ nguyên ảnh/bản đồ cũ của widget cho phạm vi task đó. Entry này sửa phần ấy.
- Sản phẩm không có toạ độ thì không có điểm trên bản đồ, thay vì đặt giả ở tâm thành phố.
- Ảnh stock Unsplash ở trang chủ/danh mục (`destinationCovers.ts`, `verticals.ts`, `HomeView.tsx`) là ảnh bìa điểm đến,
  không phải ảnh sản phẩm, nên giữ nguyên.

## Kiểm tra

- `node_modules/.bin/vitest run tests/unit/widgetPlan.test.ts tests/unit/widgetDays.test.tsx`: 12/12 PASS.
- `node_modules/.bin/vitest run` (src/frontend): 50 file, 506 test PASS.
- `node_modules/.bin/tsc --noEmit`: không có lỗi ngoài `.next/` (lỗi sẵn có của route đã xoá).
- `eslint` các file đã sửa: 0 lỗi, 2 warning `react-hooks/exhaustive-deps` sẵn có ở `ItineraryMap.tsx`.
- `.venv/bin/python -m pytest -q src/backend/tests`: 1096 passed, 21 skipped.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (contract và fixture không đổi).

## Còn lại / rủi ro

- Chưa xem trực quan trên trình duyệt với backend + catalog thật (ảnh catalog, điểm trên bản đồ, tag khách sạn).
- Itinerary vẫn chưa có điểm đánh giá: Search (`application/search/use_cases.py` `hit`) không trả `rating`/`reviewCount`.
  Phần này đi cùng đề xuất thẻ trong khung chat (giai đoạn 2).
- Bố cục mobile (< 1024 px không mở được khung lịch trình) chưa sửa. Người dùng chốt mục tiêu là desktop, việc này để task riêng.
