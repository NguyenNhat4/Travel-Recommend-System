# Sửa E2E assistant drawer theo UI hiện tại

- Ngày: 2026-09-24
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev` ở repository gốc; checkout frontend lồng bên trong đang ở `main`
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Khắc phục test E2E assistant drawer bị fail vì test còn tìm nút `#aiAssistantBtn` và các label của component cũ, trong khi homepage hiện mở `AiFloatingWidget` bằng nút accessible name `Mở trợ lý du lịch AI`.

## File thay đổi

- `src/frontend/tests/e2e/routes.spec.ts` — đổi test stream assistant sang trigger, input, nút gửi và trạng thái phiên của `AiFloatingWidget` hiện tại; đổi tên test để phản ánh đúng UI.
- `history/2026-09-24-fix-frontend-e2e-assistant-drawer.md` — thêm: ghi nguyên nhân và kết quả kiểm tra.

## Quyết định

- Sửa selector và assertion của test theo accessibility contract đang được component cung cấp.
- Không thêm lại `#aiAssistantBtn` vào UI vì source hiện tại không có header assistant drawer riêng; homepage dùng floating assistant widget.

## Kiểm tra

- `npx playwright test tests/e2e/routes.spec.ts --grep "floating assistant drawer streams a backend result"` — PASS: 1 test.
- `npm run test:e2e` — PASS: 13 test, 1 skipped; test live FastAPI assistant được skip khi `RUN_ASSISTANT_LIVE_E2E` chưa bật.
- `next-env.d.ts` được khôi phục sau build để không giữ thay đổi sinh tự động ngoài phạm vi.

## Còn lại / rủi ro

- Không còn test E2E mock nào fail.
- Test live FastAPI vẫn cần backend chạy và `RUN_ASSISTANT_LIVE_E2E` nếu muốn chạy; lần kiểm tra này không khẳng định live backend.
