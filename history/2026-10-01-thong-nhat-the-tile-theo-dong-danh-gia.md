# Thống nhất thẻ tile: bỏ chip sao ở góc ảnh

- Ngày: 2026-10-01
- Tác giả: người dùng / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Thẻ `tile` ở search ("Tất cả") và ở landing trông khác nhau: sản phẩm không có `aggregateRating` hiện chip hạng sao ở góc ảnh, sản phẩm có thì hiện dòng điểm đánh giá bên dưới. Người dùng muốn mọi nơi giống kiểu landing.

## File thay đổi

- `src/frontend/src/components/common/ProductCard.tsx` — sửa: variant `tile` bỏ chip sao ở góc ảnh; sản phẩm chỉ có `starRating` hiện dòng "★ N sao" cùng vị trí với dòng đánh giá

## Quyết định

- Giữ thông tin hạng sao bằng dòng chữ thay vì bỏ hẳn. Chỉ sửa variant `tile`; `grid`, `row`, `compact` không đổi.

## Kiểm tra

- `tsc --noEmit`: sạch. `vitest run`: 48 file, 482 test pass. Chưa xem trên trình duyệt.

## Còn lại / rủi ro

- Chưa kiểm tra vì sao khách sạn Hà Nội thiếu `aggregateRating` (dữ liệu hay mapping search).
- Variant `grid` và `row` vẫn còn chip sao ở góc ảnh.
