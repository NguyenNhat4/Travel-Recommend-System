# Khách sạn: bỏ hộp đặt dính, nút Đặt ngay nằm trên từng thẻ hạng phòng

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Ở trang chi tiết khách sạn, hộp đặt dính bên phải (Floating Card) không đúng logic: khách đi từ kết quả tìm kiếm đã có sẵn ngày và số khách, vậy mà vẫn phải chọn hạng phòng ở một chỗ rồi đặt ở chỗ khác. Yêu cầu: với khách sạn đặt thẳng trên nút của từng hạng phòng, bỏ các phần còn lại của hộp đặt. Các loại khác (vé máy bay, vé tham quan, golf, combo) giữ nguyên hộp đặt.

Mã yêu cầu: FR-CAT-02, FR-CAT-03, FR-BKG-01, AC-BKG-15 (khách sạn chỉ có Đặt ngay, không có Thêm vào giỏ). Không lệch PRD: `docs/prd/user-flow.md` chỉ ghi chung "Book-now CTA" cho trang chi tiết, hộp đặt dính nằm ở spec nên sửa spec.

## File thay đổi

- `src/frontend/src/components/detail/RoomCard.tsx` — sửa: bỏ ô chọn phủ thẻ (`role="radio"`), trạng thái "đã chọn" và nút giả "Chọn phòng"; thay bằng nút **Đặt ngay** thật (`onBook`, `canBook`, `bookNote`).
- `src/frontend/src/components/detail/HotelTripBar.tsx` — thêm: thanh tìm kiếm kiểu tấm tìm kiếm ở trang danh mục (tên khách sạn, ngày + số đêm, phòng và khách, nút tìm; dùng lại `DateRangePicker`, `GuestsPopover`), đặt trên cùng trang, phía trên thanh phân cấp, theo yêu cầu bổ sung cùng ngày.
- `src/frontend/src/components/detail/DateInput.tsx` — thêm: tách `DateInput` khỏi `ProductDetailView` để dùng ở cả hai nơi (nội dung giữ nguyên).
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: nhánh `hotelMode` (không cột phải, không hạng phòng "đang chọn", `handleBookRoom`, kiểm sức chứa từng phòng); hộp đặt chỉ còn cho loại khác; bỏ các nhánh khách sạn đã thành mã chết trong hộp đặt.
- `src/frontend/tests/unit/productDetailView.test.tsx`, `tests/unit/tripPrefill.test.tsx` — sửa: đặt theo nút trên thẻ phòng; thêm kiểm sức chứa từng phòng, không còn radio/hộp ước tính.
- `docs/spec/hop-dong-tich-hop-frontend.md` (§3, §4.3), `docs/spec/product.md` (§4.3.1–4.3.4) — sửa: mô tả bố cục khách sạn mới.
- `history/2026-10-08-bo-hop-dat-khach-san-nut-dat-tren-the-phong.md` — thêm: entry này.

## Quyết định

- Giữ một thanh tìm kiếm ngày/số khách (trên cùng trang, "trên cả thanh điều hướng" được hiểu là trên thanh phân cấp, không phải trên header của site) thay vì bỏ hẳn: người vào thẳng trang (trang chủ, trợ lý, đơn hàng) không mang ngữ cảnh tìm kiếm, bỏ hẳn thì không có cách nào đổi ngày hay số khách; lỗi ngày cũng cần một chỗ để hiện. Nếu muốn bỏ luôn thanh này thì mọi người vào thẳng chỉ đặt được 1 đêm, ngày mai, 1 người lớn.
- Bỏ luôn tổng ước tính và dòng "Giá chính thức…" khỏi vị trí cũ; chỉ giữ lời "đặt trực tiếp, không thêm vào giỏ" và lời giá chính thức ở chân danh sách. Tổng tiền do bước thanh toán tính.
- Sức chứa kiểm theo từng hạng phòng: đoàn khách không vừa thì chỉ phòng đó khoá nút kèm "cần ít nhất N phòng", phòng lớn hơn vẫn đặt được. Trước đây số khách vượt sức chứa của phòng đang chọn bị bỏ khi điền sẵn từ URL; nay giữ nguyên số khách và khoá theo phòng.
- Trang một hạng phòng lẻ (không phân tầng, ví dụ mở từ đơn hàng) hiện đúng thẻ phòng đó cùng thanh ngày/số khách, nên tiêu đề phòng xuất hiện cả ở h1 lẫn thẻ.
- Không đổi contract, DDL, backend: vẫn gọi `POST /booking-drafts` với `productId` của hạng phòng.

