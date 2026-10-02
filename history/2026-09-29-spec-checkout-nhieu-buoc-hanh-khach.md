# Spec checkout nhiều bước: hành khách người lớn/trẻ em và giá theo loại khách

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu (với vai PO) viết spec cho lỗi logic thanh toán của giỏ hàng nhiều loại dịch vụ (vé máy bay, khách sạn, phòng, khu vui chơi). Checkout hiện là một trang chỉ lấy thông tin đăng ký. Yêu cầu: chuyển thành nhiều bước, có người lớn và trẻ em, kiểm tra ở cả frontend và backend, tham khảo UX của Trip.com và các trang khác qua Mobbin. Người dùng chốt đầu ra là **một file `.md` trong `docs/spec`**.

## File thay đổi

- `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` — thêm: spec checkout ba bước (Hành khách → Dịch vụ → Xem lại và thanh toán). Gồm lỗi hiện tại L1–L9 kèm vị trí trong code; quy tắc tuổi và giá theo loại khách; bộ luật kiểm tra dùng chung cho Web và Backend (mã luật, `reason`, câu thông báo); wireframe; đề xuất contract 1.8.0, DDL và migration 0005; bảng 22 ca kiểm thử chung; AC-BKG-05…07 đề xuất; 11 quyết định cần chốt; danh sách lệch PRD; tham khảo Mobbin. Phục vụ FR-BKG-01, FR-BKG-02, FR-BKG-06, FR-CAT-02, FR-CAT-03, NFR-SEC-01, NFR-MAINT-02; đề xuất mã mới FR-BKG-08.

## Quyết định

- **Spec để trạng thái "bản nháp, chờ chốt".** Nội dung lệch PRD: `user-flow.md` §3.3 và §4.4 (checkout một trang), `requirements.md` §1.5 (chưa có yêu cầu về hành khách hay giá trẻ em), `data-model.md` §2.2. `AGENTS.md` §7 và §8 yêu cầu có đề xuất đã chốt trước khi viết spec lệch PRD. Người dùng yêu cầu rõ một file spec, nên spec được viết dưới dạng bản nháp; §15 liệt kê đủ nội dung cần đưa vào đề xuất `docs/prd/update/`. Không sửa PRD, contract, DDL hay code.
- **Giá trẻ em chỉ dùng khi `0 < childPrice ≤ unitPrice`** (D2). Đo trên snapshot `2026-09-23`: 297 sản phẩm có `childPrice`. Trong đó 103 có giá 0; mẫu cho thấy 0 nghĩa là "không có giá riêng", ví dụ thẻ hội viên 6.000.000 ₫, workshop cho trẻ em 500.000 ₫. 97 sản phẩm có giá trẻ em cao hơn giá người lớn (nghi sai dữ liệu). Chỉ 97 sản phẩm dùng được.
- **Chuyến bay tính mọi hành khách bằng giá người lớn** (D3), vì catalog không có giá trẻ em hay em bé. Không đặt tỷ lệ giảm giá tự nghĩ ra (FR-BKG-02: số tiền tính từ catalog).
- **Adult và child của cùng sản phẩm, cùng ngày nằm trên một dòng giỏ, kèm các dòng giá.** Lý do: `app.cart_items` và `app.booking_items` có `UNIQUE (…, product_id, using_date)`, và `booking_items` khớp 1:1 với event `purchase`.
- **Không thêm mã lỗi mới**: mọi lỗi hành khách dùng `VALIDATION_ERROR` với `details.fields[].reason`, để client cũ vẫn hiểu.
- **Lưu hành khách ở bảng mới `app.booking_travelers` và cột `app.booking_items.metadata`.** `metadata` đã có trong ERD của PRD (`data-model.md` §2.2). Đề xuất sửa luôn `line_total` (cột sinh đang sai với khách sạn nhiều đêm) trong cùng migration. Postgres 16 của compose hỗ trợ `DROP EXPRESSION`.
- **UX:** tham khảo Trip.com (Enter Info ①②③, nhãn loại khách, thanh dưới cùng có đoàn khách và tổng), Kiwi.com, Klook, GetYourGuide, Tripadvisor, Expedia, KAYAK, Airbnb qua Mobbin. Không lấy đồng hồ giữ chỗ lúc điền thông tin, vì V-OTA chỉ giữ chỗ sau khi bấm Thanh toán (FR-BKG-06).

## Kiểm tra

- Không đổi code, contract, DDL, nên không chạy `validate_contract.py`, `db/verify.sql` hay test.
- Số liệu catalog trong spec đếm bằng Python trên `src/data_collection/snapshots/2026-09-23/products.jsonl.gz`: độ phủ `maxOccupancy` 7.382/7.738 hạng phòng; phân bố `childPrice` (103 bằng 0, 97 lớn hơn giá người lớn, 94 nhỏ hơn, 3 bằng). Sản phẩm dùng trong ví dụ tính tiền và giá của chúng lấy từ cùng snapshot.
- Dòng code dẫn trong bảng lỗi §2.2 đã đối chiếu với file hiện tại trên nhánh `feat/booking`.
- Wireframe ASCII đã kiểm độ rộng từng dòng bằng script.

## Còn lại / rủi ro

- **Cần người dùng chốt D1–D11** (spec §14) và tạo đề xuất trong `docs/prd/update/` theo spec §15.1. Chưa chốt thì chưa được sửa contract, DDL hay code.
- Team Data cần xác nhận nghĩa của `childPrice = 0` và soát 97 sản phẩm có giá trẻ em cao hơn giá người lớn.
- Sau khi chốt: cập nhật các spec liệt kê ở spec §15.2 và triển khai theo spec §13.
- `src/frontend/package.json` và `src/frontend/package-lock.json` đã bị sửa từ trước phiên này, không thuộc thay đổi này.
