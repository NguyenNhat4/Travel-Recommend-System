# Sửa e2e widget-opening flaky ở 768/1024px

- Ngày: 2026-10-12
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

CI fail `widget-opening.spec.ts` ở 768px và 1024px: `destinationRequests` bằng 1 thay vì 0. Khối "Bạn muốn đi đâu?" của trang chủ vào vùng nhìn trễ sau mốc `networkidle`, nên request `/destinations` của trang chủ bị tính nhầm là của widget.

## File thay đổi

- `src/frontend/tests/e2e/widget-opening.spec.ts` — sửa: trước mốc đếm, cuộn tới khối điểm đến, chờ request của trang chủ xảy ra rồi mới reset bộ đếm.

## Quyết định

- Chỉ sửa test; code ứng dụng đúng (widget không tự tải điểm đến). Điều kiện kiểm giữ nguyên.

## Kiểm tra

- Playwright (dev server :3000), `widget-opening --repeat-each=3`: 18/18 pass. Chưa chạy lại toàn bộ e2e trên CI.

## Còn lại / rủi ro

- Không có.
