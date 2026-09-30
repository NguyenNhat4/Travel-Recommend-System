# Checkout nhiều bước: hành khách người lớn/trẻ em, giá theo loại khách và kiểm tra hai phía

- Ngày: 2026-09-29 (viết, chốt và triển khai trong cùng ngày)
- Người viết: mihhquan / Claude Code (vai PO). Phần triển khai và §10–§16: Claude Code.
- Trạng thái: **Đã chốt và đã triển khai** trên nhánh `feat/booking`. Đề xuất `docs/prd/update-archive/2026-09-29-checkout-nhieu-buoc-hanh-khach.md` được mihhquan chốt ngày 2026-09-29 và đã áp dụng vào PRD (FR-BKG-08, AC-BKG-05…07, §15.1). **Chưa làm:** Phụ lục A (FR-BKG-11, AC-BKG-10) và hai yêu cầu vé máy bay khác đã vào PRD, FR-BKG-10 (hạng vé, khứ hồi, AC-BKG-09) và FR-BKG-12 (xuất vé mô phỏng) (§13.4). **Chưa có nghiệm thu cuối** của người dùng: danh sách kiểm ở §12.4.
- Phục vụ: FR-BKG-01, FR-BKG-02, FR-BKG-06, FR-BKG-08, FR-CAT-02, FR-CAT-03, NFR-SEC-01, NFR-MAINT-02 và AC-BKG-05…07 (`docs/prd/requirements.md`).
- Giữ nguyên: giữ chỗ 30 phút, Stripe Checkout, webhook, đối soát, huỷ và hoàn tiền (`docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md`). Spec này chỉ đổi phần **trước** khi bấm Thanh toán, cách tính tiền theo loại khách và dữ liệu hành khách lưu kèm đơn.
- Căn cứ: code nhánh `feat/booking` (commit `5feb987`, trước khi triển khai), snapshot catalog `src/data_collection/snapshots/2026-09-23`, mẫu UX trên Mobbin (§16).
- Mã quyết định D1–D11 xuất hiện xuyên suốt tài liệu; bảng đầy đủ ở §14. Mã lỗi `reason` ở §5.6, dùng chung cho Web và Backend.

## Mục lục

1. Tóm tắt
2. Hiện trạng và lỗi
3. Mục tiêu và phạm vi
4. Khái niệm và quy tắc giá
5. Bộ luật kiểm tra
6. Luồng nhiều bước (UX)
7. Hợp đồng API
8. Backend
9. Database
10. Frontend
11. Trường hợp biên
12. Kiểm thử và nghiệm thu
13. Kế hoạch triển khai và rủi ro
14. Quyết định cần chốt
15. Lệch PRD và tài liệu phải sửa sau khi chốt
16. Tham khảo UX (Mobbin)

Phụ lục A. Dịch vụ thêm của vé máy bay (FR-BKG-11)

---

## 1. Tóm tắt

- **Vấn đề.** Mỗi dịch vụ trong giỏ chỉ có một con số `quantity`. Hệ thống không biết đoàn có những ai, bao nhiêu trẻ em. Vì vậy trẻ em bị tính giá người lớn, phòng nhận quá sức chứa, vé máy bay thiếu tên, và Backend nhận mọi thông tin khách mà không kiểm (§2).
- **Giải pháp.** `/checkout` chia thành ba bước: **① Hành khách → ② Dịch vụ → ③ Xem lại và thanh toán**. Sau đó sang Stripe như hiện nay.
- **Khai đoàn một lần, dùng cho mọi dịch vụ.** Khách khai đoàn một lần: người lớn từ 12 tuổi, trẻ em dưới 12 tuổi kèm ngày sinh. Ở mỗi dịch vụ, khách chọn ai dùng. Với khách sạn, khách xếp người vào từng phòng.
- **Giá theo loại khách, do Backend tính từ catalog.** Vé có giá trẻ em hợp lệ thì trẻ em trả giá đó. Vé không có giá trẻ em thì mọi khách trả một giá. Web không tự cộng tiền.
- **Một bộ luật, kiểm ở hai nơi.** Web kiểm để báo lỗi sớm, ngay tại trường. Backend kiểm lại toàn bộ và có quyết định cuối cùng, kể cả khi có người gọi API trực tiếp (§5).

---

## 2. Hiện trạng và lỗi

Mục này mô tả trạng thái **trước** khi triển khai (commit `5feb987`); các lỗi L1–L9 đã được xử lý, bảng đối chiếu ở §13.3.

### 2.1. Luồng hiện tại

`/checkout` (`src/frontend/src/components/checkout/CheckoutView.tsx`) là **một trang** gồm bốn khối: thông tin liên hệ; thông tin từng dịch vụ; phương thức thanh toán; điều khoản và nút Thanh toán. Quy tắc tên khách hiện tại (`docs/spec/hop-dong-tich-hop-frontend.md` §4.5): khách sạn 1 tên; vé máy bay đủ `quantity` tên; loại khác không có tên. Khi khách bấm Thanh toán, Web gọi `POST /bookings`, Backend giữ chỗ và tạo phiên Stripe.

### 2.2. Lỗi logic

| # | Lỗi | Hậu quả | Chỗ trong code |
|---|---|---|---|
| L1 | Không có khái niệm đoàn khách. `quantity` là số phòng (khách sạn) hoặc số khách (loại khác), không tách người lớn và trẻ em. Trợ lý thêm mọi mục vào giỏ với `quantity = 1`. | Lịch trình cho 2 người lớn + 2 trẻ em, nhưng giỏ và Stripe chỉ tính 1 vé máy bay, 1 vé vui chơi. Tổng ở checkout thấp hơn tổng trên lịch trình. | `src/frontend/src/hooks/useAssistantCart.ts:24`; ghi nhận ở `history/2026-09-25-widget-thanh-toan-them-du-gio.md` |
| L2 | Trẻ em trả giá người lớn. Thành tiền luôn là `unitPrice × quantity`, bỏ qua `attributes.childPrice`. | Vé "[Wonder Ngon] VinWonders Nha Trang + Buggy + Fastpass" có giá người lớn 1.500.000 ₫, trẻ em 504.000 ₫. Gia đình 2 người lớn + 1 trẻ em bị tính 4.500.000 ₫ thay vì 3.504.000 ₫. | `src/backend/app/domain/booking/pricing.py:11-14` |
| L3 | Khách sạn có một ô tên cho mọi phòng. Hệ thống không kiểm sức chứa, dù 95% hạng phòng có `maxOccupancy`. | Đặt 3 phòng chỉ có 1 tên khách. Đoàn 5 người đặt 1 phòng sức chứa 2 mà không có cảnh báo nào. | `CheckoutView.tsx:39-40`; `Product.max_occupancy` (`src/backend/app/domain/catalog/models.py:62`) chưa được booking dùng |
| L4 | Vé máy bay chỉ có tên, không có loại khách. Hệ thống không kiểm trẻ em có người lớn đi cùng, không kiểm số em bé. | Vé cho một trẻ 1 tuổi đi một mình trông giống hệt vé người lớn. | `CheckoutView.tsx:39-44` |
| L5 | Backend không kiểm thông tin khách. Nó chỉ giới hạn `guestNames` tối đa 20 phần tử. Mục giỏ không có `itemDetails` vẫn được đặt. | Theo code hiện tại, gọi thẳng `POST /bookings` cho vé máy bay 3 khách mà không gửi tên nào vẫn nhận `201`. | `src/backend/app/api/v1/schemas/booking.py:33`; `src/backend/app/application/booking/create_hold.py:96-101` |
| L6 | Vé tham quan, combo, golf không ghi vé dành cho ai. | Giỏ mua 1 vé cho đoàn 4 người không bị phát hiện. | `hop-dong-tich-hop-frontend.md` §4.5 ("loại khác không gửi `guestNames`") |
| L7 | Stripe nhận một dòng mỗi mục, với đơn giá là `unitPrice`. | Khi có giá trẻ em, trang Stripe không khớp tóm tắt đơn. | `create_hold.py:59`, `create_hold.py:120` |
| L8 | `app.booking_items.line_total` là cột sinh `unit_price * quantity`. Cột này đã sai với khách sạn nhiều đêm và sẽ sai thêm khi có giá trẻ em. | Truy vấn SQL doanh thu theo dòng ra kết quả sai. | `db/vota_schema.sql:253` |
| L9 | Một trang dài chứa mọi dịch vụ. Lỗi chỉ lộ ra khi bấm Thanh toán ở cuối trang. | Với giỏ 5 dịch vụ, khách phải cuộn qua 5 khối, và lỗi ở khối đầu dễ bị bỏ sót. | `docs/spec/product.md` §4.5.2 ("Một trang, 3 khối") |

### 2.3. Dữ liệu catalog liên quan

Đếm trên snapshot `2026-09-23` (11.387 sản phẩm).

| Dữ liệu | Có ở | Hệ quả cho spec |
|---|---|---|
| `attributes.maxOccupancy` của hạng phòng | 7.382 / 7.738 hạng phòng (95%) | Dùng để kiểm sức chứa. Với 5% còn lại, hệ thống không kiểm và UI ghi rõ điều đó |
| `attributes.childPrice` | 297 sản phẩm: 199 vé tham quan, 93 combo, 5 golf | Chỉ **97** sản phẩm có giá dùng được (0 < giá trẻ em ≤ giá người lớn). **103** sản phẩm có giá 0, nghĩa là nguồn không có giá riêng, không phải miễn phí. Ví dụ: thẻ hội viên Aquafield 6.000.000 ₫, workshop cho trẻ em 500.000 ₫. **97** sản phẩm có giá trẻ em cao hơn giá người lớn, nghi là sai dữ liệu. Ví dụ: Grand Park, người lớn 100.000 ₫, trẻ em 450.000 ₫ |
| Giá trẻ em, em bé của chuyến bay | Không có | Mọi hành khách trả `unitPrice` (D3) |
| Giá khách sạn | Theo phòng/đêm. Khách sạn cấp property hỏi giá cho 2 người lớn (`priceAdults = 2`) | Số khách không làm đổi giá phòng. Phụ thu trẻ em chỉ có trong văn bản tự do (`conditions`, `policies`) |
| Quy định vé trẻ em của Vinpearl | Văn bản trong `attributes.policies`, tính theo **chiều cao**: dưới 100 cm miễn phí; từ 100 đến dưới 140 cm giá trẻ em | Không phân tích tự động được. Web hiện nguyên văn để khách tự quyết trẻ nào cần vé |

---

## 3. Mục tiêu và phạm vi

### 3.1. Mục tiêu

- **G1.** Mỗi dịch vụ trong đơn biết đúng ai dùng: số người lớn, số trẻ em, họ tên từng người. Với khách sạn: ai ở phòng nào.
- **G2.** Tiền thu bằng tổng giá catalog theo loại khách. Tổng ở bước ③ bằng `payment.amount` trên Stripe.
- **G3.** Không tạo được đơn vi phạm luật ở §5, kể cả khi gọi API trực tiếp.
- **G4.** Khách thấy lỗi ngay tại trường, ở bước đang làm, không phải chờ tới nút Thanh toán.
- **G5.** Hành vi giữ chỗ, Stripe, huỷ đã chốt không đổi. FR-BKG-03…07 và AC-BKG-01…04 vẫn đạt.

Các mục tiêu được đo bằng test (§12), không cần số liệu người dùng. Mọi ca trong bảng §12.2 phải cho cùng kết quả ở Web và Backend, và `db/verify.sql` không được có đơn nào lệch tổng.

### 3.2. Trong phạm vi

| Ưu tiên | Hạng mục |
|---|---|
| P0 | Checkout ba bước; bộ luật §5 ở Web và Backend; giá theo loại khách; lưu hành khách kèm đơn; trang đơn hiển thị hành khách |
| P0 | Giỏ lưu số người lớn/trẻ em của mỗi mục (`guests`) và các dòng giá (`fares`) |
| P1 | Trang chi tiết: chọn số người lớn/trẻ em (vé), hoặc số phòng và số khách (khách sạn) khi thêm vào giỏ |
| P1 | Trợ lý: thêm vào giỏ theo `intent.party` thay vì `quantity = 1` |
| P1 | Trang giỏ: hiện và sửa số khách của từng mục |

### 3.3. Ngoài phạm vi

- Sổ hành khách lưu trong hồ sơ để chọn lại lần sau. Đây là hướng mở rộng của FR-USR-02, cần đề xuất riêng.
- Giấy tờ tuỳ thân, quốc tịch, giới tính, số hộ chiếu. Catalog chỉ có chuyến bay nội địa và hệ thống không xuất vé thật.
- Bảo hiểm, suất ăn, mã giảm giá. Hành lý ký gửi và chọn ghế của vé máy bay thuộc phạm vi qua Phụ lục A (FR-BKG-11).
- Giá trẻ em/em bé riêng của chuyến bay; phụ thu trẻ em hoặc giường phụ của khách sạn; vé người cao tuổi. Catalog chưa có dữ liệu có cấu trúc cho các loại giá này.
- Kiểm chiều cao trẻ em khi mua vé khu vui chơi. Nhân viên kiểm tại cổng.
- Khách chưa đăng nhập: checkout vẫn bắt buộc đăng nhập.
- Mọi thay đổi về giữ chỗ, Stripe, huỷ, hoàn tiền.

---

## 4. Khái niệm và quy tắc giá

### 4.1. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Đoàn khách | Những người đi trong đơn, khai một lần ở bước ①. Tối đa 9 người (D6) |
| Hành khách | Một người trong đoàn, gồm loại khách, họ tên và ngày sinh (bắt buộc với trẻ em). Web gán cho mỗi người một mã tạm `travelerRef` để các dịch vụ tham chiếu |
| Người liên hệ | Người nhận thông tin đơn (`contact`). Có thể không đi cùng (D10) |
| Loại khách (`TravelerType`) | `ADULT`: từ 12 tuổi. `CHILD`: dưới 12 tuổi |
| Em bé | Trẻ em dưới 2 tuổi tại ngày bay. Không phải một loại khách riêng; chỉ dùng cho luật chuyến bay |
| Phân bổ | Ai dùng dịch vụ nào. Với khách sạn: ai ở phòng nào, ai là người đại diện nhận phòng |
| Loại giá (`FareType`) | `ADULT`, `CHILD` (dịch vụ tính theo người), `ROOM` (khách sạn), `PACKAGE` (combo) |
| Dòng giá (`FareLine`) | Một loại giá trong một dịch vụ, gồm đơn giá, số lượng, số đêm (chỉ với `ROOM`) và thành tiền |
| `guests` | Số người lớn và số trẻ em (theo loại giá) của một mục giỏ. Lưu ở giỏ, không chứa tên |

### 4.2. Loại khách và cách tính tuổi (D1)

- **Người lớn:** từ 12 tuổi. Hệ thống không hỏi ngày sinh và tin vào khai báo.
- **Trẻ em:** dưới 12 tuổi tại **ngày sử dụng sớm nhất của đơn**. Bắt buộc có ngày sinh.
- **Loại giá của trẻ em** ở từng dịch vụ tính theo tuổi tại `usingDate` của dịch vụ đó. Nếu trẻ tròn 12 tuổi giữa chuyến, các dịch vụ từ ngày đó tính giá người lớn, và Web báo rõ (W-04).
- **Em bé:** trẻ em dưới 2 tuổi tại `usingDate` của chuyến bay.
- **Cách tính tuổi:** số năm tròn theo lịch Việt Nam (`Asia/Ho_Chi_Minh`). `tuổi(d) = năm(d) − năm(sinh)`, trừ thêm 1 nếu ngày-tháng của `d` đứng trước ngày-tháng sinh. Với người sinh ngày 29/02, năm không nhuận coi sinh nhật là 01/03. Web và Backend dùng cùng quy tắc và cùng một bộ ngày để test (§12.2).
- **Căn cứ mốc 12 và 2 tuổi:** chuẩn hành khách của các hãng bay nội địa. Khách sạn và vé dùng chung mốc này, để mỗi người chỉ có một loại khách trong cả đơn. Quy định trẻ em riêng của từng điểm đến (tính theo chiều cao) chỉ được hiển thị, không dùng để tính giá (§2.3).

