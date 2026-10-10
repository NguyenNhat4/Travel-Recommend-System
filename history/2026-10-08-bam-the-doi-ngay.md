# Bấm thẻ khách sạn là đổi ngay, không thêm tin nhắn; hàng thẻ dưới mục "Nơi nghỉ"

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, docs
- Thay thế: một phần quyết định trong `history/2026-10-08-chon-phuong-an-hang-the.md` (xem trước + nút "Dùng phương án
  này" + lời đáp ngắn cho lượt bấm)

## Mục tiêu

Người dùng thử giao diện và yêu cầu: hàng thẻ nằm dưới chữ "Nơi nghỉ" thay vì cuối câu trả lời; bấm chọn khách sạn thì
không sinh tin nhắn mới, tổng tiền tính lại như đổi bình thường. Người dùng chốt: "Bấm thẻ là đổi luôn" và "Lưu ngầm lên
server" (đề xuất `docs/prd/update-archive/2026-10-08-bam-the-doi-ngay.md`).

## File thay đổi

- `docs/prd/requirements.md` — sửa: AC-AGT-04 theo phần chốt bổ sung.
- `docs/prd/update-archive/2026-10-08-bam-the-doi-ngay.md` — thêm: đề xuất bổ sung, `đã áp dụng`.
- `src/backend/app/agents/steps/option_swap.py` — sửa: `silent` (lượt `selectStayOption`), lượt bấm không có `message`;
  lượt gõ "lấy phương án N" giữ câu trả lời ngắn (`_change_message`).
- `src/backend/app/agents/nodes.py` — sửa: `finalize` không thêm lượt hội thoại cho lượt bấm; archive gọi
  `update_last_turn` thay vì `record_turn`.
- `src/backend/app/application/ports/conversation_archive.py`,
  `src/backend/app/infrastructure/persistence/postgres_conversation_archive.py` — sửa: `update_last_turn` (gộp `response`
  theo khoá vào câu trả lời gần nhất, thay `workingState`, cập nhật `intent`; kiểm chủ hội thoại).
- `src/backend/app/agents/steps/narration.py` — sửa: bỏ alias `link`/`cost_line` không còn dùng.
- `src/backend/app/agents/steps/messages.py` — sửa: `options_pick` mới; giữ `swap_*` cho lượt gõ.
- `src/backend/tests/unit/agents/test_option_swap.py` — sửa/thêm: lượt bấm không `message`, không thêm lượt hội thoại;
  lượt gõ có câu trả lời; archive `update_last_turn`.
- `src/backend/tests/unit/agents/test_composition_plan_criteria.py` — sửa: câu `options_pick`.
- `src/frontend/src/context/AssistantProvider.tsx`, `src/frontend/src/context/assistantState.ts` — sửa:
  `selectStayOption` gửi ngầm `POST /assistant/itineraries`; action `stay-option-applied` thay `response` của câu trả lời
  gần nhất, không thêm tin nhắn, giữ chữ.
- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — sửa: cả thẻ là nút đổi ngay, "Đang đổi…" khi đang
  lưu, khoá ở câu trả lời cũ; bỏ nút "Dùng phương án này".
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: `chooseStayOption` (đổi lạc quan, lưu ngầm,
  lỗi thì quay lại + toast); bỏ trạng thái xem trước.
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — trả về như trước (bỏ dải xem trước, bỏ khoá thanh
  toán).
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx`, `WidgetChat.tsx` — sửa: prop `after` chèn hàng thẻ
  ngay sau thẻ khách sạn (mục "Nơi nghỉ"), neo theo productId khách sạn của mọi thẻ; không có thì cuối bong bóng.
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — sửa: `narrationProducts` gồm khách sạn của các phương án
  (lời diễn giải cũ vẫn nhắc khách sạn trước khi đổi).
- `src/frontend/tests/unit/widgetStayOptions.test.tsx`, `widgetNarration.test.tsx`, `assistantState.test.ts` — sửa/thêm.
- `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`,
  `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/nghiep-vu/sua-lich-qua-nhieu-luot.md` — sửa theo hành vi mới.

## Quyết định

- Lượt bấm thẻ không thêm lượt vào `conversation_history` (ngữ cảnh LLM) và không thêm tin nhắn vào archive; lựa chọn
  vẫn đến các lượt sau qua `constraints.specific_hotel` và `previous_plan`. Archive cập nhật câu trả lời gần nhất nên mở
  lại hội thoại thấy đúng lịch đã chọn, chữ giữ nguyên.
- Lượt gõ "lấy phương án N" vẫn có câu trả lời (người dùng đã gửi tin nhắn).
- Frontend đổi lạc quan bằng lịch đã có sẵn trong `stayOptions` (không chờ server), rồi thay bằng response của server
  (hàng thẻ đánh số lại, thẻ vừa chọn thành "Đang chọn").
- Chỉ câu trả lời mới nhất đổi được khách sạn: server chỉ giữ phương án của lượt gần nhất.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests`: 1897 passed, 1 failed (câu `options_pick` cũ trong
  `test_composition_plan_criteria.py`), sửa test rồi chạy lại file đó: 8 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- `cd src/frontend && node_modules/.bin/vitest run`: 72 files, 726 tests passed; `tsc --noEmit`: sạch.
- `update_last_turn` chạy thật trên Postgres local (hội thoại tạm, xoá sau khi kiểm): 2 tin nhắn trước và sau (không thêm),
  chữ giữ nguyên, `response.itinerary`/`stayOptions` thay mới, `restore` trả working state mới, người dùng khác bị chặn.
- Backend thật cổng 8001 (LLM thật), hội thoại `1869797e-a219-4115-9203-8d6155286fd8`: lập lịch 17,2 s (Hoang Long Son 2,
  23.001.910 ₫); bấm thẻ qua `POST /assistant/itineraries` `selectStayOption {index 1}` < 0,1 s, không có `message`,
  Hotel Sunny Saigon 22.624.000 ₫; lượt sau "đổi sang 4 ngày" giữ Hotel Sunny Saigon (36.189.000 ₫).
- Chưa xem trên trình duyệt.

## Còn lại / rủi ro

- Chưa thử giao diện trên trình duyệt (desktop/mobile).
- Lời diễn giải cũ trong chat vẫn mô tả khách sạn trước khi đổi (đúng yêu cầu "không thêm tin nhắn"); hàng thẻ và cột phải
  là nơi thể hiện lựa chọn hiện tại.
