# Gắn link tại chỗ cho sản phẩm LLM nhắc bằng chữ thường

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Người dùng thấy câu trả lời Phú Quốc "bị cắt nửa chừng" (FR-AGT-03). Trace `01a0f62e-8c4c-76b3-bc11-3b9d2844d2cb`
(project `nhat-10-1`, 06:37 UTC): giao diện hiện đủ toàn bộ câu LLM trả, không có gì bị cắt. Hai nguyên nhân:

1. Backend vẫn là tiến trình uvicorn chạy từ 11:54 (không có `--reload`). Các thay đổi `planning.py` (13:18), `prompts.py`
   (13:20) và `narration.py` (13:36) chưa có hiệu lực, nên LLM dùng prompt bản đầu: không ghi giá, không có mục
   "Chi phí dự kiến"/"Lưu ý", và gói 3 ngày vẫn nằm trong slot.
2. LLM nhắc "Cầu Hôn Phú Quốc" bằng chữ thường, không có link. Backend dồn sản phẩm đó xuống mục "Ngoài ra trong lịch
   trình" ở cuối, trông như câu trả lời bị cắt dở.

## File thay đổi

- `src/backend/app/agents/steps/narration.py` — sửa: `_link_plain_mention` gắn link vào lần đầu tên sản phẩm (gốc hoặc đã bỏ ngoặc) xuất hiện ngoài các link có sẵn; chỉ khi không thấy tên mới thêm vào mục "Ngoài ra".
- `src/backend/tests/unit/agents/test_narration.py` — sửa: thêm test theo đúng câu trong trace.
- `history/2026-10-01-gan-link-ten-san-pham-nhac-bang-chu.md` — thêm: entry này.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents`: 289 passed.
- Chưa chạy lại trên giao diện: cần khởi động lại backend.

## Còn lại / rủi ro

- Khởi động lại backend rồi chạy lại hội thoại; trace `narrate` phải có giá từng mục, mục chi phí và mục gói nhiều ngày.
- Chưa commit.