### 4.3. Số lượng, số khách và dòng giá theo loại dịch vụ

| `taxonomy` | `quantity` là | `guests` | Dòng giá | Thành tiền |
|---|---|---|---|---|
| `hotel` (hạng phòng) | Số phòng | Khách ở các phòng. Mỗi phòng có ít nhất 1 người lớn và không vượt sức chứa | Một dòng `ROOM` | `unitPrice × số đêm × số phòng`. Số khách không làm đổi giá |
| `flight` | Số hành khách, bằng `adults + children` | Bắt buộc khớp `quantity` | `ADULT`, `CHILD` | Mọi hành khách có ghế riêng và trả `unitPrice` (D3) |
| `attraction`, `golf` | Số vé, bằng `adults + children` | Bắt buộc khớp `quantity` | `ADULT`, `CHILD` | Người lớn trả `unitPrice`. Trẻ em trả giá trẻ em hợp lệ (§4.4); không có thì trả `unitPrice` |
| `combo` | Số gói | Những người dùng gói, chỉ để ghi nhận, không ràng buộc với `quantity` | Một dòng `PACKAGE` | `unitPrice × số gói` (D4) |

`lineTotal` của một mục bằng tổng `amount` các dòng giá của mục đó. `total` của giỏ và của đơn bằng tổng `lineTotal`. Công thức hiện tại ở `hop-dong-tich-hop-backend.md` §2.6 là trường hợp riêng khi không có trẻ em, nên client cũ không thấy khác biệt.

Mọi đơn giá lấy từ catalog tại thời điểm tính (FR-BKG-02). Hệ thống không tự đặt tỷ lệ giảm giá và không nhận số tiền từ client.

### 4.4. Giá trẻ em hợp lệ (D2)

Giá trẻ em **hợp lệ** khi `attributes.childPrice` là một số và `0 < childPrice ≤ unitPrice`. Khi đó vé trẻ em có đơn giá `childPrice`. Mọi trường hợp khác (không có trường này, giá bằng 0, giá cao hơn người lớn) đều coi như sản phẩm **không có giá trẻ em riêng**: trẻ em trả `unitPrice`, và UI ghi "Trẻ em: cùng giá người lớn".

- **Không dùng giá bằng 0.** Dữ liệu cho thấy 0 nghĩa là nguồn không có giá riêng (§2.3). Hiểu 0 là miễn phí sẽ khiến V-OTA thu thiếu tiền.
- **Không dùng giá cao hơn người lớn.** Có 97 sản phẩm lệch kiểu này, nhiều khả năng do job cào lấy nhầm giá. Khách không bao giờ phải trả vé trẻ em đắt hơn vé người lớn vì lỗi dữ liệu.
- **Việc của Data:** soát 200 sản phẩm lệch và xác nhận nghĩa của `childPrice = 0` (§13, bước 0). Khi dữ liệu được sửa, luật này tự áp dụng, không cần đổi code.

### 4.5. Ví dụ tính tiền

Gia đình 2 người lớn + 1 trẻ em (sinh 12/05/2019, 7 tuổi) đi Nha Trang. Giá lấy từ catalog snapshot 2026-09-23.

| Dịch vụ | Ngày | Phân bổ | Dòng giá | Thành tiền | Cách tính hiện tại |
|---|---|---|---|---|---|
| Lucky Sun Hotel Nha Trang Beach, Phòng Deluxe 3 Người (sức chứa 3) | 17/10 → 19/10 (2 đêm) | Phòng 1: 3 khách, người đại diện là Nguyễn Minh Anh | `ROOM` 777.192 ₫ × 2 đêm × 1 phòng | 1.554.384 ₫ | 1.554.384 ₫ |
| [Wonder Ngon] Vé VinWonders Nha Trang + Buggy + Fastpass 3 game hot | 18/10 | 3 khách | `ADULT` 2 × 1.500.000 ₫; `CHILD` 1 × 504.000 ₫ | 3.504.000 ₫ | 4.500.000 ₫ (với `quantity = 3`) |
| VietJet Air VJ601 Nha Trang → TP. Hồ Chí Minh 16:20 | 19/10 | 3 khách | `ADULT` 2 × 634.000 ₫; `CHILD` 1 × 634.000 ₫ | 1.902.000 ₫ | 1.902.000 ₫ |
| **Tổng** | | | | **6.960.384 ₫** | 7.956.384 ₫ |

---

## 5. Bộ luật kiểm tra

### 5.1. Nguyên tắc

- Mỗi luật có một mã. Web và Backend dùng cùng mã luật, cùng `reason` và cùng câu thông báo (§5.6).
- **Web** kiểm để báo lỗi sớm. Lỗi định dạng được kiểm khi khách rời trường (blur); luật của cả bước được kiểm khi khách bấm **Tiếp tục**. Web không kiểm theo từng phím gõ (giữ nguyên `product.md` §4.5.2).
- **Backend** kiểm lại toàn bộ và có quyết định cuối cùng. Backend trả về **mọi** vi phạm trong một lần, không dừng ở vi phạm đầu tiên.
- **Chặn** nghĩa là Web không cho sang bước sau và Backend trả `400 VALIDATION_ERROR`. **Cảnh báo** nghĩa là chỉ hiển thị, không chặn; chỉ Web làm.

### 5.2. Luật đoàn khách và người liên hệ (bước ①)

| Mã | Luật | Mức | `reason` (trường) |
|---|---|---|---|
| R-TRV-01 | Đoàn có ít nhất 1 người lớn | Chặn | `ADULT_REQUIRED` (`travelers`) |
| R-TRV-02 | Đoàn có từ 1 đến 9 người | Chặn | `PARTY_TOO_LARGE` (`travelers`) |
| R-TRV-03 | Mọi hành khách phải có họ và tên đệm và tên, nhập ở hai ô (D5). Sau khi bỏ khoảng trắng thừa, mỗi ô dài 1–50 ký tự, chỉ gồm chữ cái (kể cả tiếng Việt có dấu), khoảng trắng, `'` và `-`. Backend nối "{Họ} {Tên đệm và tên}" thành `full_name` | Chặn | `REQUIRED`, `NAME_INVALID` (`travelers[i].surname`, `travelers[i].givenNames`) |
| R-TRV-04 | Trẻ em có ngày sinh. Ngày sinh không ở tương lai và không sau ngày sử dụng sớm nhất của đơn | Chặn | `REQUIRED`, `BIRTH_DATE_INVALID` (`travelers[i].birthDate`) |
| R-TRV-05 | Trẻ em dưới 12 tuổi tại ngày sử dụng sớm nhất của đơn | Chặn | `CHILD_AGE_INVALID` (`travelers[i].birthDate`) |
| R-TRV-06 | `travelerRef` không trùng nhau trong đơn. Chỉ Backend kiểm, vì Web tự sinh mã | Chặn | `TRAVELER_DUPLICATED` (`travelers[i].travelerRef`) |
| R-CON-01 | Người liên hệ: họ tên 1–100 ký tự; số điện thoại khớp `^0[0-9]{9}$`; email đúng định dạng (Web gửi email của tài khoản) | Chặn | `REQUIRED`, `NAME_INVALID` (quá 100 ký tự), `PHONE_INVALID`, `EMAIL_INVALID` (`contact.fullName`, `contact.phone`, `contact.email`) |

Trên Web, bộ đếm khoá nút − và + ở giới hạn, nên R-TRV-01 và R-TRV-02 chủ yếu để Backend chặn request gọi thẳng API.

### 5.3. Luật theo dịch vụ (bước ②)

| Mã | Áp dụng | Luật | Mức | `reason` (trường) |
|---|---|---|---|---|
| R-ITM-01 | Mọi mục | Mỗi mục giỏ có đúng một `itemDetails`: không thiếu, không thừa, không lặp | Chặn | `ITEM_DETAIL_MISSING`, `ITEM_DETAIL_UNKNOWN`, `ITEM_DETAIL_DUPLICATED` (`itemDetails`) |
| R-ITM-02 | Mọi mục | Mục có ít nhất 1 hành khách. Mọi `travelerRef` phải có trong `travelers`. Một người không xuất hiện hai lần trong cùng mục | Chặn | `ITEM_WITHOUT_TRAVELER`, `TRAVELER_UNKNOWN`, `TRAVELER_DUPLICATED` (`itemDetails[j]…`) |
| R-ITM-03 | Mọi mục | Mục có trẻ em phải có ít nhất 1 người lớn trong cùng mục | Chặn | `ADULT_REQUIRED` (`itemDetails[j].travelerRefs`) |
| R-ITM-04 | `flight`, `attraction`, `golf` | Số người lớn và trẻ em (theo loại giá tại ngày của mục) khớp `guests` của mục giỏ, tức là khớp giá khách đã thấy | Chặn | `GUEST_COUNT_MISMATCH` (`itemDetails[j]`) |
| R-FLT-01 | `flight` | Số em bé (dưới 2 tuổi tại ngày bay) không vượt số người lớn trên chuyến | Chặn | `INFANTS_EXCEED_ADULTS` (`itemDetails[j].travelerRefs`) |
| R-HTL-01 | `hotel` | Số phòng trong `rooms` bằng `quantity` của mục | Chặn | `ROOM_COUNT_MISMATCH` (`itemDetails[j].rooms`) |
| R-HTL-02 | `hotel` | Mỗi phòng có ít nhất 1 người lớn | Chặn | `ADULT_REQUIRED` (`itemDetails[j].rooms[k]`) |
| R-HTL-03 | `hotel` | Số khách mỗi phòng, tính cả trẻ em, không vượt `maxOccupancy`. Hạng phòng không có `maxOccupancy` thì bỏ qua luật này (D7) | Chặn | `OCCUPANCY_EXCEEDED` (`itemDetails[j].rooms[k]`) |
| R-HTL-04 | `hotel` | Một người chỉ ở một phòng trong cùng mục | Chặn | `TRAVELER_DUPLICATED` (`itemDetails[j].rooms[k].travelerRefs`) |
| R-HTL-05 | `hotel` | Người đại diện nhận phòng là người lớn ở trong phòng đó | Chặn | `LEAD_GUEST_INVALID` (`itemDetails[j].rooms[k].leadTravelerRef`) |

Khách sạn và combo không kiểm R-ITM-04, vì số khách không làm đổi giá. Phân bổ gửi lúc checkout được dùng làm số khách thật của đơn.

### 5.4. Cảnh báo (không chặn, chỉ Web)

| Mã | Tình huống | Hiển thị |
|---|---|---|
| W-01 | Một người trong đoàn không dùng dịch vụ nào | "{Tên} chưa có dịch vụ nào trong đơn." |
| W-02 | Dịch vụ tính theo người không phủ cả đoàn | Nhãn "{n}/{tổng} khách" trên thẻ dịch vụ |
| W-03 | Một người ở hai khách sạn có đêm trùng nhau | "{Tên} đang ở 2 khách sạn trong đêm {dd/mm}." |
| W-04 | Trẻ em tròn 12 tuổi trước ngày của một dịch vụ | "Từ {dd/mm/yyyy}, {tên} tính giá người lớn." |
| W-05 | Hai hành khách trùng họ tên | "Có hai hành khách cùng tên {tên}. Kiểm tra lại nếu nhập nhầm." |

### 5.5. Luật khi thêm hoặc sửa mục giỏ

Áp dụng cho `POST /cart/items` và `PATCH /cart/items/{cartItemId}`. Lỗi trả `400 VALIDATION_ERROR` với `reason` như bảng.

| Mã | Luật | `reason` |
|---|---|---|
| R-CRT-01 | `guests.adults ≥ 1`, `guests.children ≥ 0`, tổng không quá 9 | `ADULT_REQUIRED`, `PARTY_TOO_LARGE` |
| R-CRT-02 | `flight`, `attraction`, `golf`: khi gửi `guests`, `quantity` bằng `adults + children` (được phép bỏ `quantity`). Gửi cả hai mà lệch nhau thì bị từ chối | `GUEST_COUNT_MISMATCH` |
| R-CRT-03 | `hotel`: `adults ≥ quantity` (mỗi phòng một người lớn). `adults + children ≤ maxOccupancy × quantity` khi hạng phòng có `maxOccupancy` | `ADULT_REQUIRED`, `OCCUPANCY_EXCEEDED` |
| R-CRT-04 | Thêm trùng `productId` + `usingDate` thì cộng dồn cả `quantity` lẫn `guests`, riêng combo: `quantity` cộng dồn còn `guests` lấy giá trị lớn hơn theo từng loại, vì khách của combo chỉ để ghi nhận. Kết quả sau khi cộng vẫn phải đạt R-CRT-01…03 | Như trên |
| R-CRT-05 | Không gửi `guests` (client cũ): `hotel` và dịch vụ tính theo người mặc định `{adults: quantity, children: 0}`; `combo` mặc định `{adults: 1, children: 0}`. `PATCH` chỉ đổi `quantity` của mục đang có trẻ em thì giữ nguyên `children` và đặt `adults = quantity − children`, với điều kiện kết quả ≥ 1. `PATCH` khách sạn chỉ tăng số phòng thì `adults` được nâng lên bằng số phòng | `ADULT_REQUIRED` |

### 5.6. Mã `reason` và câu thông báo

Mọi lỗi trong bảng dưới đều là `400 VALIDATION_ERROR`. `message` dùng tiếng Việt, hiển thị được trực tiếp cho người dùng. Câu chữ nằm ở `src/backend/app/application/booking/messages.py` (Backend) và `src/frontend/src/components/checkout/checkoutRules.ts` (Web); đổi ở một phía phải đổi phía kia, và bộ ca dùng chung (§12.2) kiểm cả `reason` lẫn `field`.

| `reason` | Câu thông báo |
|---|---|
| `REQUIRED` | Tuỳ trường: "Vui lòng nhập họ."; "Vui lòng nhập tên đệm và tên."; "Vui lòng nhập ngày sinh."; "Vui lòng nhập họ và tên người liên hệ."; "Vui lòng nhập số điện thoại."; "Vui lòng nhập email." |
| `NAME_INVALID` | Hành khách: "Chỉ gồm chữ cái, đúng như trên giấy tờ." Người liên hệ (quá 100 ký tự): "Họ và tên người liên hệ tối đa 100 ký tự." |
| `PHONE_INVALID` | "Số điện thoại gồm 10 chữ số, bắt đầu bằng 0." |
| `EMAIL_INVALID` | "Email không hợp lệ." |
| `BIRTH_DATE_INVALID` | "Ngày sinh không hợp lệ." |
| `CHILD_AGE_INVALID` | "Bé đã đủ 12 tuổi vào {dd/mm/yyyy}. Vui lòng chọn loại Người lớn." |
| `ADULT_REQUIRED` | Tuỳ chỗ: "Cần ít nhất 1 người lớn (từ 12 tuổi)."; "Trẻ em cần đi cùng ít nhất 1 người lớn trong dịch vụ này."; "Mỗi phòng cần ít nhất 1 người lớn." |
| `PARTY_TOO_LARGE` | "Mỗi đơn tối đa 9 khách. Vui lòng tách thành nhiều đơn." |
| `TRAVELER_UNKNOWN` | "Hành khách không có trong đoàn." (lỗi kỹ thuật; Web không để xảy ra) |
| `TRAVELER_DUPLICATED` | "{Tên} đã được chọn ở chỗ khác trong dịch vụ này." Riêng trường `travelers[i].travelerRef`: "Mã hành khách bị trùng." |
| `ITEM_DETAIL_MISSING` | "Thiếu thông tin cho {tên dịch vụ}." |
| `ITEM_DETAIL_UNKNOWN`, `ITEM_DETAIL_DUPLICATED` | "Thông tin dịch vụ không khớp giỏ hàng. Vui lòng tải lại giỏ." (lỗi kỹ thuật; Web tải lại giỏ) |
| `ITEM_WITHOUT_TRAVELER` | "Chọn ít nhất 1 khách dùng {tên dịch vụ}, hoặc xoá dịch vụ khỏi giỏ." |
| `GUEST_COUNT_MISMATCH` | "Số khách của {tên dịch vụ} vừa thay đổi. Vui lòng xem lại giá." Riêng khi thêm/sửa giỏ (trường `quantity`): "Số lượng phải bằng số người lớn cộng số trẻ em." |
| `INFANTS_EXCEED_ADULTS` | "Mỗi em bé dưới 2 tuổi cần một người lớn đi kèm trên chuyến bay." |
| `ROOM_COUNT_MISMATCH` | "Bạn đã đặt {n} phòng. Hãy xếp khách vào đủ {n} phòng hoặc giảm số phòng." |
| `OCCUPANCY_EXCEEDED` | "Phòng {k} chứa tối đa {x} khách." Riêng khi thêm/sửa giỏ: "Mỗi phòng chứa tối đa {x} khách. Vui lòng thêm phòng." |
| `LEAD_GUEST_INVALID` | "Người đại diện nhận phòng phải là người lớn ở trong phòng." |
| `TRAVELERS_REQUIRED` | "Đơn có trẻ em cần khai thông tin hành khách. Vui lòng tải lại trang và thử lại." Chỉ với request cũ không có `travelers` mà giỏ có trẻ em (§7.6) |