- Chỉnh giao diện theo quy tắc ui-ux-pro-max (giữ bảng màu xanh dương hiện có của V-OTA, không theo bảng màu gợi ý): ô và nút cao 48–44px, vòng focus nhìn thấy, `aria-label` có ngữ cảnh cho nút ngày và khách, nút Đặt ngay có trạng thái "Đang xử lý" kèm vòng xoay và khoá bấm đôi (`bookingRoomId`), tôn trọng `prefers-reduced-motion`.

- Thanh tìm kiếm ở đầu trang tìm được như tấm ở `/hotels`: ô địa điểm gõ được, có gợi ý điểm đến; đổi địa điểm rồi bấm tìm thì `navigate(buildSearchHref(...))` sang `/hotels?q=…&destination=…` kèm ngày và số khách (đã thử trên trình duyệt thật: Đà Nẵng → `/hotels?...destination=Đà+Nẵng&checkIn=…`); không đổi địa điểm thì chỉ áp ngày/khách và cuộn tới phòng. Không thêm "tìm gần đây" cho ô này.

- Đổi màu thanh tìm kiếm: bỏ gradient cyan/teal (màu duy nhất không có ở nơi nào khác trong app) sang nền xanh navy `from-blue-800 to-blue-900` cùng họ với `.ota-hero-bg`, ô trắng, nút tìm vàng hổ phách `amber-400` lấy từ logo V-OTA (chữ `blue-950`, tương phản đạt); vòng focus đổi sang amber để thấy được trên nền xanh. `globals.css` không có token màu (màu rải bằng tiện ích Tailwind blue/slate, nền trang `#f6f8fb`), chưa dựng lớp token vì sẽ phải sửa hàng chục file.

## Kiểm tra

- `node_modules/.bin/vitest run tests/unit` (từ `src/frontend`): 64 file, 677 test pass. `tsc --noEmit` sạch. `eslint .`: 0 lỗi, 2 cảnh báo cũ ở `ItineraryMap.tsx`.
- Trình duyệt thật với backend thật (`localhost:3000`, backend `:8000`): `/product/<id khách sạn>?checkIn=2026-10-20&checkOut=2026-10-22&adults=2&rooms=1` hiện ba thẻ phòng mỗi thẻ một nút Đặt ngay, thanh điền sẵn 20/10–22/10, 2 người lớn, 1 phòng; không có hộp ước tính; ảnh chụp đã xem.
- Chưa chạy Playwright e2e đầy đủ và chưa bấm thử luồng Đặt ngay → thanh toán trên trình duyệt thật (unit test kiểm lời gọi `startBooking`). Không đổi contract nên không chạy `validate_contract.py`.

## Còn lại / rủi ro

- Nút tìm chỉ ghi URL và cuộn tới phòng (ngày/khách đã áp dụng ngay khi đổi), không gọi lại API. Trên điện thoại thanh xếp một cột; chưa kiểm bằng thiết bị thật. `docs/spec/product.md` §9 (thanh dính đáy cho điện thoại) chưa phản ánh việc khách sạn không còn hộp đặt.
- `src/frontend/README.md` còn nói chung "prefill the booking box"; đúng với vé, chưa chỉnh riêng cho khách sạn.
