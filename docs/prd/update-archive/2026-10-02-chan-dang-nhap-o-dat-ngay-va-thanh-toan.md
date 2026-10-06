# Chặn khách chưa đăng nhập ngay ở nút "Đặt ngay" và "Thanh toán"

- Ngày: 2026-10-02
- Người đề xuất: mihhquan / Claude
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-10-02
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §FR-BKG-01 (dòng "Nơi lưu"), FR-USR-03, AC-BKG-17; `docs/prd/user-flow.md` mục "Đăng nhập" của luồng thanh toán
- Mã FR/NFR: FR-BKG-01, FR-USR-03

## Lý do

PRD hiện cho khách chưa đăng nhập bấm "Đặt ngay", vào `/checkout` và điền cả ba bước, chỉ đến nút Thanh toán mới hỏi đăng nhập. Người dùng coi đó là lỗi nghiêm trọng: khách thấy mình "đặt hàng được" khi chưa có tài khoản. Backend vẫn chặn (`POST /bookings` trả 401), nên không có đơn nào tạo ra khi chưa đăng nhập; đề xuất này chỉ dời điểm chặn lên sớm hơn.

## Nội dung đề xuất

**FR-BKG-01, dòng "Nơi lưu"**

- Hiện tại: "Khách chưa đăng nhập cũng thêm giỏ và bấm "Đặt ngay" được; giỏ và đơn nháp của họ lưu trong Redis 3 ngày ... Tạo đơn và thanh toán luôn cần đăng nhập."
- Đề xuất: "Khách chưa đăng nhập vẫn thêm giỏ được; giỏ lưu trong Redis 3 ngày và được chuyển sang tài khoản khi đăng nhập (mục chưa có thì thêm, mục trùng thì giữ một). **"Đặt ngay" và "Thanh toán" cần đăng nhập:** khách chưa đăng nhập bấm một trong hai nút thì hộp đăng nhập mở ngay trên trang; đăng nhập xong, hệ thống tự làm tiếp việc vừa bấm (tạo đơn nháp từ "Đặt ngay" rồi vào `/checkout`; hoặc từ trang giỏ vào `/checkout`) để khách hoàn tất đặt chỗ. Tạo đơn và thanh toán vẫn cần đăng nhập ở Backend."

**FR-USR-03**: bỏ cụm "Giỏ hàng và đơn nháp không thuộc nhóm endpoint cần đăng nhập" cho đơn nháp: giỏ vẫn dùng được khi là khách; tạo đơn nháp ("Đặt ngay") do giao diện chặn bằng đăng nhập. Backend giữ nguyên khả năng nhận đơn nháp của khách (BFF/guest) để không phá vỡ contract v1.

**AC-BKG-17** (viết lại): Khách chưa đăng nhập thêm một vé tham quan vào giỏ được. Bấm "Đặt ngay" một phòng khách sạn hoặc bấm Thanh toán ở giỏ thì hộp đăng nhập mở, chưa vào `/checkout`. Đăng nhập xong: giỏ có vé tham quan, `cdp.events` có `add_to_cart` cho vé đó, hệ thống tự tạo đơn nháp phòng vừa chọn và mở `/checkout` để khách điền và thanh toán tiếp. Trước khi đăng nhập không có sự kiện nào trong `cdp.events`. Phiên khách khác không đọc được giỏ.

**user-flow.md, mục "Đăng nhập"**: thay bằng: "Khách chưa đăng nhập vẫn thêm giỏ. Bấm Đặt ngay hoặc Thanh toán thì hộp đăng nhập mở ngay trên trang; đăng nhập xong, giỏ của phiên khách chuyển sang tài khoản và Web tự tiếp tục: vào `/checkout` với đơn nháp của lần Đặt ngay đó (hoặc với giỏ), để khách hoàn tất. Mở thẳng `/checkout` khi chưa đăng nhập vẫn bị chặn ở nút Thanh toán như cũ (lớp bảo vệ dự phòng)."

## Thay đổi source sau khi chốt

- `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md`: R-CHK-06, §8 (khách), bảng hành vi giao diện dòng "Bấm Thanh toán khi chưa đăng nhập"; thêm quy tắc "Đặt ngay cần đăng nhập".
- Frontend: các nút "Đặt ngay" (`ProductDetailView.tsx`, `features/flights/results`, `AssistantResultPanel.tsx`, `WidgetPlanPanel.tsx`) và nút Thanh toán ở `CartView.tsx` gọi `openLoginModal(callback)` khi chưa có `currentPersona`; callback tạo đơn nháp rồi `navigate` tới `/checkout`. Giữ guard sẵn có ở `useCheckout.ts` `pay()` làm lớp dự phòng.
- Test: `src/frontend/tests/unit` (checkoutView, useAssistantCart, bổ sung test nút Đặt ngay khi chưa đăng nhập), e2e `routes.spec.ts`.
- Không đổi contract OpenAPI, DDL hay Backend.
