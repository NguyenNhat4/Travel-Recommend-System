# Áp dụng thẻ sản phẩm trong khung chat và panel chi tiết (desktop)

- Ngày: 2026-10-02
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend, backend, docs

## Mục tiêu

Áp dụng đề xuất `docs/prd/update-archive/2026-10-02-the-va-panel-chi-tiet-trong-tro-ly.md`, người dùng chốt ngày 2026-10-02.
Hai thay đổi: lời diễn giải có thẻ gọn ngay sau lần nhắc đầu tiên của mỗi sản phẩm, và bấm thẻ hoặc tên sản phẩm thì mở
panel chi tiết ở cột phải. Phục vụ FR-AGT-03, FR-AGT-04, AC-AGT-01, NFR-REL-01.

## File thay đổi

- `docs/prd/user-flow.md` — sửa §3.2 và §4.2 theo đề xuất.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa §4.8 (hàng "Xem chi tiết sản phẩm trong widget") và §5 (`ItineraryProductCard`).
- `docs/spec/product.md` — sửa §4.8.1 (bỏ quyết định cũ "chỉ chứa thẻ tóm tắt") và §6.5 (thêm loại tin nhắn thẻ sản phẩm).
- `docs/prd/update/…` → `docs/prd/update-archive/2026-10-02-the-va-panel-chi-tiet-trong-tro-ly.md` — đổi trạng thái sang `đã áp dụng`, lưu trữ.
- `src/backend/app/application/search/use_cases.py` — sửa: `scored()` để Search/Similar trả `rating`/`reviewCount`.
  Recommendation vẫn dùng `hit` rút gọn theo spec backend.
- `src/backend/tests/unit/application/test_hybrid_search.py` — sửa: test kết quả Search có điểm đánh giá.
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx` — thêm: `narrationBlocks` tách lời diễn giải và chèn
  thẻ sau lần nhắc đầu tiên.
- `src/frontend/src/features/itinerary/widget/WidgetProductDetail.tsx` — thêm: panel chi tiết đọc `GET /products/{id}`.
  Gồm bộ ảnh, mô tả, địa chỉ với "Chỉ đường", giờ mở cửa, điểm đánh giá, giá, "Thêm vào giỏ", "Xem trang chi tiết".
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: `selectedProduct`, `openProductDetail` (thay
  `focusProduct`), `closeProductDetail`, `addPlanItemToCart`. Esc đóng panel trước.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx`, `FloatingWidget.tsx`, `widgetTypes.ts`, `widgetPlan.ts`
  (`narrationProducts`), `widgetVisuals.ts` (`placeholderOnError`), `WidgetDays.tsx` — sửa: nối thẻ và panel.
- `src/frontend/src/components/common/ProductCard.tsx` — sửa: bản compact thêm `onSelect`, `priceLabel`,
  `showRatingAndAddress` và placeholder khi ảnh lỗi. Giỏ hàng không truyền các prop mới nên không đổi.
- `src/frontend/tests/unit/widgetNarration.test.tsx`, `widgetProductDetail.test.tsx` — thêm.
- `history/2026-10-02-ap-dung-the-va-panel-chi-tiet-tro-ly.md` — thêm: entry này.

## Quyết định

- Thẻ và panel chỉ lấy dữ liệu sản phẩm từ response hoặc catalog; id lạ thì không có thẻ.
- Không có danh sách bình luận hay video, vì catalog không có dữ liệu này.
- Điểm đánh giá ghi dạng "4.6/5", không dùng biểu tượng sao, để không lẫn với hạng sao (`starRating`).
- Panel ghi `product_view` chỉ khi đã đăng nhập, giống trang chi tiết.
- Nút "Thêm" chỉ có ở mục thuộc `cartItems` của lịch trình.
- Thứ tự: thay đổi Search (backend) được sửa trước khi cập nhật PRD. Lệch §8 bước 3, nhưng cả hai nằm trong cùng thay đổi chưa commit.

## Kiểm tra

- `vitest run` (src/frontend): 52 file, 515 test PASS. `tsc --noEmit`: không có lỗi ngoài `.next/`. eslint widget và `ProductCard`: sạch.
- `pytest src/backend/tests/unit/application src/backend/tests/contract`: 322 passed.

## Còn lại / rủi ro

- Chưa kiểm tra trực quan trên trình duyệt với backend thật.
- Sơ đồ `user-flow.md` §3.2 dùng id node `H` cho hai node khác nhau (lỗi có từ trước). Cần đề xuất riêng để sửa.
- Mobile chưa có panel (ngoài phạm vi).
