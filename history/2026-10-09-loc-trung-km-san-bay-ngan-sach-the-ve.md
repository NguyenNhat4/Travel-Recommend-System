# Lọc trùng giữ vé có phí, km tính cả sân bay, bản đồ cả chuyến, "Ngân sách dự tính" và thẻ vé trong chat

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs, contract, agent, frontend
- Thay thế: 2026-10-09-de-xuat-diem-mien-phi-rieng-km-san-bay.md

## Mục tiêu

Áp dụng đề xuất ngày 09/10 sau khi người dùng chốt trong phiên, và thêm hai yêu cầu mới của người dùng:
1. Điểm tham quan tự do **không** tách khỏi lịch. Chúng vẫn tính 0 đ, nên không thành "chưa rõ giá" và không làm mất phương
   án khách sạn. Khi lọc trùng, cặp giữa điểm tự do và vé có phí thì giữ vé ("Cáp Treo Hòn Thơm" thay "hòn Thơm").
2. Km tính cả chặng sân bay; mọi số km có "≈" kèm một dòng lưu ý.
3. Bấm thẻ khách sạn để xem trước thì bản đồ xem cả chuyến: có sân bay, chỉ khách sạn của phương án đó, vẽ đường dần.
4. Khối "Ngân sách dự tính" chia tổng tiền theo Vé máy bay, Lưu trú, Vui chơi (không có Ăn uống).
5. Thẻ vé máy bay trong câu trả lời theo mẫu người dùng gửi.

## File thay đổi

- `docs/prd/update/2026-10-09-diem-mien-phi-rieng-km-san-bay-ban-do.md` → đổi tên và chuyển thành
  `docs/prd/update-archive/2026-10-09-loc-trung-giu-ve-km-san-bay-ban-do.md` — sửa: viết lại theo phạm vi đã chốt, trạng
  thái "đã áp dụng". File gốc chưa từng commit nên không dùng `git mv`.
- `docs/prd/update-archive/2026-10-09-ngan-sach-du-tinh.md` — thêm: đề xuất "Ngân sách dự tính", đã chốt và áp dụng.
- `docs/prd/requirements.md` — sửa: AC-AGT-04 (thứ tự giữ khi lọc trùng, chặng sân bay, "≈" và dòng lưu ý, bản đồ cả chuyến).
- `docs/prd/user-flow.md` — sửa: §4.2 thêm khối "Ngân sách dự tính".
- `docs/spec/agent/nghiep-vu/xep-lich.md`, `docs/spec/agent/nghiep-vu/glossary.md` — sửa: lọc trùng, quãng đường có sân
  bay, "≈", `costBreakdown`.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: km và bản đồ của `stayOptions`, `costBreakdown`, thẻ vé trong chat.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: `costBreakdown` (1.21.0).
- `src/shared/contracts/openapi.yaml`, `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: 1.21.0, thêm
  `ItineraryCostBreakdown` và `ItineraryPlan.costBreakdown` (tuỳ chọn, thêm vào nên tương thích ngược).
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại bằng `npm run generate:api-types`.
- `src/backend/app/main.py`, `src/backend/tests/contract/test_search_contract.py` — sửa: phiên bản 1.21.0.
- `src/backend/app/domain/itinerary/planning.py` — sửa:
  - `keep_rank` đặt vé có phí trước điểm tự do;
  - thêm `cost_breakdown` và `price_plan`; `validate_plan` kiểm cả phần chia;
  - `compose_plan` nhận `airports`;
  - tóm tắt sản phẩm giữ thêm `originLatitude`/`originLongitude`.
- `src/backend/app/domain/itinerary/routing.py` — sửa: thêm `day_ends`; `route_cost` và `optimize` nhận `airports`.
- `src/backend/app/domain/itinerary/flights.py` — sửa: thêm `airports(legs)`.
- `src/backend/app/domain/itinerary/geo.py` — sửa: thêm `point_at` (toạ độ ở hai khoá bất kỳ).
- `src/backend/app/domain/itinerary/types.py` — sửa: `Plan.costBreakdown`.
- `src/backend/app/agents/steps/composition.py` — sửa: truyền sân bay; dùng `price_plan`.
- `src/backend/app/agents/steps/messages.py` — sửa: "khoảng"/"about" trước số km thành "≈".
- `src/backend/tests/unit/domain/test_itinerary_dedupe.py`, `test_itinerary_routing.py`, `test_itinerary_flights.py`,
  `src/backend/tests/unit/agents/test_composition_plan_criteria.py` — sửa/thêm test.
- `src/frontend/src/services/routeGeometry.ts` — sửa: thêm `getAirportPoints`; chặng sân bay trong `buildRouteRequests`.
- `src/frontend/src/components/assistant/ItineraryMap.tsx` — sửa: ghim sân bay, prop `overview`, vẽ đường dần theo thứ
  tự đi.
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — sửa: `overview` khi đang xem trước.
- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — sửa: "≈" và dòng lưu ý.
- `src/frontend/src/features/itinerary/widget/WidgetBudget.tsx` — thêm: khối "Ngân sách dự tính".
- `src/frontend/src/features/itinerary/widget/WidgetFlightCard.tsx`, `widgetFlight.ts` — thêm: thẻ vé trong chat.
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx`, `WidgetChat.tsx`, `useFloatingWidget.ts`,
  `widgetPlan.ts`, `widgetTypes.ts` — sửa: dùng thẻ vé, khối ngân sách, `bookPlanItem`, `budgetSummary`.
