# Đồng bộ đề xuất nền: họ và tên hai ô

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng đồng ý tách họ và tên thành hai ô miễn đủ thông tin. Đưa vào đề xuất nền để hai đề xuất không mâu thuẫn.

## File thay đổi

- `docs/prd/update/2026-09-29-checkout-nhieu-buoc-hanh-khach.md` — sửa: Q7, FR-BKG-08, mô tả bước ①, `APP_BOOKING_TRAVELERS` thêm `surname`, `given_names`.
- `docs/prd/update/2026-09-29-ve-may-bay-thong-tin-hanh-khach.md` — sửa: ghi nhận đã chốt, bỏ cột trùng `surname`/`given_names` khỏi mục `data-model.md`.

## Quyết định

- `full_name` giữ, nối từ hai ô. Cả hai đề xuất vẫn `chờ chốt`.

## Kiểm tra

- Không có (chỉ sửa tài liệu).

## Còn lại / rủi ro

- Spec `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` chưa sửa; cập nhật sau khi đề xuất được chốt.
- Đề xuất thông tin bay còn nhắc `surname`, `given_names` ở dòng "thêm" cần kiểm lại nếu chốt.
