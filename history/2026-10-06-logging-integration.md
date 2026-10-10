# Test tích hợp log trên khoa/logging và sửa instrumentation

- Ngày: 2026-10-06
- Tác giả: Khoa / Claude
- Nhánh: khoa/logging-integration-fixes
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Sau khi merge #111–#114 vào `khoa/logging`, kiểm tích hợp. `next build` báo cảnh báo: `instrumentation.ts` dùng `process.on/exit` trong bundle edge.

## File thay đổi

- `src/frontend/src/instrumentation.ts` — sửa: chỉ gọi `registerNode()` khi runtime là Node
- `src/frontend/src/instrumentation-node.ts` — thêm: `app.startup` và handler SIGTERM/SIGINT tách khỏi bundle edge
- `history/2026-10-06-logging-integration.md` — thêm

## Quyết định

- Tách file thay vì tắt cảnh báo, để bundle edge không còn thấy API của Node.

## Kiểm tra

- Backend `pytest src/backend/tests`: 1205 passed, 30 skipped (trên bản đã merge).
- Frontend `vitest run`: 616 passed, 1 failed (có sẵn: `WidgetProgress.tsx` trùng tên `widgetProgress.ts`, chỉ lỗi trên macOS).
- `docker build -f src/frontend/Dockerfile.web` thành công trên Linux; container in `app.startup` JSON có `severity`, `ts +07:00`, `pino` có trong image.
- Backend qua TestClient: `request_id` giữ nguyên, `error.code`, số điện thoại bị che; grep `hunter2`, số điện thoại, JWT, email trong toàn bộ output: 0 kết quả.

## Còn lại / rủi ro

- Chưa chạy stack docker đầy đủ (Postgres, Weaviate, Redis) và luồng đăng nhập → tìm kiếm → giỏ → checkout → trợ lý; chưa chạy lượt crawler `daily` thật.
- `bff.session.store` ghi ERROR cho mỗi lần Redis reconnect, có thể ồn khi Redis sập.
- Chưa kiểm Ops Agent trên VM thật.
