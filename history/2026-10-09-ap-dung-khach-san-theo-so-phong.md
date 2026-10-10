# Áp dụng: khách sạn cho đoàn đông lọc theo một phòng, tính tiền theo số phòng

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, contract, frontend, docs

## Mục tiêu

Áp dụng đề xuất đã chốt `docs/prd/update-archive/2026-10-09-khach-san-theo-so-phong-cho-doan-dong.md` (đề xuất tạo ở
`history/2026-10-09-de-xuat-khach-san-theo-so-phong.md`). Lỗi gốc: đoàn 10 người lớn chỉ có một khách sạn vì search gửi
`travelContext.guests = {adults: 10}` (contract hiểu là sức chứa một phòng) nên `total: 0`; tiền khách sạn tính như một
phòng cho cả đoàn.

## File thay đổi

- `docs/prd/requirements.md` — FR-AGT-01 thêm luật lọc theo số khách một phòng; AC-AGT-04 thêm tiền × số phòng, trần
  9 phòng, cảnh báo khi thiếu `priceAdults`, hiển thị số phòng; dòng chốt trỏ đề xuất.
- `docs/prd/update/2026-10-09-khach-san-theo-so-phong-cho-doan-dong.md` → `docs/prd/update-archive/` — trạng thái
  `đã áp dụng`, ghi người chốt; câu hiển thị số phòng chỉnh thành "khi từ 2 phòng trở lên" cho khớp PRD. File chưa từng
  được commit nên chuyển bằng `mv`.
- `src/shared/contracts/schemas/itinerary-agent.yaml` — `ItineraryStay.rooms` (1–9, additive); mô tả `stays` và
  `costBreakdown.stays` gồm × rooms.
- `src/shared/contracts/openapi.yaml`, `src/backend/app/main.py`, `src/backend/tests/contract/test_search_contract.py`,
  `src/backend/tests/contract/test_search_llm_contract.py` — version 1.22.0 → 1.23.0.
- `src/frontend/src/types/api.gen.ts` — sinh lại bằng `npm run generate:api-types`.
- `src/backend/app/domain/itinerary/planning.py` — `stay_rooms`, `rooms_of`, `room_guests` (dùng `booking.party.MAX_ROOMS`);
  `_known_cost` nhận `rooms`; `cost_breakdown`, `money` của routing nhân số phòng; `compose_plan` bỏ khách sạn cần quá
  9 phòng; `render_proposal` ghi `rooms` và bác khách sạn quá 9 phòng; `validate_plan` tính lại `rooms` từ candidate.
- `src/backend/app/agents/steps/tool_planning.py` — `travelContext.guests` của search khách sạn = `room_guests(party)`.
- `src/backend/app/agents/steps/composition.py` — cảnh báo `STAY_ROOMS_UNKNOWN` (kèm `productId`) khi khách sạn thiếu
  `priceAdults`.
- `src/backend/app/agents/steps/narration.py`, `messages.py` — giá khách sạn (placeholder `[[price:id]]` và bản fallback)
  ghi "× N phòng" khi từ 2 phòng; LLM không viết số phòng.
- `src/frontend/src/types/travel.ts`, `features/itinerary/widget/widgetPlan.ts`, `WidgetDays.tsx`,
  `WidgetStayOptions.tsx` — `rooms` trong stay của widget, hậu tố "× N phòng" sau giá một đêm ở thẻ khách sạn và thẻ
  phương án.
- Test: `src/backend/tests/unit/domain/test_itinerary_composition.py` (`StayRoomsTests`),
  `src/backend/tests/unit/agents/test_composition_stay_rooms.py` (mới), `test_itinerary_tools.py` (sửa kỳ vọng guests
  của gia đình 2+1 thành 1+0, thêm đoàn 10 và 9+9), `test_narration.py` (`StayRoomsTests`),
  `src/frontend/tests/unit/widgetDays.test.tsx`, `widgetStayOptions.test.tsx`.
- Spec: `docs/spec/agent/nghiep-vu/tim-ung-vien.md` (guests một phòng; sửa luôn "các loại khác 10" thành 50 còn sót từ
  `history/2026-10-09-search-limit-50-du-hoat-dong-buoi-chieu.md`), `docs/spec/agent/nghiep-vu/xep-lich.md` (bảng tiền,
  luật số phòng, bỏ điểm ⚠️ số phòng), `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (đoạn 1.23.0, guests).

Các file khác trong `git status` (`filtering.py`, `dedupe.py`, `test_filter_node.py`, `test_itinerary_dedupe.py` và phần
sửa trước đó trong `xep-lich.md`) thuộc task khác đang dở trong cây làm việc, không thuộc entry này.

## Quyết định

- Người dùng trả "đã chốt" không chọn lại hai điểm mở, nên giữ đúng nội dung chính: lọc `ceil(tổng/9)` cho mọi đoàn
  (gia đình 2+2 gửi 1, không còn lọc phòng 4 chỗ), trẻ em không tính phòng.
- Số phòng ghi vào `stays[].rooms` lúc render (từ bản đầy đủ của candidate) vì `summary` không giữ `priceAdults`;
  `validate_plan` tính lại để plan không tự khai số phòng.
- Thứ tự khách sạn ở nhánh không có toạ độ (`_stay_order`) vẫn theo giá một đêm; catalog hiện mọi `priceAdults` = 2 nên
  thứ tự theo giá phòng và theo tổng đoàn trùng nhau. Nhánh khoảng cách so tiền đã nhân phòng.
- Giỏ hàng từ lịch trình không đổi: vẫn gửi `party`, khách xếp người vào phòng ở checkout (FR-BKG-08).

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain` → 1811 passed (trước khi
  thêm test narration/composition); test domain và tool viết trước, fail ở import/kỳ vọng guests rồi mới sửa code. Test
  narration và composition viết sau code (đã pass ngay), chưa chứng minh fail trên code cũ.
- `.venv/bin/python -m pytest -q src/backend/tests` → 2606 passed, 2 failed, 36 skipped: hai test ghim version contract
  1.22.0; đã nâng lên 1.23.0, chạy lại `src/backend/tests/contract` → 113 passed. Sau khi xong narration/composition:
  `pytest src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/architecture` → 1824 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` → PASS (120 schemas, 94 fixtures).
- Frontend: `vitest run` cả bộ → 813 passed, 3 failed (`confirmationView`, `flightResultsView`, `productDetailView`, mỗi
  test 6–8 s); chạy riêng ba file → 57/57 passed, nên là timeout khi chạy cả bộ, không liên quan. Hai test widget mới fail
  trước khi sửa component, pass sau. `tsc --noEmit` sạch.
- Tầng bằng chứng: fixture/tất định. Chưa chạy lại lượt thật 10 người lớn với search và LLM thật.

## Việc còn lại

- Chạy lại một lượt "Phú Quốc 7 ngày, 10 người lớn" và xem trace: search khách sạn có `guests = {adults: 2}` và
  `total > 0`, lịch có nhiều phương án khách sạn, giá ghi "× 5 phòng".
- `_stay_order` chưa xét số phòng nếu sau này catalog có `priceAdults` khác 2.
