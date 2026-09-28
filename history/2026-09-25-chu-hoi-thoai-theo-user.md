# Chủ hội thoại trợ lý theo user, Web tự mở hội thoại mới khi hết hạn

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, frontend, docs

## Mục tiêu

Tiếp nối `2026-09-25-sse-loi-graph-phat-run-failed.md`. Entry đó đoán lỗi `CONVERSATION_NOT_FOUND` là do backend restart; bằng chứng sau cho thấy nguyên nhân chính khác. Log có `POST /auth/session/token` ngay trước request lỗi, tức là BFF vừa làm mới access token (`bffSession.ts` `ensureFreshAccessToken`: TTL 600s, làm mới khi còn ≤ 60s). Chủ hội thoại lại là `sha256(header Authorization)` (`runtime_dependencies.py`), nên token mới dẫn tới chủ mới, `load()` trả None và backend trả 404. Người dùng đăng nhập sẽ mất hội thoại khoảng 9 phút một lần.

Phục vụ FR-AGT-01 và FR-AGT-05 (hội thoại đa lượt, điều chỉnh qua lượt tiếp theo).

## File thay đổi

- `src/backend/app/api/deps.py` — sửa: thêm dependency `conversation_owner` trả `cdp_user_id` của Bearer hợp lệ. Không có hoặc hỏng Bearer thì trả None, không trả 401, vì contract của stream không khai báo 401.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: hai route itinerary nhận `owner` và truyền vào `use_case.planner`.
- `src/backend/app/application/itinerary/use_cases.py`, `src/backend/app/application/ports/itinerary_planner.py`, `src/backend/app/main.py` — sửa: factory planner nhận thêm `owner`.
- `src/backend/app/agents/runtime_dependencies.py` — sửa: chủ = `user:<cdp_user_id>`. Bearer không xác thực được thì chủ = `token:<sha256>`; khách vẫn là `anonymous`.
- `src/backend/tests/unit/api/test_conversation_owner.py` — thêm: token làm mới của cùng user giữ nguyên chủ; user khác ra chủ khác; khách, token hỏng và token đúng user không dùng chung nhóm.
- `src/frontend/src/context/assistantState.ts` — sửa: action `conversation-restarted` xoá `conversationId` và thêm dòng "Đã bắt đầu cuộc trò chuyện mới.".
- `src/frontend/src/context/AssistantProvider.tsx` — sửa: `run.failed` mang `CONVERSATION_NOT_FOUND` thì gửi lại đúng tin nhắn với `conversationId: null`. Request chỉ có `intentOverride` thì vẫn hiện lỗi như cũ.
- `src/frontend/tests/unit/assistantProvider.test.tsx` — sửa: thay test "không tự retry" bằng hai test mới, gửi lại một lần cho tin nhắn và không gửi lại cho patch chip.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: §6 ghi quy tắc chủ hội thoại.
- `docs/spec/agent/presentation-slides.html` — sửa: slide 9 thêm dòng 404 `CONVERSATION_NOT_FOUND` và câu về `run.completed`/`run.failed`; slide 10 ghi hội thoại gắn với `cdp_user_id`; slide 14 thêm việc lưu hội thoại bền.
- `docs/spec/agent/presentation-script.md` — sửa: lời nói slide 9, 10, 14 và thêm một câu hỏi dễ gặp về backend restart.

## Quyết định

- Frontend tự gửi lại tin nhắn khi gặp 404 để hiện thực đúng `docs/spec/hop-dong-tich-hop-frontend.md` dòng 349 ("Xóa `conversationId`, gửi lại tin nhắn như cuộc hội thoại mới..."). Test cũ khẳng định điều ngược với spec nên được thay. Dòng hệ thống hiển thị như một tin nhắn assistant, vì transcript chỉ có hai sender `user`/`assistant`.
- Không đổi contract, DDL hay PRD, nên không cần đề xuất. `AuthPrincipal` là nguồn danh tính duy nhất theo auth §3.5.
- Chưa làm adapter Postgres (`app.conversations`). DDL chưa có chỗ cho `constraints`/`previous_selection`, PK là `uuid` trong khi code sinh `conv-<hex>`, và `cdp_user_id` có FK tới `cdp.profiles`. Cần người dùng quyết cách lưu trước.
- Theo yêu cầu người dùng, chỉ cập nhật slide của agent, không sửa `docs/prd/slides/`.

## Kiểm tra

- `pytest src/backend/tests/unit/api/test_conversation_owner.py src/backend/tests/unit/api/test_backend_wiring.py`: 14 passed.
- `pytest src/backend/tests/contract/test_assistant_contract.py src/backend/tests/architecture`: 20 passed.
- `npx vitest run tests/unit` (src/frontend): 84 passed. `npx tsc --noEmit`: pass. `npm run lint`: 0 lỗi, 4 warning có sẵn.
- Chụp slide 9, 10, 14 bằng Playwright chromium headless: không tràn khung.
- Chưa chạy E2E Playwright của frontend, chưa chạy toàn bộ suite backend, chưa thử lại trên app thật.

## Còn lại / rủi ro

- Hội thoại vẫn nằm trong RAM của process, nên mất khi backend restart và lỗi ngẫu nhiên nếu chạy nhiều worker. Việc còn lại là adapter Postgres.
- Khách (không đăng nhập) dùng chung nhóm `anonymous`; ai có `conversationId` thì đọc được hội thoại đó, như trước.
- Nút "Thử lại" sau 404 của patch chip vẫn gửi `conversationId` cũ.
