# Dọn code hàng thẻ phương án khách sạn (/simplify)

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, contract (chỉ mô tả), docs

## Mục tiêu

Người dùng yêu cầu sao lưu rồi chạy `/simplify` trên toàn bộ thay đổi chưa commit của tính năng hàng thẻ phương án khách sạn.
Bản sao lưu: nhánh `backup/feat-agent-hang-the-2026-10-08` (commit `6be8f86e`, không gồm `Makefile`,
`checkoutView.test.tsx`, `history/2026-10-07-unit-checkout-cho-doan-mac-dinh.md`). Bốn hướng review: tái sử dụng, đơn
giản hoá, hiệu năng, đúng tầng. Không đổi hành vi.

## File thay đổi

- `src/backend/app/agents/steps/narration.py` — xoá `_options_block` và hai chỗ gọi, cờ `options_shown_separately` (luôn
  None từ khi có `stayOptions`); `_link` → `product_link` công khai.
- `src/backend/app/agents/steps/prompts.py` — xoá câu về `options_shown_separately`.
- `src/backend/app/agents/steps/messages.py` — xoá khoá `section_options` (vi/en).
- `src/backend/tests/unit/agents/test_narration.py` — xoá `StayOptionsTests` (chỉ chạy đường đã xoá).
- `src/backend/app/agents/steps/composition.py` — `with_options_warning` bỏ bộ lọc `STAY_OPTIONS` không bao giờ khớp.
- `src/backend/app/agents/steps/option_swap.py` — `_change_message` dùng `product_link` (trước đó ghép link tay, tên có
  `[ ]` làm hỏng link); thêm `archived`/`restored`; sửa tên nút trong docstring.
- `src/backend/app/agents/nodes.py` — `_silent_option_turn(state, issues)` tính một lần; một nhánh ghi archive thay hai
  khối try/except chép nhau; archive ghi `option_swap.archived(...)`, restore qua `option_swap.restored(...)`.
- `src/backend/app/application/ports/conversation_archive.py`,
  `src/backend/app/infrastructure/persistence/postgres_conversation_archive.py` — `restore` trả kèm `lastResponse`
  (response của cùng dòng).
- `src/backend/tests/unit/agents/test_option_swap.py` — thêm `ArchivedWorkingStateTests` (2 test).
- `src/shared/contracts/schemas/itinerary-agent.yaml`, `src/frontend/src/types/api.gen.ts` — mô tả `selectStayOption`
  theo nút "Đổi sang khách sạn này" (chỉ chữ mô tả, không đổi schema).
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — dùng `itineraryStays` thay 3 bản chép nhánh `stay` cũ;
  `stayOptionCards(response, currentPlan)` dùng lại lịch đã chuyển.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — `stayPreview` chỉ giữ `{messageId, key}`; trả một
  giá trị `previewedStay`; helper `showStayPlan` thay phần chép giữa xem trước và đổi; selector giữ hàng thẻ theo
  `data-stay-row` thay nhãn aria; truyền `plan` vào `stayOptionCards`.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — `previewKey` từ `previewedStay`.
- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — `data-stay-row`; giá/đêm dùng `priceString`.
- `docs/spec/agent/nghiep-vu/xep-lich.md` — bỏ `options_shown_separately`, ghi "Phương án khác" là hàng thẻ.

## Quyết định

- **Archive không lưu lặp lịch:** mỗi dòng trả lời trước đây lưu khoảng 8 bản lịch (4 trong `response`, 4 trong
  `workingState`). `previous_plan.itinerary`/`searchResults` và `previous_options[i].itinerary` giống hệt các trường
  trong `response` cùng dòng, nên chỉ bỏ khi `response` có chúng (lượt hỏi lại sau lịch vẫn giữ đủ) và dựng lại lúc
  restore. Thiếu thì `chosen_option` trả None, lượt chọn đi luồng thường.
- **Bỏ qua, không đổi trong lần này:**
  - Gộp hai cây DOM của `FloatingWidget` (thu gọn/mở rộng) thành một `WidgetChat` không dựng lại: gốc của
    `keepInViewRef` và `orderRef`, nhưng là refactor riêng (~100 dòng, cả focus và animation).
  - Sắp thẻ theo `distanceKm` thay `orderRef`: đổi hành vi (thẻ đang chọn không còn đứng đầu, trái AC-AGT-04).
  - Server bỏ dòng khách sạn ở mục "Nơi nghỉ" thay cho client cắt chữ: cần sửa prompt/narrate và đường dự phòng cho
    hội thoại cũ.
  - Lỗi `selectStayOption` (phương án không còn) trả lỗi có kiểu thay vì đi luồng thường: đã chốt đi luồng thường.
  - Dùng `HScroller` cho hàng thẻ: nút của nó nằm lệch ra ngoài hàng (`lg:-left-5`), dễ bị cắt trong khung chat; đã
    kiểm giao diện hiện tại trên trình duyệt.
  - Bỏ `distanceKm` khỏi thẻ phương án: nhỏ, giữ để kiểu thẻ đồng nhất.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests`: 1897 passed, 35 skipped (sau mọi thay đổi; xoá 3 test
  `StayOptionsTests`, thêm 2 test archive).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (119 schemas).
- `cd src/frontend && node_modules/.bin/vitest run`: 72 files, 731 tests passed; `tsc --noEmit`: sạch.
- Trình duyệt thật (Playwright, frontend :3000 dev, backend :8000 đang chạy): chạm thẻ xem trước + dải + khoá thanh toán,
  bấm "Đổi" → "Đang chọn: Hotel Sunny Saigon", thứ tự giữ, vị trí chat giữ (649 → 649), vẫn 2 tin nhắn. Backend :8000 là
  tiến trình của người dùng, không chắc đã nạp code mới; phần archive chỉ kiểm bằng unit test.

## Còn lại / rủi ro

- Refactor một `WidgetChat` cho cả hai kiểu hiển thị (xem Quyết định).
