# Báo lỗi có hướng dẫn khi stream trợ lý bị gián đoạn; cập nhật trạng thái logging

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: hoàn thành
- Phạm vi: frontend | docs

## Mục tiêu

- D4 (người dùng chốt): khi luồng SSE của trợ lý bị đứt giữa chừng, người dùng thấy thông báo tiếng Việt có hướng dẫn cách xử lý, không phải chuỗi kỹ thuật tiếng Anh.
- Phase 1.5: các entry logging đang ghi *dang dở* (`2026-10-06-logging-schema-chung`, `2026-10-06-logging-monitoring`) nhưng các nhánh con đã merge. Entry cũ không được sửa, nên trạng thái mới được ghi ở đây.

## File thay đổi

- `src/frontend/src/services/assistantStream.ts` — sửa: thông báo khi stream kết thúc trước sự kiện kết thúc (`MISSING_TERMINAL_EVENT`, retryable) là hướng dẫn tiếng Việt: bấm "Thử lại", nếu vẫn lỗi thì tải lại trang. Mã lỗi giữ nguyên.
- `history/2026-10-08-sse-bao-loi-co-huong-dan-va-trang-thai-logging.md` — thêm: entry này.

## Quyết định

- Giữ mã `MISSING_TERMINAL_EVENT` và cờ retryable để UI đã có (nút "Thử lại" trong `WidgetChat.tsx` hiện khi `retryable`) và test không đổi.
- Không thêm cơ chế tự nối lại SSE: chưa có thiết kế (`Last-Event-ID`, đếm lại sự kiện). Thông báo có hướng dẫn thay thế cho việc tự nối lại trong phạm vi này.
- Trạng thái logging: các nhánh `khoa/logging-backend`, `-frontend`, `-crawler`, `-monitoring`, `-integration-fixes` và `khoa/logging` đã merge (PR #111–#116, #118). Trạng thái *dang dở* trong hai entry cũ là lỗi cập nhật, không phải việc còn mở. Việc còn lại của logging được theo dõi ở các mục kiểm trên VM trong plan, không ở hai entry này.

## Kiểm tra

- `npx vitest run tests/unit/assistantStream.test.ts tests/unit/assistantProvider.test.tsx`: 2 file, 24 test PASS.
- Chưa kiểm trên trình duyệt thật.

## Còn lại / rủi ro

- Chưa có kiểm thử tự động cho chính chuỗi tiếng Việt mới (test chỉ khẳng định mã lỗi).
- Chưa kiểm xem trình duyệt có tự động thử lại trước khi hiện thông báo hay không; hiện chỉ có nút thủ công.