---

## 6. Luồng nhiều bước (UX)

### 6.1. Tổng quan

```mermaid
flowchart LR
    C["/cart"] -->|Tiến hành đặt chỗ| S1["① Hành khách"]
    S1 -->|"Tiếp tục: đạt §5.2"| P["PATCH guests từng mục"]
    P --> S2["② Dịch vụ"]
    S2 -->|"Tiếp tục: đạt §5.3"| S3["③ Xem lại và thanh toán"]
    S2 -->|Quay lại| S1
    S3 -->|Sửa| S1
    S3 -->|Sửa| S2
    S3 -->|Thanh toán| B["POST /bookings"]
    B -->|"400: lỗi ở travelers, contact"| S1
    B -->|"400: lỗi ở itemDetails"| S2
    B -->|"409, 422, 503"| S3
    B -->|"201 PENDING_PAYMENT"| ST["Trang Stripe"]
    ST --> BK["/booking/:referenceCode"]
```

```mermaid
sequenceDiagram
    actor K as Khách
    participant W as Web /checkout
    participant B as Backend
    participant S as Stripe
    K->>W: Mở /checkout?step=travelers
    W->>B: GET /cart
    B-->>W: CartResponse (items, guests, fares)
    W->>W: Dựng đoàn mặc định (§6.5)
    K->>W: Nhập hành khách, bấm Tiếp tục
    W->>W: Kiểm §5.2, tính phân bổ mặc định
    loop Mỗi mục có guests hoặc số phòng khác phân bổ
        W->>B: PATCH /cart/items/{id} {guests, quantity}
        B-->>W: CartResponse mới hoặc 400 VALIDATION_ERROR
    end
    K->>W: Chỉnh phân bổ ở bước ②, bấm Tiếp tục
    W->>W: Kiểm §5.3, chờ mọi PATCH xong
    K->>W: Bước ③: chọn Stripe, đồng ý điều khoản, bấm Thanh toán
    W->>B: POST /bookings {contact, travelers, itemDetails}
    B->>B: Kiểm theo §8.3
    alt Có vi phạm
        B-->>W: 400 VALIDATION_ERROR {fields[]}
        W->>W: Về bước chứa trường lỗi đầu tiên
    else Hợp lệ
        B->>S: Tạo Checkout Session (mỗi dòng giá một line item)
        B-->>W: 201 PENDING_PAYMENT + checkoutUrl
        W->>S: Chuyển trình duyệt sang Stripe
    end
```

### 6.2. Điều hướng

- Route vẫn là `/checkout` (bảng route của PRD). Bước hiện tại nằm ở query `step`: `travelers` (mặc định), `services`, `review`. Mỗi lần chuyển bước tạo một mục trong lịch sử trình duyệt, nên nút Back của trình duyệt đưa khách về bước trước mà không mất dữ liệu.
- Nếu khách mở thẳng một bước sau trong khi bước trước chưa đạt (ví dụ tải lại trang ở `?step=review`), Web chuyển về bước đầu tiên chưa đạt.
- Thanh bước ở đầu trang: bước đã xong có dấu ✓ và bấm được để quay lại; bước hiện tại tô đậm; bước chưa tới không bấm được.
- Nút **Tiếp tục** luôn bấm được. Nếu bấm khi còn lỗi, Web không chuyển bước mà hiện hộp tóm tắt lỗi ở đầu bước (mỗi dòng là một link tới trường lỗi), gắn lỗi dưới từng trường và đưa focus tới trường lỗi đầu tiên. Không khoá nút Tiếp tục, vì nút bị khoá không cho khách biết mình còn thiếu gì.
- Nút **Thanh toán** ở bước ③ giữ quy tắc PRD hiện hành (`user-flow.md` §3.3): khoá cho tới khi khách đã chọn phương thức và đồng ý điều khoản. Dữ liệu ở các bước trước đã đạt, nên không còn điều kiện nào khác.
- Không giữ chỗ, không tạo đơn, không gọi Stripe trước khi bấm Thanh toán (FR-BKG-06). Cập nhật số khách ở bước ① và ② chỉ sửa giỏ (`PATCH /cart/items`) và không ghi event CDP.
- Mỗi lần chuyển bước, Web gọi `GET /cart`. Nếu giỏ bị đổi ở tab khác: mục mới nhận phân bổ mặc định, mục đã xoá bị bỏ ra, và Web hiện banner "Giỏ hàng vừa thay đổi". Nếu giỏ rỗng thì về `/cart`.
- Nếu hết phiên (401) giữa chừng: hiện hộp đăng nhập lại và giữ nguyên dữ liệu đang nhập (như `product.md` §4.5.3).

### 6.3. Khung chung của ba bước

- **Header rút gọn:** logo và "← Quay lại giỏ hàng", như hiện hành.
- **Desktop:** cột trái là nội dung bước. Cột phải là **Tóm tắt đơn**, dính khi cuộn: đoàn khách ("2 người lớn · 1 trẻ em"), từng dịch vụ kèm ngày và thành tiền, và tổng. Mọi con số lấy từ `CartResponse`. Khi một `PATCH` đang chạy, thành tiền của mục đó và tổng hiện khung chờ (skeleton).
- **Mobile** (dưới breakpoint `lg`): một cột. Thanh cố định ở đáy màn hình gồm đoàn khách, tổng tiền và nút chính của bước. Bấm vào tổng mở tóm tắt chi tiết dạng bottom sheet. Mẫu tham khảo: Trip.com [M2].

Thanh dưới cùng trên mobile:

```
┌──────────────────────────────────────────┐
│ 2 người lớn · 1 trẻ em     6.960.384 ₫ ⌃ │
│ [              Tiếp tục               ]  │
└──────────────────────────────────────────┘
```

### 6.4. Bước ① Hành khách

```
┌ Logo · ← Quay lại giỏ hàng ─────────────────────────────────────────────────────────┐
│  ① Hành khách ──── ② Dịch vụ ──── ③ Xem lại và thanh toán                           │
├──────────────────────────────────────────────────────┬──────────────────────────────┤
│ AI ĐI CHUYẾN NÀY?                                    │ ĐƠN CỦA BẠN (3 dịch vụ)      │
│  Người lớn   Từ 12 tuổi          [ − ]  2  [ + ]     │ 2 người lớn · 1 trẻ em       │
│  Trẻ em      Dưới 12 tuổi        [ − ]  1  [ + ]     │ Khách sạn Lucky Sun          │
│  Tối đa 9 khách mỗi đơn.                             │  17–19/10 · 1 phòng          │
│                                                      │              1.554.384 ₫     │
│ THÔNG TIN HÀNH KHÁCH                                 │ Vé VinWonders · 18/10        │
│  ⓘ Nhập đúng họ tên như trên CCCD hoặc giấy khai     │              3.504.000 ₫     │
│    sinh. Hãng bay, khách sạn có thể từ chối nếu      │ Bay VJ601 · 19/10            │
│    tên sai.                                          │              1.902.000 ₫     │
│ ┌ Người lớn 1 ─────────────────────────────────────┐ │ ──────────────────────────── │
│ │ Họ *              [Nguyễn                      ] │ │ Tổng         6.960.384 ₫     │
│ │ Tên đệm và tên *  [Minh Anh                    ] │ │                              │
│ └──────────────────────────────────────────────────┘ │                              │
│ ┌ Người lớn 2 ─────────────────────────────────────┐ │                              │
│ │ Họ *              [                            ] │ │                              │
│ │ Tên đệm và tên *  [                            ] │ │                              │
│ └──────────────────────────────────────────────────┘ │                              │
│ ┌ Trẻ em 1 ────────────────────────────────────────┐ │                              │
│ │ Họ *              [                            ] │ │                              │
│ │ Tên đệm và tên *  [                            ] │ │                              │
│ │ Ngày sinh *       [dd/mm/yyyy]                   │ │                              │
│ │ 7 tuổi vào 17/10/2026 (ngày sử dụng sớm nhất)    │ │                              │
│ └──────────────────────────────────────────────────┘ │                              │
│ NGƯỜI LIÊN HỆ                                        │                              │
│  Họ và tên *      [Nguyễn Minh Anh             ]     │                              │
│  Số điện thoại *  [0912345678                  ]     │                              │
│  Email            [minhanh@example.vn (khoá)   ]     │                              │
│  ☑ Người liên hệ cũng là Người lớn 1                 │                              │
│                                       [ Tiếp tục → ] │                              │
└──────────────────────────────────────────────────────┴──────────────────────────────┘
```

| Trường | Bắt buộc | Cách nhập | Luật |
|---|---|---|---|
| Số người lớn | Có | Bộ đếm 1–9, dòng phụ "Từ 12 tuổi" | R-TRV-01, R-TRV-02 |
| Số trẻ em | Có | Bộ đếm từ 0 tới (9 − số người lớn), dòng phụ "Dưới 12 tuổi" | R-TRV-02 |
| Họ (mỗi hành khách) | Có | Ô chữ, tối đa 50 ký tự | R-TRV-03 |
| Tên đệm và tên (mỗi hành khách) | Có | Ô chữ, tối đa 50 ký tự | R-TRV-03 |
| Ngày sinh (trẻ em) | Có | Ô `dd/mm/yyyy`, bàn phím số, tự chèn `/` | R-TRV-04, R-TRV-05 |
| Người liên hệ: họ tên, số điện thoại | Có | Như hiện hành; email khoá theo tài khoản | R-CON-01 |
| "Người liên hệ cũng là Người lớn 1" | — | Checkbox, mặc định bật | Khi bật, họ tên người liên hệ luôn bằng "{Họ} {Tên đệm và tên}" của Người lớn 1; sửa ô người liên hệ thì tách từ đầu tiên làm họ, phần còn lại làm tên đệm và tên. Thẻ Người lớn 1 hiện nhãn "Là người liên hệ" |

Hành vi:

- Tăng bộ đếm thì thêm một thẻ hành khách vào cuối nhóm; giảm thì bỏ thẻ cuối nhóm. Nếu thẻ bị bỏ đã có dữ liệu, Web hỏi lại trước khi xoá.
- Khi khách nhập xong ngày sinh (blur), thẻ trẻ em hiện dòng phụ "{n} tuổi vào {ngày sử dụng sớm nhất}". Ô ngày sinh tự chèn dấu `/` khi gõ số; xoá lùi thì để nguyên, còn dán đè một giá trị khác thì định dạng lại từ các chữ số.
- Hai hành khách trùng họ tên: hiện cảnh báo W-05 dưới danh sách thẻ, không chặn.
- Khi bấm Tiếp tục, Web kiểm §5.2, tính phân bổ mặc định (§6.5), rồi `PATCH` lần lượt các mục có `guests` hoặc số phòng khác phân bổ. Trong lúc đó nút hiện "Đang cập nhật giá (2/3)…". Xong thì sang bước ②. Nếu một `PATCH` lỗi, Web vẫn sang bước ② và gắn lỗi vào thẻ dịch vụ đó.

### 6.5. Điền sẵn và phân bổ mặc định

**Đoàn mặc định** khi mở `/checkout` lần đầu trong phiên:

1. Số người lớn là giá trị lớn nhất trong `guests.adults` của các mục giỏ. Số trẻ em là giá trị lớn nhất trong `guests.children`. Luôn có ít nhất 1 người lớn. Nhờ vậy, giỏ tạo từ trợ lý cho 2 người lớn + 2 trẻ em mở ra đúng đoàn đó.
2. Họ tên Người lớn 1 lấy từ tài khoản; các ô khác để trống. Tên tài khoản không dùng được làm họ tên trên giấy tờ (có chữ số hoặc ký hiệu, quá 50 ký tự, hoặc chỉ một từ) thì để trống cả hai ô của Người lớn 1, thay vì điền sẵn một giá trị sẽ bị báo lỗi. Ngày sinh trẻ em luôn để trống, vì giỏ không lưu ngày sinh.

**Phân bổ mặc định** chỉ tính cho mục khách chưa chỉnh trong phiên. Mục khách đã chỉnh thì giữ nguyên, chỉ bỏ những người đã rời đoàn.

- `flight`, `attraction`, `golf`, `combo`: gán cả đoàn (D10). Nếu có người không dùng, khách bỏ chọn ở bước ②, ví dụ trẻ dưới 100 cm được vào cửa miễn phí.
- `hotel` có R phòng, mỗi phòng chứa tối đa C người (hạng phòng không có C thì không giới hạn):
  1. Lần lượt xếp mỗi phòng một người lớn, theo thứ tự trong đoàn.
  2. Xếp người lớn còn lại, rồi đến trẻ em, xoay vòng vào các phòng còn chỗ.
  3. Người đại diện của mỗi phòng là người lớn đầu tiên trong phòng.
  4. Nếu còn người chưa có chỗ, thẻ khách sạn báo "Còn {n} khách chưa có phòng" kèm nút [+ Thêm phòng]. Nút chỉ hiện khi đoàn còn người lớn chưa đứng tên phòng nào. Nếu số người lớn ít hơn số phòng, thẻ báo R-HTL-02 trên phòng trống kèm nút [− Bớt phòng].
- Sau khi phân bổ, `guests` của mỗi mục là số người lớn và trẻ em theo loại giá tại `usingDate` của mục. Trẻ đã tròn 12 tuổi tại ngày đó được tính là người lớn.

### 6.6. Bước ② Dịch vụ

```
│  ① Hành khách ✓ ──── ② Dịch vụ ──── ③ Xem lại và thanh toán                          │
│ CHUYẾN NHA TRANG                                                                     │
│ ┌ [Khách sạn] Lucky Sun – Phòng Deluxe 3 Người · 17/10 → 19/10 · 2 đêm ────── ✓ ───┐ │
│ │ Số phòng [ − ] 1 [ + ]          Tối đa 3 khách/phòng                             │ │
│ │ Phòng 1 (3/3): [Minh Anh ×] [Thu Hà ×] [Gia Bảo ×]                               │ │
│ │   Người đại diện nhận phòng: [Nguyễn Minh Anh ▾]                                 │ │
│ │ 777.192 ₫ × 2 đêm × 1 phòng                                                      │ │
│ │ Yêu cầu đặc biệt (không bắt buộc) [                                            ] │ │
│ └──────────────────────────────────────────────────────────────── 1.554.384 ₫ ─────┘ │
│ ┌ [Vé tham quan] VinWonders + Buggy + Fastpass 3 game hot · 18/10 ─────────── ✓ ───┐ │
│ │ Ai dùng vé?  ☑ Nguyễn Minh Anh · Người lớn   ☑ Trần Thu Hà · Người lớn           │ │
│ │              ☑ Nguyễn Gia Bảo · Trẻ em, 7 tuổi                                   │ │
│ │ Người lớn  2 × 1.500.000 ₫                                                       │ │
│ │ Trẻ em     1 ×   504.000 ₫                                                       │ │
│ │ ▸ Điều kiện vé trẻ em của điểm đến                                               │ │
│ └──────────────────────────────────────────────────────────────── 3.504.000 ₫ ─────┘ │
│ ┌ [Vé máy bay] VietJet VJ601 Nha Trang → TP. Hồ Chí Minh · 19/10 16:20 ────── ✓ ───┐ │
│ │ Hành khách:  ☑ Minh Anh · Người lớn  ☑ Thu Hà · Người lớn  ☑ Gia Bảo · Trẻ em    │ │
│ │ Người lớn 2 × 634.000 ₫ · Trẻ em 1 × 634.000 ₫                                   │ │
│ │ ⓘ Chưa có giá vé trẻ em riêng: trẻ em và em bé có ghế riêng, tính giá người lớn. │ │
│ └──────────────────────────────────────────────────────────────── 1.902.000 ₫ ─────┘ │
│ [← Quay lại]                                                         [ Tiếp tục → ]  │
```

