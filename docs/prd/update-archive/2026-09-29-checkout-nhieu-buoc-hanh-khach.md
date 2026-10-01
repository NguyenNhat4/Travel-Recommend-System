# Checkout nhiều bước: đoàn khách người lớn/trẻ em và giá theo loại khách

- Ngày: 2026-09-29
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-29 (chốt toàn bộ Q1–Q10 theo cột Đề xuất)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.5, §3 · `docs/prd/user-flow.md` §2, §3.3, §4.3, §4.4 · `docs/prd/data-model.md` §2.2
- Mã FR/NFR: FR-BKG-02 (sửa) · FR-BKG-08 (mới — cần cấp mã) · AC-BKG-05, AC-BKG-06, AC-BKG-07 (mới — cần cấp mã) · giữ nguyên FR-BKG-03…07, NFR-SEC-01, NFR-MAINT-02

Spec chi tiết (bản nháp): `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md`. Mock giao diện: https://claude.ai/artifact/FAmeEkdDFeDUvwzbfe2aji (riêng tư, người đề xuất cần chia sẻ quyền xem).

Đề xuất này là nền cho bốn đề xuất vé máy bay cùng ngày: `2026-09-29-ve-may-bay-thong-tin-hanh-khach.md`, `2026-09-29-ve-may-bay-hang-ve-va-khu-hoi.md`, `2026-09-29-ve-may-bay-dich-vu-them.md`, `2026-09-29-ve-may-bay-xuat-ve-mo-phong.md`.

## Lý do

Giỏ hàng chỉ biết một con số `quantity` cho mỗi dịch vụ; hệ thống không biết đoàn có ai. Hệ quả đo được trên code nhánh `feat/booking`:

- **Trẻ em trả giá người lớn.** Vé "[Wonder Ngon] VinWonders Nha Trang + Buggy + Fastpass" có giá người lớn 1.500.000 ₫, trẻ em 504.000 ₫. Gia đình 2 người lớn + 1 trẻ em bị tính 4.500.000 ₫ thay vì 3.504.000 ₫.
- **Trợ lý thêm mọi mục với `quantity = 1`**, nên lịch trình cho 4 người chỉ thu tiền 1 vé.
- **Khách sạn có một ô tên cho mọi phòng** và không kiểm sức chứa, dù 95% hạng phòng có `maxOccupancy`.
- **Backend không kiểm thông tin khách.** Gọi thẳng `POST /bookings` cho vé máy bay 3 khách không có tên nào vẫn nhận `201`.
- **Một trang dài chứa mọi dịch vụ**, lỗi chỉ lộ ra khi bấm Thanh toán ở cuối trang.
- `app.booking_items.line_total` là cột sinh `unit_price * quantity`, đã sai với khách sạn nhiều đêm.

PRD hiện tại mô tả `/checkout` là một trang chỉ nhập thông tin liên lạc (`user-flow.md` §3.3, §4.4) và không có yêu cầu nào về hành khách hay giá trẻ em (`requirements.md` §1.5). Sửa các lỗi trên làm đổi luồng, dữ liệu đơn và tiêu chí nghiệm thu, nên cần chốt.

## Các quyết định cần chốt

Cột "Đề xuất" là phương án agent chọn; mã D trong ngoặc là mã quyết định trong spec.

| # | Câu hỏi | Đề xuất | Phương án khác |
|---|---|---|---|
| Q1 | Cấu trúc trang | Ba bước trên cùng route `/checkout` (`?step=travelers|services|review`): ① Hành khách → ② Dịch vụ → ③ Xem lại và thanh toán | Giữ một trang, thêm khối hành khách |
| Q2 | Mốc tuổi (D1) | Người lớn từ 12 tuổi; trẻ em dưới 12 tuổi tại ngày sử dụng sớm nhất của đơn, bắt buộc ngày sinh. Em bé (dưới 2 tuổi) chỉ dùng cho luật chuyến bay | Mốc riêng theo từng nhà cung cấp |
| Q3 | Giá trẻ em hợp lệ (D2) | Dùng `attributes.childPrice` khi `0 < childPrice ≤ unitPrice`; còn lại trẻ em trả giá người lớn. Snapshot 2026-09-23 có 297 sản phẩm có trường này, chỉ 97 dùng được | Coi `childPrice = 0` là miễn phí (nguy cơ thu thiếu tiền) |
| Q4 | Vé máy bay (D3) | Mọi hành khách trả `unitPrice`, vì catalog không có giá trẻ em, em bé | Tự đặt tỷ lệ giảm: trái FR-BKG-02 (số tiền phải từ catalog) |
| Q5 | Combo (D4) | Tính theo gói; số khách chỉ để ghi nhận | Tính theo người |
| Q6 | Cỡ đoàn (D6) | 1–9 khách mỗi đơn | Không giới hạn |
| Q7 | Họ tên (D5) | Bắt buộc cho mọi hành khách, dùng cho mọi dịch vụ; nhập ở hai ô Họ và Tên đệm và tên (mock đã duyệt), `full_name` nối từ hai ô | Chỉ bắt buộc với vé máy bay và người đại diện phòng |
| Q8 | Lưu hành khách (D8) | Bảng mới `app.booking_travelers`; ngày sinh chỉ lưu ở đây, không trả qua API, không gửi CDP, Insider, Stripe | Lưu trong `booking_items.metadata` |
| Q9 | `line_total` (D9) | Bỏ biểu thức sinh, Backend ghi giá trị bằng tổng các dòng giá | Giữ cột sinh (vẫn sai) |
| Q10 | Contract | Thêm trường tuỳ chọn trong v1 (OpenAPI 1.8.0); request thiếu `travelers` theo luật cũ nhưng được kiểm thật; gỡ đường cũ ở v2 (D11) | Làm luôn v2 |

