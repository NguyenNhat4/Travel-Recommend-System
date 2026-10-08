# Đề xuất PRD: trang Đơn hàng của tôi, chi tiết đơn và đơn đã trả tiền nhưng hết chỗ

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành (tạo đề xuất; chưa chốt)
- Phạm vi: docs

## Mục tiêu

Người dùng muốn một trang lịch sử đặt chỗ có lọc theo trạng thái, dịch vụ và ngày đặt, có trang chi tiết đầy đủ, có trạng thái trống thân thiện, và muốn biết xử lý thế nào khi Stripe đã thu tiền mà vé máy bay hết chỗ. Đã khảo sát code và PRD (không có `GET /bookings`, không có route `/profile` ở frontend, không có bước kiểm tra chỗ sau khi thu tiền; PRD không có FR nào cho danh sách đơn hay cho ca hết chỗ), nên đây là thay đổi lệch PRD và phải có đề xuất đã chốt trước khi sửa source (AGENTS.md mục 8).

Giao diện đã được người dùng chốt trên bản mẫu https://claude.ai/artifact/ATHDHksuHw5ddMFS5ADqX9 ngày 2026-10-07: ba tab Sắp đến / Hoàn thành / Đã huỷ, chip dịch vụ, lọc ngày đặt 1/7/30/60 ngày, phân trang 5 đơn mỗi trang, trang chi tiết hai cột.

## File thay đổi

- `docs/prd/update/2026-10-07-lich-su-don-hang-va-het-cho-sau-thanh-toan.md` — thêm: đề xuất FR-BKG-14/15/16, AC-BKG-18..20, sửa FR-USR-02, dòng route `/profile` và `/booking/:referenceCode`, ví dụ API §2.6; trạng thái "chờ chốt".
- `history/2026-10-07-de-xuat-lich-su-don-hang-va-het-cho.md` — thêm: entry này.

## Quyết định

- Không tự chốt đề xuất; chưa sửa `docs/prd/`, contract, DDL, backend, frontend (AGENTS.md mục 8, bước 2).
- Cách gộp trạng thái vào ba tab và giá trị mặc định giờ nhận/trả phòng (14:00/12:00) do người dùng chọn ngày 2026-10-07; số tổng đài và phạm vi kiểm tra hết chỗ (mọi dịch vụ hay chỉ vé máy bay) để mở trong đề xuất.
- Đã chọn phương án kiểm tra lại catalog rồi tự hoàn 100% bằng cơ chế `reject_paid` và hoàn tiền sẵn có (`domain/booking/models.py`, `application/booking/settlement.py`), thay vì xác nhận đơn rồi xử lý thủ công, vì khách đã trả tiền cho thứ không còn bán. Giới hạn: "hết chỗ" chỉ dựa trên bản chụp catalog (`project-brief.md` §4.2), đã ghi trong đề xuất.

## Kiểm tra

- Chỉ có thay đổi tài liệu, không chạy lệnh kiểm tra. Chưa chạy `validate_contract.py` vì contract chưa đổi.
- Đã đọc: `docs/prd/README.md`, `docs/prd/requirements.md` §1.5, §1.6, §3, `docs/prd/user-flow.md` §2, `docs/prd/api-contract.md` §2.6, `docs/prd/update/` (chỉ có đề xuất golden dataset, không liên quan), `history/README.md` và các entry gần đây (không entry nào về lịch sử đơn).

## Còn lại / rủi ro

- Chờ mihhquan chốt đề xuất (hoặc yêu cầu sửa) trước khi cập nhật PRD và bắt đầu code. Kế hoạch triển khai chi tiết nằm ở file kế hoạch của phiên này.
- Cần số tổng đài thật cho dòng "Liên hệ hỗ trợ".
- Chưa kiểm tra `ProductSummary` trong dữ liệu đơn có mang địa chỉ, hạng sao, khoá tiện ích hay phải gọi thêm API sản phẩm; việc này kiểm khi viết contract.
