# Làm rõ bước chọn phương thức thanh toán trong đề xuất Stripe

- Ngày: 2026-09-24
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Phần `user-flow.md` của đề xuất `docs/prd/update/2026-09-24-thanh-toan-stripe-mor.md` cần mô tả rõ: khách điền hết thông tin, chọn phương thức thanh toán (hiện chỉ Stripe), bấm Thanh toán thì mới chuyển sang trang Stripe.

## File thay đổi

- `docs/prd/update/2026-09-24-thanh-toan-stripe-mor.md` — sửa: mục `user-flow.md` thêm Payment Method Selector, đoạn mô tả bước thanh toán, sơ đồ có bước chọn phương thức và nút Thanh toán, wireframe `/checkout`.

## Quyết định

- Chỉ sửa đề xuất (trạng thái vẫn `chờ chốt`); không sửa `docs/prd/user-flow.md`, theo AGENTS.md mục 8.
- Phương thức khác Stripe nếu hiển thị thì vô hiệu hoá, nhãn "Sắp có".

## Kiểm tra

- Không có lệnh kiểm tra tự động; đã đọc lại nội dung mục đã sửa.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất.
