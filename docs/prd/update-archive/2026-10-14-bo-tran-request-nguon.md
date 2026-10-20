# Orc v2: bỏ trần số request nguồn mỗi lượt

- Ngày: 2026-10-14
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-14 (trong chat: "set ko giới hạn"; thay mức 25 vừa đề xuất trước đó,
  mức 25 chưa commit)
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (Ngân sách thực thi; function calling), `docs/prd/requirements.md` AC-AGT-06
- Mã FR/NFR: FR-AGT-02, AC-AGT-02, AC-AGT-06

## Lý do

Đo chuỗi "Lập lịch Đà Nẵng 4 ngày từ 16/10, 2 người lớn" → "lịch trình tiết kiệm thôi" → "thêm vé máy bay đi từ hcm"
×3 trên model thật (backend local): lượt thêm vé 0/3 có vé. Cả ba lần đã dùng 10/10 request nguồn: get_products tra lại
8–9 điểm của lịch (mỗi điểm một request, bắt buộc theo grounding), tra vé còn 0–2 request trong khi một chiều cần tới
năm request, nên `lookup_flights` trả `TOOL_LIMIT` hoặc `partial` không có chuyến. Mức 10 chép từ orchestrator cũ làm
baseline để đo, không tính cho việc tra lại lịch kèm vé.

## Nội dung đề xuất

`architecture.md` §3, Ngân sách thực thi:

- Hiện tại: "… 10 request nguồn vật lý, …"
- Thay bằng: "… không trần số request nguồn (chặn bằng deadline lượt), …"

`architecture.md` §3, function calling:

- Hiện tại: "call vượt trần request nguồn trả TOOL_LIMIT, không thực thi."
- Thay bằng: "request nguồn sau deadline trả TIME_LIMIT, không thực thi."

`requirements.md` AC-AGT-06: "10 request nguồn" → "không trần request nguồn".

Deadline lượt, timeout model, 4 lượt tool và 6 lần gọi model giữ nguyên; đây là giới hạn còn lại của một lượt.

## Thay đổi source sau khi chốt

- `src/backend/app/application/itinerary/orc_dispatch.py`: `SourceBudget(limit=None)` mặc định không trần, vẫn kiểm deadline.
- `src/backend/app/agents/orc_v2.py`: docstring, `PROMPT`; `remaining` bỏ `source_requests`, `flight_max_source_requests`.
- `src/backend/tests/unit/agents/test_orc_loop.py`: `remaining` không còn `source_requests`.
- `docs/spec/agent/working-context.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.

## Ảnh hưởng

- Lượt có vé đọc đủ các trang chuyến bay nên có thể chậm hơn; deadline lượt vẫn chặn.
- Model gọi lan man không còn bị chặn bằng số request, chỉ bằng số lượt, số lần model và deadline.
- Không đổi contract HTTP/SSE.
