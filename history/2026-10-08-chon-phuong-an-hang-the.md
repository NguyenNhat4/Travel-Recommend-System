# Chọn phương án khách sạn bằng hàng thẻ, đổi lịch tức thì (AC-AGT-04)

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, contract, docs

## Mục tiêu

Áp dụng đề xuất đã chốt `docs/prd/update-archive/2026-10-08-chon-phuong-an-bang-nut.md` (chốt bởi Nguyễn Minh Nhật,
2026-10-08): mục "Phương án khác" thành hàng thẻ khách sạn lướt ngang trong câu trả lời; bấm thẻ thì cột phải hiện lịch
của phương án đó kèm bản đồ; "Dùng phương án này" đổi lịch đúng như đã báo, không tìm lại, không gọi LLM. Trước đây nhắn
"lấy phương án 1" chạy lại extract → tool plan → search → compose → narrate (~15 s) và lịch có thể khác số đã báo.

## File thay đổi

- `docs/prd/requirements.md` — sửa: AC-AGT-04 theo nội dung đã chốt (hàng thẻ, xem trước, chọn không tìm lại, < 3 s).
- `docs/prd/update/2026-10-08-chon-phuong-an-bang-nut.md` → `docs/prd/update-archive/…` — đổi tên (git mv), trạng thái
  `đã áp dụng`, kèm phần tinh chỉnh hàng thẻ và xem trước ở cột phải.
- `src/shared/contracts/schemas/itinerary-agent.yaml`, `src/shared/contracts/openapi.yaml` — sửa: contract 1.20.0,
  `ItineraryStayOption`, `ItineraryStayOptions`, `ItineraryCompleted.stayOptions`, `ItineraryRequest.selectStayOption`.
- `src/frontend/src/types/api.gen.ts` — sinh lại (`npm run generate:api-types`).
- `src/backend/app/main.py`, `src/backend/tests/contract/test_search_contract.py` — sửa: version 1.20.0.
- `src/backend/app/domain/itinerary/routing.py` — sửa: `Option.route` (lịch đã giải của phương án).
- `src/backend/app/domain/itinerary/planning.py` — sửa: tách `_layout`/`_proposed_stays`; mỗi option có `proposal` đầy đủ.
- `src/backend/app/domain/itinerary/types.py` — sửa: `ProposedOption.proposal`.
- `src/backend/app/agents/steps/composition.py` — sửa: `_planned` (lịch + cảnh báo dùng chung cho lịch chính và từng phương
  án), `with_options_warning`, `stay_options_payload`, `options_text` (công khai, nhận km); option lỗi luật thì bỏ + log.
- `src/backend/app/agents/steps/option_swap.py` — thêm: `chosen_option`, `rebased`, `stored_products`, `swapped`.
- `src/backend/app/agents/nodes.py` — sửa: `apply_option_node`; `intake` nhận `select_stay_option` (không message thì query
  "lấy phương án N"), khôi phục `previous_plan`; `finalize` lưu `previous_plan` (itinerary của response cuối, có tiêu đề).
- `src/backend/app/agents/routing.py`, `src/backend/app/agents/graph.py` — sửa: `route_after_intake`, node `apply_option`.
- `src/backend/app/agents/state.py` — sửa: `select_stay_option`, `current_plan`, `previous_plan`.
- `src/backend/app/agents/steps/narration.py` — sửa: bỏ mục chữ "Phương án khác" khi có `stayOptions`; công khai
  `link`, `cost_line`.
- `src/backend/app/agents/steps/validation.py` — sửa: `finalize` kiểm lịch từng phương án (`option_grounding`).
- `src/backend/app/agents/steps/messages.py` — sửa: câu `swap_*`, `options_pick` mới (vi/en).
- `src/backend/app/api/v1/schemas/itinerary.py`, `src/backend/app/application/itinerary/use_cases.py`,
  `src/backend/app/api/v1/routes/assistant.py` — sửa: nhận `selectStayOption`, đưa vào graph, tên trace "chọn phương án N".
- `src/backend/tests/unit/agents/test_option_swap.py` — thêm: 8 test (compose lưu lịch từng phương án, chọn/quay lại,
  câu nhắn, phương án không còn, finalize bắt option sai grounding, `rebased`).
- `src/backend/tests/unit/agents/test_lab_copy.py`, `test_composition_plan_criteria.py` — sửa: 13 node, câu hướng dẫn mới.
- `src/frontend/src/services/assistantStream.ts`, `src/frontend/src/context/AssistantProvider.tsx` — sửa:
  `selectStayOption`, `submitStayOption`.
- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — thêm: hàng thẻ lướt ngang (scroll-snap, mũi tên
  trên máy tính), chip chênh tiền/km, nhãn vượt ngân sách, nút "Dùng phương án này".
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts`, `widgetTypes.ts`, `useFloatingWidget.ts`, `WidgetChat.tsx`,
  `WidgetPlanPanel.tsx` — sửa: `stayOptionCards`, xem trước ở cột phải + bản đồ, dải "Đang xem phương án N", khoá thanh
  toán khi đang xem trước.
- `src/frontend/tests/unit/widgetStayOptions.test.tsx` — thêm: 4 test.
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx` — sửa: prop `after` chèn hàng thẻ ngay sau thẻ khách sạn
  (mục "Nơi nghỉ") thay vì cuối bong bóng, theo yêu cầu người dùng; neo theo productId vì tiêu đề mục do LLM viết.
- `src/frontend/tests/unit/widgetNarration.test.tsx` — thêm: 2 test vị trí hàng thẻ.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/hop-dong-tich-hop-frontend.md`,
  `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md`,
  `docs/spec/agent/nghiep-vu/sua-lich-qua-nhieu-luot.md` — sửa: hành vi và field mới.

## Quyết định

- **Lời đáp của lượt chọn do code dựng, không gọi LLM.** Mục tiêu < 3 s; `narrate` đầy đủ mất 7,4 s và tự chèn lại mọi sản
  phẩm (lưới grounding), nên không còn là "nêu ngắn phần thay đổi". Câu gồm khách sạn mới (link), chênh tiền, chênh km,
  tổng km, chi phí.
- **Lịch từng phương án dựng lúc `compose`** bằng đúng `render_proposal` + `with_flights` + `validate_plan` của lịch chính;
  lượt chọn chỉ lấy ra. Nguồn grounding của lượt chọn là sản phẩm trong các lịch đã lưu phía server (không từ client).
- **Chênh km tính lại từ km tuyệt đối** (`distanceKm` lưu cho từng lịch), chênh tiền tuyến tính, vượt ngân sách từ
  `estimatedTotal`: quay lại ra đúng số ban đầu (đã thử thật).
- Giữ luật 2 km và tối đa 3 phương án (người dùng không yêu cầu nới). Lịch vừa bỏ luôn được giữ để quay lại.
- `constraints.specific_hotel` = khách sạn đã chọn, như hành vi "lấy phương án N" trước đây, để lượt sau giữ khách sạn.
- Warning `STAY_OPTIONS` vẫn giữ (client cũ); `message` bỏ mục chữ khi có `stayOptions`.
- Không tìm thấy lịch đã lưu (hội thoại cũ, số không tồn tại) thì đi luồng thường như câu "lấy phương án N".

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (119 schemas).
- `.venv/bin/python -m pytest -q src/backend/tests`: 1897 passed, 35 skipped.
- `cd src/frontend && node_modules/.bin/vitest run`: 72 files, 723 tests passed; `node_modules/.bin/tsc --noEmit`: sạch.
- Backend thật cổng 8001 (inprocess, LLM thật, LangSmith `nhat-10-7`), hội thoại `71edf39a-9217-4df7-8098-688e24c75e86`:
  - lượt lập lịch 17,5 s: Hoang Long Son 2, 33,1 km, 23.001.910 ₫; `stayOptions` 1 phương án (Hotel Sunny Saigon,
    +9,2 km, −377.910 ₫); `message` không còn mục chữ "Phương án khác";
  - `selectStayOption {index 1}`: < 0,1 s (trace "chọn phương án 1" 10 ms, không token LLM), lịch Hotel Sunny Saigon
    22.624.000 ₫, 42,3 km; thẻ quay lại Hoang Long Son 2 (−9,2 km, +377.910 ₫);
  - chọn lại thẻ đó: về đúng Hoang Long Son 2, 33,1 km, 23.001.910 ₫;
  - đường SSE `/stream`: 3 node (intake, apply_option, finalize) rồi `run.completed`.
- Chưa thử giao diện trên trình duyệt (chỉ vitest + tsc).

## Còn lại / rủi ro

- Chưa xem hàng thẻ và dải xem trước trên trình duyệt thật (desktop/mobile).
- Response `COMPLETED` nặng hơn (tối đa 3 lịch phụ); hội thoại lưu thêm các lịch đó.
- Chưa có mock `completed` mẫu có `stayOptions` trong `src/shared/mocks/itinerary-agent/`.
- Chưa thêm golden case cho lượt chọn phương án.
- Đề xuất `docs/prd/update/2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md` vẫn chờ chốt.