| Loại dịch vụ | Khách chỉnh gì | Hiển thị giá |
|---|---|---|
| Vé máy bay | Chọn hành khách trên chuyến (checkbox). Mỗi người có nhãn Người lớn, Trẻ em hoặc Em bé theo tuổi tại ngày bay | "Người lớn 2 × 634.000 ₫ · Trẻ em 1 × 634.000 ₫", kèm ghi chú về giá trẻ em (D3) |
| Khách sạn (hạng phòng) | Số phòng; xếp khách vào từng phòng (chip tên, chọn phòng từ danh sách); người đại diện mỗi phòng | "777.192 ₫ × 2 đêm × 1 phòng". Mỗi phòng hiện "3/3 khách". Hạng phòng không có `maxOccupancy` thì hiện "Khách sạn chưa công bố sức chứa phòng" |
| Vé tham quan, golf | Chọn ai dùng vé (checkbox) | Hai dòng giá. Nếu sản phẩm không có giá trẻ em hợp lệ thì ghi "Trẻ em: cùng giá người lớn". Mục "Điều kiện vé trẻ em" mở ra văn bản `attributes.policies` nếu có |
| Combo | Chọn ai dùng gói (để ghi nhận). Số gói giữ như trong giỏ | "{số gói} × {đơn giá}" |

Mọi thẻ đều có ô "Yêu cầu đặc biệt (không bắt buộc, tối đa 500 ký tự)" như hiện hành.

Hành vi:

- Thẻ dịch vụ gom theo điểm đến như ở trang giỏ và sắp theo ngày sử dụng. Mỗi thẻ có trạng thái: ✓ (hợp lệ) hoặc ! (cần sửa).
- Khi một thay đổi làm đổi `guests` hoặc số phòng, Web chờ 400 ms không có thao tác mới rồi gọi `PATCH /cart/items/{cartItemId}`. Các `PATCH` của cùng một mục chạy lần lượt. Thành tiền của thẻ và tổng hiện khung chờ cho tới khi có `CartResponse` mới. Nút Tiếp tục chờ mọi `PATCH` xong.
- Nếu `PATCH` trả lỗi nghiệp vụ (`PRODUCT_UNAVAILABLE`, `DATE_OUT_OF_RANGE`, `VALIDATION_ERROR`), Web gắn lỗi vào thẻ. Nếu mục hết chỗ, thẻ có nút [Xoá khỏi giỏ].
- Nếu đơn giá trong `CartResponse` mới khác lần trước mà không do đổi số khách, Web hiện toast "Giá {tên} vừa cập nhật: {cũ} → {mới}".
- Khi bấm Tiếp tục, Web kiểm §5.3. Cảnh báo §5.4 được hiện nhưng không chặn.

### 6.7. Bước ③ Xem lại và thanh toán

```
│  ① Hành khách ✓ ──── ② Dịch vụ ✓ ──── ③ Xem lại và thanh toán                        │
│ HÀNH KHÁCH (3)                                                              [Sửa]    │
│  Nguyễn Minh Anh · Người lớn   Trần Thu Hà · Người lớn   Nguyễn Gia Bảo · Trẻ em, 7t │
│  Liên hệ: Nguyễn Minh Anh · 0912345678 · minhanh@example.vn                          │
│ DỊCH VỤ (3)                                                                 [Sửa]    │
│  Lucky Sun – Deluxe 3 Người · 17–19/10 · 1 phòng, 3 khách            1.554.384 ₫     │
│  VinWonders + Buggy + Fastpass · 18/10 · 2 người lớn, 1 trẻ em       3.504.000 ₫     │
│  VJ601 Nha Trang → TP. Hồ Chí Minh · 19/10 · 3 khách                 1.902.000 ₫     │
│ ──────────────────────────────────────────────────────────────────────────────────── │
│  Tổng thanh toán                                                     6.960.384 ₫     │
│ PHƯƠNG THỨC THANH TOÁN                                                               │
│  (●) Stripe — Thẻ (chế độ test)  ( ) Ví điện tử [Sắp có]  ( ) Chuyển khoản [Sắp có]  │
│ ☐ Tôi đã kiểm tra họ tên hành khách và đồng ý Điều khoản dịch vụ, Chính sách huỷ:    │
│   hoàn 100% nếu huỷ trước 00:00 ngày 16/10/2026.                                     │
│ [                         Thanh toán 6.960.384 ₫                          ]          │
│  Giữ chỗ 30 phút sau khi bấm Thanh toán. Bạn sẽ được chuyển sang Stripe.             │
```

- Khối Hành khách và Người liên hệ có nút [Sửa] về bước ①. Khối Dịch vụ có nút [Sửa] về bước ②. Mỗi dịch vụ hiện ngày, tóm tắt phân bổ, các dòng giá (mở rộng được) và thành tiền.
- Tổng thanh toán là `CartResponse.total`.
- Chính sách huỷ hiện hạn tính theo FR-BKG-07: 00:00 của ngày liền trước ngày sử dụng sớm nhất. Đây chỉ là hiển thị; Backend vẫn quyết định `cancellableUntil`. Nếu hạn đó đã qua ngay lúc đặt (ngày sử dụng sớm nhất là hôm nay hoặc ngày mai), câu "hoàn 100% nếu huỷ trước …" được thay bằng "đã quá hạn hoàn tiền (00:00 ngày …), đơn này không được hoàn tiền nếu huỷ", vì khi khách huỷ, Backend trả `409 BOOKING_NOT_CANCELLABLE` với `details.reason = TOO_LATE`.
- Phương thức thanh toán như hiện hành: Stripe chọn sẵn; ví điện tử và chuyển khoản ghi "Sắp có".
- Checkbox điều khoản gộp thêm việc xác nhận họ tên. Trip.com dùng một hộp thoại riêng cho việc này [M1]; ở đây gộp vào để không thêm một bước.
- Nút "Thanh toán {tổng}". Khi đang gửi: hiện spinner và chặn bấm lặp, như hiện hành. Web gửi `POST /bookings` với `contact`, `travelers`, `itemDetails` (§7.4).

Cách Web xử lý kết quả (bổ sung cho `hop-dong-tich-hop-frontend.md` §8):

| Kết quả | Web làm gì |
|---|---|
| `400 VALIDATION_ERROR`, trường thuộc `travelers[…]` hoặc `contact.*` | Về bước ①, gắn lỗi vào trường, focus trường đầu tiên |
| `400 VALIDATION_ERROR`, trường thuộc `itemDetails[…]` | Về bước ②, cuộn tới thẻ dịch vụ, gắn lỗi |
| `400 VALIDATION_ERROR` có `GUEST_COUNT_MISMATCH` | `GET /cart`, tính lại phân bổ cho mục đó, về bước ② kèm thông báo |
| `409 PRICE_CHANGED` | Như hiện hành. Nếu có `details.fareType`, banner ghi rõ loại giá, ví dụ "Giá vé trẻ em của …" |
| `409 PRODUCT_UNAVAILABLE`, `422 DATE_OUT_OF_RANGE` | Như hiện hành (banner và link Quay lại giỏ) |
| `409 BOOKING_PENDING_PAYMENT` | Như hiện hành (hộp thoại tiếp tục thanh toán, hoặc huỷ đơn đó và đặt lại). Đặt lại thì gửi lại đúng dữ liệu đang có |
| `503 PAYMENT_PROVIDER_UNAVAILABLE`, lỗi mạng | Như hiện hành: ở lại bước ③, có nút Thử lại |
| `400 CART_EMPTY` | Về `/cart` |

### 6.8. Sau Stripe: trang đơn

Ở `/booking/{referenceCode}`, khối thông tin chuyến hiện hành khách của từng dịch vụ (`BookingItem.travelers`) và các dòng giá (`fares`). Khách sạn hiện khách theo phòng và đánh dấu người đại diện. Trang không hiện ngày sinh. Đơn tạo trước thay đổi này vẫn hiện `guestNames` như hiện nay.

### 6.9. Trang giỏ, trang chi tiết, trợ lý (P1)

- **Trang giỏ `/cart`:** mỗi mục hiện "2 người lớn · 1 trẻ em" và các dòng giá. Nút [Sửa] mở cùng bộ đếm như ở trang chi tiết (`GuestCounters`) và gọi `PATCH` với `guests` khi bấm Cập nhật. Đơn giá vé trẻ em nằm ở `attributes` của sản phẩm mà `CartResponse` không mang, nên Web tải `GET /products/{id}` khi mở [Sửa]; chưa tải xong hoặc lỗi thì bộ đếm chỉ hiện giới hạn tuổi, không nói "cùng giá người lớn". Mục hết chỗ không có nút [Sửa].
- **Trang chi tiết, hộp đặt:**
  - Vé tham quan, golf, chuyến bay: thay bộ đếm "số khách" bằng hai bộ đếm Người lớn (≥ 1) và Trẻ em (≥ 0), kèm đơn giá từng loại [M4] [M5]. Tổng trong hộp đặt vẫn là ước tính để hiển thị, tính theo cùng luật §4.4.
  - Khách sạn: số phòng, số người lớn, số trẻ em, kèm gợi ý "Tối đa {C} khách/phòng". Khi vượt sức chứa, gợi ý thêm phòng [M7] [M11].
  - Combo: giữ bộ đếm số gói.
  - `POST /cart/items` gửi kèm `guests`. Bộ đếm chặn ở nút bấm theo R-CRT-01…03 (tối thiểu 1 người lớn, tối đa 9 khách, mỗi phòng một người lớn); nút "Thêm vào giỏ hàng" và "Đặt ngay" khoá khi lựa chọn chưa hợp lệ, ví dụ vượt sức chứa (kèm nút "Thêm 1 phòng").
- **Trợ lý** (`useAssistantCart`, dùng cho cả widget và `/assistant`): lấy `intent.party` của `ItineraryResponse`.
  - Dịch vụ tính theo người: gửi `guests = party`, `quantity` bằng tổng số khách.
  - Khách sạn: gửi `quantity = min(adults, max(1, ⌈(adults + children) / C⌉))` phòng và `guests = party`. Hạng phòng không có C thì đặt 1 phòng.
  - Combo: gửi `guests = party`, `quantity = 1`.
  - Mục bị từ chối (ví dụ vượt sức chứa) được báo trong toast tổng kết như hiện nay.
  - Tổng trên lịch trình vẫn có thể khác tổng giỏ ở những vé có giá trẻ em. Giá ở checkout là giá chính thức (`hop-dong-tich-hop-backend.md` §7.2).

### 6.10. Văn bản giao diện

| Chỗ | Văn bản |
|---|---|
| Tên bước | "Hành khách", "Dịch vụ", "Xem lại và thanh toán" |
| Bộ đếm | "Người lớn · Từ 12 tuổi", "Trẻ em · Dưới 12 tuổi" |
| Nhãn ô họ tên | "Họ *" và "Tên đệm và tên *" (ví dụ: "Nguyễn", "Minh Anh") |
| Ghi chú họ tên | "Nhập đúng họ tên như trên CCCD, hộ chiếu hoặc giấy khai sinh. Hãng bay, khách sạn có thể từ chối nếu tên sai." |
| Ngày sinh | Nhãn "Ngày sinh (dd/mm/yyyy)"; dòng phụ "{n} tuổi vào {dd/mm/yyyy}" |
| Hộp tóm tắt lỗi | "Còn {n} thông tin cần sửa", mỗi dòng là một link tới trường |
| Nút | "Tiếp tục", "Quay lại", "Thanh toán {tổng}" |
| Vé không có giá trẻ em | "Trẻ em: cùng giá người lớn" |
| Chuyến bay có trẻ em | "Chưa có giá vé trẻ em riêng: trẻ em và em bé có ghế riêng, tính giá người lớn." |
| Sức chứa phòng | "Tối đa {x} khách/phòng"; "Khách sạn chưa công bố sức chứa phòng" |
| Tải lại trang | "Để bảo vệ thông tin cá nhân, họ tên và ngày sinh không được lưu khi tải lại trang. Vui lòng nhập lại." |
| Giỏ đổi ở tab khác | "Giỏ hàng vừa thay đổi. Danh sách dịch vụ đã được cập nhật." |

### 6.11. Khả năng truy cập

- Thanh bước là `<nav aria-label="Các bước thanh toán">` chứa `<ol>`; bước hiện tại có `aria-current="step"`.
- Khi chuyển bước, focus chuyển tới tiêu đề của bước mới.
- Hộp tóm tắt lỗi có `role="alert"`. Lỗi của từng trường được nối với trường qua `aria-describedby`.
- Nút bộ đếm có nhãn đọc được ("Thêm người lớn", "Bớt trẻ em"); số hiện tại được đọc qua vùng `aria-live="polite"`.
- Ô ngày sinh dùng `inputMode="numeric"`, có ví dụ định dạng trong nhãn, không chỉ trong placeholder.

---

## 7. Hợp đồng API

### 7.1. Nguyên tắc

- Chỉ thêm schema và trường mới. Mọi trường mới là tuỳ chọn, cả trong request lẫn response (`api-contract.md` §3.2). Không đổi tên, không xoá, không đổi nghĩa trường cũ: `quantity`, `lineTotal`, `guestNames` giữ nguyên nghĩa.
- File đã sửa: `src/shared/contracts/schemas/booking.yaml`, `schemas/common.yaml`, và phần mô tả trong `paths/booking.yaml`. `openapi.yaml` lên **1.10.0**. `src/frontend/src/types/api.gen.ts` sinh lại bằng `openapi-typescript`, và `validate_contract.py` kiểm thêm các mock mới (§7.7).

### 7.2. Schema mới

```yaml
TravelerType:
  type: string
  enum: [ADULT, CHILD]
  description: ADULT từ 12 tuổi; CHILD dưới 12 tuổi tại ngày sử dụng sớm nhất của đơn.
FareType:
  type: string
  enum: [ADULT, CHILD, ROOM, PACKAGE]
GuestCounts:
  type: object
  required: [adults, children]
  properties:
    adults:   { type: integer, minimum: 1, maximum: 9 }
    children: { type: integer, minimum: 0, maximum: 8 }
FareLine:
  type: object
  required: [fareType, unitPrice, count, nights, amount]
  properties:
    fareType:  { $ref: ../openapi.yaml#/components/schemas/FareType }
    unitPrice: { type: integer, minimum: 0, description: VND cho 1 khách, 1 phòng-đêm hoặc 1 gói. }
    count:     { type: integer, minimum: 1 }
    nights:    { type: [integer, 'null'], minimum: 1, description: Chỉ khác null khi fareType là ROOM. }
    amount:    { type: integer, minimum: 0, description: unitPrice × count × (nights hoặc 1). }
CheckoutTraveler:
  type: object
  required: [travelerRef, type, surname, givenNames]
  properties:
    travelerRef: { type: string, pattern: '^[A-Za-z0-9_-]{1,36}$', description: Mã tạm do Web sinh, duy nhất trong request. }
    type:        { $ref: ../openapi.yaml#/components/schemas/TravelerType }
    surname:     { type: string, minLength: 1, maxLength: 50, description: Họ. Chỉ chữ cái, khoảng trắng, dấu nháy đơn, gạch nối. }
    givenNames:  { type: string, minLength: 1, maxLength: 50, description: Tên đệm và tên. Cùng quy tắc ký tự. }
    birthDate:   { type: [string, 'null'], format: date, description: Bắt buộc khi type là CHILD (Backend kiểm, lỗi REQUIRED). }
CheckoutRoom:
  type: object
  required: [travelerRefs, leadTravelerRef]
  properties:
    travelerRefs:    { type: array, minItems: 1, maxItems: 9, items: { type: string } }
    leadTravelerRef: { type: string }
BookingTraveler:
  type: object
  required: [fullName, type, roomNo, isLead]
  properties:
    fullName: { type: string }
    type:     { $ref: ../openapi.yaml#/components/schemas/TravelerType }
    roomNo:   { type: [integer, 'null'], minimum: 1, description: Chỉ khác null với khách sạn. }
    isLead:   { type: boolean, description: Người đại diện nhận phòng. Luôn false với loại khác. }
```

