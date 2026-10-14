# In đậm số tiền trong câu trả lời trợ lý v2

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent
- Mã FR/NFR: AC-AGT-07 (trình bày câu trả lời), PRD `user-flow.md` §4.2

## Mục tiêu

Chat 14/10: giá tiền và số quan trọng trong câu trả lời (ví dụ "Chi phí dự kiến … là 15.000.000 ₫") cần in đậm để
khách thấy ngay.

## File thay đổi

- `src/backend/app/application/itinerary/v2_final.py` — sửa: `_fact_text` bọc số tiền (field `_vnd`/`Price`) trong
  `**…**`; `_warning_text(bold=True)` in đậm số tiền của câu cảnh báo nằm trong `message`, `warnings[].message` giữ chữ
  thường; `_HEADING` bỏ qua đậm mở đầu bằng chữ số để số tiền ngay sau link sản phẩm không bị tách thành tiêu đề.
- `src/backend/tests/unit/application/test_assistant_v2_final.py` — sửa hai test so chuỗi theo số tiền in đậm, thêm
  kiểm cảnh báo vượt ngân sách và `test_price_right_after_a_product_link_stays_inline_not_a_heading`.
- `history/2026-10-14-in-dam-so-tien-trong-cau-tra-loi.md` — thêm: entry này.

## Quyết định

- In đậm ở code, chỗ điền dữ kiện: số tiền chỉ đến từ đoạn `fact` (LLM không được viết số), nên đậm luôn đúng và
  không phụ thuộc prompt. Widget đã hiển thị `**…**` giữa dòng (`AssistantText`).
- Chỉ in đậm số tiền; giờ, ngày, điểm và số đánh giá giữ chữ thường để câu không rối.
- Không lệch PRD: PRD không quy định kiểu chữ của số tiền.

## Kiểm tra

- `test_assistant_v2_final.py` trên code cũ: 3 failed; sau sửa 15 passed.
- `.venv/bin/python -m pytest -q src/backend/tests/unit src/backend/tests/contract src/backend/tests/architecture`:
  3098 passed, 2 skipped, 3 xfailed.
- Chưa chạy LLM thật (thay đổi tất định ở bước dựng câu trả lời); chưa chạy frontend (không đổi frontend).

## Còn lại / rủi ro

- Một đoạn chỉ có số tiền đứng riêng một dòng sẽ được widget hiển thị như tiêu đề (`NarrationText` coi dòng chỉ có
  `**…**` là tiêu đề). Chưa gặp trong câu trả lời thật.
- Backend :8000 cần khởi động lại để nhận thay đổi.
