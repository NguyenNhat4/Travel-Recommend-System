# Câu từ chối ngoài phạm vi hiện như tin nhắn của trợ lý

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Khi agent từ chối (ngoài phạm vi, guardrail chặn chèn lệnh/đòi secret), backend gửi `run.failed` mã `VALIDATION_ERROR`. Widget chat hiện câu đó trong khung lỗi đỏ, không có logo mascot. Người dùng muốn nó hiện như tin nhắn bình thường của AI, có logo.

## File thay đổi

- `src/frontend/src/context/assistantState.ts` — sửa: thêm action `request-refused`, đẩy câu từ chối vào transcript như tin nhắn assistant, `phase: 'idle'`, `error: null`.
- `src/frontend/src/context/AssistantProvider.tsx` — sửa: `run.failed` mã `VALIDATION_ERROR` dispatch `request-refused` thay vì `request-failed`.
- `src/frontend/tests/unit/assistantState.test.ts` — sửa: thêm test cho `request-refused`.

## Quyết định

- Chỉ đổi phía frontend, không đổi contract: backend vẫn trả 400 `VALIDATION_ERROR` như trước.
- Chỉ áp dụng cho `run.failed` trong stream. Lỗi HTTP trước khi stream (đường `.catch`) vẫn là `request-failed`.

## Kiểm tra

- `npx vitest run tests/unit/assistantState.test.ts`: 7 test pass.
- `npx tsc --noEmit`: chỉ còn lỗi sẵn có ở `.next/types` (file Next sinh ra), không có lỗi ở file đã sửa.
- Chưa kiểm tay trên trình duyệt.

## Còn lại / rủi ro

- Mọi `run.failed` mã `VALIDATION_ERROR` đều thành tin nhắn; hiện chỉ nhánh từ chối của agent phát mã này trong stream.
- Chưa có test cho nhánh trong `AssistantProvider`.
