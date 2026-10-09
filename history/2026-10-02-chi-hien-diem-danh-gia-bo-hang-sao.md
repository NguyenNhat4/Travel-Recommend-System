# Chỉ hiển thị điểm đánh giá, bỏ hạng sao trên thẻ và trang chi tiết

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

`attributes.starRating` (hạng sao, một phần là Booking tự ước lượng) cùng điểm đánh giá khiến người dùng bối rối. Chỉ hiển thị `aggregateRating`.

## File thay đổi

- `src/frontend/src/components/common/ProductCard.tsx` — sửa: bỏ hạng sao ở 4 biến thể; compact và row hiện `aggregateRating`.
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: bỏ dòng sao ở đầu trang chi tiết và import `Star`.
- `history/2026-10-02-chi-hien-diem-danh-gia-bo-hang-sao.md` — thêm.

## Quyết định

- Chỉ bỏ phần hiển thị. Bộ lọc "Hạng sao khách sạn" ở tab Lưu trú và dữ liệu `starRating` giữ nguyên.

## Kiểm tra

- `tsc --noEmit`, `eslint` (ProductCard, detail): sạch.
- `vitest run tests/unit`: 493 test pass.

## Còn lại / rủi ro

- Một số chữ cố định "5 sao" ở widget lịch trình (`widgetPlan.ts`, `widgetVisuals.ts`) và nhãn bộ lọc chưa đổi.
