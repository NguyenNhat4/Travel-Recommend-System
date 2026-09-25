# Sửa E2E clarification cho khớp UI trợ lý mới

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Job `Frontend E2E smoke tests` của Frontend CI fail ở `tests/e2e/routes.spec.ts` (test "clarification submits an intent override…"): test chờ nút "3 ngày" nhưng nút không còn trên `/assistant`. Nguyên nhân: commit `e40e4a5` (`history/2026-09-24-form-mo-dau-tro-ly.md`) cố ý hiện câu hỏi làm rõ và NO_RESULTS như tin nhắn assistant thường, không render card có nút gợi ý (`AssistantConversation.tsx`, `AssistantView.tsx`), nhưng không cập nhật E2E.

## File thay đổi

- `src/frontend/tests/e2e/routes.spec.ts` — sửa: test clarification kiểm tra câu hỏi hiện đúng một lần và không có nút "3 ngày"; người dùng trả lời bằng cách gõ "3 ngày", payload thứ hai là `{ message: '3 ngày', conversationId: 'clarification-session', intentOverride: null }`. Mock route phân biệt lần gọi theo `payloads.length` thay vì `intentOverride`.

## Quyết định

- Chọn giữ hành vi UI của `e40e4a5` (người dùng chọn phương án B) và sửa test, không khôi phục nút gợi ý.
- Hệ quả đã biết: `suggestedValues` và `submitIntentOverride` không còn đường kích hoạt từ trang `/assistant`; người dùng phải gõ câu trả lời. Test không còn phủ nhánh `intentOverride`.

## Kiểm tra

- `npm run build:web` rồi `CI=true npx playwright test` (src/frontend): 13 passed, 1 skipped, gồm test clarification mới.
- `npm run lint`: 0 lỗi, 4 warning có sẵn. `npm run typecheck`: pass.
- Chưa chạy `validate_contract.py` (không đụng contract).

## Còn lại / rủi ro

- Lỗi CI riêng ở nhánh `dev`: bước "Check generated OpenAPI types are committed" fail (`src/frontend/src/types/api.gen.ts` lệch contract); chưa xử lý ở entry này. Trên `feat/agent` regenerate không sinh diff.
- Code `onIntentOverride` / `submitIntentOverride` hiện chưa có đường gọi từ UI; cần quyết định giữ hay gỡ.
