# Hỏi gộp số ngày cùng ngày đi, số người, ngân sách, nơi đi trong một câu (kịch bản bản 5 cảnh 7)

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent
- Mã FR/NFR: FR-AGT-01, AC-AGT-01 ("hỏi gộp một câu, một lần, những gì còn thiếu")
- Liên quan: việc còn lại ở `history/2026-10-10-golden-kich-ban-ban-5.md` (SC-MAIN lượt 8)

## Mục tiêu

"Hà Nội có gì chơi?" → "Ok, lên lịch Hà Nội luôn" chỉ hỏi "Bạn muốn đi Hà Nội mấy ngày?" (2/2 lần trên backend local, golden
SC-MAIN lượt 8 fail); ngày đi, số người, ngân sách để lượt sau mới hỏi. Kịch bản cảnh 7 và AC-AGT-01: hỏi gộp một câu.

## File thay đổi

- `src/backend/app/agents/steps/classification.py` — sửa: `_extract_update` lần hỏi đầu mà chỉ thiếu số ngày (đã có điểm
  đến, chưa hỏi chi tiết, không phải chip sửa tay) thì `missing_fields` = số ngày + ngày đi, số người, ngân sách, nơi đi còn
  thiếu, đánh dấu `start_date_asked`; lượt sau còn thiếu ngày đi/số người thì ra form như cũ.
- `src/backend/app/agents/steps/conversation.py` — sửa: `_days_and_details`; tiêu đề và câu dự phòng cho câu hỏi gộp.
- `src/backend/app/agents/steps/messages.py` — sửa: `title_days_and_details`, `missing_days_and_details` (vi, en).
- `src/backend/tests/unit/agents/test_ask_days_with_details.py` — thêm: 4 test (2 test fail trên code cũ).
- `history/2026-10-10-hoi-gop-so-ngay-va-chi-tiet.md` — thêm: entry này.

## Quyết định

- Thiếu cả điểm đến thì vẫn hỏi điểm đến và số ngày trước như cũ: chưa biết nơi thì chưa hỏi ngày đi, số người.
- Không đổi PRD: AC-AGT-01 đã ghi hỏi gộp một câu, một lần.

## Kiểm tra

- `pytest src/backend/tests` (bỏ `AUTH_REDIS_URL`, `ITINERARY_LLM_REASONING_EFFORT` của container, xem
  `history/2026-10-10-lich-tham-khao-ngoai-cua-so-mo-ban.md`): 2745 passed, 36 skipped.
- Backend local, LLM thật: "Ok, lên lịch Hà Nội luôn" 3/3 lần hỏi gộp số ngày, ngày khởi hành, số người, ngân sách, nơi đi;
  "3 ngày, 2 vợ chồng với 1 bé, chưa biết ngày" → form kèm nút "Thứ 7 này", "Thứ 7 tuần sau" (cảnh 8).
- Golden `agent_scenarios_v5.yaml --only SC-MAIN`: PASS 9/9 (trước: 8/9, lượt 8 fail).

## Còn lại / rủi ro

- Câu do LLM viết đôi khi nói ngày đi, số người "có thể bỏ qua" dù đây là trường bắt buộc (lượt sau sẽ ra form); lời dặn
  trong `CONVERSATION_PROMPT` có từ trước, chưa sửa.
