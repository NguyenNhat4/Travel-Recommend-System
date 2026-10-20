# Tăng testTimeout frontend để test polling không timeout trên CI

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent), sửa theo CI check fail "Frontend quality checks" của PR #157 (run 38223122941, `222f90c7`)
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

CI fail ở ba test: `confirmationView` ("polls after returning from Stripe…"), `flightResultsView` ("says there is no flight on the searched day…") và `landingSearchSheet` ("guests: never exceeds 9 people…"). Log báo `Test timed out in 5000ms`; các test này chạy polling hoặc render thật, và khi CI chạy 79 file song song chúng vượt 5 giây mặc định của Vitest.

## File thay đổi

- `src/frontend/vitest.config.ts` — sửa: thêm `testTimeout: 20000` (kèm comment).

## Quyết định

- Đặt timeout ở cấu hình chung thay vì từng test: ba test này không phải là các test duy nhất chạy lâu dưới tải. Assertion không đổi, test vẫn fail nếu logic sai.

## Kiểm tra

- `npx vitest run` trên ba file test: `confirmationView` 23/23, `flightResultsView` 13/13, `landingSearchSheet` 19/19 passed.

## Còn lại / rủi ro

- Nếu CI còn timeout, cần xem log để biết test nào và thời gian chờ thực tế.