- `src/frontend/tests/routeGeometry.test.ts`, `src/frontend/tests/unit/widgetStayOptions.test.tsx` — sửa/thêm test.
- `src/frontend/tests/unit/widgetBudgetAndFlight.test.tsx` — thêm test.

## Quyết định

- **Điểm tự do giữ nguyên trong lịch.** Phần "tách điểm tự do ra mục riêng" và nguồn Catalog `GET /products` bị bỏ khỏi đề
  xuất, nên `architecture.md` §3 không đổi và contract không có `freeAttractions`. Đề xuất ngày 08/10
  (`docs/prd/update/2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md`) vẫn chờ chốt riêng, không bị ảnh hưởng.
- **Lọc trùng:** người dùng chọn "ưu tiên có vé nếu trùng". Tiêu chí vé có phí đứng **trước** cả nguồn Search/Recommendation
  (cặp trùng là cùng một nơi, nên nguồn không còn quan trọng bằng việc có sản phẩm đặt được).
- **Chặng sân bay:**
  - Ngày 1 = sân bay → khách sạn (một số km cố định), rồi khách sạn → các điểm → khách sạn. Không có khách sạn thì đi
    thẳng từ sân bay.
  - Ngày cuối kết thúc ở sân bay đi.
  - Chuyến 1 ngày vẫn kết thúc ở khách sạn, như luật 1 đêm cũ.
  - Toạ độ sân bay lấy theo khoá catalog: chặng đi lấy `latitude`/`longitude`, chặng về lấy
    `originLatitude`/`originLongitude` (snapshot 2026-09-30 có toạ độ, `locationPrecision: airport`). Catalog tổng hợp
    local không có toạ độ, nên dev local chạy nhánh dự phòng (tính như cũ).
- **Dòng lưu ý km:** chỉ có vế "gồm cả đường sân bay" khi lịch có sân bay. Đây là điều chỉnh của review, đã ghi vào PRD.
- **Bản đồ:**
  - giữ quyết định cũ là không vẽ đường thẳng khi OSRM không trả tuyến;
  - xem trước thì chuyển sang "Tất cả", thôi xem trước thì về ngày đang chọn;
  - đoạn sau chờ đoạn trước để vẽ đúng thứ tự đi.
- **"Ngân sách dự tính":**
  - backend tính `costBreakdown` cùng chỗ với tổng (`price_plan`), client không cộng tiền;
  - đặt ở cuối bong bóng câu trả lời, như hình mẫu (mặc định, vì người dùng chưa chọn chỗ đặt).
- **Thẻ vé:**
  - PRD đã có thẻ chặng bay (user-flow §4.2), nên phần này không cần đề xuất.
  - Nhãn "Đã chọn cho lịch" thay cho "Lựa chọn tốt nhất", vì vé được chọn bằng luật, không qua đánh giá.
  - Không hiện hạng vé, hành lý, logo hãng: catalog không có các dữ liệu này.
  - Thời gian bay tính từ `departureAt`/`arrivalAt`.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests -p no:cacheprovider`: 1925 passed, 35 skipped.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (120 schemas, 94 fixtures).
- `cd src/frontend && node_modules/.bin/vitest run`: 73 files, 744 tests passed. `node_modules/.bin/tsc --noEmit -p .`: OK.
- `eslint` trên các file frontend đã sửa: 5 lỗi `react-hooks/refs` ở `WidgetStayOptions.tsx` dòng 51–53 và 3 cảnh báo đều
  có từ trước. Đã so với bản trước thay đổi (cũng 8 vấn đề), không có vấn đề mới.
- Test mới fail trên code cũ: hai test lọc trùng (giữ vé). Test sân bay và `cost_breakdown` dùng hàm mới nên không chạy
  được trên code cũ. Test "khách sạn gần sân bay chỉ thắng khi có vé" kiểm cả hai chiều.
- Tầng bằng chứng: unit/fixture tất định. **Chưa chạy** agent với LLM thật (hội thoại Phú Quốc trong trace
  `01a11e8e-1f8a-7d70-b7fc-3f9b42e7d370`), chưa chạy backend với Postgres có snapshot thật, chưa xem trên trình duyệt.

## Còn lại / rủi ro

- Cần xem trên trình duyệt:
  - hiệu ứng vẽ dần và ghim sân bay của `ItineraryMap` (không có unit test vì Leaflet chạy trong jsdom kém);
  - thẻ vé và khối ngân sách trên màn hẹp.
- Vẽ mọi ngày qua OSRM công cộng (1 yêu cầu/giây): chuyến 3 ngày có sân bay khoảng 7–9 đoạn nên mất vài giây mới vẽ xong.
  Các đoạn đã có trong bộ nhớ đệm thì hiện ngay.
- Chạy lại hội thoại Phú Quốc với LLM thật và dữ liệu snapshot, để xem khách sạn được chọn có đổi do chặng sân bay không.
- Golden case cho lọc trùng giữ vé chưa thêm.
- Lỗi lint `react-hooks/refs` có sẵn ở `WidgetStayOptions` chưa sửa (ngoài phạm vi).