`BookingTraveler` không có ngày sinh, để response trả ít dữ liệu cá nhân nhất có thể.

`ValidationFieldError` (trong `schemas/common.yaml`) là một phần tử của `details.fields[]`:

```yaml
ValidationFieldError:
  type: object
  required: [field, reason, message]
  properties:
    field:      { type: string, description: 'Đường dẫn trong request, ví dụ travelers[2].birthDate hoặc itemDetails[0].rooms[1].' }
    reason:     { type: string, description: Mã ở §5.6. Client gặp mã lạ thì hiển thị message. }
    message:    { type: string, description: Tiếng Việt, hiển thị được trực tiếp. }
    cartItemId: { type: string, description: 'Có khi vi phạm thuộc một mục giỏ, để Web gắn lỗi vào đúng thẻ dịch vụ.' }
```

### 7.3. Trường thêm vào schema có sẵn

| Schema | Trường thêm | Ghi chú |
|---|---|---|
| `AddCartItemRequest` | `guests?: GuestCounts` | Theo R-CRT-01…05 |
| `UpdateCartItemRequest` | `guests?: GuestCounts` | Được tính vào `minProperties: 1` |
| `CartItem` | `guests?: GuestCounts`, `fares?: FareLine[]` | Backend mới luôn trả hai trường này. `lineTotal` bằng tổng `fares[].amount` |
| `CheckoutRequest` | `travelers?: CheckoutTraveler[]` (1–9 phần tử) | Có `travelers` thì áp dụng luật mới; không có thì theo §7.6 |
| `CheckoutItemDetail` | `travelerRefs?: string[]` (dịch vụ tính theo người, combo), `rooms?: CheckoutRoom[]` (khách sạn) | Khi request có `travelers`, `guestNames` bị bỏ qua |
| `BookingItem` | `fares?: FareLine[]`, `travelers?: BookingTraveler[]` | `guestNames` là họ tên các khách của mục, theo thứ tự trong đoàn |
| Lỗi `VALIDATION_ERROR` | `details.fields[]` (`ValidationFieldError`: `field`, `reason`, `message`, `cartItemId?`) | Mã `reason` ở §5.6. `field` là đường dẫn trong request, ví dụ `travelers[2].birthDate`. `cartItemId` có khi lỗi thuộc một mục giỏ |
| Lỗi `PRICE_CHANGED` | `details.fareType?` | Có giá trị `CHILD` khi giá trẻ em đổi |

### 7.4. Ví dụ

`POST /api/v1/bookings` cho gia đình ở §4.5:

```json
{
  "contact": { "fullName": "Nguyễn Minh Anh", "email": "minhanh@example.vn", "phone": "0912345678" },
  "travelers": [
    { "travelerRef": "t1", "type": "ADULT", "surname": "Nguyễn", "givenNames": "Minh Anh" },
    { "travelerRef": "t2", "type": "ADULT", "surname": "Trần", "givenNames": "Thu Hà" },
    { "travelerRef": "t3", "type": "CHILD", "surname": "Nguyễn", "givenNames": "Gia Bảo", "birthDate": "2019-05-12" }
  ],
  "itemDetails": [
    {
      "cartItemId": "ci-hotel",
      "rooms": [ { "travelerRefs": ["t1", "t2", "t3"], "leadTravelerRef": "t1" } ],
      "specialRequest": "Phòng tầng cao nếu còn"
    },
    { "cartItemId": "ci-vinwonders", "travelerRefs": ["t1", "t2", "t3"] },
    { "cartItemId": "ci-vj601", "travelerRefs": ["t1", "t2", "t3"] }
  ]
}
```

Một `CartItem` trong `CartResponse`:

```json
{
  "cartItemId": "ci-vinwonders",
  "product": { "productId": "…", "name": "[Wonder Ngon] - Vé VinWonders Nha Trang + Buggy + Fastpass 3 game hot", "taxonomy": "attraction", "unitPrice": 1500000, "attributes": { "childPrice": 504000 }, "…": "ProductSummary" },
  "usingDate": "2026-10-18",
  "quantity": 3,
  "nights": null,
  "guests": { "adults": 2, "children": 1 },
  "fares": [
    { "fareType": "ADULT", "unitPrice": 1500000, "count": 2, "nights": null, "amount": 3000000 },
    { "fareType": "CHILD", "unitPrice": 504000, "count": 1, "nights": null, "amount": 504000 }
  ],
  "lineTotal": 3504000
}
```

Phần thêm vào một `BookingItem` khách sạn:

```json
{
  "fares": [ { "fareType": "ROOM", "unitPrice": 777192, "count": 1, "nights": 2, "amount": 1554384 } ],
  "travelers": [
    { "fullName": "Nguyễn Minh Anh", "type": "ADULT", "roomNo": 1, "isLead": true },
    { "fullName": "Trần Thu Hà", "type": "ADULT", "roomNo": 1, "isLead": false },
    { "fullName": "Nguyễn Gia Bảo", "type": "CHILD", "roomNo": 1, "isLead": false }
  ],
  "guestNames": ["Nguyễn Minh Anh", "Trần Thu Hà", "Nguyễn Gia Bảo"]
}
```

