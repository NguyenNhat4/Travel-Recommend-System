# Header: biểu tượng giỏ chỉ hiển thị giỏ hàng

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend | docs

## Mục tiêu

Sau khi có trang `/profile`, biểu tượng ở header vẫn tên "Đặt chỗ của tôi", liệt kê 3 đơn đã đặt lấy từ bộ nhớ trình duyệt và hiện huy hiệu số đơn thay cho số mục giỏ. Thông tin đặt chỗ bị lặp (header và `/profile`) và dễ nhầm với giỏ. Người dùng yêu cầu bỏ bớt: biểu tượng này chỉ hiển thị giỏ hàng.

## File thay đổi

- `src/frontend/src/components/common/Header.tsx` — sửa: biểu tượng giỏ (`ShoppingCart`), tên "Giỏ hàng", huy hiệu luôn là `cartCount`; danh sách tối đa 3 mục giỏ (tên, ngày, giá) + "và n dịch vụ khác" + "Xem giỏ hàng →"; trạng thái trống "Giỏ hàng đang trống"; bỏ danh sách đơn, nút "Xem tất cả đơn hàng" và các import không còn dùng. Đơn đã đặt chỉ còn lối vào ở menu tài khoản ("Chuyến đi & Đặt phòng của tôi" → `/profile`).
- `src/frontend/tests/e2e/navigation.spec.ts` — sửa: tìm nút theo tên "Giỏ hàng".
- `docs/spec/product.md` — sửa: mô tả header ở §ghi chú desktop.

## Quyết định

- Không đổi PRD: PRD không mô tả nút này ở header; chỉ spec `product.md` nói tới.
- Mục giỏ lấy từ `cart` của `TravelContext` (response `GET /cart`), không lấy từ `bookings` trong bộ nhớ.
- Trạng thái `bookings` và `rememberBooking` trong `TravelContext` vẫn còn vì `ConfirmationView` dùng; không dọn trong thay đổi này.

## Kiểm tra

- `tsc --noEmit` sạch; `eslint` file đã sửa sạch; `vitest run tests/unit`: 56 file, 596 test pass.
- Chưa chạy Playwright e2e (cần `next build`) và chưa mở lại trên trình duyệt sau thay đổi này.

## Còn lại / rủi ro

- Không có.
