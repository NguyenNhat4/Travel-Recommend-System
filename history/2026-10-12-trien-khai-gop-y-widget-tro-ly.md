# Triển khai góp ý widget trợ lý: form qua nút, sở thích theo catalog, thẻ khách sạn có loại, combo nổi bật

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Codex (phần lớn code), Claude Code (sửa lỗi, test, snapshot, entry này)
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, contract, docs

## Mục tiêu

Áp dụng 9 góp ý cho widget trợ lý và đề xuất đã chốt `docs/prd/update-archive/2026-10-12-form-theo-followup-va-so-thich-linh-hoat.md` (AC-AGT-01, AC-AGT-03, AC-AGT-04; FR-AGT-01/03/04/06/07, FR-SRC-03, NFR-REL-01). Session Codex làm phần chính rồi hết lượt giữa lúc chạy test; Claude Code tiếp tục sửa lỗi và hoàn tất kiểm tra.

## File thay đổi

PRD và đề xuất:
- `docs/prd/requirements.md`, `docs/prd/user-flow.md`, `docs/prd/architecture.md` — sửa: AC-AGT-01 (form qua nút, sở thích 3 nhóm, tạo bằng AI), AC-AGT-04 (4 loại thẻ khách sạn), luồng và kiến trúc gợi ý sở thích.
- `docs/prd/update-archive/2026-10-12-form-theo-followup-va-so-thich-linh-hoat.md` — thêm (chuyển từ `docs/prd/update/`): đề xuất đã áp dụng.
- `docs/prd/update/2026-10-12-dong-bo-ac-agt-06-voi-nut-mo-form.md` — thêm: đề xuất chờ chốt, đồng bộ câu chữ AC-AGT-06 với nút mở form.

Contract:
- `src/shared/contracts/openapi.yaml`, `paths/itinerary-agent.yaml`, `schemas/itinerary-agent.yaml` — sửa: `GET/POST /assistant/preferences`, `TripPreference*`, `clarificationForm.autoOpen`.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract.

Backend:
- `src/backend/app/domain/itinerary/preference_options.py` — thêm: tổng hợp sở thích có bằng chứng trong thuộc tính catalog theo điểm đến (hotel/attraction/combo, hạng phòng tách riêng).
- `src/backend/app/application/itinerary/preference_suggestions.py` — thêm: `TripPreferences` (liệt kê; LLM chọn ID, code chỉ giữ ID có trong danh sách, tối đa 3 mỗi nhóm, lỗi/quá giờ thì `unavailable`).
- `src/backend/app/application/ports/product_query.py`, `src/backend/app/infrastructure/persistence/postgres_catalog.py`, `src/backend/tests/fakes/catalog.py` — sửa: `preference_products(destination)`.
- `src/backend/app/api/v1/routes/assistant.py`, `src/backend/app/api/v1/schemas/itinerary.py`, `src/backend/app/main.py` — sửa: route và wiring `/assistant/preferences`.
- `src/backend/app/agents/steps/conversation.py` — sửa: kèm form (nút) khi thiếu điểm đến/số ngày/ngày đi/số người, `autoOpen` khi người dùng xin form; cắt `interestOptions` còn 8 theo `maxItems` của contract.
- `src/backend/app/agents/steps/classification.py`, `src/backend/app/domain/itinerary/preferences.py`, `src/backend/app/domain/itinerary/search_hints.py` — sửa: giữ nguyên sở thích chỉnh tay từ form, đưa vào Search đúng loại; thêm nhãn tiện ích catalog.
- `src/backend/app/agents/steps/prompts.py`, `src/backend/app/agents/steps/narration.py` — sửa: lời trả lời không lặp giá/tổng/mục Chi phí dự kiến; điểm tham quan tự do mô tả như địa điểm.
- `src/backend/app/domain/itinerary/routing.py` — sửa: thêm phương án khách sạn cao cấp (4–5 sao, ưu tiên điểm ≥ 4,5 và ≥ 50 lượt).
- `src/backend/app/agents/steps/tool_planning.py` — sửa: bỏ lời gọi search của loại người dùng đã loại trừ thay vì huỷ cả lượt.