### 7.5. Lỗi

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Thông tin hành khách chưa hợp lệ.",
    "retryable": false,
    "requestId": "01JB…",
    "details": {
      "fields": [
        { "field": "travelers[2].birthDate", "reason": "CHILD_AGE_INVALID", "message": "Bé đã đủ 12 tuổi vào 17/10/2026. Vui lòng chọn loại Người lớn." },
        { "field": "itemDetails[0].rooms[0]", "reason": "OCCUPANCY_EXCEEDED", "message": "Phòng 1 chứa tối đa 3 khách.", "cartItemId": "ci-hotel" }
      ]
    }
  }
}
```

Không thêm mã lỗi mới vào `ErrorCode`. Mọi lỗi hành khách dùng `VALIDATION_ERROR` và phân biệt bằng `reason`, để client cũ vẫn hiểu được.

### 7.6. Tương thích với client cũ

- **Giỏ không có `guests`:** áp dụng mặc định R-CRT-05. Số tiền y như hiện nay.
- **`POST /bookings` không có `travelers`:** Backend coi `guestNames` là tên người lớn. Chỉ chấp nhận khi mọi mục giỏ không có trẻ em; giỏ có trẻ em thì trả `400 VALIDATION_ERROR` với `reason = TRAVELERS_REQUIRED`. Quy tắc tên hiện có trong `hop-dong-tich-hop-frontend.md` §4.5 nay được Backend kiểm thật: vé máy bay đủ `quantity` tên không rỗng; khách sạn có ít nhất 1 tên; mọi mục có `itemDetails`. Vi phạm thì trả `400 VALIDATION_ERROR`. Đây là phần sửa lỗi L5, nên request cũ nào đang lọt qua sẽ bị từ chối.
- **Số khách tối đa 9 (D6):** vé, chuyến bay, golf và khách sạn có `quantity` (hoặc `adults + children`) quá 9 bị từ chối theo R-CRT-01, trước đây được nhận tới 99. Combo giữ giới hạn 99 gói vì khách của combo chỉ để ghi nhận.
- Đường cũ sẽ được gỡ ở v2, sau khi Web chuyển hết sang luật mới (D11). Hiện chỉ Web gọi `/cart` và `/bookings`; Agent không gọi hai nhóm endpoint này.

### 7.7. Mock

Theo `docs/spec/shared-assets.md`, tất cả đăng ký trong `src/shared/mocks/index.json`:

- Mới: `getCart.200-family.json`, `createBooking.201-family.json`, `createBooking.400-party-invalid.json`, `createBooking.409-price-changed-child.json` (`details.fareType = CHILD`), `updateCartItem.200-guests.json`, `updateCartItem.400-guests-invalid.json`.
- Sửa cho có `guests`, `fares`, `travelers`: các fixture giỏ và đơn hiện có (`addCartItem`, `getCart`, `removeCartItem`, `updateCartItem`, `createBooking`, `getBooking`).
- `src/shared/contracts/tests/validate_contract.py` kiểm thêm: ví dụ request ở §7.4 hợp lệ theo `CheckoutRequest` và `AddCartItemRequest`; các ca sai bị từ chối (thiếu `givenNames`, `travelerRef` có khoảng trắng, không có cả `quantity` lẫn `guests`, `GuestCounts` không có người lớn hoặc 10 khách, `FareLine` loại `BAG` (chưa có ở 1.10.0), loại khách `INFANT`); mọi phần tử `details.fields[]` trong mock booking đúng `ValidationFieldError`. Việc `lineTotal` bằng tổng `fares[].amount` và `total` bằng tổng `lineTotal` do contract test của Backend kiểm (`tests/contract/test_booking_contract.py`).
- Bộ ca kiểm thử luật dùng chung cho Web và Backend: `src/shared/contracts/tests/booking-rules-cases.json` (§12.2).

---

## 8. Backend

### 8.1. Domain

Đây là code thuần, không import framework (`architecture.md` §2, quy tắc 4).

| File | Nội dung |
|---|---|
| `domain/booking/party.py` (mới) | `TravelerType`, `Traveler`, `Guests`, `RoomAllocation`, `MAX_PARTY`; `age_on`, `adult_from` (ngày tròn 12 tuổi), `fare_type_on`, `is_infant_on` |
| `domain/booking/fares.py` (mới) | `FareType`, `FareLine` (đọc/ghi JSON của `booking_items.metadata`), `child_unit_price` theo §4.4, `fare_lines` theo §4.3, `lines_total`; hằng `PER_PERSON_TAXONOMIES`, `CHILD_PRICED_TAXONOMIES` |
| `domain/booking/party_rules.py` (mới) | Hàm kiểm thuần cho §5.2, §5.3, §5.5, mỗi hàm trả danh sách `Violation(field, reason, params, cart_item_id)` và không dừng ở vi phạm đầu tiên: `check_contact`, `check_party`, `check_items`, `check_checkout`, `check_legacy` (request cũ, §7.6), `check_cart_guests`, `resolve_cart_guests` (thêm/sửa mục giỏ, R-CRT-01…05), `default_guests`. Dữ liệu vào là các dataclass `ContactInput`, `TravelerInput`, `RoomInput`, `ItemInput`, `CartFacts` |
| `domain/booking/pricing.py` | `line_total` giữ lại cho đơn tạo trước thay đổi và client cũ (trường hợp không có trẻ em). Thêm `effective_child_price` và `check_child_price`: so giá vé trẻ em với snapshot của mục giỏ, lệch thì `PRICE_CHANGED` kèm `fareType = CHILD` |
| `domain/booking/models.py` | `CartLine` thêm `adults`, `children`, `child_unit_price_snapshot` và thuộc tính `guests`; `BookingItem` thêm `fares`, `traveler_refs`, `rooms`; `Booking` thêm `travelers`. `BookingItem.line_total` là tổng `fares` (đơn cũ không có `fares` thì dùng công thức không có trẻ em) |

### 8.2. Application và adapter

- `CartService.add` và `CartService.update` nhận `guests`, tính `quantity` và `guests` bằng `resolve_cart_guests` (cộng dồn khi thêm trùng, R-CRT-04), kiểm R-CRT, rồi ghi `adults`, `children`, snapshot giá người lớn và snapshot giá trẻ em. `cart_response` trả thêm `guests` và `fares`. Port `CartRepository.add` (cộng dồn trong SQL) đổi thành `upsert` ghi giá trị **tuyệt đối**, vì luật sức chứa và số khách tối đa phải kiểm trên kết quả đã cộng, mà SQL không biểu diễn được.
- `CreateBookingHold` nhận `travelers`, `ItemDetail.traveler_refs`, `ItemDetail.rooms`. Nó kiểm theo §8.3 trước khi gọi Stripe, rồi dựng `BookingItem` có `fares` và phân bổ. `travelers = None` là request cũ (§7.6).
- `application/booking/messages.py` (mới) dựng câu thông báo tiếng Việt (§5.6) từ `Violation`; `errors.ValidationFailed` mang `fields[]` có `reason`, `message` và `cartItemId`. Domain chỉ trả `Violation`, không chứa câu chữ.
- `views.booking_response` thêm `fares`, `travelers` (không có ngày sinh), và dựng `guestNames` từ hành khách. `cart_response` thêm `guests`, `fares` và `product.attributes.maxOccupancy` để Web kiểm sức chứa mà không gọi thêm.
- Adapter Postgres của giỏ và đơn nằm chung ở `infrastructure/persistence/postgres_booking.py`; nó đọc và ghi các cột mới (§9), ghi thêm `booking_travelers` và `line_total` do Backend tính. Port `BookingStore` không đổi chữ ký vì `Booking` đã mang `travelers`.
- DTO ở `api/v1/schemas/booking.py` và route `api/v1/routes/booking.py` ánh xạ các trường mới. Sai kiểu dữ liệu vẫn do pydantic trả `422`; vi phạm luật nghiệp vụ trả `400 VALIDATION_ERROR`, và `api/errors.py` dùng câu tổng của `ValidationFailed` thay câu mặc định. Route không chứa luật nghiệp vụ.

### 8.3. Trình tự kiểm của `POST /bookings`

Phần này bổ sung vào `so-do-luong-dat-cho-thanh-toan.md` §6.2.

1. Kiểm schema request (pydantic). Sai kiểu dữ liệu (ví dụ `birthDate` không phải ngày, `travelerRef` sai mẫu): `422`, như mọi endpoint khác. Sai **luật** (thiếu họ, trẻ em đã đủ 12 tuổi, …) không tới bước này mà nằm ở bước 5.
2. Có đơn giữ chỗ còn hạn: `409 BOOKING_PENDING_PAYMENT` (như hiện hành).
3. Giỏ rỗng: `400 CART_EMPTY`.
4. Tải sản phẩm từ catalog. Sản phẩm không tồn tại: `404 PRODUCT_NOT_FOUND`.
5. Kiểm luật dữ liệu: R-ITM-01, §5.2, §5.3 (dùng `maxOccupancy` của catalog và `guests` của giỏ); request cũ không có `travelers` đi qua `check_legacy` (§7.6). Gom **mọi** vi phạm vào một `400 VALIDATION_ERROR`. Có vi phạm thì dừng: không gọi Stripe, không ghi gì.
6. Với từng mục: còn bán; giá người lớn và giá trẻ em khớp snapshot; ngày nằm trong cửa sổ bán. Vi phạm trả `409 PRODUCT_UNAVAILABLE`, `409 PRICE_CHANGED` hoặc `422 DATE_OUT_OF_RANGE`, như hiện hành. Giá được kiểm sau luật dữ liệu để khách thấy thay đổi giá ngay trước khi trả tiền.
7. Tạo phiên Stripe (§8.4).
8. Ghi đơn, hành khách và dòng giá trong một transaction, như hiện hành.

### 8.4. Stripe

- Mỗi dòng giá thành một line item. Tên line item: "{tên sản phẩm} · Người lớn", "· Trẻ em", với khách sạn là "· {n} đêm", với combo là "· Gói"; tên sản phẩm dài hơn 180 ký tự thì cắt và thêm "…". `unit_amount` bằng đơn giá (khách sạn nhân thêm số đêm để dòng khớp `amount`); `quantity` bằng `count`.
- Tổng các line item phải bằng `total` của đơn. Nếu lệch (chỉ xảy ra khi code có lỗi), Backend không tạo phiên, ghi log lỗi và trả lỗi máy chủ; không gửi số tiền lệch sang Stripe.
- Không gửi họ tên hay ngày sinh hành khách sang Stripe, kể cả trong metadata. Stripe chỉ nhận `customer_email`, như hiện hành.

### 8.5. CDP

- Không thêm event, không đổi trường của event. 13 trường theo handbook là cố định.
- Event `purchase` vẫn là một event cho mỗi mục, khớp 1:1 với `booking_items`. `quantity` là `quantity` của mục (số khách, vé, phòng hoặc gói); `unitPrice` là giá catalog người lớn, như hiện nay.
- Hệ quả: tổng chi tiêu tính từ CDP (FR-CDP-03) có thể cao hơn số tiền thu thật khi đơn có vé trẻ em. Doanh thu chính xác đọc từ `app.bookings`. Điểm này cần ghi vào `hop-dong-tich-hop-cdp.md` sau khi chốt.

### 8.6. Dữ liệu cá nhân và log

- Họ tên và ngày sinh chỉ đi trong `POST /bookings` (qua BFF, HTTPS) và chỉ lưu ở `app.booking_travelers`.
- Không ghi log họ tên, ngày sinh, số điện thoại. Log chỉ ghi số lượng (`adults=2 children=1`) và `requestId` (NFR-SEC-01, `hop-dong-tich-hop-backend.md` §8.6).
- Response không trả ngày sinh.
- Không gửi dữ liệu hành khách sang CDP, Insider hay Stripe.

---

## 9. Database

`db/vota_schema.sql`, `db/init/01_vota.sql` và migration `db/migrations/0005_checkout_travelers.sql` phải sửa cùng nhau, trong cùng một commit (`AGENTS.md` §6).

### 9.1. Thay đổi

| Bảng | Thay đổi | Ghi chú |
|---|---|---|
| `app.cart_items` | Thêm `adults integer NOT NULL DEFAULT 1` (≥ 1); `children integer NOT NULL DEFAULT 0` (≥ 0); `CHECK (adults + children <= 9)`; `child_unit_price_snapshot numeric(14,2)` (NULL nghĩa là sản phẩm không có giá trẻ em hợp lệ lúc thêm hoặc sửa) | Nguồn của `guests`, và của việc kiểm `PRICE_CHANGED` cho giá trẻ em. Dòng có sẵn được điền theo R-CRT-05: `adults = quantity` (khách sạn: số phòng; combo: 1); `quantity` của dòng không phải combo quá 9 bị kéo về 9 |
| `app.booking_travelers` (mới) | `traveler_id uuid` (khoá chính), `booking_id` (FK `app.bookings`, xoá theo đơn), `traveler_ref`, `position` (1–9), `traveler_type` (`adult` hoặc `child`), `surname`, `given_names`, `full_name` (Backend nối từ hai cột trên), `birth_date`. `UNIQUE (booking_id, traveler_ref)`; `UNIQUE (booking_id, position)`; `CHECK (traveler_type = 'adult' OR birth_date IS NOT NULL)` | Đoàn khách của đơn (D8). Khoá chính là `traveler_id` thay vì (`booking_id`, `traveler_ref`) để bảng giống các bảng `app` còn lại; ràng buộc duy nhất giữ đúng ý cũ |
| `app.booking_items` | Thêm `metadata jsonb NOT NULL DEFAULT '{}'`. `line_total` bỏ biểu thức sinh (`ALTER COLUMN line_total DROP EXPRESSION`, cần Postgres 13 trở lên; compose đang dùng Postgres 16) và từ nay do Backend ghi | `metadata` là trường đã có trong ERD của PRD (`data-model.md` §2.2: "Thông tin vé, phòng, ghi chú đặc biệt"). `line_total` là phần sửa lỗi L8 (D9) |

`guest_names` được giữ lại và ghi bằng họ tên khách của mục, để truy vấn cũ và client cũ không vỡ.

Migration `0005_checkout_travelers.sql` chạy lại được nhiều lần (idempotent) và không xoá dữ liệu: `adults` thêm dạng cho phép NULL, điền từ `quantity`, rồi mới đặt `NOT NULL`; `line_total` bỏ biểu thức sinh bằng `DROP EXPRESSION IF EXISTS` và chỉ tính lại cho đơn khách sạn cũ có `metadata = '{}'` (đơn mới đã có `fares`). Đã thử trên một bản sao cơ sở dữ liệu ở lược đồ cũ: sau migration lược đồ giống hệt lược đồ dựng mới từ `db/init/01_vota.sql`. `db/verify.sql` thêm năm phép kiểm: tổng đơn bằng tổng `line_total`; tổng đơn bằng số tiền thanh toán; mục có `metadata.fares` thì `line_total` bằng tổng `fares[].amount`; thứ tự hành khách liên tục 1…n và tối đa 9 người mỗi đơn; mục giỏ có ít nhất 1 người lớn và tối đa 9 khách. Trẻ em luôn có ngày sinh nhờ `CHECK` của bảng. Seed (`src/data_collection/seed/database.py`) ghi `line_total` cho các đơn mẫu.

### 9.2. Nội dung `booking_items.metadata`

```json
{
  "fares": [
    { "fareType": "ADULT", "unitPrice": 1500000, "count": 2, "nights": null, "amount": 3000000 },
    { "fareType": "CHILD", "unitPrice": 504000, "count": 1, "nights": null, "amount": 504000 }
  ],
  "travelerRefs": ["t1", "t2", "t3"],
  "rooms": []
}
```

---

## 10. Frontend

### 10.1. Cấu trúc file

Thư mục `src/frontend/src/components/checkout/` (mới):

| File | Vai trò |
|---|---|
| `CheckoutView.tsx` | Khung `/checkout`: kiểm đăng nhập, tải giỏ, thanh bước, bước hiện tại, tóm tắt đơn. Gọi `useCheckout()` một lần ở đây |
| `useCheckout.ts` | Toàn bộ trạng thái và hành động của ba bước: đoàn khách, phân bổ, lỗi, đồng bộ giỏ, thanh toán |
| `TravelersStep.tsx`, `ServicesStep.tsx`, `ReviewStep.tsx` | Ba bước ①, ②, ③ |
| `OrderSummary.tsx` | `SummaryPanel` (cột phải, dính khi cuộn) và `MobileBar` (thanh đáy cùng bottom sheet) |
| `CheckoutParts.tsx` | Mảnh dùng chung: `Stepper`, `ErrorSummaryBox`, `Field`, `CounterRow`, `PrimaryButton`, `Skeleton`, `Notice` |
| `FareLines.tsx` | Hiển thị `fares` (giỏ, bước ②, trang đơn); chỉ hiển thị, không tự tính |
| `GuestCounters.tsx` | Bộ đếm khách dùng chung cho hộp đặt ở trang chi tiết và nút [Sửa] ở giỏ |
| `checkoutRules.ts` | Bộ luật §5 ở Web. Code thuần, phản chiếu `domain/booking/party_rules.py` |
| `allocation.ts` | Đoàn mặc định (§6.5), phân bổ, đổi phân bổ thành `guests`, dữ liệu gửi Backend |
| `serverErrors.ts` | Đưa `details.fields[]` của `VALIDATION_ERROR` về đúng bước và trường |
| `patchQueue.ts` | Hàng đợi `PATCH /cart/items` theo từng mục (§10.3) |
| `fareEstimate.ts` | Ước tính dòng giá để **hiển thị** ở hộp đặt, trước khi có giỏ. Phản chiếu `domain/booking/fares.py` |
| `guestCounts.ts` | Luật của bộ đếm (R-CRT chặn ngay ở nút bấm) và `partyCartRequest` cho trợ lý (§6.9) |

Sửa thêm: `services/booking.ts` (kiểu `GuestCounts`, `FareLine`, `CheckoutTraveler`, `BookingTraveler`, `ValidationFieldError`), `context/TravelContext.tsx` (`addToCart` nhận `options.guests`; `updateCartItem` trả `ApiError | null` và có tuỳ chọn `silent`), `cart/CartView.tsx`, `detail/ProductDetailView.tsx`, `confirmation/ConfirmationView.tsx`, `hooks/useAssistantCart.ts`, `assistant/AssistantResultPanel.tsx`, `assistant/AiFloatingWidget.tsx`, và `types/api.gen.ts` (sinh lại).

### 10.2. Nguyên tắc

- **Trạng thái nằm ở một hook**, gọi ở `CheckoutView`. Nhờ vậy hộp đăng nhập lại (phiên hết hạn giữa chừng) hiện đè lên mà dữ liệu đang nhập vẫn còn (§6.2).
- **Web không tự cộng tiền.** Mọi số tiền trong `/checkout`, `/cart`, `/booking` lấy từ `CartResponse` và `BookingResponse`. `fareEstimate.ts` chỉ dùng ở hộp đặt của trang chi tiết, có nhãn "ước tính", và không gửi đi đâu.
- **Họ tên và ngày sinh chỉ nằm trong bộ nhớ của trang.** Không ghi `localStorage`, `sessionStorage`, URL hay cookie. Tải lại trang thì mất; Web nói rõ điều này (§6.10).
- **Một bộ luật, hai bản.** `checkoutRules.ts` và `party_rules.py` chạy cùng `booking-rules-cases.json` (§12.2), và dùng cùng mã `reason` và câu thông báo (§5.6).
- **Bước nằm ở `?step=`** và mỗi lần chuyển là một mục trong lịch sử trình duyệt. Next.js 16 dùng History API gốc (`window.history.pushState`), tích hợp với router, nên không cần thư viện thêm; sự kiện `popstate` cập nhật bước.
- **Chặn ở nút bấm khi có thể.** Bộ đếm khoá − và + ở giới hạn, nên phần lớn R-TRV-01, R-TRV-02, R-CRT-01…03 không cần báo lỗi.

### 10.3. Đồng bộ giỏ (`patchQueue.ts`)

Mỗi thay đổi phân bổ làm đổi `guests` hoặc số phòng của một mục phải ghi vào giỏ để Backend tính lại giá (§6.6). Có ba điểm dễ sai, và hàng đợi xử lý cả ba:

- **Đợi 400 ms không có thao tác mới rồi mới gọi.** Khách bấm liên tục chỉ tốn một request.
- **Các lần chạy của cùng một mục nối tiếp nhau, không bao giờ song song.** `PATCH` ghi giá trị tuyệt đối, nên lần sau phải tới sau lần trước thì giỏ mới khớp lựa chọn cuối của khách.
- **So với cái đã gửi, không so với cái đã vẽ.** Sau một `PATCH`, React chưa kịp vẽ lại giỏ mới thì lần đồng bộ kế tiếp vẫn đọc giỏ cũ. Nếu khách bỏ rồi chọn lại một người, giá trị mong muốn trùng giỏ cũ và lần `PATCH` thứ hai bị bỏ qua, để Backend giữ giá trị của lần thứ nhất. Web lưu số khách đã gửi (hoặc đang gửi) cho từng mục và so với đó. Đã có test tái hiện đúng tình huống này (§12.3).

Trạng thái "đang cập nhật giá" của một mục đúng cả lúc chờ debounce, chờ tới lượt và đang chạy, và không nháy tắt giữa hai lần chạy liền nhau. Nút Tiếp tục và việc đổi bước chờ mọi `PATCH` xong, rồi tải `GET /cart` (theo thứ tự đó, để bản `GET` cũ không đè kết quả `PATCH`) trước khi vẽ bước sau, nên thẻ dịch vụ hiện đúng giá ngay lần vẽ đầu. Rời trang khi còn lần đồng bộ đang chờ thì lần đó được gửi nốt.

### 10.4. Đưa lỗi của Backend về đúng chỗ (`serverErrors.ts`)

- `travelers[i].surname`, `.givenNames`, `.birthDate`, `contact.*` và `travelers` thuộc bước ①; `itemDetails[j]…` thuộc bước ②. Lỗi ở cả hai bước thì về bước sớm nhất.
- `travelers[i]` được đổi thành `travelerRef` theo thứ tự đã gửi, rồi thành id ô nhập (`sn-{ref}`, `gn-{ref}`, `dob-{ref}`, `c-name`, `c-phone`); `itemDetails[j]` thành `cartItemId` theo thứ tự đã gửi, hoặc lấy từ `cartItemId` của lỗi; `rooms[k]` thành id phòng.
- Hộp tóm tắt lỗi chỉ liệt kê lỗi của **bước đích**, vì lỗi ở bước sau chưa có ô nào để link tới. Lỗi của bước sau vẫn được giữ và hiện trên thẻ khi khách tới đó.
- `GUEST_COUNT_MISMATCH`: Web tải lại giỏ, tính lại phân bổ mặc định cho mục đó, về bước ② kèm dòng "Số khách của một số dịch vụ vừa thay đổi. Vui lòng xem lại giá."
- Chuyển bước thì hộp tóm tắt lỗi của bước cũ bị xoá trước, rồi mới ghi lỗi của Backend (thứ tự ngược lại làm mất hộp lỗi).

### 10.5. Trang giỏ, trang chi tiết, trợ lý, trang đơn

- **Bộ đếm dùng chung `GuestCounters`:** vé tham quan, golf, chuyến bay có Người lớn (≥ 1) và Trẻ em (≥ 0) kèm đơn giá từng loại; khách sạn có Số phòng, Người lớn, Trẻ em, gợi ý sức chứa và nút "Thêm 1 phòng" khi vượt sức chứa; combo chỉ có số gói (1–20). Luật ở `guestCounts.ts` và có test riêng.
- **Trang chi tiết:** hộp đặt dùng `GuestCounters` và `estimateFares` để hiện các dòng giá ước tính; gửi `guests` khi thêm vào giỏ (combo chỉ gửi `quantity`).
- **Trang giỏ:** hiện đoàn và dòng giá; [Sửa] mở `GuestCounters` trong một khung, bấm Cập nhật thì `PATCH`.
- **Trợ lý:** `itineraryCartItems(itinerary, party)` gắn `intent.party` vào từng mục; `useAssistantCart` đổi ra số lượng và `guests` bằng `partyCartRequest` (§6.9).
- **Trang đơn:** `ItemTravelers` hiện hành khách theo phòng (đánh dấu người đại diện) hoặc một dòng; `FareLines` hiện dòng giá. Đơn tạo trước thay đổi (`travelers` rỗng) hiện `guestNames`.

### 10.6. Khả năng truy cập

Đã làm đủ §6.11. Thêm: bottom sheet tóm tắt trên mobile là hộp thoại (`role="dialog"`, `aria-modal`); hộp thoại xác nhận bỏ khách và hộp thoại đơn đang giữ chỗ cũng vậy; khung chờ giá có `role="status"` và nhãn "Đang cập nhật giá".

---

## 11. Trường hợp biên

| # | Tình huống | Xử lý |
|---|---|---|
| E1 | Mở `/checkout` khi giỏ rỗng | Về `/cart` (§6.2) |
| E2 | Chưa đăng nhập | Hiện nút Đăng nhập, không hiện ba bước |
| E3 | Phiên hết hạn giữa chừng | Hộp đăng nhập lại có email điền sẵn; dữ liệu đang nhập giữ nguyên |
| E4 | Tải lại trang ở `?step=review` | Về bước ①, nói rõ họ tên và ngày sinh không được lưu khi tải lại (§6.10) |
| E5 | Giỏ đổi ở tab khác | Mục mới nhận phân bổ mặc định, mục đã xoá bị bỏ, banner "Giỏ hàng vừa thay đổi" |
| E6 | Trẻ tròn 12 tuổi giữa chuyến | Cảnh báo W-04; dịch vụ từ ngày đó tính giá người lớn; `guests` theo loại giá tại ngày của từng dịch vụ |
| E7 | Trẻ tròn 12 tuổi đúng ngày sử dụng sớm nhất | Chặn (R-TRV-05), câu nói rõ ngày tròn 12 tuổi |
| E8 | Sinh ngày 29/02 | Năm không nhuận coi sinh nhật là 01/03 (§4.2, có trong bộ ca chung) |
| E9 | Đoàn quá 9 người | Bộ đếm khoá; gọi thẳng API thì `PARTY_TOO_LARGE` |
| E10 | Dịch vụ hết chỗ giữa chừng | Thẻ báo lỗi; nút Thanh toán khoá khi giỏ còn mục hết chỗ; `409 PRODUCT_UNAVAILABLE` khi vẫn gửi |
| E11 | Giá vé trẻ em đổi sau khi bỏ vào giỏ | `409 PRICE_CHANGED` kèm `fareType = CHILD`; banner "Giá vé trẻ em của … đã đổi từ … thành …" và nút "Cập nhật và tiếp tục" (`PATCH` giữ `quantity` để ghi lại snapshot mới) |
| E12 | Đang có đơn giữ chỗ | `409 BOOKING_PENDING_PAYMENT`: hộp thoại tiếp tục thanh toán hoặc huỷ đơn đó và đặt lại đúng dữ liệu đang có |
| E13 | Stripe không phản hồi | `503`: ở lại bước ③ với nút Thử lại; không mất dữ liệu |
| E14 | Khách đổi ý liên tục, `PATCH` chậm | Hàng đợi §10.3: lần sau tới sau lần trước, giá cuối khớp lựa chọn cuối |
| E15 | Hạng phòng không công bố `maxOccupancy` (khoảng 5%) | Không kiểm sức chứa; thẻ ghi "Khách sạn chưa công bố sức chứa phòng" (D7) |
| E16 | Vé không có giá trẻ em hợp lệ (không có, bằng 0, cao hơn người lớn) | Trẻ em trả giá người lớn; UI ghi "Trẻ em: cùng giá người lớn" (D2) |
| E17 | Chuyến bay có trẻ em | Mọi hành khách trả `unitPrice`; ghi chú về giá vé trẻ em (D3) |
| E18 | Một `PATCH` lỗi ở bước ② | Lỗi gắn vào thẻ; bấm Tiếp tục hiện hộp tóm tắt, không sang bước ③ |
| E19 | Hạn hoàn tiền đã qua ngay lúc đặt | Câu chính sách huỷ nói rõ đơn không được hoàn tiền (§6.7) |
| E20 | Tên tài khoản có chữ số hoặc chỉ một từ | Ô họ tên của Người lớn 1 để trống thay vì điền sẵn giá trị sai (§6.5) |
| E21 | Hai hành khách trùng họ tên | Cảnh báo W-05, không chặn |
| E22 | Gọi thẳng `POST /bookings` với dữ liệu sai | `400 VALIDATION_ERROR` liệt kê mọi vi phạm; không tạo đơn, không tạo phiên Stripe (AC-BKG-06) |
| E23 | Client cũ không gửi `travelers` | Chấp nhận nếu giỏ không có trẻ em; có trẻ em thì `TRAVELERS_REQUIRED` (§7.6) |
| E24 | Đơn tạo trước thay đổi | `travelers` rỗng nên trang đơn hiện `guestNames`; `fares` được dựng lại theo công thức cũ (không có trẻ em) |
| E25 | Combo thêm trùng | `quantity` cộng dồn, `guests` lấy giá trị lớn hơn (R-CRT-04) |
| E26 | Ngày sinh dán đè một giá trị khác vào ô đã có | Định dạng lại từ các chữ số |

---

## 12. Kiểm thử và nghiệm thu

### 12.1. Tiêu chí nghiệm thu

Lấy nguyên từ `docs/prd/requirements.md` §3; cột phải là nơi được kiểm tự động.

| Mã | Kiểm ở đâu |
|---|---|
| AC-BKG-05 | `fares` trong bộ ca chung (ví dụ §4.5); `test_booking_contract.py` (`test_family_checkout_returns_travelers_and_fares_and_never_the_birth_date`, giỏ và đơn cùng tổng); `db/verify.sql` (tổng đơn, tổng dòng, số tiền thanh toán); `checkoutView.test.tsx` (tổng ở tóm tắt và bước Xem lại) |
| AC-BKG-06 | Ca cuối của nhóm `checkout` trong bộ ca chung; `test_validation_error_lists_every_violation_with_field_reason_and_message`; `test_checkout_travelers.py` (không gọi Stripe, không ghi đơn khi có vi phạm) |
| AC-BKG-07 | `checkoutView.test.tsx` (hộp "Còn n thông tin cần sửa", ở lại bước, focus vào trường đầu tiên, lỗi từ Backend về đúng bước); `checkoutServerErrors.test.ts` |
| G3 | Toàn bộ nhóm `checkout` và `cart` của bộ ca chung, chạy ở cả Backend và Web |
| G5 | Các test giữ chỗ, Stripe, huỷ, hoàn tiền có sẵn vẫn chạy và đạt |

### 12.2. Bộ ca dùng chung

`src/shared/contracts/tests/booking-rules-cases.json` là một file dữ liệu duy nhất, được đọc bởi `src/backend/tests/unit/domain/booking/test_party_rules.py` và `src/frontend/tests/unit/checkoutRules.test.ts`. Mỗi ca ghi dữ liệu vào và kết quả mong đợi (`field` và `reason` của mọi vi phạm). Một ca chạy sai ở một phía nghĩa là hai bản luật đã lệch nhau.

| Nhóm | Số ca | Nội dung |
|---|---|---|
| `age` | 14 | Tuổi tại một ngày: 7 tuổi, sát và đúng sinh nhật thứ 12, đủ 2 tuổi (em bé), sinh 29/02 ở năm nhuận và không nhuận, trẻ sơ sinh |
| `turnsAdult` | 3 | Ngày tròn 12 tuổi, kể cả sinh 29/02 |
| `checkout` | 41 | R-TRV-01…06, R-CON-01, R-ITM-01…04, R-FLT-01, R-HTL-01…05, combo, trẻ tròn 12 tuổi giữa chuyến, và ca AC-BKG-06 (nhiều vi phạm cùng lúc) |
| `cart` | 22 | R-CRT-01…05: thêm và sửa mục giỏ, client cũ không gửi `guests`, cộng dồn, sức chứa, combo |
| `fares` | 10 | Dòng giá theo §4.3, §4.4, §4.5: khách sạn nhiều đêm, vé có giá trẻ em, `childPrice` bằng 0 hoặc cao hơn giá người lớn, chuyến bay, combo |

Thêm một luật hoặc sửa một câu thông báo: thêm hoặc sửa ca trong file này trước, rồi sửa hai phía cho tới khi cả hai đạt.

### 12.3. Kiểm thử theo tầng

| Tầng | File | Kiểm gì |
|---|---|---|
| Unit domain | `tests/unit/domain/booking/test_party_rules.py` | Chạy bộ ca chung; các hàm tuổi, loại giá, dòng giá |
| Unit application | `tests/unit/application/booking/test_checkout_travelers.py`, `test_booking_flow.py` | Trình tự §8.3; không tạo đơn và không gọi Stripe khi có vi phạm; tổng dòng giá bằng tổng đơn; `PRICE_CHANGED` của giá trẻ em; request cũ; họ tên và ngày sinh không vào log, Stripe, CDP (§8.6); giữ chỗ, huỷ, hoàn tiền như trước |
| Contract API | `tests/contract/test_booking_contract.py` | Giỏ trả `guests` và `fares`; `POST /bookings` gia đình; `400` liệt kê mọi vi phạm; sai kiểu vẫn `422`; luật thêm/sửa giỏ; `PATCH` tính lại `quantity` và `fares`; response không có ngày sinh |
| Integration DB | `tests/integration/test_booking_postgres.py` | `upsert` ghi giá trị tuyệt đối; lưu và đọc hành khách; ràng buộc `CHECK`. Cần `RUN_POSTGRES_INTEGRATION=1` và `DATABASE_URL` trỏ Postgres đã có lược đồ mới |
| Contract file | `src/shared/contracts/tests/validate_contract.py` | §7.7 |
| DB | `db/verify.sql` | Năm phép kiểm tiền và đoàn khách (§9.1) |
| Web, code thuần | `checkoutRules.test.ts`, `checkoutAllocation.test.ts`, `checkoutServerErrors.test.ts`, `guestCounts.test.ts`, `patchQueue.test.ts` | Bộ ca chung; đoàn mặc định; ánh xạ lỗi Backend; bộ đếm và số phòng cho trợ lý; hàng đợi (debounce, tuần tự, khoá chờ, không kẹt khi lỗi) |
| Web, giao diện | `checkoutView.test.tsx`, `cartView.test.tsx`, `productDetailView.test.tsx`, `confirmationView.test.tsx`, `useAssistantCart.test.tsx`, `assistantResultPanel.test.tsx` | Ba bước và mọi nhánh lỗi ở §6.7; tình huống `PATCH` chậm khi khách đổi ý (đã kiểm chứng là test đỏ nếu bỏ phần "so với cái đã gửi" ở §10.3); giỏ, chi tiết, trợ lý, trang đơn |

Lệnh chạy: `cd src/backend && python -m pytest`; `cd src/frontend && node_modules/.bin/vitest run`, `node_modules/.bin/tsc --noEmit`, `node_modules/.bin/eslint .`; từ gốc repo `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`; `db/verify.sql` chạy bằng `SEED_DATABASE_URL` (superuser). Kết quả các lần chạy ghi ở `history/2026-09-29-trien-khai-checkout-nhieu-buoc-hanh-khach.md`.

### 12.4. Danh sách nghiệm thu cuối (người dùng chạy tay)

Môi trường: backend với `PAYMENT_PROVIDER=stripe` (khoá test) hoặc `fake`, Postgres đã `make db-migrate`, web tại `http://localhost:3000`. Tài khoản dùng thử: `test01@vota.demo` … `test50@vota.demo`, mật khẩu `Demo@2026`.

