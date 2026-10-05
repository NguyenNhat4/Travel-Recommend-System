# Sửa test ngày khách sạn chạy đua trên CI

- Ngày: 2026-10-05
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

CI nhánh release-mvp-v2 fail 1 test: `productDetailView.test.tsx` › "khách sạn: trả phòng không sau nhận phòng…" — `checkIn.value` rỗng thay vì `dd/mm/yyyy`.

## File thay đổi

- `src/frontend/tests/unit/productDetailView.test.tsx` — sửa: hai test khách sạn đọc ô "Nhận phòng" nay chờ chính ô text này có giá trị `dd/mm/yyyy` thay vì chờ `input[type="date"]` ẩn; ba test vé tham quan, chuyến bay, combo thêm `await act(async () => {})` trước khi bấm bộ đếm.

## Quyết định

- Nguyên nhân: `DateInput` (`ProductDetailView.tsx`) cấp `value` cho ô date ẩn ngay lúc render, còn ô text hiển thị chỉ được đồng bộ sau đó trong `useEffect`. `waitFor` có thể qua trước khi effect chạy (CI chậm), nên ô text còn rỗng. Cùng kiểu chạy đua làm ba test bấm bộ đếm (vé, chuyến bay, combo) fail khi máy tải nặng: effect đặt lại `counts` chạy sau lần render đầu và ghi đè lần bấm. Lỗi ở test, không phải hành vi sản phẩm; không đổi component, không lệch PRD.

## Kiểm tra

- `vitest run tests/unit/productDetailView.test.tsx`: 13/13 pass; chạy song song 12 tiến trình (giả lập CI chậm) đều 13/13. Trước khi sửa hết ba test bấm bộ đếm, cùng cách chạy này làm 1–3 lần fail.
- Chưa chạy lại toàn bộ suite (576 test) trên CI.

## Còn lại / rủi ro

- Test capacity khách sạn (đã chờ ô date ẩn từ commit 2e959b5) không fail khi chạy tải nặng nên giữ nguyên.
