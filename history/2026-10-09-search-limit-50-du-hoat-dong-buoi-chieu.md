# Search lấy 50 kết quả để lịch dài có buổi chiều

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Lịch trình nhiều ngày chỉ có buổi sáng, gần như không có buổi chiều. Trace LangSmith (project `nhat-10-7`, 10 lượt
compose ngày 2026-10-09) cho thấy lịch 7 ngày Phú Quốc chỉ 1–3 ngày đầu có chiều, các ngày còn lại mỗi ngày một slot
MORNING. Lượt 06:39:26 ("doi sang ngay 13 thang 10"): search attraction `limit=10` trả 10 điểm, 3 là vé nhiều ngày
(`multi_day_span`) nên không xếp slot, còn 7 + 2 recommendation; compose xếp 7 hoạt động cho 7 ngày (sức chứa ~13
slot). Luật rải "ngày ít nhất thắng" (`planning.compose_plan`) cho mỗi ngày một điểm trước, và ngày có một điểm thì
`_layout` đặt vào MORNING — buổi chiều chỉ có khi số hoạt động lớn hơn số ngày. Luật cả ngày (`durationMinutes ≥ 360`)
không liên quan: không ứng viên nào dính.

## File thay đổi

- `src/backend/app/agents/steps/tool_planning.py` — `SEARCH_LIMIT` 10 → 50 (tối đa contract `search_products.limit`).
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — mục tham số search: mọi search dùng `limit=50`, kèm lý do.

## Quyết định

- Theo yêu cầu người dùng: dùng luôn tối đa contract cho mọi search thay vì tính theo số ngày.
- Không đổi luật rải ngày trong `domain/itinerary/planning.py`; thiếu buổi chiều là do thiếu ứng viên.
- Không lệch PRD: chỉ đổi số ứng viên lấy về, vẫn trong `maximum` của contract; grounding không đổi.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain` → 1802 passed
  (tầng fixture/tất định; test so với hằng `SEARCH_LIMIT` và kiểm `SEARCH_LIMIT ≤ maximum` của contract).
- Chưa chạy lại end-to-end với search thật và LLM thật để xác nhận lịch 7 ngày có buổi chiều.

## Việc còn lại

- Chạy lại một lượt 7 ngày Phú Quốc, xem compose trên LangSmith có đủ chiều không và latency `filter_node` (LLM chỉ
  cặp trùng nhận nhiều ứng viên hơn).
- Lỗi thấy trong cùng trace, chưa điều tra: tên chuyến bay lệch `departureAt` (VJ1326 tên "08:20", `departureAt`
  09:00; VJ336 tên "16:50", `departureAt` 06:20); lượt 06:11:50 có ngày 6 trống.
