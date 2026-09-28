# Vé máy bay: dịch vụ thêm (hành lý ký gửi, chỗ ngồi, suất ăn, bảo hiểm)

- Ngày: 2026-09-29
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-29 (chốt Q1–Q7 theo đề xuất)
- PRD bị ảnh hưởng: `docs/prd/project-brief.md` §4.1, §4.2 · `docs/prd/requirements.md` §1.5, §3 · `docs/prd/data-model.md` §2.2, §3.1 · `docs/prd/user-flow.md` §4.4
- Mã FR/NFR: FR-BKG-02 (liên quan: "phụ phí") · FR-BKG-11 (mới — cần cấp mã) · AC-BKG-10 (mới — cần cấp mã)
- Phụ thuộc: `2026-09-29-checkout-nhieu-buoc-hanh-khach.md`, `2026-09-29-ve-may-bay-thong-tin-hanh-khach.md`

Mock giao diện: https://claude.ai/artifact/FAmeEkdDFeDUvwzbfe2aji, thẻ vé máy bay ở bước Dịch vụ, mục "Chỗ ngồi" và "Dịch vụ thêm" (riêng tư, người đề xuất cần chia sẻ quyền xem). Toàn bộ giá, sơ đồ ghế, thực đơn và quyền lợi bảo hiểm trong mock là minh hoạ.

## Lý do

Trang đặt vé máy bay thường cho mua thêm hành lý, chọn ghế, suất ăn và bảo hiểm ngay khi đặt. V-OTA hiện chỉ bán giá vé. PRD không nhắc tới dịch vụ thêm: không nằm trong phạm vi (`project-brief.md` §4.1), không có yêu cầu (`requirements.md` §1.5), không có nguồn giá trong catalog (`data-model.md` §3.1).

Bốn loại có mức rủi ro khác nhau:

- **Hành lý ký gửi, chỗ ngồi:** là dịch vụ của chính hãng bay, gắn với từng hành khách và từng chặng. Cần bảng giá theo hãng; sơ đồ ghế cần loại tàu bay.
- **Suất ăn:** cần thực đơn và giá theo hãng; chưa có nguồn.
- **Bảo hiểm:** là sản phẩm của công ty bảo hiểm, không phải của hãng bay. Bán bảo hiểm cần đối tác và điều khoản pháp lý, vượt vai trò MoR của V-OTA cho dịch vụ du lịch.

Ghế "đã có người" không thể là số liệu thật, vì tồn kho thời gian thực nối hãng bay nằm ngoài phạm vi (`project-brief.md` §4.2).

## Các quyết định cần chốt

| # | Câu hỏi | Đề xuất | Phương án khác |
|---|---|---|---|
| Q1 | Làm những loại nào | Giai đoạn này: **hành lý ký gửi** và **chọn chỗ ngồi**. Suất ăn, bảo hiểm để sau | Làm cả bốn; hoặc không làm dịch vụ thêm |
| Q2 | Nguồn giá | Bảng giá tĩnh theo hãng do Data nạp vào catalog (gói hành lý theo kg; giá ghế theo loại: tiêu chuẩn, hàng đầu, lối thoát hiểm). Không có bảng giá cho hãng nào thì không bán dịch vụ thêm của hãng đó | Web tự đặt giá: trái FR-BKG-02 (số tiền phải từ catalog) |
| Q3 | Sơ đồ ghế | Sơ đồ tĩnh theo loại tàu bay. Ghế "đã có người" chỉ là mô phỏng và giao diện ghi rõ; khi hãng xếp ghế khác, V-OTA không cam kết số ghế | Không có sơ đồ, chỉ chọn "gần cửa sổ / lối đi" |
| Q4 | Luật ghế | Trẻ em, em bé và người lớn đi kèm em bé không ngồi hàng lối thoát hiểm. Không chọn ghế thì hãng xếp ngẫu nhiên, miễn phí | — |
| Q5 | Hạng vé đã gồm | Hạng đã gồm hành lý ký gửi hoặc ghế hàng đầu thì không bán thêm phần đó (phụ thuộc đề xuất hạng vé) | — |
| Q6 | Ghi nhận tiền | Mỗi loại dịch vụ thêm là một dòng giá riêng của mục vé máy bay (`BAG`, `SEAT`, sau này `MEAL`, `INS`), có mặt trong tổng đơn, line item Stripe và `booking_items.metadata`. Event `purchase` gửi CDP giữ nguyên 13 trường, không tách dịch vụ thêm | Mỗi dịch vụ thêm là một mục giỏ riêng: vướng `UNIQUE (product_id, using_date)` và khớp 1:1 với event `purchase` |
| Q7 | Huỷ | Dịch vụ thêm huỷ và hoàn theo cả đơn (FR-BKG-07) | Không hoàn dịch vụ thêm |