1. Trang chi tiết một vé có giá trẻ em (ví dụ "[VinWonders Nha Trang] - Vé vào cửa 03 ngày ra vào không giới hạn"): bộ đếm Người lớn, Trẻ em, mỗi loại kèm đơn giá; thêm 2 người lớn + 1 trẻ em thì tổng ước tính bằng 2 × giá người lớn + 1 × giá trẻ em. Thêm vào giỏ.
2. Trang chi tiết một hạng phòng có `maxOccupancy`: gợi ý "Tối đa … khách/phòng"; thêm khách vượt sức chứa thì hiện cảnh báo, khoá nút và có nút "Thêm 1 phòng". Thêm vào giỏ 1 phòng với 2 người lớn + 1 trẻ em.
3. Một chuyến bay: thêm 2 người lớn + 1 trẻ em; có ghi chú "Chưa có giá vé trẻ em riêng…".
4. `/cart`: mỗi mục ghi "2 người lớn · 1 trẻ em" và các dòng giá; [Sửa] bỏ trẻ em rồi Cập nhật thì thành tiền đổi; sửa lại như cũ.
5. `/checkout`, bước ①: bấm Tiếp tục khi chưa nhập gì. Phải thấy "Còn n thông tin cần sửa", lỗi dưới từng ô, con trỏ ở ô lỗi đầu tiên, và bấm một dòng trong hộp lỗi thì nhảy tới đúng ô (AC-BKG-07).
6. Nhập ngày sinh trẻ em tròn 12 tuổi đúng ngày sử dụng sớm nhất: bị chặn và nói rõ ngày. Nhập ngày sinh của bé 7 tuổi: hiện dòng phụ "7 tuổi vào …".
7. Bước ②: bỏ chọn trẻ em ở vé tham quan, thành tiền và tổng đổi theo Backend; chọn lại thì về như cũ. Bấm liên tục vài lần, kết quả cuối phải khớp lựa chọn cuối. Ở khách sạn thấy phòng, "n/C khách", người đại diện.
8. Bước ③: nút Thanh toán khoá tới khi đồng ý điều khoản; tổng bằng tổng ở bước ②. Bấm nút Back của trình duyệt hai lần rồi Forward hai lần: dữ liệu đã nhập còn nguyên. Tải lại trang ở `?step=review`: về bước ① kèm thông báo.
9. Bấm Thanh toán: sang Stripe, số tiền và các dòng ("… · Người lớn", "… · Trẻ em", "… · {n} đêm") khớp bước ③ (AC-BKG-05). Trả bằng thẻ test `4242 4242 4242 4242`.
10. `/booking/{mã}`: hành khách theo phòng, người đại diện có nhãn, các dòng giá, không có ngày sinh.
11. AC-BKG-06: gọi thẳng `POST /api/v1/bookings` (qua BFF, có phiên đăng nhập) với `travelers` sai (thiếu họ, trẻ em có ngày sinh đã đủ 12 tuổi) và `itemDetails` xếp quá sức chứa: nhận `400 VALIDATION_ERROR` liệt kê mọi vi phạm; không có đơn mới trong `app.bookings`.
12. Điện thoại (rộng 390 px): thanh cố định ở đáy có đoàn khách, tổng và nút; bấm vào tổng mở bảng tóm tắt; không cuộn ngang ở cả ba bước.
13. Giỏ tạo từ trợ lý (Thêm cả lịch trình vào giỏ): mỗi mục có đúng số khách của lịch trình. Đây mới được kiểm bằng unit test, chưa chạy với LLM thật.
14. Huỷ một đơn đã thanh toán, đơn đang giữ chỗ hết hạn: vẫn như trước (AC-BKG-01…04).

---

## 13. Kế hoạch triển khai và rủi ro

### 13.1. Thứ tự đã làm

| Bước | Việc | Trạng thái |
|---|---|---|
| 0 | **Data:** soát 200 sản phẩm có `childPrice` lệch (§4.4) và xác nhận nghĩa của `childPrice = 0`. Luật D2 chạy đúng với dữ liệu hiện có nên không chặn các bước sau | **Chưa làm** (việc của Data) |
| 1 | Contract 1.10.0, mock mới, `validate_contract.py`, sinh lại `api.gen.ts` | Xong |
| 2 | DDL, migration 0005, `db/verify.sql`, seed; thử migration trên bản sao lược đồ cũ | Xong |
| 3 | Backend domain (`party`, `fares`, `party_rules`, `pricing`) và bộ ca chung | Xong |
| 4 | Backend application, adapter, API; contract test và integration test | Xong |
| 5 | Web code thuần (`checkoutRules`, `allocation`, `serverErrors`, `patchQueue`, `fareEstimate`, `guestCounts`) cùng test | Xong |
| 6 | Web ba bước, tóm tắt đơn, thanh đáy mobile | Xong |
| 7 | Web P1: trang chi tiết, giỏ, trợ lý, trang đơn | Xong |
| 8 | Tài liệu (§15.2) và `history/` | Xong |
| 9 | Chạy thử toàn tuyến trên trình duyệt thật với backend `PAYMENT_PROVIDER=fake` và Postgres đã migrate: thêm vào giỏ, ba bước, Stripe giả, webhook, trang đơn, hộp thoại đơn đang giữ chỗ, `PRICE_CHANGED` của giá trẻ em, giao diện điện thoại | Xong (chạy tay bằng script, không nằm trong repo) |
| 10 | Nghiệm thu cuối của người dùng (§12.4) | **Chờ** |

### 13.2. Rủi ro

| Rủi ro | Mức | Cách giảm |
|---|---|---|
| Web và Backend lệch luật, khách thấy "hợp lệ" ở Web nhưng bị Backend từ chối | Cao | Bộ ca chung (§12.2), cùng mã `reason` và câu thông báo; Backend là nơi quyết định cuối |
| Migration trên cơ sở dữ liệu đã có dữ liệu | Cao | Idempotent, không xoá gì; đã thử trên bản sao lược đồ cũ và so với lược đồ dựng mới. Trước khi chạy trên máy có dữ liệu quan trọng, `pg_dump` trước |
| `PATCH` đua nhau làm giỏ lệch lựa chọn của khách | Trung bình | Hàng đợi §10.3 và test tái hiện |
| Giá vé trẻ em sai trong catalog | Trung bình | D2 chỉ dùng giá hợp lệ; ngoài ra trả giá người lớn. Việc của Data ở bước 0 |
| Tổng chi tiêu CDP có thể cao hơn tiền thu thật khi có vé trẻ em (§8.5) | Thấp | `unitPrice` của event là giá người lớn; doanh thu chính xác đọc từ `app.bookings`. Đã ghi vào `hop-dong-tich-hop-cdp.md` |
| Số line item Stripe tăng (mỗi dòng giá một line item) | Thấp | Tối đa vài chục dòng mỗi đơn; tổng được kiểm bằng tổng đơn trước khi gọi Stripe |
| Lộ dữ liệu cá nhân | Cao | Họ tên và ngày sinh chỉ ở `app.booking_travelers`; không log, không gửi CDP, Insider, Stripe; response không trả ngày sinh (§8.6) |
| Client cũ gửi request thiếu `travelers` | Thấp | §7.6; gỡ ở v2 (D11) |
| Giao diện phức tạp trên mobile | Trung bình | Thanh đáy và bottom sheet; đã kiểm ở 390 px không cuộn ngang |
| Người dùng chưa từng thấy luồng nhiều bước | Thấp | Thanh bước, "Còn n thông tin cần sửa", giữ dữ liệu khi Back |

