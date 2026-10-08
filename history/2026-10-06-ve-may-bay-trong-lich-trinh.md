# Vé máy bay trong lịch trình của trợ lý, hỏi nơi đi và gợi ý nơi đi từ vị trí trình duyệt

- Ngày: 2026-10-06
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, contract, frontend, docs
- Thay thế: history/2026-10-06-de-xuat-ve-may-bay-trong-lich-trinh.md

## Mục tiêu

Áp dụng đề xuất `docs/prd/update-archive/2026-10-06-ve-may-bay-trong-lich-trinh-va-vi-tri.md`, do Nguyễn Minh Nhật chốt
ngày 2026-10-06. Mã liên quan: FR-AGT-01/02/03, AC-AGT-01 (sửa), AC-AGT-02 và AC-AGT-03 (mới). Lịch trình có chặng bay
đi/về chọn bằng luật từ chuyến bay thật của catalog. Nơi đi được hỏi cùng câu hỏi gộp và có ô riêng trong form. Web gợi ý
nơi đi từ vị trí trình duyệt, chỉ khi người dùng bấm.

## File thay đổi

**PRD (áp dụng trước khi sửa source)**
- `docs/prd/requirements.md` — sửa FR-AGT-01/02/03, AC-AGT-01; thêm AC-AGT-02, AC-AGT-03.
- `docs/prd/architecture.md` — sửa §3: sơ đồ (Nơi đi; tìm "phòng, tour và chuyến bay"), thêm chuẩn grounding cho vé và vị trí.
- `docs/prd/user-flow.md` — sửa §4.2: ô nơi đi của form gợi ý, thẻ chặng bay trong khung chat.
- `docs/prd/update/2026-10-06-ve-may-bay-trong-lich-trinh-va-vi-tri.md` → `docs/prd/update-archive/` — đổi tên, trạng thái `đã áp dụng`.

**Contract** (1.17.0 → 1.18.0, chỉ thêm, tương thích v1)
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa:
  - `TripIntent.origin` (tuỳ chọn), `TripIntentPatch.origin`;
  - `origin` trong enum `missingFields` và `clarificationForm.fields`;
  - thêm `FlightDirection`, `ItineraryFlight`, `ItineraryPlan.flights`.
- `src/shared/contracts/openapi.yaml` — sửa: version 1.18.0, đăng ký hai schema mới.

**Backend**
- `src/backend/app/domain/itinerary/flights.py` — thêm luật thuần: `skip_reason`, `choose_flights`, `flight_candidates`, `flight_cost`.
- `src/backend/app/application/itinerary/flights.py` — thêm `flight_options`: tra tuyến và chuyến qua `CatalogPort.list_products`, chuẩn hoá nơi đi theo catalog.
- `src/backend/app/application/ports/itinerary_tools.py` — sửa: `list_products` trên `CatalogPort`, `ToolExecutorPort`.
- `src/backend/app/agents/tools/itinerary_gateway.py` — sửa: `list_products` (kiểm tham số, validate `ProductListResponse`; planner không thấy).
- `src/backend/app/application/itinerary/engine_tools.py` — sửa: adapter inprocess `list_products`.
- `src/backend/app/infrastructure/clients/itinerary_http_clients.py`, `itinerary_fixture_clients.py` — sửa: `list_products`.
- `src/backend/app/main.py` — sửa: nối provider `list_products` cho tool inprocess; `version` 1.18.0 theo contract.
- `src/backend/app/agents/nodes.py`, `agents/state.py` — sửa: `tool_node` tra vé song song với lời gọi của planner, ghi `flight_options` và nơi đi chuẩn; `intake` reset.
- `src/backend/app/agents/steps/composition.py` — sửa: `with_flights` gắn vé, tính lại tổng, thêm warning `FLIGHT_*`.
- `src/backend/app/agents/steps/validation.py`, `domain/itinerary/planning.py` — sửa: grounding vé, `totals` cộng vé, `summary` giữ khoá thẻ vé.
- `src/backend/app/agents/steps/narration.py`, `prompts.py` — sửa: mục **Vé máy bay** do hệ thống viết; NARRATE không nói về vé; EXTRACT trích `origin`/`require_flight`/loại trừ vé.
- `src/backend/app/agents/models.py`, `steps/classification.py`, `steps/conversation.py`, `steps/turn_notes.py`, `steps/messages.py`, `domain/itinerary/types.py` — sửa: `origin` là chi tiết chuyến đi hỏi gộp và ô form; câu chữ vi/en.

