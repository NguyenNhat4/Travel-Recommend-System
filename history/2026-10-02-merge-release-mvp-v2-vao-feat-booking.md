# Merge release-mvp-v2 vào feat/booking

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs, frontend

## Mục tiêu

Kéo `origin/release-mvp-v2` (đến commit `0023a08`) vào `feat/booking`. Hai nhánh cùng sửa widget trợ lý: release thêm thẻ sản phẩm trong chat, panel chi tiết, tiến trình/nút dừng; `feat/booking` thêm đặt trực tiếp khách sạn/vé máy bay qua đơn nháp, bắt đăng nhập ở Đặt ngay, giỏ chỉ còn tour và tiện ích.

## File thay đổi

Xung đột đã giải quyết (các file khác của release vào nguyên trạng):

- `docs/prd/user-flow.md` — sửa: giữ bố cục thẻ + panel của release, thêm lại luồng Đặt ngay / Thanh toán tất cả và ghi chú nút theo loại sản phẩm.
- `src/frontend/src/hooks/useAssistantCart.ts` — sửa: giữ lọc `isCartEligible`, không đòi đăng nhập (giỏ khách), `useBookItinerary` của `feat/booking`; giữ `feedback` và chống bấm trùng của release.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: giữ `selectedProduct`/`useWidgetCart` của release và `itemActions`/`bookItinerary` của `feat/booking`; thêm `selectedCanAddToCart`, `bookSelectedNow`.
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx`, `FloatingWidget.tsx`, `WidgetProductDetail.tsx` — sửa: panel chi tiết có nút Đặt ngay; Thêm vào giỏ chỉ khi mục vào giỏ được.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: nút thêm nhanh trên thẻ chỉ cho mục vào giỏ được.
- `src/frontend/src/features/itinerary/widget/WidgetDays.tsx` — sửa: bỏ lưới ảnh khách sạn theo release, giữ `ItemActions`.
- `src/frontend/src/components/common/ProductCard.tsx` — sửa: gộp import.
- `src/frontend/tests/unit/useWidgetCart.test.tsx`, `widgetDays.test.tsx` — sửa: test cũ giả định phải đăng nhập mới thêm giỏ, và controller thiếu `itemActions`.

## Quyết định

- Khách sạn và vé máy bay trong thẻ chat không có nút thêm nhanh vào giỏ; chỉ có Đặt ngay ở panel chi tiết, vì chúng chỉ đặt trực tiếp (R-DIR-02).
- Thêm vào giỏ trong widget không còn mở LoginModal (theo quyết định của `feat/booking`); Đặt ngay vẫn bắt đăng nhập ở `startBooking`.

## Kiểm tra

- `tsc --noEmit` (src/frontend): sạch.
- `vitest run` (src/frontend): lần cuối 574/575 pass; 1 test `productDetailView` lỗi chập chờn khi chạy cả bộ, pass khi chạy riêng 2/2.
- `validate_contract.py`: PASS.
- `pytest src/backend/tests` (src/backend/.venv): chạy đến 100%, không có test lỗi, 25 test bị bỏ qua theo thiết kế.

## Còn lại / rủi ro

- Chưa kiểm tay trên trình duyệt widget (thẻ chat, panel, Đặt ngay).
