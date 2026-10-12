# Test ProductDetailView chờ ngày khách sạn trước khi tìm, sửa flaky trên CI

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent), sửa theo CI check fail "Frontend quality checks" của PR #157 (run 38202250091, `3c82c937`)
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

CI fail ở `tests/unit/productDetailView.test.tsx`: "khách sạn: đổi địa điểm ở thanh tìm kiếm rồi bấm tìm thì sang /hotels theo địa điểm, ngày và số khách" báo `travel.navigate` được gọi 0 lần thay vì 1.

## File thay đổi

- `src/frontend/tests/unit/productDetailView.test.tsx` — sửa: trước khi đổi địa điểm và bấm tìm, chờ `date-error` biến mất bằng `waitFor`.

## Nguyên nhân (suy luận)

Ngày nhận/trả của khách sạn được đặt bởi `useEffect` trong `ProductDetailView` sau khi phòng hiện ra. Nếu test bấm tìm trước khi effect chạy xong, `dateError` còn báo "Ngày nhận phòng không được ở quá khứ" và `onSubmit` của `HotelTripBar` return sớm, nên không `navigate`. Trên máy local test luôn pass (đã thử chạy song song 6 lần, và ba múi giờ UTC / America/Los_Angeles / Asia/Ho_Chi_Minh), nên không tái hiện được; đây là giả thuyết chưa được chứng minh, khớp với lỗi chỉ xuất hiện khi CI chạy song song.

## Quyết định

- Sửa ở test, không đổi component: người dùng không bấm trong vài mili-giây sau khi phòng hiện ra, nên hành vi thật không cần đổi.
- Không nới assertion: vẫn kiểm đúng `/hotels`, `q`, `adults`, `checkIn`.

## Kiểm tra

- `npx vitest run tests/unit/productDetailView.test.tsx`: 21/21 passed (sau sửa).
- Chạy song song 6 lần trước khi sửa: 21/21 passed mỗi lần (không tái hiện được).

## Còn lại / rủi ro

- Test "nút tìm ghi ngày và số khách lên URL" cùng file dùng cùng mẫu `await findRoomButtons()` rồi bấm; chưa sửa vì không thấy lỗi ở đó.
- Nếu CI vẫn fail với lỗi này, cần xem log chi tiết và kiểm tra lại giả thuyết race.