### 13.3. Các lỗi ở §2.2 đã xử lý thế nào

| Lỗi | Cách xử lý |
|---|---|
| L1 | Giỏ lưu `guests` mỗi mục; trợ lý thêm theo `intent.party` (§6.9) |
| L2 | Dòng giá theo loại khách, giá trẻ em theo D2 (§4.3, §4.4) |
| L3 | Xếp khách vào từng phòng, kiểm sức chứa và người lớn mỗi phòng (R-HTL-01…05, R-CRT-03) |
| L4 | Loại khách theo tuổi tại ngày bay; trẻ em cần người lớn, em bé không vượt số người lớn (R-ITM-03, R-FLT-01) |
| L5 | Backend kiểm thật theo §8.3; request cũ cũng được kiểm (§7.6) |
| L6 | Mọi mục có `itemDetails` và ít nhất 1 hành khách (R-ITM-01, R-ITM-02) |
| L7 | Mỗi dòng giá một line item Stripe, tổng khớp tổng đơn (§8.4) |
| L8 | `line_total` do Backend ghi (D9), `db/verify.sql` kiểm tổng |
| L9 | Ba bước; lỗi báo ngay ở bước đang làm (§6) |

### 13.4. Chưa làm và ngoài phạm vi đợt này

- **Phụ lục A** (FR-BKG-11, AC-BKG-10): hành lý ký gửi và chọn chỗ ngồi. Catalog chưa có `baggageOptions` và `seatPricing` (`data-model.md` §3.1), nên chưa có gì để bán.
- **FR-BKG-10** (hạng vé, khứ hồi, AC-BKG-09) và **FR-BKG-12** (xuất vé mô phỏng): thuộc hai đề xuất vé máy bay khác đã áp dụng vào PRD, chưa có code.
- Sổ hành khách lưu trong hồ sơ (§3.3), giá trẻ em và em bé riêng của chuyến bay, phụ thu trẻ em của khách sạn.
- Thử với khoá Stripe test thật và `stripe listen` (webhook thật): chưa chạy; kiểm tra bằng cổng thanh toán giả và webhook mô phỏng. Kiểm ở bước 9 của §12.4.
- Thử luồng trợ lý với LLM thật (§12.4, mục 13).
- **Bước 0 của Data** (§13.1).

---

## 14. Quyết định cần chốt

Cả bảng đã được chốt: các mã có cột "Chốt" là câu hỏi Q1–Q10 của đề xuất `docs/prd/update-archive/2026-09-29-checkout-nhieu-buoc-hanh-khach.md`, mihhquan chốt toàn bộ theo phương án đề xuất ngày 2026-09-29. D7 và D10 là quyết định thiết kế đi kèm, không phải câu hỏi riêng.

| Mã | Quyết định | Chốt | Áp dụng ở |
|---|---|---|---|
| D1 | Người lớn từ 12 tuổi; trẻ em dưới 12 tuổi tại ngày sử dụng sớm nhất, bắt buộc ngày sinh; em bé (dưới 2 tuổi) chỉ dùng cho luật chuyến bay | Q2 | §4.2 |
| D2 | Giá trẻ em hợp lệ khi `0 < childPrice ≤ unitPrice`; còn lại trẻ em trả giá người lớn | Q3 | §4.4 |
| D3 | Vé máy bay: mọi hành khách trả `unitPrice` (catalog không có giá trẻ em, em bé) | Q4 | §4.3 |
| D4 | Combo tính theo gói; số khách chỉ để ghi nhận | Q5 | §4.3 |
| D5 | Họ tên bắt buộc cho mọi hành khách, dùng cho mọi dịch vụ; nhập ở hai ô Họ và Tên đệm và tên | Q7 | §5.2 |
| D6 | Đoàn 1–9 khách mỗi đơn | Q6 | §5.2, §5.5, §7.6 |
| D7 | Sức chứa phòng tính cả trẻ em; hạng phòng không công bố `maxOccupancy` thì không kiểm sức chứa và UI nói rõ | — (thiết kế) | R-HTL-03, §11 E15 |
| D8 | Đoàn khách của đơn lưu ở bảng `app.booking_travelers`; ngày sinh chỉ lưu ở đây | Q8 | §9 |
| D9 | `app.booking_items.line_total` bỏ biểu thức sinh, Backend ghi bằng tổng các dòng giá | Q9 | §9 |
| D10 | Khai đoàn một lần và gán cả đoàn mặc định cho dịch vụ tính theo người; người liên hệ không bắt buộc đi cùng | — (thiết kế) | §4.1, §6.5 |
| D11 | Thêm trường tuỳ chọn trong v1 (OpenAPI 1.10.0); request thiếu `travelers` theo đường cũ nhưng được kiểm thật; gỡ đường cũ ở v2 | Q10 | §7 |

Q1 (ba bước trên cùng route `/checkout`) không có mã D vì là quyết định cấu trúc trang (§6).

**Cần người viết spec xác nhận lại D7.** Bản spec gốc bị cắt và mã D7 không xuất hiện ở đoạn nào còn lại. Nội dung D7 ở trên được dựng lại từ luật R-HTL-03 và số liệu ở §2.3 (95% hạng phòng có `maxOccupancy`), và code đang chạy theo nội dung này. Nếu D7 gốc là một quyết định khác thì sửa dòng này và đối chiếu lại R-HTL-03, R-CRT-03.

---

## 15. Lệch PRD và tài liệu phải sửa sau khi chốt

### 15.1. PRD đã sửa (đã áp dụng)

Theo đề xuất `docs/prd/update-archive/2026-09-29-checkout-nhieu-buoc-hanh-khach.md`:

- `docs/prd/requirements.md`: FR-BKG-02 (tổng theo dòng giá), FR-BKG-08 (mới), AC-BKG-05…07 (mới).
- `docs/prd/user-flow.md`: §2 (dòng `/checkout`), §3.3, §4.3 (hành khách và dòng giá ở trang đơn), §4.4 (wireframe ba bước).
- `docs/prd/data-model.md` §2.2: `APP_BOOKING_TRAVELERS`, `booking_items.metadata`, số khách của giỏ.

Triển khai chỉ hiện thực đúng điều PRD đã ghi, nên không cần đề xuất mới. Các chi tiết bổ sung không lệch PRD: khoá chính `traveler_id` của `app.booking_travelers` (§9.1), tên các trường `surname` và `givenNames` (PRD ghi "hai ô"), mã `reason` mới `PHONE_INVALID`, `EMAIL_INVALID`, `TRAVELERS_REQUIRED` (§5.6), và câu chính sách huỷ khi hạn hoàn tiền đã qua (§6.7).

### 15.2. Tài liệu spec, hướng dẫn đã sửa cùng đợt triển khai

| File | Sửa gì |
|---|---|
| `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` | Bản này: trạng thái, §10–§16, khớp với code |
| `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md` | §6.2 và §8.3: trình tự kiểm mới, Stripe nhiều line item |
| `docs/spec/hop-dong-tich-hop-frontend.md` | §4.5 (Checkout ba bước), giỏ và trang chi tiết |
| `docs/spec/product.md` | §4.5.2 (từ một trang thành ba bước) |
| `docs/spec/hop-dong-tich-hop-backend.md` | §7: giỏ có `guests`, `fares`; `POST /bookings` có `travelers` |
| `docs/spec/hop-dong-tich-hop-cdp.md` | Doanh thu tính từ CDP có thể cao hơn tiền thu thật khi có vé trẻ em (§8.5) |
| `docs/spec/DATABASE_SCHEMA.md` | Bảng `app.cart_items`, `app.booking_items`, `app.booking_travelers` |
| `docs/plan/2026-09-29-checkout-nhieu-buoc-hanh-khach.md` | Bảng tiến độ |
| `src/backend/README.md`, `src/frontend/README.md` | Cấu trúc thư mục mới |

### 15.3. Tồn đọng phát hiện khi làm

- `docs/prd/user-flow.md` lặp §4.2, §4.3, §4.4 hai lần (dòng 141–235 rồi 236–349), và bản lặp thứ hai vẫn còn wireframe `/checkout` một trang. Lỗi có từ trước và nằm trong PRD, nên không sửa ở đây; cần một đề xuất trong `docs/prd/update/` để dọn.

---

## 16. Tham khảo UX (Mobbin)

Mẫu tham khảo cho các quyết định giao diện ở §6. Chỉ cần đọc để hiểu ý đồ; cách làm của V-OTA nằm ở §6. Ảnh trên Mobbin hết hạn liên kết trực tiếp sau 30 ngày, nên chỉ ghi liên kết màn hình.

| Mã | Ứng dụng | Màn hình | Dùng cho | Liên kết |
|---|---|---|---|---|
| M1 | Trip.com (iOS) | "Confirm Booking Details": bảng liệt kê chuyến, khách sạn, tên từng hành khách, liên hệ và điều khoản, nút "Confirm & Pay" | Bước xác nhận họ tên trước khi trả tiền (§6.7: gộp vào ô đồng ý điều khoản để không thêm một bước) | [Mobbin](https://mobbin.com/screens/308b29d6-a39b-433c-abb3-dcb0f7d32971) |
| M2 | Trip.com (iOS) | "Select Service": thanh cố định ở đáy có "Total (1 adult)", tổng tiền và nút "Go to Payment" | Thanh dưới cùng trên mobile (§6.3) | [Mobbin](https://mobbin.com/screens/a16319fc-7081-4c81-a343-095e108b958d) |
| M4 | GetYourGuide (iOS) | "Participants": Adult (Age 14–99), Children (Age 4–13), Infant, mỗi loại một bộ đếm − và + | Hai bộ đếm Người lớn và Trẻ em kèm giới hạn tuổi (§6.4, §6.9) | [Mobbin](https://mobbin.com/screens/81e9806c-00d1-455c-8f7b-cac99cb4ca69) |
| M5 | Shopee (iOS) | Chọn vé công viên nước: mỗi loại vé một dòng giá và một bộ đếm, có tạm tính | Đơn giá từng loại đi kèm bộ đếm (§6.9) | [Mobbin](https://mobbin.com/screens/33af9902-3f29-4349-a81e-dbf51164dc83) |
| M7 | Trip.com (iOS) | "Rooms and Guests": Rooms, Adults, Children và dòng "If there are more guests, consider adding more rooms" | Gợi ý thêm phòng khi vượt sức chứa (§6.9) | [Mobbin](https://mobbin.com/screens/c07464b3-1609-451a-a8e1-30ef44ec6296) |
| M11 | Skyscanner (iOS) | "Rooms and guests": Adults, Children, Rooms kèm ghi chú "Each room should contain at least 1 adult" | Luật mỗi phòng có ít nhất 1 người lớn (§6.9) | [Mobbin](https://mobbin.com/screens/fda330ad-b233-4f17-8484-4a7f15403a10) |

Các mã M3, M6, M8, M9, M10 không được trích dẫn ở đoạn nào còn lại của spec nên không có trong bảng. Sáu màn hình trên được tìm lại trên Mobbin ngày 2026-09-29 theo đúng vai trò mà các đoạn trích dẫn giao cho M1, M2, M4, M5, M7, M11, vì danh sách gốc bị cắt cùng phần §10–§16. Nếu bản gốc dùng màn hình khác, thay dòng tương ứng.

---

## Phụ lục A. Dịch vụ thêm của vé máy bay (FR-BKG-11)

**Trạng thái: chưa triển khai** (ngoài phạm vi đợt này, §13.4). Phần dưới là thiết kế để làm tiếp, không phản ánh code hiện có.

Phục vụ FR-BKG-11, AC-BKG-10, FR-BKG-02 (`docs/prd/requirements.md`). Căn cứ đề xuất đã áp dụng `docs/prd/update-archive/2026-09-29-ve-may-bay-dich-vu-them.md`. Giai đoạn này chỉ có hành lý ký gửi và chọn chỗ ngồi; suất ăn và bảo hiểm ngoài phạm vi.

### A.1. Quy tắc

| Mã | Quy tắc | Xử lý |
|---|---|---|
| R-EXT-01 | Chỉ bán dịch vụ thêm khi chuyến bay có `baggageOptions` hoặc `seatPricing` trong catalog (`data-model.md` §3.1). Thiếu thì ẩn phần tương ứng | Không có lựa chọn |
| R-EXT-02 | Hành lý ký gửi chọn theo từng hành khách và từng chặng, một gói `kg` trong `baggageOptions`. Hạng vé đã gồm `checkedKg` ≥ gói thì không bán thêm phần đó | Chặn: `EXTRA_INCLUDED_IN_FARE` |
| R-EXT-03 | Chọn ghế theo từng hành khách và từng chặng; không hai hành khách cùng ghế. Không chọn thì hãng xếp miễn phí | Chặn: `SEAT_TAKEN` |
| R-EXT-04 | Trẻ em, em bé và người lớn đi kèm em bé không ngồi hàng lối thoát hiểm (`aircraft.exitRows`) | Chặn: `SEAT_NOT_ALLOWED` (`extras.seats[i]`) |
| R-EXT-05 | Ghế trên sơ đồ có sẵn hay "đã có người" là mô phỏng, sinh ổn định từ mã chuyến và ngày bay; giao diện ghi rõ | Không kiểm tồn kho thật |
| R-EXT-06 | Hạng vé đã gồm ghế hàng đầu thì không tính phí ghế hàng đầu | Giá ghế = 0 |
| R-EXT-07 | Backend tính lại giá dịch vụ thêm từ catalog khi tạo đơn; giá client gửi lên không được tin | Lệch giá: `PRICE_CHANGED` |

### A.2. Dòng giá và tiền

`FareType` thêm `BAG` (hành lý ký gửi) và `SEAT` (chọn chỗ ngồi). Mỗi loại là một `FareLine` riêng của mục vé máy bay, `count` là số lượt chọn và `amount = unitPrice × count`; `lineTotal` vẫn bằng tổng `fares[].amount`. Dòng giá đi vào tổng đơn, line item Stripe và `booking_items.metadata.fares`. Event `purchase` gửi CDP giữ nguyên 13 trường và không tách dịch vụ thêm. Huỷ và hoàn cùng đơn theo FR-BKG-07.

### A.3. Hợp đồng API (sửa contract trước khi code)

- `FareType` thêm `BAG`, `SEAT`.
- `CheckoutItemDetail` thêm `extras?: { baggage?: [{ travelerRef, kg }], seats?: [{ travelerRef, seat }] }`, tách theo chặng vì mỗi chặng là một mục giỏ riêng.
- `BookingItem` trả lại `extras` đã lưu.
- Mã `reason` mới: `EXTRA_INCLUDED_IN_FARE`, `SEAT_TAKEN`, `SEAT_NOT_ALLOWED`.
- Sơ đồ ghế: trả trong chi tiết sản phẩm chuyến bay từ `attributes.aircraft` (không thêm endpoint riêng nếu chi tiết sản phẩm đủ).

### A.4. Backend, database, frontend

- Backend: dòng giá `BAG`/`SEAT` trong `domain/booking/fares.py`; luật ghế trong `domain/booking/party_rules.py`; line item Stripe gộp theo loại dịch vụ.
- Database: không thêm cột; ghế và hành lý lưu trong `booking_items.metadata.extras`.
- Frontend: nút "Chọn ghế", sơ đồ ghế theo tab chặng và hành khách, lựa chọn hành lý trong form thông tin bay (wireframe `user-flow.md` §4.4).

### A.5. Kiểm thử

AC-BKG-10: ghế 12A cho trẻ em bị từ chối kèm lý do; ghế 6A cho người lớn và 20 kg ký gửi chiều đi được tính; tổng đơn và số tiền Stripe khớp. Thêm unit test cho R-EXT-02…04 và contract test cho `extras`.

