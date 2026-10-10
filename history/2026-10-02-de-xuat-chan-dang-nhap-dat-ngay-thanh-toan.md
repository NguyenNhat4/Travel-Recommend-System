# Đề xuất chặn đăng nhập ở nút Đặt ngay và Thanh toán

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: dang dở
- Phạm vi: docs
- Bị thay thế bởi: 2026-10-02-chan-dang-nhap-o-dat-ngay-va-thanh-toan.md

## Mục tiêu

Người dùng báo khách chưa đăng nhập vẫn bấm đặt hàng được. Điều tra: hành vi này do PRD chốt (FR-USR-03, AC-BKG-17, R-CHK-06) và Backend đã chặn tạo đơn bằng 401. Người dùng chọn chặn sớm hơn ở nút "Đặt ngay" và "Thanh toán", đăng nhập xong quay lại checkout để hoàn tất. Việc này lệch PRD nên cần đề xuất.

## File thay đổi

- `docs/prd/update/2026-10-02-chan-dang-nhap-o-dat-ngay-va-thanh-toan.md` — thêm: đề xuất, trạng thái chờ chốt.

## Quyết định

- Chưa sửa code/PRD/spec; chờ người dùng chốt đề xuất (AGENTS.md mục 8).

## Kiểm tra

- Không chạy lệnh nào (chỉ thêm tài liệu).

## Còn lại / rủi ro

- Sau khi chốt: cập nhật PRD, spec booking, rồi sửa frontend và test như mục "Thay đổi source sau khi chốt" của đề xuất.
