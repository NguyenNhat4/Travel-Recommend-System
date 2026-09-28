# Vé máy bay: chọn hạng vé theo chặng và hiển thị khứ hồi

- Ngày: 2026-09-29
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-29 (chốt Q1–Q7 theo đề xuất)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.1, §1.5, §3 · `docs/prd/data-model.md` §3.1 · `docs/prd/user-flow.md` §4.4
- Mã FR/NFR: FR-CAT-03 (sửa) · FR-BKG-10 (mới — cần cấp mã) · AC-BKG-09 (mới — cần cấp mã) · FR-BKG-07 (liên quan, xem Q5)
- Phụ thuộc: `2026-09-29-checkout-nhieu-buoc-hanh-khach.md`; phần hạng vé cần dữ liệu mới từ workstream Data

Mock giao diện: https://claude.ai/artifact/FAmeEkdDFeDUvwzbfe2aji, chọn "Khứ hồi" trên thanh Mock (riêng tư, người đề xuất cần chia sẻ quyền xem). Tên hạng, phụ thu, điều kiện và số ghế trong mock là minh hoạ.

## Lý do

- **Hạng vé.** Mỗi chuyến bay trong catalog chỉ có một giá (`unitPrice`, giá rẻ nhất). Khách không chọn được hạng có hành lý ký gửi hay đổi chuyến miễn phí, dù đây là lựa chọn quen thuộc trên các trang đặt vé. PRD mô tả `cabinClass` và `baggageAllowanceKg` là một giá trị cho mỗi chuyến (`data-model.md` §3.1), nhưng snapshot 2026-09-23 không có hai khoá này, và một giá trị thì không đủ để khách chọn.
- **Khứ hồi.** Catalog lưu mỗi chiều là một sản phẩm riêng. `roundTripFrom` chỉ là giá tham khảo ở cấp tuyến, không đặt được. Giỏ có hai chuyến ngược chiều (ví dụ VJ1602 SGN → CXR ngày 17/10 và VJ601 CXR → SGN ngày 19/10) hiện hiển thị như hai dịch vụ rời, khách không thấy đây là một chuyến khứ hồi.

## Các quyết định cần chốt

| # | Câu hỏi | Đề xuất | Phương án khác |
|---|---|---|---|
| Q1 | Nguồn dữ liệu hạng vé | Data bổ sung `attributes.fareClasses` cho `flight_instance`: mỗi hạng có mã, tên, giá, hành lý xách tay, hành lý ký gửi, suất ăn, điều kiện đổi. Khi sản phẩm chỉ có một hạng, giao diện không hiện phần chọn hạng | Không làm hạng vé; giữ một giá |
| Q2 | Phạm vi áp dụng | Một hạng cho mỗi chặng, áp dụng cho mọi hành khách của chặng đó; khứ hồi chọn hạng riêng từng chiều | Mỗi hành khách một hạng |
| Q3 | Tính tiền | Giá của hạng đã chọn là đơn giá của mục, lấy từ catalog; `PRICE_CHANGED` kiểm theo giá của hạng đó | Giá rẻ nhất cộng phụ thu cố định |
| Q4 | Ghế còn lại | **Không** hiện số ghế còn theo thời gian thực: tồn kho nối hãng bay nằm ngoài phạm vi (`project-brief.md` §4.2). Hạng chỉ bị khoá khi dữ liệu snapshot ghi hết chỗ | Hiện "Còn N ghế" từ snapshot (dễ gây hiểu nhầm là số liệu thời gian thực) |
| Q5 | Mâu thuẫn chính sách huỷ | Giữ FR-BKG-07 (hoàn 100% nếu huỷ trước 00:00 ngày liền trước ngày sử dụng) cho mọi mục, kể cả vé máy bay. Giao diện không hiện dòng "Hoàn vé" theo hạng, chỉ hiện chính sách huỷ của V-OTA | Vé máy bay huỷ theo điều kiện hạng: phải sửa FR-BKG-07 và AC-BKG-04, và tính hoàn tiền từng phần cho đơn nhiều dịch vụ |
| Q6 | Nhận biết khứ hồi | Hai mục vé máy bay có tuyến ngược nhau (A → B rồi B → A, ngày về sau ngày đi) được gộp thành một thẻ "Khứ hồi · 2 chặng" ở bước Dịch vụ, tóm tắt đơn, bước Xem lại và trang đơn. Dữ liệu vẫn là hai mục giỏ | Thêm sản phẩm khứ hồi riêng trong catalog |
| Q7 | Giá khứ hồi | Bằng tổng hai chặng; không dùng `roundTripFrom`, không giảm giá khứ hồi | Áp giá khứ hồi tham khảo: không có sản phẩm đặt được tương ứng |

