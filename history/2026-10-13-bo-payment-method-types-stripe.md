# Bỏ payment_method_types khỏi Stripe Checkout Session

- Ngày: 2026-10-13
- Tác giả: Khoa15 / Claude Code
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Stripe trả lỗi 400 khi tạo Checkout Session: `The payment_method_types parameter is no longer supported when creating a Checkout Session`. Mọi đặt phòng có thanh toán đều không tạo được phiên Stripe. Mục tiêu là bỏ tham số này để tạo phiên thành công trở lại.

## File thay đổi

- `src/backend/app/infrastructure/payments/stripe_gateway.py` — sửa: bỏ `"payment_method_types": ["card"]` khỏi `create_checkout_session`.
- `src/backend/tests/unit/infrastructure/test_stripe_gateway.py` — sửa: thêm assertion body form không chứa `payment_method_types`; viết trước khi sửa code và đã chạy thấy fail.
- `docs/plan/2026-09-24-booking-thanh-toan-stripe.md` — sửa: dòng 171 bỏ `payment_method_types=[card]`, trỏ về entry này.

## Quyết định

- Chọn hướng A (chỉ xoá tham số), không dùng `payment_method_configuration`. Phương thức thanh toán do các phương thức bật trong Dashboard quyết định.
- Không đề xuất `docs/prd/update/`. PRD chỉ ghi "thanh toán qua trang Stripe Checkout" (`docs/prd/project-brief.md:63`) và kịch bản test dùng thẻ test `4242` (`docs/prd/test-plan.md:90`); không ghi chỉ thẻ. Ràng buộc chỉ thẻ chỉ có trong plan 2026-09-24, nên đây là thay đổi plan, không lệch PRD.
- Idempotency key `booking:{booking_id}` giữ nguyên. Theo tài liệu Stripe, request lỗi validation không được lưu kết quả idempotency nên dùng lại key không bị trả lại lỗi cũ.
- Giới hạn `expires_at` của Stripe (ít nhất 30 phút) không đổi trong entry này. `booking_hold_minutes` mặc định 30 (`src/backend/app/core/config.py:237`) là ngưỡng biên, cần kiểm tra riêng.

## Kiểm tra

- `python3 -m pytest src/backend/tests/unit/infrastructure/test_stripe_gateway.py -q`: trước khi sửa code, 1 failed (assertion mới), 16 passed; sau khi sửa, 17 passed.
- `python3 -m pytest src/backend/tests/unit -q`: 2837 passed, 2 skipped, 3 xfailed.
- Chưa gọi Stripe thật ở staging hoặc test mode. Chưa kiểm chứng request thật.

## Còn lại / rủi ro

- **Dashboard test mode phải chỉ bật Card** (Settings → Payment methods). Nếu bật thêm phương thức khác, trang Checkout sẽ hiện thêm phương thức, lệch với plan và kịch bản test PRD.
- Kiểm tra Dashboard live cùng cấu hình trước khi đưa lên production. Test mode và live mode cấu hình riêng.
- Chưa xác định vì sao Stripe bắt đầu từ chối tham số: code không pin `Stripe-Version`, nên phiên bản API là mặc định của tài khoản. Cần xem phiên bản API của tài khoản trong Dashboard để xác nhận.
- Biên `booking_hold_minutes = 30` và giới hạn 30 phút của `expires_at` cần kiểm tra riêng (xem Quyết định).
