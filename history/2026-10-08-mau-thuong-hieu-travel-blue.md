# Màu thương hiệu Travel Blue, tách màu AI

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Áp bản đề xuất thương hiệu do người dùng gửi: Travel Blue (`#2563EB`) cho đặt chỗ, `#0EA5E9` phụ, `#F59E0B` nhấn, `#7C3AED` riêng cho Trợ lý AI; giá tiền không dùng màu brand; ô tìm kiếm nền trắng, nút Tìm màu primary. Thay thế bảng thử `2026-10-08-thu-bang-mau-den-vang.md`. Chỉ đổi màu, không lệch PRD.

## File thay đổi

- `src/frontend/src/app/globals.css` — sửa: `brand` về thang xanh, thêm `secondary`, `accent` (amber), `ai` (tím); nền trang `#F8FAFC`, chữ `#0F172A`.
- `src/frontend/src/features/itinerary/widget/{FloatingWidget,WidgetLauncher,WidgetChat,WidgetComposer,WidgetOpening,WidgetNarration,WidgetProgress,WidgetHistory,WidgetPlanEmpty}.tsx`, `src/frontend/src/components/search/SearchAssistantBanner.tsx`, `src/frontend/src/components/assistant/{AssistantTripStarter,TripDetailsForm}.tsx` — sửa: `brand-*` → `ai-*`.
- `src/frontend/src/components/common/PriceTag.tsx` — sửa: giá `text-slate-900`.
- `src/frontend/src/components/detail/HotelTripBar.tsx` — sửa: nền trắng, viền `slate-200`, ô `slate-50`, focus và nút Tìm `brand-600`.
- `docs/spec/hop-dong-tich-hop-frontend.md` (§6.7) — sửa: bảng vai trò màu.
- `history/2026-10-08-mau-thuong-hieu-travel-blue.md` — thêm: entry này.

## Quyết định

- Phần "đặt chỗ" trong widget AI (thẻ sản phẩm, kế hoạch ngày, chi tiết sản phẩm: `WidgetPlanPanel`, `WidgetDays`, `WidgetProductDetail`, `WidgetProductGallery`) giữ màu brand: xanh = đặt chỗ, tím = AI.
- Không dùng màu cho giá; `accent` chưa có chỗ dùng cố định (dành cho khuyến mãi).
- Gradient AI `#6366F1 → #8B5CF6` chưa dùng ở đâu; token `ai-500/600` đủ cho hiện trạng.

## Kiểm tra

- 680 unit test pass, `tsc` sạch, `eslint`: 0 lỗi. Trình duyệt thật: trang chi tiết khách sạn (thanh tìm kiếm trắng, nút xanh) và trang `/hotels` đã xem.
- Chưa xem trực quan widget AI màu tím (không mở được widget bằng script) và các trang còn lại.

## Còn lại / rủi ro

- `PromoBanner`, `AssistantResultPanel`, `ItineraryMap` (hex ghim) chưa xét lại theo vai trò màu mới.
- Chưa có lint chặn `blue-*`/`violet-*` viết trực tiếp.
