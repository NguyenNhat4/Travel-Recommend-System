# SSE assistant phát run.failed khi graph kết thúc bằng lỗi

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Web hiện "Lỗi từ Backend Agent — Backend returned an invalid assistant response" khi chat tiếp trong một hội thoại cũ. Log backend: `intake → classify → dead_letter → finalize`, `httpStatus=404 status=ERROR` (`CONVERSATION_NOT_FOUND`: `InMemoryConversationStore` mất dữ liệu khi backend restart/reload, còn frontend giữ `conversationId` trong `sessionStorage`).

Lỗi thật nằm ở `POST /assistant/itineraries/stream`: mọi kết quả graph, kể cả Error Envelope 404/422/500, đều được phát dưới `run.completed`. Frontend (`isAssistantResponse`) từ chối payload này và hiện thông báo chung, nên `assistantState` không bao giờ nhận được mã `CONVERSATION_NOT_FOUND` để xoá `conversationId` cũ. Hợp đồng (`paths/itinerary-agent.yaml`, `hop-dong-tich-hop-itinerary-assistant.md` §4.1) quy định lỗi nằm trong `run.failed.httpStatus`.

## File thay đổi

- `src/backend/app/api/v1/routes/assistant.py` — sửa: `http_status >= 400` thì phát `run.failed {runId, httpStatus, error: <Error Envelope>}`; còn lại giữ `run.completed`.
- `src/backend/tests/contract/test_assistant_contract.py` — sửa: thêm `test_stream_reports_a_graph_error_as_run_failed` (conversationId không tồn tại → `run.failed` 404, envelope đúng contract, không có `run.completed`).

## Quyết định

- Sửa phía backend cho khớp hợp đồng đã có; không đổi contract/PRD nên không cần đề xuất `docs/prd/update/`. Frontend đã xử lý sẵn `run.failed` (`backendEventError`) và `CONVERSATION_NOT_FOUND` (`assistantState.ts`).
- Không đổi `retry` ở frontend: test `assistantProvider.test.tsx` cố ý khẳng định retry gửi đúng payload cũ.

## Kiểm tra

- `pytest src/backend/tests/contract/test_assistant_contract.py`: 12 passed.
- Chưa chạy `validate_contract.py` (không đụng contract). Chưa chạy lại toàn bộ backend test và E2E frontend.

## Còn lại / rủi ro

- Nút "Thử lại" sau `CONVERSATION_NOT_FOUND` gửi lại `conversationId` cũ nên vẫn 404; người dùng phải gõ tin mới (khi đó id đã bị xoá). Cần quyết định có đổi test retry hay không.
- `InMemoryConversationStore` mất hội thoại mỗi lần backend reload; cần store bền nếu muốn hết hạn hội thoại ngoài ý muốn ở dev/staging.
- Trong đoạn chat còn thấy "Lịch trình đã được hoàn tất." cho tin "đi 4 ngày thôi"; chưa điều tra (chưa rõ đó là text cố định của UI hay của backend).