## Nội dung đề xuất

### `requirements.md` §1.5

FR-BKG-02, gạch đầu dòng thứ hai:

> Tính tổng giá trị đơn hàng, hiển thị chi tiết phụ phí và thuế (nếu có).

→

> Tính tổng giá trị đơn hàng theo các dòng giá của từng dịch vụ (người lớn, trẻ em, phòng-đêm, gói), hiển thị chi tiết phụ phí và thuế (nếu có). Tổng ở bước xem lại bằng số tiền trên trang Stripe.

Thêm sau FR-BKG-07:

> - **FR-BKG-08 (Đoàn khách và giá theo loại khách):** Checkout gồm ba bước trên `/checkout`: Hành khách → Dịch vụ → Xem lại và thanh toán. Khách khai đoàn một lần: 1–9 người, ít nhất 1 người lớn; người lớn từ 12 tuổi, trẻ em dưới 12 tuổi tại ngày sử dụng sớm nhất và phải có ngày sinh; mọi người có họ và tên đệm và tên (hai ô). Ở từng dịch vụ khách chọn ai dùng; với khách sạn, khách xếp người vào từng phòng (mỗi phòng có ít nhất 1 người lớn, không vượt sức chứa, có một người lớn đại diện nhận phòng). Mỗi dịch vụ tính tiền theo dòng giá lấy từ catalog; trẻ em dùng giá trẻ em của sản phẩm khi giá đó lớn hơn 0 và không cao hơn giá người lớn, còn lại trả giá người lớn. Web và Backend kiểm cùng một bộ luật; Backend trả mọi vi phạm trong một lần và là nơi quyết định cuối cùng. Không gửi họ tên hay ngày sinh sang CDP, Insider, Stripe; API không trả ngày sinh.

### `requirements.md` §3

Thêm ba dòng sau AC-BKG-04:

| Mã tiêu chí | Kịch bản / Điều kiện kích hoạt | Hành vi kỳ vọng của hệ thống |
|---|---|---|
| **AC-BKG-05** | Giỏ có vé VinWonders (người lớn 1.500.000 ₫, trẻ em 504.000 ₫) cho 2 người lớn và 1 trẻ em 7 tuổi | Mục tính 3.504.000 ₫. Tóm tắt đơn, bước Xem lại, số tiền phiên Stripe và `app.bookings` có cùng tổng. |
| **AC-BKG-06** | Gọi thẳng `POST /bookings` với dữ liệu sai: vé máy bay 3 khách không có tên, phòng sức chứa 3 xếp 4 khách, trẻ em đã đủ 12 tuổi khai là trẻ em | `400 VALIDATION_ERROR` liệt kê mọi vi phạm, mỗi vi phạm có trường và mã lý do. Không tạo đơn, không tạo phiên Stripe. |
| **AC-BKG-07** | Khách bấm Tiếp tục khi bước hiện tại còn thiếu hoặc sai thông tin | Không chuyển bước; đầu bước hiện "Còn n thông tin cần sửa" với link tới từng trường, lỗi hiện dưới trường và con trỏ về trường lỗi đầu tiên. Backend trả lỗi hành khách thì Web về đúng bước chứa trường đó. |

### `user-flow.md` §2

Dòng `/checkout`, cột mục đích và thành phần:

> Xem lại đơn, nhập thông tin liên lạc, chọn phương thức thanh toán, bấm Thanh toán để chuyển sang trang Stripe | Cart Items Summary, Guest Info Form, Price Breakdown, Payment Method Selector, Pay CTA

→

