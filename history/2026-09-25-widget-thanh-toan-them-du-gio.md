# Nút "Thanh toán" của widget trợ lý thêm đủ mục vào giỏ trước khi sang checkout

- Ngày: 2026-09-25
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Khi kiểm thử, bấm **Thanh toán** trong lịch trình của widget trợ lý nổi (`AiFloatingWidget`) thì giỏ ở `/checkout` thiếu sản phẩm. Phục vụ FR-BKG-01, FR-AGT-04, `docs/prd/user-flow.md` §1.2 bước 4 ("lưu toàn bộ sản phẩm trong lịch trình vào giỏ và thanh toán một lần").

Nguyên nhân trong widget (`handleAddAllToCart` cũ):

1. Gọi `addToCart` cho từng mục **không `await`**: N request `POST /cart/items` bay song song, rồi `navigate('/checkout')` ngay. `trackCart` chỉ nhận response có số thứ tự lớn hơn bản đã áp. Response của request gửi sau có thể về trước và chưa chứa mục của request gửi trước; response về sau đó bị bỏ. Kết quả: state giỏ và `GET /cart` lúc checkout mở thiếu mục, nhất là những mục còn đang bay.
2. Không truyền ngày. Mọi mục dùng "ngày mai" thay cho `days[].date`, và khách sạn chỉ có 1 đêm. Khách sạn còn bị gửi `quantity = nights` thay cho `nights`.
3. Không lọc mục không đặt được, không bỏ trùng `productId`. Toast từng mục đè lên nhau, và số "Đã thêm N dịch vụ" đếm cả mục bị backend từ chối.

## File thay đổi

- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa:
  - Bỏ `handleAddAllToCart`.
  - Plan của widget (`WidgetPlan`) mang `cartItems = itineraryCartItems(response.itinerary)`, cùng quy tắc với `/assistant`.
  - Nút Thanh toán gọi `useAssistantCart` và chỉ chuyển `/checkout` sau khi mọi mục đã xong. Trong lúc thêm, nút bị khoá và hiện "Đang thêm vào giỏ…".
- `src/frontend/src/hooks/useAssistantCart.ts` — sửa:
  - Hàm trả về là `async`.
  - Thêm tham số `onAdded(added)`, chỉ chạy khi mọi request đã xong và có ≥ 1 mục vào giỏ. Khách chưa đăng nhập thì `onAdded` chạy sau khi đăng nhập và thêm xong.
  - Hành vi cũ của `/assistant` giữ nguyên.
- `src/frontend/tests/unit/useAssistantCart.test.tsx` — thêm 4 test:
  - thêm tuần tự đúng ngày, `onAdded` chạy sau mục cuối;
  - một mục lỗi không chặn mục còn lại, gom lỗi vào một toast;
  - không có mục nào vào giỏ thì không gọi `onAdded`;
  - khách chưa đăng nhập: mở LoginModal một lần rồi thêm cả nhóm.

## Quyết định

- Dùng lại `itineraryCartItems` và `useAssistantCart` thay vì sửa logic riêng trong widget. Cả hai đã hiện thực `docs/spec/hop-dong-tich-hop-frontend.md` §4.8: tuần tự, mỗi `productId` một lần, `usingDate = day.date`, stay nhận phòng `days[0].date` và trả phòng + `nights`, một toast tổng kết. Nhờ vậy widget và `/assistant` cho cùng một giỏ. Không lệch PRD, không đổi contract.
- `quantity = 1` cho mọi mục, theo `useAssistantCart`. Widget cũ gửi `2` cố định. Trước đây giá trị này không có căn cứ trong spec.
- Nút ghim trên bản đồ (`ItineraryMap onAddToCart`, `quantity 2`) để nguyên vì ngoài phạm vi lỗi này.

## Kiểm tra

- `node_modules/.bin/tsc --noEmit` (src/frontend): pass.
- `node_modules/.bin/eslint` trên 3 file đã đổi: pass.
- `node_modules/.bin/vitest run tests/unit`: 17 file, 87 test pass.
- Chưa chạy lại E2E, chưa bấm thử trên trình duyệt.

## Còn lại / rủi ro

- **Stay là khách sạn cấp property thì vẫn không vào giỏ.** Ví dụ trong ảnh kiểm thử: "Vinpearl Beachfront Nha Trang" là `hotel_property` với `is_bookable = false`, nhưng có `unit_price` và là search unit. `compose_plan` chọn nó làm `stay`, `isCartEligible` phía Web cho qua, rồi `CartService.add` từ chối với `PRODUCT_UNAVAILABLE`. Theo FR-CAT-02, property phải đặt qua phòng con. Cần người dùng chọn một trong hai cách: agent chọn phòng con (`hotel_room`) làm `stay`, hoặc Web đổi sang phòng rẻ nhất còn bán qua `GET /products?parentProductId=`. Lỗi này ảnh hưởng cả `/assistant`. Hiện toast tổng kết ghi rõ tên mục không thêm được.
- Tổng tiền của lịch trình nhân vé `PER_PERSON` với số khách (`planning.totals`). Giỏ thêm `quantity = 1` nên tổng ở checkout có thể thấp hơn tổng hiển thị trên lịch trình. Spec §4.8 chưa quy định `quantity`; cần chốt nếu muốn hai tổng khớp nhau.
