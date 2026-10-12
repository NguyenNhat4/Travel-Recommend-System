# Kiểm soát timer của test polling xác nhận thanh toán

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Sửa frontend quality checks của PR #169, run 38234244738, job 114760884643: một test không tìm thấy trạng thái thành công trong thời hạn mặc định; 839 test khác pass. Phục vụ FR-BKG-04/06, kiểm thử luồng xác nhận sau Stripe.

## File thay đổi

- `src/frontend/tests/unit/confirmationView.test.tsx` — sửa: dùng fake timers và act cho riêng ca polling sau Stripe; chạy từng lượt và kiểm tra số lần gọi, trạng thái, gợi ý chỉ sau CONFIRMED và polling dừng.
- `history/2026-10-12-fix-ci-confirmation-poll-timers.md` — thêm: entry này.

## Quyết định

- Ca cũ mock chu kỳ 5ms nhưng vẫn dùng timer thật và findByText với timeout mặc định; có thể hết hạn trên runner bận. Log xác nhận timeout, chưa đo tải runner để khẳng định nguyên nhân chậm.
- Chủ động điều khiển thời gian thay vì tăng timeout. Flush mỗi lượt trong act riêng để React commit và đăng ký lượt tiếp theo.
- Chỉ đổi test; không đổi thời gian polling 2 giây/15 lần của sản phẩm, API, fixture hoặc PRD. Căn cứ PRD requirements FR-BKG-04/06, test-plan và lịch sử `2026-09-24-trien-khai-booking-thanh-toan-stripe.md`, `2026-10-07-trang-don-hang-cua-toi-va-chi-tiet-don.md`.

## Kiểm tra

- `gh run view 38234244738 --job 114760884643 --log-failed`: 1 failed, 839 passed. Head SHA 9ceb8552; CI pull_request kiểm tra cây merge, khác cây nhánh local về tổng số test.
- `npm exec -- vitest run tests/unit/confirmationView.test.tsx`: 23/23 PASS, exit 0.
- `npm test -- --maxWorkers=2`: 79 file, 831/831 PASS, exit 0.
- `node_modules/.bin/eslint tests/unit/confirmationView.test.tsx`: PASS.
- `git diff --check`: PASS.

## Còn lại / rủi ro

- Cần CI GitHub xác nhận lại trên cây merge của PR #169 sau push. Không kiểm nghiệm Stripe hoặc backend thật trong test mock này.
