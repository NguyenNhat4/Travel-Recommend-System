# Đề xuất PRD: hồ sơ cá nhân và địa chỉ /profile/booking_history

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành (tạo đề xuất và bản mẫu giao diện; chưa chốt)
- Phạm vi: docs

## Mục tiêu

Người dùng muốn chỉnh bố cục và màu của trang lịch sử đặt chỗ, thêm trang hồ sơ cá nhân sửa được thông tin, và đổi địa chỉ: `/profile` là hồ sơ, `/profile/booking_history` là lịch sử đặt chỗ. Đã khảo sát: `app.users` chỉ có `display_name`, `AuthUser` chỉ có họ tên và email, không có API sửa hồ sơ; chỉ có `PUT /auth/password`. Sửa họ tên và số điện thoại cần endpoint mới và cột mới, đổi route là đổi bảng route của PRD, nên phải có đề xuất đã chốt trước khi sửa source (AGENTS.md mục 8). Người dùng chọn phạm vi sửa: họ tên, số điện thoại, đổi mật khẩu (email chỉ xem).

## File thay đổi

- `docs/prd/update/2026-10-07-ho-so-ca-nhan-va-url-lich-su-dat-cho.md` — thêm: đề xuất FR-USR-04, AC-USR-01/02, đổi FR-BKG-14 và AC-BKG-18 sang `/profile/booking_history`, cột `app.users.phone`, `PATCH /auth/me`; trạng thái "chờ chốt".
- `history/2026-10-07-de-xuat-ho-so-ca-nhan-va-url-lich-su.md` — thêm: entry này.
- Bản mẫu giao diện (ngoài repo): https://claude.ai/artifact/J5umeEEBdAnLcYsaKgBL8B.

## Quyết định

- Không tự chốt đề xuất; chưa sửa PRD, contract, DDL, backend, frontend (AGENTS.md mục 8, bước 2).
- Giữ tông xanh V-OTA hiện có của frontend thay vì bảng màu xanh lá mà công cụ gợi ý thiết kế đưa ra; chỉ áp các quy tắc tương phản, vùng chạm 44px, nhãn trường, kiểm tra khi rời ô.
- Số điện thoại chỉ lưu ở `app.users`, không gửi CDP/Insider/Stripe, theo tinh thần FR-BKG-08 và NFR-SEC-01.
- Sở thích du lịch (phần còn lại của FR-USR-02) không đưa vào đợt này.

## Kiểm tra

- Chỉ có thay đổi tài liệu; không chạy lệnh kiểm tra. Bản mẫu giao diện đã mở trên trình duyệt thật (máy tính và điện thoại), không có lỗi console.

## Còn lại / rủi ro

- Chờ mihhquan chốt đề xuất (hoặc yêu cầu sửa) trước khi cập nhật PRD và code. Khi chốt: cập nhật PRD, rồi contract, migration `0008`, backend, frontend, test, chuyển đề xuất sang `update-archive/`.
- Làm mới họ tên trong phiên BFF sau khi lưu cần chọn cách làm khi triển khai.
