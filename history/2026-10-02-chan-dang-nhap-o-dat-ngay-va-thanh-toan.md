# Chặn đăng nhập ở nút Đặt ngay và Thanh toán

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Khách chưa đăng nhập vẫn vào được `/checkout` qua "Đặt ngay". Đề xuất `docs/prd/update-archive/2026-10-02-chan-dang-nhap-o-dat-ngay-va-thanh-toan.md` (mihhquan chốt 2026-10-02): hộp đăng nhập mở khi bấm Đặt ngay hoặc Thanh toán, đăng nhập xong tự tiếp tục vào checkout. Thay thế phần quyết định trước đó ở entry `2026-10-02-de-xuat-chan-dang-nhap-dat-ngay-thanh-toan.md` (đề xuất đã áp dụng).

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-BKG-01 (Nơi lưu), FR-USR-03, AC-BKG-17.
- `docs/prd/user-flow.md` — sửa: mục "Đăng nhập" của luồng thanh toán.
- `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md` — sửa: mục 6 mở đầu, R-CHK-06, bảng hành vi giao diện, dòng "Thêm giỏ và Đặt ngay".
- `docs/prd/update-archive/2026-10-02-chan-dang-nhap-o-dat-ngay-va-thanh-toan.md` — chuyển từ `update/`, trạng thái đã áp dụng.
- `src/frontend/src/context/TravelContext.tsx` — sửa: `startBooking` mở hộp đăng nhập khi chưa có phiên, đăng nhập xong gọi lại (qua `startBookingRef`).
- `src/frontend/src/components/cart/CartView.tsx` — sửa: nút Tiến hành đặt chỗ mở hộp đăng nhập khi chưa đăng nhập.
- `src/frontend/src/features/flights/results/FlightResultsView.tsx` — sửa: chỉ cập nhật comment.
- `src/frontend/README.md` — sửa: mô tả luồng đăng nhập.
- `src/frontend/tests/unit/cartView.test.tsx` — sửa: thêm 2 test (đã/chưa đăng nhập).
- `history/2026-10-02-de-xuat-chan-dang-nhap-dat-ngay-thanh-toan.md`, `history/2026-10-02-chan-dang-nhap-o-dat-ngay-va-thanh-toan.md` — thêm.

## Quyết định

- Đặt guard một chỗ trong `startBooking` nên mọi nút Đặt ngay (trang sản phẩm, vé máy bay, trợ lý, widget, `addToCart` của khách sạn/vé bay) đều được chặn.
- Giữ guard trong `useCheckout.pay()` và 401 của Backend làm lớp dự phòng; không đổi contract, DDL, Backend.

## Kiểm tra

- `node_modules/.bin/tsc --noEmit` (src/frontend): sạch.
- `node_modules/.bin/vitest run` (src/frontend): 50 file, 537 test pass.
- Không đổi contract nên không chạy `validate_contract.py`.
- Chưa có test đơn vị cho guard trong `startBooking` (TravelProvider chưa có test harness).

## Còn lại / rủi ro

- Chưa kiểm tay trên trình duyệt luồng Đặt ngay → đăng nhập → /checkout.
