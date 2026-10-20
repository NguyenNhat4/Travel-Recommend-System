# Orc v2: bớt gọi tool lặp, Think nêu lý do gọi tiếp, tiến trình ghi "xem thêm"

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, frontend

## Mục tiêu

Người dùng thấy "Tìm điểm tham quan ở TP. Hồ Chí Minh" hiện 3 lần trong một lượt mà không rõ vì sao. Trace LangSmith
(`nhat-10-7`, trace `01a13590-1315-7a02-bc6b-9edae3a59a41`): vòng 1 lấy trang đầu (20/50 điểm, 20/129 khách sạn), vòng 2
lấy trang 2 (offset 20), vòng 3 không có request nguồn (trùng tham số, lấy cache); orc chỉ chọn 3 thẻ. Lời giải thích chỉ
nói "xem tiếp…", không nói vì sao chưa đủ. Phục vụ AC-AGT-09, FR-AGT-02; không lệch PRD.

## File thay đổi

- `src/backend/app/agents/orc_v2.py` — sửa `PROMPT`: đủ ứng viên thì respond ngay bằng thẻ chọn từ kết quả đó, chỉ lấy
  trang tiếp/tìm lại khi thiếu đúng thứ khách cần; explanation khi gọi tiếp phải nói kết quả đang có thiếu gì, giọng ghi
  chú công việc, không mở kiểu trò chuyện.
- `src/frontend/src/features/itinerary/widget/widgetProgressView.ts` — sửa: lần thứ hai trở đi cùng việc/loại/nơi trong
  lượt hiện "Xem thêm …" thay vì lặp "Tìm …".
- `src/frontend/tests/unit/widgetV2.test.ts` — thêm test nhãn "xem thêm".

## Quyết định

- Sửa bằng prompt (cách orc quyết định gọi tiếp) và nhãn hiển thị; không chặn gọi lặp bằng code (PRD cho phép trả cache
  khi trùng fingerprint, orc tự chủ quyết định gọi).

## Kiểm tra

- `vitest run tests/unit/widgetV2.test.ts`: 9 passed; `tsc --noEmit`: sạch. `pytest test_orc_loop.py
  test_orc_contracts.py`: 22 passed.
- LLM thật, backend local `inprocess` cổng 8001, `assistant_v2_cases`:
  - Lần 1 (`alias-saigon`, `explore-story` ×3): 6/6 một vòng tool (10–16 giây, trước ~23 giây) nhưng 1 lượt respond không
    thẻ, nói "cần tra thêm" → chỉnh câu luật thành "chọn thẻ từ chính các kết quả đó".
  - Lần 2 (`alias-saigon`, `alias-short` ×4): 8/8 có thẻ; 6/8 một vòng tool (9–12 giây); 1 lượt đọc detail 3 sản phẩm,
    1 lượt thêm một trang catalog.

## Còn lại / rủi ro

- Lời giải thích không được lưu trong output của `assistant_v2_cases` nên chưa đo giọng văn mới; cần xem trên giao diện.
- Vòng gọi trùng tham số (cache) vẫn hiện như một dòng việc; muốn ẩn cần thêm cờ vào `ActivityData` (đổi contract).
