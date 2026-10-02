# Vé máy bay: trạng thái xuất vé mô phỏng trên trang đơn

- Ngày: 2026-09-29
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-29 (chốt Q1–Q5 theo đề xuất)
- PRD bị ảnh hưởng: `docs/prd/project-brief.md` §4.2 · `docs/prd/requirements.md` §1.5 · `docs/prd/user-flow.md` §4.3 · `docs/prd/data-model.md` §2.2, §4.1
- Mã FR/NFR: FR-BKG-04 (sửa) · FR-BKG-12 (mới — cần cấp mã)
- Phụ thuộc: `2026-09-29-ve-may-bay-thong-tin-hanh-khach.md`

Mock giao diện: https://claude.ai/artifact/FAmeEkdDFeDUvwzbfe2aji. Đi hết luồng tới bước Xem lại, bấm Thanh toán, rồi bấm "Thanh toán thành công" trong hộp Stripe mô phỏng (riêng tư, người đề xuất cần chia sẻ quyền xem).

## Lý do

Sau khi trả tiền, người mua vé máy bay cần biết vé đã được xuất chưa, **mã đặt chỗ của hãng (PNR)** để làm thủ tục, và số vé của từng hành khách. Trang đơn hiện chỉ có mã đơn V-OTA (`FR-BKG-04`).

Xuất vé thật cần nối hệ thống đặt chỗ của hãng bay. PRD ghi rõ việc này ngoài phạm vi (`project-brief.md` §4.2: không liên kết trực tiếp với hãng hàng không). Nếu vẫn muốn trang đơn đủ thông tin như một vé thật, chỉ có thể làm dạng **mô phỏng**, cùng tinh thần dùng Stripe ở test mode: luồng chạy thật, dữ liệu không có giá trị thật.

## Các quyết định cần chốt

| # | Câu hỏi | Đề xuất | Phương án khác |
|---|---|---|---|
| Q1 | Có làm không | Làm **xuất vé mô phỏng**, mọi chỗ hiện PNR và số vé đều gắn nhãn "Mô phỏng — không dùng được tại sân bay" | Không làm; trang đơn chỉ có mã đơn V-OTA |
| Q2 | Trạng thái | Không thêm trạng thái vào vòng đời đơn (`data-model.md` §4.1). Mỗi mục vé máy bay của đơn `CONFIRMED` có trạng thái xuất vé riêng trong `booking_items.metadata`: `ISSUING` → `ISSUED`; job nền chuyển sau vài giây | Thêm trạng thái đơn `TICKETED` |
| Q3 | PNR và số vé | Sinh ngẫu nhiên theo định dạng hãng (PNR 6 ký tự; số vé 13 chữ số, tiền tố theo mã hãng); mỗi chặng một PNR vì mỗi chặng là một vé một chiều | Không hiện PNR, chỉ hiện số vé |
| Q4 | Huỷ sau khi xuất vé | Theo FR-BKG-07 như mọi mục; trạng thái xuất vé đổi thành `VOIDED` | Không cho huỷ sau khi xuất vé |
| Q5 | Thông tin kèm theo | Trang đơn hiện: nhắc làm thủ tục trực tuyến 24 giờ trước giờ bay, giấy tờ cần mang (CCCD, hộ chiếu, giấy khai sinh), ghế và hành lý từng hành khách | Chỉ hiện PNR |

## Nội dung đề xuất

### `project-brief.md` §4.2

Dòng tồn kho thời gian thực, thêm cuối câu: "Xuất vé máy bay chỉ ở dạng mô phỏng: mã đặt chỗ và số vé do V-OTA sinh, không có giá trị tại sân bay."

### `requirements.md` §1.5

FR-BKG-04:

> Sau khi đơn chuyển `CONFIRMED`, hiển thị mã đặt chỗ, tóm tắt chuyến đi và lập tức hiển thị các sản phẩm gợi ý bổ trợ cho chặng tiếp theo.

→

> Sau khi đơn chuyển `CONFIRMED`, hiển thị mã đặt chỗ, tóm tắt chuyến đi (với vé máy bay: trạng thái xuất vé, mã đặt chỗ của hãng và số vé theo FR-BKG-12) và lập tức hiển thị các sản phẩm gợi ý bổ trợ cho chặng tiếp theo.

Thêm:

> - **FR-BKG-12 (Xuất vé máy bay mô phỏng):** Khi đơn chuyển `CONFIRMED`, mỗi mục vé máy bay chuyển trạng thái xuất vé từ "Đang xuất vé" sang "Đã xuất vé" và nhận một mã đặt chỗ (PNR) cùng số vé cho từng hành khách. Đây là dữ liệu mô phỏng, luôn gắn nhãn không dùng được tại sân bay; V-OTA không nối hệ thống đặt chỗ của hãng. Huỷ đơn theo FR-BKG-07 thì vé chuyển "Đã huỷ".

### `user-flow.md` §4.3

Khối "Thông tin chuyến đi đã đặt" với vé máy bay: trạng thái xuất vé; từng chặng có PNR và bảng hành khách (tên in trên vé, ghế, hành lý, số vé); hai ô nhắc làm thủ tục và giấy tờ cần mang.

### `data-model.md` §2.2, §4.1

`APP_BOOKING_ITEMS.metadata` của vé máy bay thêm `ticketing` (`status`: ISSUING, ISSUED, VOIDED; `pnr`; `tickets` theo `travelerRef`; `simulated: true`). Ghi chú dưới §4.1: trạng thái xuất vé thuộc từng mục, không đổi vòng đời đơn.

## Thay đổi source sau khi chốt

- **Spec:** mục trang đơn vé máy bay trong `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` §6.8.
- **Contract:** `BookingItem` thêm `ticketing` (tuỳ chọn).
- **Backend:** job xuất vé mô phỏng chạy sau khi đơn `CONFIRMED`; chuyển `VOIDED` khi huỷ.
- **Frontend:** trang `/booking/:referenceCode` hiện khối vé máy bay và nhãn mô phỏng.