## Nội dung đề xuất

### `requirements.md` §1.1

FR-CAT-03, gạch đầu dòng thứ hai:

> Hỗ trợ cơ sở định giá đa dạng (`per_night`, `per_person`, `per_package`).

→

> Hỗ trợ cơ sở định giá đa dạng (`per_night`, `per_person`, `per_package`). Chuyến bay có thể có nhiều hạng vé, mỗi hạng một giá và điều kiện riêng (`attributes.fareClasses`).

### `requirements.md` §1.5

Thêm:

> - **FR-BKG-10 (Hạng vé và khứ hồi):** Khi chuyến bay có từ hai hạng vé trở lên, khách chọn một hạng cho mỗi chặng; hạng áp dụng cho mọi hành khách của chặng và giá lấy từ catalog. Giao diện so sánh hành lý, suất ăn và điều kiện đổi của các hạng; chính sách huỷ vẫn theo FR-BKG-07. Hai chặng bay ngược chiều trong cùng giỏ được hiển thị là một chuyến khứ hồi; mỗi chặng vẫn là một mục riêng, tổng tiền bằng tổng hai chặng. Hệ thống không hiển thị số ghế còn theo thời gian thực.

### `requirements.md` §3

| Mã tiêu chí | Kịch bản / Điều kiện kích hoạt | Hành vi kỳ vọng của hệ thống |
|---|---|---|
| **AC-BKG-09** | Giỏ có VJ1602 SGN → CXR ngày 17/10 và VJ601 CXR → SGN ngày 19/10 cho 3 khách; khách đổi chiều về sang hạng có hành lý ký gửi | Bước Dịch vụ hiện một thẻ "Khứ hồi · 2 chặng". Giá chiều về đổi theo giá hạng mới cho cả 3 khách; chiều đi giữ nguyên. Tổng ở bước Xem lại bằng số tiền trên Stripe. |

### `data-model.md` §3.1

Khối "Chuyến bay (`flight_instance`)": thay `cabinClass` và `baggageAllowanceKg` đơn lẻ bằng:

```json
"fareClasses": [
  { "code": "ECO", "name": "Phổ thông", "price": 634000, "carryOnKg": 7, "checkedKg": 0, "mealIncluded": false, "changeRule": "Phí + chênh lệch giá", "soldOut": false }
]
```

`unitPrice` của sản phẩm là giá của hạng rẻ nhất còn chỗ. Thiếu `fareClasses` thì coi như một hạng duy nhất với giá `unitPrice`.

### `user-flow.md` §4.4

Thêm wireframe thẻ vé máy bay khứ hồi: hai chặng xếp dọc, giữa là "{n} đêm ở {thành phố}", mỗi chặng có phần chọn hạng dạng thẻ và link "So sánh điều kiện các hạng".

## Thay đổi source sau khi chốt

- **Data:** cào giá theo hạng, ghi `attributes.fareClasses`; cập nhật `docs/spec/data-collection/schema.md` (quy chuẩn `attributes`).
- **Spec:** thêm mục hạng vé và khứ hồi vào `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md`.
- **Contract:** `AddCartItemRequest`, `UpdateCartItemRequest`, `CartItem`, `BookingItem` thêm `fareClass` (tuỳ chọn); `FareLine` ghi mã hạng.
- **DDL:** `app.cart_items` thêm `fare_class` và snapshot giá của hạng; migration tương ứng.
- **Backend:** giá theo hạng trong `domain/booking/fares.py`, kiểm `PRICE_CHANGED` theo hạng.
- **Frontend:** phần chọn hạng, bảng so sánh, thẻ gộp khứ hồi.
