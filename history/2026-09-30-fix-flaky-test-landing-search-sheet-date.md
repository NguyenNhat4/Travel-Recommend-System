# Sửa flaky test ngày tháng trong landingSearchSheet.test.tsx khi chạy cuối tháng

- Ngày: 2026-09-30
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend, tests

## Mục tiêu

Sửa lỗi CI/CD GitHub Actions trên PR vào `release-mvp-v2` (`Frontend quality checks` fail ở bước chạy test Vitest):
- `tests/unit/landingSearchSheet.test.tsx > LandingSearchSheet > dates: past days are disabled and a range needs the end after the start`: `AssertionError: expected false to be true`.

## Nguyên nhân gốc

- `LandingSearchSheet` khởi tạo ngày check-in mặc định là `tomorrow = addDaysIso(todayVN(), 1)`.
- `DateRangePicker` khởi tạo tháng hiển thị mặc định `view` là tháng của `start` (tức `checkIn`).
- Vào các ngày bình thường trong tháng (ngày 1 đến 28/29), cả `today` và `tomorrow` cùng thuộc một tháng, dialog mở ra ở tháng hiện tại. Nút ngày `today - 1` là ngày trong quá khứ nên có thuộc tính `disabled = true`, và nút "Tháng trước" bị vô hiệu hoá (`disabled = true`).
- Vào **ngày cuối cùng của tháng** (ví dụ 30/09), `today = 30`, `tomorrow = 01/10`. Nút mở lịch chọn ngày sẽ mở `view` ở tháng 10 (tháng của ngày `start`). Trong tháng 10, nút `29 tháng 10` là ngày tương lai nên `disabled = false`, khiến assertion `expect(disabled).toBe(true)` bị fail.

## File thay đổi

- `src/frontend/tests/unit/landingSearchSheet.test.tsx`:
  - Trong `beforeEach`: cố định thời gian hệ thống bằng `vi.useFakeTimers({ toFake: ['Date'] })` và `vi.setSystemTime(new Date('2026-09-15T10:00:00+07:00'))` (ngày giữa tháng ổn định).
  - Trong `afterEach`: khôi phục bằng `vi.useRealTimers()`.
- `history/2026-09-30-fix-flaky-test-landing-search-sheet-date.md`: entry này.

## Kiểm tra

- `npm run test -- tests/unit/landingSearchSheet.test.tsx`: 8/8 tests pass.
- `npm run test`: 42/42 test files pass, 386/386 tests pass.
- `npm run lint`: 0 error.
- `npm run typecheck`: 0 error.
- Contract validation: `validate_contract.py`: PASS.
