# Prompt clarify: không lặp câu khi người dùng đổi mà chưa nói đổi thành gì

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Sonnet 5.5
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

"đổi điểm đến" → "mình muốn đổi" → "đổi" khiến agent trả y hệt nhiều lượt (nhánh `change_without_value`, xem
`history/2026-09-30-hoi-lai-khi-doi-ma-chua-noi-cu-the.md`). Đo với `gpt-4o-mini` thật, nhiệt độ 0, state dựng lại từ
screenshot: 9/9 lần ra cùng một câu. `CONVERSATION_PROMPT` không có luật cho trường hợp câu hỏi đã được hỏi rồi.

## File thay đổi

- `src/backend/app/agents/steps/prompts.py` — sửa: `CONVERSATION_PROMPT` thêm luật cho `change_without_value`: câu hỏi đã được hỏi mà người dùng vẫn chưa nói giá trị thì không lặp/diễn đạt lại, nêu 3–4 lựa chọn, cho giữ giá trị hiện tại; "đâu cũng được" thì gợi ý một phương án.

## Quyết định

- Chỉ sửa prompt. Không đổi payload, node, contract; không lệch PRD (PRD §3 vẫn chỉ ghi nhánh `AskUser`). Form gợi ý cho nhánh này đã bị chốt là không làm ở entry trước.
- Phần prompt nhắc `supported_destinations` nhưng payload của nhánh này **chưa** mang trường đó (bản có gửi `supported_destinations` cho `clarify` đã bỏ khỏi thay đổi này).

## Kiểm tra

- Mô phỏng 6 lượt liên tiếp với `gpt-4o-mini` thật (mỗi lượt đưa câu trả lời trước vào lịch sử), payload hiện tại (không có `supported_destinations`): lượt 1–3 vẫn cùng một dạng câu và lượt 2, 3 giống hệt nhau; model tự nghĩ ví dụ (Đà Nẵng, Nha Trang, Phú Quốc) thay vì hỏi loại chuyến đi. "đến đâu cũng được" thì ra "Mình gợi ý Đà Nẵng nhé". Nghĩa là riêng prompt mới giảm lặp, chưa hết lặp.
- Chưa chạy bộ test đầy đủ cho thay đổi prompt cuối này.

## Còn lại / rủi ro

- Muốn hết lặp thì cần đưa danh sách điểm đến vào payload (`conversation_input`) hoặc leo thang sang form gợi ý (cần đề xuất `docs/prd/update/`).
- Prompt đang tham chiếu `supported_destinations` là trường chưa có trong payload; luật "danh sách rỗng thì hỏi loại chuyến đi" không được model tuân thủ.