**Frontend**
- `src/frontend/src/types/api.gen.ts` — sinh lại bằng `npm run generate:api-types`.
- `src/frontend/src/services/flights.ts` — sửa: thêm `listDepartureAirports`, `nearestDepartureCity`.
- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — sửa: ô nơi đi, nút "Dùng vị trí hiện tại", câu yêu cầu có "đi từ X".
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts`, `WidgetDays.tsx`, `src/frontend/src/types/travel.ts`,
  `src/frontend/src/components/assistant/AssistantResultPanel.tsx` — sửa: `flights` trong plan, thẻ chặng bay, thẻ trong
  chat, "Đặt ngay" và "Thanh toán tất cả" có vé, focus.

**Test**
- `src/backend/tests/unit/domain/test_itinerary_flights.py` — thêm.
- `src/backend/tests/unit/application/test_itinerary_flights_lookup.py` — thêm.
- `src/backend/tests/unit/application/test_itinerary_engine_tools.py` — sửa: thêm test adapter `list_products`.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: thêm `FlightTests` end-to-end; kỳ vọng câu hỏi gộp có `origin`.
- `src/backend/tests/unit/agents/test_classify.py`, `test_turn_context.py` — sửa: kỳ vọng có `origin`.
- `src/backend/tests/contract/test_assistant_contract.py` — sửa: fixture đủ chi tiết có thêm `origin`.
- `src/backend/tests/contract/test_search_contract.py` — sửa: phiên bản contract 1.18.0.
- `src/frontend/tests/unit/itineraryFlights.test.ts` — thêm.
- `src/frontend/tests/unit/tripDetailsForm.test.tsx`, `widgetDays.test.tsx` — sửa: thêm test nơi đi, vị trí, thẻ chặng bay.

**Spec**
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: thêm §2.7.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa §4.8: hai dòng nơi đi/vị trí và vé.
- `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md` — sửa: `flight_options`, `origin`.

## Quyết định

- **Tra vé tất định, không qua LLM planner.** Nơi đi, điểm đến và ngày đã đủ để tra. Skill agent: quyết định kiểm được
  bằng luật thì làm bằng luật.
- **Vé không vào `tool_results`/`candidates`.** Chặng về đến nơi đi và bay ngày cuối, nên luật điểm đến/ngày của `collect`
  sẽ loại nhầm; đưa vào cũng làm lệch `drop_summary` và FALLBACK. Vé có nguồn grounding riêng (`flight_candidates`).
- **Lấy chuyến qua GET /products** (tuyến theo điểm đến, chuyến theo `parentProductId`), giống trang `/flights`.
  `/search` inprocess không nhận `origin`.
- **`origin` là trường tuỳ chọn trong contract và không có trong `empty_intent`.** Response chỉ có `origin` khi biết, để
  không phá client và mock cũ (TripIntent liệt kê mọi trường khác là bắt buộc).
- **Nơi đi được hỏi một lần trong câu hỏi gộp, giống ngân sách** (AC-AGT-01 đã chốt). Hệ quả: câu đầu đủ ngày đi, số
  người, ngân sách mà thiếu nơi đi thì trợ lý hỏi thêm một lượt. 13 test cũ được cập nhật theo hành vi này.
- **Mục Vé máy bay do hệ thống viết**, cả bản LLM lẫn bản dựng bằng luật, để giá × số khách và lý do thiếu vé luôn đúng
  dữ liệu. LLM được dặn không nói về vé.
- **Web tìm thành phố có sân bay gần nhất** từ `originLatitude`/`originLongitude` của tuyến trong catalog, không dùng bảng
  tĩnh. Toạ độ chỉ sống trong callback; test kiểm không request nào mang toạ độ.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` → PASS
  (111 schema, 87 fixture; CDP clone 12 schema).
- `pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/architecture` → 1067 passed
  trước khi thêm test vé. Test mới: domain 10 passed, application 5 + 1 passed, `FlightTests` 3 passed.
- `pytest -q src/backend/tests` (toàn bộ backend) → 1738 passed, 32 skipped, 4 failed. Cả 4 là test contract: fixture
  thiếu `origin` (3) và phiên bản app 1.17.0 (1). Đã sửa; chạy lại `pytest src/backend/tests/contract` → 86 passed.
- Frontend: `vitest run` → 64 file, 627 passed; `tsc --noEmit` sạch; `eslint` trên các file sửa sạch.
- LLM thật, backend local inprocess (3.183 sản phẩm, `gpt-6-luna`), gọi `POST /api/v1/assistant/itineraries`:
  - **Câu có nơi đi:** "Lên lịch trình 3 ngày ở Đà Nẵng từ ngày 8/10/2026, 2 người lớn, ngân sách 10 triệu, đi từ Hà Nội"
    → `COMPLETED`.
    - Chặng đi VJ505 08/10 19:50 (432.000 ₫) và chặng về VJ518 10/10 19:45 (628.000 ₫), 2 khách.
    - `estimatedTotal` 4.060.000 ₫, `WITHIN_BUDGET`; lời diễn giải có mục **Vé máy bay**.
  - **Câu không có nơi đi:** hỏi `missingFields: ['origin']`. Trả lời "không cần, cứ lên lịch đi" → `COMPLETED` kèm
    `FLIGHT_NO_ORIGIN` và câu mời cho biết nơi đi.

## Còn lại / rủi ro

- **Hoạt động có thể xếp trước giờ đến.** Trong lượt LLM thật ở trên, chặng đi cất cánh 19:50 ngày 1 nhưng Bà Nà xếp
  sáng ngày 1. Luật đã chốt xếp giá trước giờ bay, và `compose` chưa biết giờ đến/giờ về. Muốn sửa (bỏ slot trước giờ
  đến, hoặc ưu tiên giờ trước giá) là đổi AC-AGT-02, cần đề xuất mới.
- Câu hỏi gộp do LLM viết có lúc nói như nơi đi là bắt buộc ("Mình cần biết nơi đi để lên lịch"). Bản cố định ghi rõ
  "để mình thêm vé máy bay". Có thể bổ sung `CONVERSATION_PROMPT` sau.
- Mock `src/shared/mocks/itinerary-agent/completed.json` chưa có ví dụ `flights`: bộ 50 sản phẩm mẫu không có chuyến bay.
- Chưa thêm golden case "Hà Nội → Đà Nẵng 3 ngày" vào `agent_test_cases_nhat.yaml`.
- Chưa chạy e2e Playwright cho nút vị trí; trình duyệt thật cần HTTPS hoặc localhost mới cho geolocation.