> Ba bước: khai đoàn khách và người liên hệ; chọn ai dùng từng dịch vụ (khách sạn xếp phòng); xem lại, chọn phương thức, bấm Thanh toán để chuyển sang trang Stripe | Stepper, Party Counter, Traveler Forms, Service Allocation Cards, Order Summary (sticky; bottom bar trên mobile), Payment Method Selector, Pay CTA

### `user-flow.md` §3.3

Câu mở đầu: 

> Ở `/checkout`, khách làm lần lượt ba việc: (1) điền đủ thông tin liên lạc; (2) chọn phương thức thanh toán; (3) bấm **Thanh toán**.

→

> Ở `/checkout`, khách đi qua ba bước: (1) **Hành khách**: số người lớn, trẻ em, họ và tên đệm và tên từng người, ngày sinh trẻ em và người liên hệ; (2) **Dịch vụ**: chọn ai dùng từng dịch vụ, khách sạn xếp khách vào phòng, giá cập nhật theo loại khách; (3) **Xem lại và thanh toán**: kiểm tra, chọn phương thức, đồng ý điều khoản và bấm **Thanh toán**. Bấm Tiếp tục khi còn lỗi thì ở lại bước đó và thấy danh sách lỗi. Chỉ sửa giỏ, không tạo đơn cho tới khi bấm Thanh toán.

Gạch đầu dòng thứ hai:

> Nút **Thanh toán** bị vô hiệu hoá cho tới khi thông tin liên lạc hợp lệ và đã chọn phương thức.

→

> Nút **Thanh toán** ở bước (3) bị vô hiệu hoá cho tới khi đã chọn phương thức và đồng ý điều khoản; thông tin ở bước (1) và (2) đã được kiểm khi bấm Tiếp tục.

Sơ đồ: thay nút `C[Điền thông tin liên lạc]` bằng chuỗi `C1[Bước 1: Hành khách] --> C2[Bước 2: Dịch vụ] --> C3[Bước 3: Xem lại]`; nhánh `D -->|Lỗi Backend hoặc Stripe| B` đổi thành `D -->|400: lỗi hành khách| C1` và `D -->|400: lỗi dịch vụ| C2`, các lỗi khác về `C3`.

### `user-flow.md` §4.4

Thay wireframe một trang bằng wireframe bước ① (đoàn khách, thẻ hành khách, người liên hệ, tóm tắt đơn dính bên phải), kèm hai dòng mô tả bước ② và ③. Nội dung lấy từ spec §6.4, §6.6, §6.7.

### `user-flow.md` §4.3

Khối "Thông tin chuyến đi đã đặt" thêm: hành khách của từng dịch vụ (khách sạn theo phòng, đánh dấu người đại diện) và các dòng giá. Không hiện ngày sinh.

### `data-model.md` §2.2

- Thêm thực thể `APP_BOOKING_TRAVELERS` (`booking_id` FK, `traveler_ref`, `position`, `traveler_type` adult/child, `surname`, `given_names`, `full_name` (nối từ hai cột trên), `birth_date` bắt buộc với trẻ em) và quan hệ `APP_BOOKINGS ||--o{ APP_BOOKING_TRAVELERS`.
- `APP_BOOKING_ITEMS.metadata`: ghi rõ nội dung là các dòng giá, danh sách hành khách của mục và phân phòng.
- Giỏ hàng: thêm số người lớn, số trẻ em và snapshot giá trẻ em cho mỗi mục.

## Thay đổi source sau khi chốt

- **Spec:** hoàn thiện `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` (bản hiện tại dừng ở §9.2, thiếu §10–§16), đổi trạng thái thành đã chốt; sửa `docs/spec/hop-dong-tich-hop-frontend.md` §4.5, `docs/spec/product.md` §4.5.2, `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md` §6.2, `docs/spec/hop-dong-tich-hop-cdp.md` (doanh thu CDP có thể cao hơn tiền thu thật khi có vé trẻ em).
- **Contract 1.8.0:** `src/shared/contracts/schemas/booking.yaml`, `schemas/common.yaml`, `paths/booking.yaml`, `openapi.yaml`; sinh lại `src/frontend/src/types/api.gen.ts`; mock mới trong `src/shared/mocks/booking/` và `index.json`.
- **DDL:** `db/vota_schema.sql`, `db/init/01_vota.sql`, migration `db/migrations/0005_checkout_travelers.sql`.
- **Backend:** `domain/booking/` (party, fares, party_rules, pricing, models), `application/booking/` (cart, create_hold, views), adapter Postgres, DTO và route booking.
- **Frontend:** `src/frontend/src/components/checkout/` (ba bước), `useAssistantCart.ts` (thêm theo `intent.party`), trang giỏ, trang chi tiết, trang đơn.
- **Test:** bộ ca kiểm thử dùng chung cho Web và Backend (spec §12, cần viết lại vì bản nháp bị thiếu), contract test, integration DB.
