# Sửa e2e navigation flaky trên CI chậm

- Ngày: 2026-10-12
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

CI fail `navigation.spec.ts`: (1) "Home loads one catalog request" thấy 0 request `/products` sau `networkidle`; (2) "a header menu lists services only" flaky, panel nhóm Lưu trú không có link. Cả hai do runner chậm: request catalog của trang chủ chỉ phát sau hydrate, `networkidle` có thể đạt trước đó, và bấm nút nhóm trước hydrate bị client thay nút.

## File thay đổi

- `src/frontend/tests/e2e/navigation.spec.ts` — sửa: chờ (`expect.poll`) request `/products` của trang chủ trước `networkidle` ở hai test.
- `history/2026-10-12-sua-e2e-navigation-flaky.md` — thêm: entry này.

## Quyết định

- Chỉ sửa test, không đổi code ứng dụng; điều kiện kiểm giữ nguyên.

## Kiểm tra

- Playwright (dev server :3000), `navigation --repeat-each=2`: 22/22 pass. Lỗi gốc không tái hiện trên máy nhanh. Chưa chạy lại trên CI.

## Còn lại / rủi ro

- Nếu CI vẫn fail thì cần xem trace của runner.
