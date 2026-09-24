# Áp dụng đề xuất thanh toán Stripe MoR vào PRD

- Ngày: 2026-09-24
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng chốt đề xuất `2026-09-24-thanh-toan-stripe-mor` (Stripe test mode, V-OTA là Merchant of Record, giữ chỗ, huỷ/hoàn tiền, chọn phương thức thanh toán ở `/checkout`). Áp dụng vào PRD theo AGENTS.md mục 8 bước 3–4.

## File thay đổi

- `docs/prd/project-brief.md` — sửa: §4.1, §4.2.
- `docs/prd/requirements.md` — sửa: FR-BKG-02/03/04, thêm FR-BKG-05/06/07, NFR-SEC-03, AC-BKG-01..04.
- `docs/prd/data-model.md` — sửa: khối lưu trữ, ERD `app.bookings` + `app.payments`, vòng đời đơn §4.1.
- `docs/prd/architecture.md` — sửa: sơ đồ, cây thư mục, stack, ranh giới Backend ↔ Stripe.
- `docs/prd/deployment-plan.md` — sửa: môi trường thanh toán, biến `STRIPE_*`, `PAYMENT_PROVIDER`, `BOOKING_HOLD_MINUTES`, `PAYMENT_MAX_FAILED_ATTEMPTS`, `PUBLIC_WEB_URL`.
- `docs/prd/user-flow.md` — sửa: route `/checkout`, `/booking/:referenceCode`, mô tả và sơ đồ luồng thanh toán, wireframe §4.4.
- `docs/prd/test-plan.md` — sửa: kịch bản webhook, bước E2E 6 và 8.
- `docs/prd/update/2026-09-24-thanh-toan-stripe-mor.md` → `docs/prd/update-archive/` — đổi tên/di chuyển; trạng thái `đã áp dụng`.

## Quyết định

- Áp dụng nguyên văn nội dung đề xuất đã chốt (Q1–Q8 theo phương án đề xuất).
- Chưa sửa source (contract, DDL, backend, frontend): theo `docs/plan/2026-09-24-booking-thanh-toan-stripe.md`.

## Kiểm tra

- Chỉ tài liệu; không chạy lệnh kiểm tra. Đã đối chiếu `git diff` các file PRD.

## Còn lại / rủi ro

- Toàn bộ thay đổi source theo plan chưa làm; `docs/spec/`, `product.md` và cấu hình vẫn mô tả bản cũ (mô phỏng, không huỷ).
