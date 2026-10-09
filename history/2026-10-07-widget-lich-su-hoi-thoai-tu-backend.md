# Widget trợ lý: lịch sử hội thoại lấy từ backend

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Người dùng báo: đang chat với trợ lý, đóng widget rồi không tìm lại được hội thoại ở đâu.

Nguyên nhân: panel "Lịch sử trò chuyện" giữ danh sách bằng `useState([])` trong `useFloatingWidget`. Danh sách chỉ có
mục khi bấm "Đoạn chat mới", và không bao giờ gọi `GET /assistant/conversations`: `listAssistantConversations()` có sẵn
trong `services/assistantHistory.ts` nhưng không ai gọi. Tải lại trang, mở tab mới, đổi tài khoản hoặc đi qua `/checkout`
(AppShell gỡ widget) đều làm danh sách rỗng, dù backend vẫn lưu hội thoại trong archive Postgres.

Đóng widget bằng X hoặc Esc không xoá transcript: transcript nằm trong `AssistantProvider`.

Phục vụ FR-AGT-01: người dùng đã đăng nhập xem danh sách, mở lại và tiếp tục hội thoại của mình; khách không có lịch sử
lâu dài. Đây là hiện thực đúng spec `docs/spec/hop-dong-tich-hop-frontend.md` §4.8 (bảng endpoint) và §9.6, không lệch PRD.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa:
  - Mở panel lịch sử thì tải `listAssistantConversations(1, 20)` khi đã đăng nhập.
  - Cuộc đang chat chưa có trong archive vẫn hiện ở đầu danh sách.
  - Đổi tài khoản thì bỏ danh sách cũ và response đang bay về.
  - Bỏ bản chụp danh sách trong bộ nhớ và bỏ xoá cục bộ.
  - Mở lại hội thoại thì dựng lịch trình từ response đã lưu.
- `src/frontend/src/features/itinerary/widget/WidgetHistory.tsx` — sửa: trạng thái đang tải, lỗi kèm "Thử lại", ghi chú
  đăng nhập cho khách; bỏ nút xoá.
- `src/frontend/src/features/itinerary/widget/widgetTypes.ts` — sửa: `ConversationSession` chỉ còn `id`, `title`, `timestamp`.
- `src/frontend/tests/unit/widgetHistory.test.tsx` — thêm: 6 test cho panel lịch sử.
- `src/frontend/tests/unit/floatingWidgetOpening.test.tsx` — sửa: bỏ test "opens the actual saved conversation…". Test
  này kiểm hành vi bản chụp trong bộ nhớ đã bỏ. Phần còn giá trị (toast khi mở lại lỗi) chuyển sang `widgetHistory.test.tsx`.

## Quyết định

- **Bỏ nút xoá hội thoại.** Contract không có endpoint xoá, nên xoá cục bộ sẽ hiện lại ở lần tải sau. Thêm endpoint là
  đổi contract, cần làm riêng.
- **Khách không gọi archive.** Endpoint bắt buộc `bearerAuth`, và FR-AGT-01 nói khách không có lịch sử lâu dài. Panel chỉ
  hiện cuộc đang chat và câu "Đăng nhập để lưu và xem lại lịch sử hội thoại."
- **Bấm cuộc đang chat thì chỉ đóng panel**, không tải lại: cuộc đó có thể chưa vào archive, hoặc người dùng là khách.
- **Lịch trình khi mở lại** lấy từ `assistantState.response`, do `conversation-loaded` khôi phục, qua effect đồng bộ sẵn
  có. Không giữ `plan` cục bộ nữa.
- Danh sách tải lại mỗi lần mở panel, không cache: một lần gọi nhỏ, và luôn khớp server.

## Kiểm tra

- `node_modules/.bin/vitest run tests/unit/widgetHistory.test.tsx` trên code cũ: 5/5 fail, như mong đợi.
- `cd src/frontend && node_modules/.bin/vitest run`: 65 file, 633 test pass.
- `node_modules/.bin/tsc --noEmit`: exit 0.
- `node_modules/.bin/eslint` trên 5 file đã đổi: exit 0.
- Tầng bằng chứng: unit test với provider và service giả. Chưa chạy thử trên app thật với backend và Postgres.

## Còn lại / rủi ro

- Chưa bấm thử trên UI thật. Các bước: đăng nhập → chat → tải lại hoặc mở tab mới → mở Lịch sử → hội thoại có trong danh
  sách và mở lại kèm lịch trình.
- Test chưa kiểm việc dựng lại lịch trình khi mở lại hội thoại (`loadConversation` bị mock). Việc này dựa vào React gộp
  `setActivePlan(null)` với dispatch `conversation-loaded` rồi effect mới chạy; cần kiểm khi bấm thử UI.
- Chỉ tải trang đầu (20 hội thoại), chưa có "Xem thêm".
- Hội thoại `status: expired` vẫn hiện và mở được transcript. Gửi tiếp: `load_conversation` trong
  `src/backend/app/agents/nodes.py` khôi phục ngữ cảnh từ archive khi Redis đã hết hạn (người dùng đã đăng nhập), nên chat
  tiếp được trong cùng hội thoại. Đọc từ code, chưa chạy thử.