## Nội dung đề xuất

### `project-brief.md` §4.1

Dòng Backend, sau "quản lý đơn hàng (Booking/Checkout: giữ chỗ, thanh toán Stripe, huỷ và hoàn tiền)" thêm: "bán kèm dịch vụ thêm của hãng bay (hành lý ký gửi, chọn chỗ ngồi) theo bảng giá nạp sẵn".

### `project-brief.md` §4.2

Thêm dòng: "Bán bảo hiểm du lịch và sản phẩm tài chính của bên thứ ba; đặt suất ăn trên máy bay (để giai đoạn sau)."

### `requirements.md` §1.5

Thêm:

> - **FR-BKG-11 (Dịch vụ thêm của vé máy bay):** Với mục vé máy bay, khách có thể mua hành lý ký gửi cho từng hành khách, từng chặng, và chọn chỗ ngồi trên sơ đồ ghế của chặng. Giá lấy từ bảng giá của hãng trong catalog; hãng chưa có bảng giá thì không bán. Không chọn ghế thì hãng xếp miễn phí. Trẻ em, em bé và người lớn đi kèm em bé không ngồi hàng lối thoát hiểm. Mỗi loại dịch vụ thêm là một dòng giá của mục, có trong tổng đơn và trên Stripe; huỷ và hoàn cùng đơn theo FR-BKG-07. Tình trạng ghế trên sơ đồ là mô phỏng.

### `requirements.md` §3

| Mã tiêu chí | Kịch bản / Điều kiện kích hoạt | Hành vi kỳ vọng của hệ thống |
|---|---|---|
| **AC-BKG-10** | Khách chọn ghế 12A (lối thoát hiểm) cho một trẻ em, rồi chọn ghế 6A cho người lớn và mua 20 kg ký gửi chiều đi | Ghế 12A bị từ chối kèm lý do. Tổng đơn có thêm dòng "Chọn chỗ ngồi" và "Hành lý ký gửi 20 kg" đúng giá catalog; số tiền trên Stripe bằng tổng này. |

### `data-model.md` §3.1

Thêm cấu trúc bảng giá dịch vụ thêm theo hãng (nằm trong `attributes` của sản phẩm cấp hãng hoặc tuyến): gói hành lý (`kg`, `price`), giá ghế theo loại, loại tàu bay và sơ đồ ghế (số hàng, cột, hàng lối thoát hiểm, hàng đầu).

### `data-model.md` §2.2

`APP_BOOKING_ITEMS.metadata` của vé máy bay thêm: ghế và hành lý theo từng hành khách.

### `user-flow.md` §4.4

Thêm wireframe mục "Chỗ ngồi" (tóm tắt ghế theo chặng, nút "Chọn ghế") và màn hình sơ đồ ghế (tab chặng, chọn hành khách, chú giải loại ghế, phí chọn ghế).

## Thay đổi source sau khi chốt

- **Data:** nạp bảng giá dịch vụ thêm và sơ đồ ghế theo hãng, loại tàu bay; cập nhật `docs/spec/data-collection/schema.md`.
- **Spec:** thêm mục dịch vụ thêm vào `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md`, bỏ "chọn ghế, hành lý" khỏi danh sách ngoài phạm vi ở §3.3.
- **Contract:** `FareType` thêm `BAG`, `SEAT`; `CheckoutItemDetail` thêm lựa chọn ghế và hành lý theo `travelerRef`.
- **Backend:** tính dòng giá dịch vụ thêm trong `domain/booking/fares.py`, luật ghế trong `party_rules.py`, line item Stripe.
- **Frontend:** sơ đồ ghế, lựa chọn hành lý trong form thông tin bay.