Frontend:
- `src/frontend/src/components/assistant/TripPreferenceFields.tsx`, `src/frontend/src/services/tripPreferences.ts` — thêm: ô sở thích 3 nhóm, nút Tạo sở thích bằng AI.
- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — sửa: dùng ô sở thích mới; lấy vị trí có giới hạn 5 giây, gợi ý thành phố khởi hành.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: form sau nút "Điền thông tin chuyến đi".
- `src/frontend/src/features/itinerary/widget/WidgetComboCard.tsx`, `WidgetNarration.tsx` — thêm/sửa: thẻ combo nổi bật, nhãn theo dữ liệu.
- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — sửa: nhãn loại Tiết kiệm nhất / Ít di chuyển nhất / Cân bằng / Cao cấp · Được yêu thích, số tuyệt đối.
- `src/frontend/src/features/itinerary/widget/WidgetBudget.tsx`, `WidgetProductGallery.tsx`, `WidgetFareDays.tsx` — sửa: ẩn dòng 0 đồng, phóng to ảnh, vé mở tab mới.
- `src/frontend/src/features/flights/results/flightHref.ts`, `FlightCard.tsx`, `FlightResultsView.tsx` — sửa: mang `fare` id, mặc định vé rẻ nhất.

Test:
- `src/backend/tests/unit/api/test_trip_preferences.py`, `src/backend/tests/unit/application/test_trip_preference_suggestions.py` — thêm.
- `src/backend/tests/unit/agents/test_exploration.py`, `test_itinerary_runtime.py`, `test_multi_day_offers.py`, `test_narration.py`, `test_itinerary_tools.py` — sửa: theo hành vi đã chốt (nút form ngay lượt đầu, không lặp giá); thêm test bỏ search loại bị loại trừ.
- `src/backend/tests/unit/agents/behavior_snapshot/cassette.json`, `snapshot.json`, `tools.json.gz` — sửa: ghi lại 32 kịch bản bị ảnh hưởng bằng LLM thật.
- `src/frontend/tests/unit/widgetComboAndFare.test.tsx` — thêm; `flightProductHref.test.ts`, `flightResultsView.test.tsx`, `tripDetailsForm.test.tsx`, `widgetBudgetAndFlight.test.tsx`, `widgetStayOptions.test.tsx` — sửa.

## Quyết định

- `clarificationForm.interestOptions` gửi 8 nhãn đầu (contract `maxItems: 8`); trước đó gửi 26 nhãn làm `finalize` báo sai schema và trả 500 ở mọi lượt có form. Danh sách đầy đủ đi qua `/assistant/preferences`, không đổi contract.
- Lượt "ok" sau lời mời lập lịch có nút mở form (`autoOpen: false`) theo AC-AGT-01 chốt 12/10, mới hơn câu "chưa đưa form" của AC-AGT-06; đã tạo đề xuất đồng bộ câu chữ AC-AGT-06.
- Planner thỉnh thoảng search cả loại đã bị loại trừ (snapshot X01 "đổi chuyến bay" kèm search vé máy bay → 503). Bỏ lời gọi đó, giống cách đang bỏ search golf không ai nhắc, thay vì huỷ cả lượt.
- Câu xác nhận đổi khách sạn vẫn ghi tiền chênh lệch ("bớt 5.400.000 ₫"): đó là chênh lệch, không phải lặp giá trên thẻ.

## Kiểm tra

- `validate_contract.py`: PASS (123 schemas, 96 fixtures).
- Backend `pytest src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract` (WEAVIATE_URL cổng đóng, SEARCH_PREWARM=false, HF_HUB_OFFLINE=1): 2795 passed, 2 skipped. Trước khi sửa: 30 failed (500 do `interestOptions`), sau sửa contract còn 7 failed (test cũ + snapshot).
- Snapshot hành vi: ghi lại 32/57 kịch bản bằng `behavior_snapshot.record --only ...`; so cũ/mới theo status, node, form, giá trong lời: 31 lượt thêm nút form (đúng AC-AGT-01), X10#2 "Đà Lạt có gì" sang nhánh khám phá (đúng AC-AGT-06), X01#4 từ 200 thành 503 → sửa `tool_planning`, ghi lại X01, làm mới messy-M09 (dùng chung cassette). `test_behavior_snapshot.py`: 4 passed.
- Frontend: `tsc --noEmit` sạch, `npm run lint` 0 lỗi (3 cảnh báo có sẵn), `vitest run` 831/831 passed.
- Chưa kiểm tra tay trên trình duyệt.

## Còn lại / rủi ro

- Chờ chốt `docs/prd/update/2026-10-12-dong-bo-ac-agt-06-voi-nut-mo-form.md`.
- Kiểm tra trên trình duyệt: mở/thu form, Tạo sở thích bằng AI, phóng to ảnh, vé mở tab mới đúng hạng, nhãn thẻ khách sạn, thẻ combo.
- Chưa commit theo yêu cầu người dùng.
