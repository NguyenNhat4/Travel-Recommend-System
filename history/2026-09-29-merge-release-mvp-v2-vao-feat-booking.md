# Giải conflict merge release-mvp-v2 vào feat/booking

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: contract, frontend, backend, docs

## Mục tiêu

Người yêu cầu: "Xử lý conflict". `git merge origin/release-mvp-v2` (đến PR #47) vào `feat/booking` dừng với 5 file xung đột.
Cần gộp checkout nhiều bước / đoàn khách (FR-BKG-08, FR-BKG-13) của nhánh này với phần mới của upstream (vé khứ hồi và
`fareClasses`, form gợi ý thông tin chuyến đi, widget trợ lý tách module) mà không mất thay đổi của bên nào.

## File thay đổi

Năm file conflict:

- `docs/prd/requirements.md` — sửa: FR-CAT-03 giữ cả dòng `attributes.fareClasses` của nhánh này lẫn dòng vé khứ hồi/hạng vé biến thể của upstream (xem Còn lại).
- `src/shared/contracts/openapi.yaml` — sửa: `info.version` = **1.10.0** (nhánh này 1.8.0, upstream 1.9.0).
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: lấy bản upstream (một dòng re-export sang `features/itinerary/widget/FloatingWidget`); nhánh này chỉ đổi đúng một dòng ở file này, đã chuyển sang `widgetPlan.ts`.
- `src/frontend/src/components/cart/CartView.tsx` — sửa: giữ bố cục của nhánh này (`FareLines`, `GuestEditor`, nút Sửa), thêm `FlightSummary` của upstream dưới tên sản phẩm.
- `src/frontend/src/components/checkout/CheckoutView.tsx` — sửa: giữ bản của nhánh này (điều phối ba bước); bản upstream sửa vào file cũ 480 dòng đã bị thay bằng các file `TravelersStep`, `ServicesStep`, `ReviewStep`, `OrderSummary`.

Sửa thêm để gộp khớp nhau:

- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — sửa: `itineraryCartItems(response.itinerary, response.intent?.party)`, giữ việc truyền đoàn khách từ trợ lý vào giỏ mà nhánh này đã làm ở widget cũ.
- `src/frontend/src/components/checkout/OrderSummary.tsx` — sửa: hiển thị `FlightSummary` (hai chặng, hạng vé) trong tóm tắt đơn, tương ứng chỗ upstream chèn ở `CheckoutView` cũ.
- `src/frontend/src/components/checkout/ReviewStep.tsx` — sửa: hiển thị `FlightSummary` ở bước xem lại trước khi thanh toán.
- `src/backend/app/main.py` — sửa: `version="1.10.0"` (git đã tự gộp thành 1.9.0), khớp `openapi.yaml`.
- `src/backend/tests/unit/application/booking/test_flight_booking.py` — sửa: test của upstream truyền danh sách `itemDetails` rỗng; luật của nhánh này không còn chấp nhận nên đổi sang `await w.details()`, cùng helper các test booking khác dùng. Ý đồ test (hạng vé giữ riêng qua giỏ, thanh toán, purchase) không đổi.
- Nhãn "contract 1.8.0" của thay đổi checkout nhiều bước đổi thành 1.10.0 trong: `src/shared/contracts/schemas/booking.yaml` (2 dòng), `src/shared/contracts/tests/validate_contract.py`, `src/backend/tests/contract/test_booking_contract.py`, `docs/spec/hop-dong-tich-hop-backend.md` (§ dòng thành tiền), `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` (4 chỗ), `docs/plan/2026-09-29-checkout-nhieu-buoc-hanh-khach.md` (2 chỗ). Không đụng `docs/prd/update-archive/` và các nhắc "1.8.0" của phía agent/strategy.
- `history/2026-09-29-merge-release-mvp-v2-vao-feat-booking.md` — thêm: entry này.

Tự gộp không xung đột (không sửa tay): toàn bộ phần còn lại của upstream, gồm `paths/catalog.yaml`, `schemas/catalog.yaml`, `schemas/itinerary-agent.yaml`, `src/frontend/src/types/api.gen.ts`.

## Quyết định

- **Version 1.10.0.** Cả hai số đã bị dùng cho hai thay đổi khác nhau: 1.8.0 là checkout nhiều bước ở nhánh này, 1.8.0 và 1.9.0 ở upstream là agent/strategy và `fareClasses`. Cây đã gộp chứa cả ba nên phải cao hơn 1.9.0; theo `docs/prd/api-contract.md` là tăng minor vì mọi thay đổi đều tương thích ngược. Cùng cách xử lý entry `2026-09-28-recsys-strategy-enum-va-cdp-fallback.md` khi trùng 1.7.0.
- **Widget lấy bản upstream, chuyển sửa đổi của mình sang.** Upstream đã tách 1.370 dòng thành `features/itinerary/widget/`; giữ bản cũ sẽ chặn refactor đó, còn thay đổi của nhánh này ở file là một dòng nên chuyển được nguyên vẹn.
- **`CheckoutView` giữ bản của nhánh này** vì bản upstream sửa vào mã đã bị thay; chỉ mang sang thay đổi có nghĩa (`FlightSummary`).
- **`requirements.md` gộp cả hai dòng, không tự chọn mô hình hạng vé** (`AGENTS.md` §8: lệch/mâu thuẫn PRD do người dùng chốt).

## Kiểm tra

Trên cây đã gộp, chưa commit:

- `validate_contract.py`: PASS (97 schema, 50 grounded products, 70 fixture, CDP clone 12 schema).
- `openapi-typescript` sinh lại từ contract đã gộp: trùng `src/frontend/src/types/api.gen.ts`.
- `tsc --noEmit`: ok. `eslint .`: 0 lỗi, 4 cảnh báo `react-hooks/exhaustive-deps` có từ trước (ItineraryMap, ShareItineraryModal, HomeView).
- Frontend `vitest run`: 32 file, **295 passed**.
- Backend `pytest backend/tests/unit backend/tests/contract backend/tests/architecture`: lần đầu 832 passed, 1 failed (`test_roundtrip_cabins_remain_distinct_through_cart_payment_and_purchase`, nguyên nhân ở mục File thay đổi); sau khi sửa test, chạy lại toàn bộ: **833 passed**.
- **Chưa chạy:** `backend/tests/integration` (cần Postgres; Docker không chạy trên máy này), Playwright e2e, `next build`, `db/verify.sql`. Upstream không đổi `db/`, migration `0005_checkout_travelers.sql` không trùng số.

## Còn lại / rủi ro

- **Mâu thuẫn chưa giải quyết ở PRD về hạng vé máy bay** (cần người dùng chốt, đi qua `docs/prd/update/`): nhánh này đã chốt mô hình một sản phẩm có nhiều hạng trong `attributes.fareClasses` (FR-CAT-03, FR-BKG-10, AC-BKG-09, `data-model.md` §3.1, đề xuất `update-archive/2026-09-29-ve-may-bay-hang-ve-va-khu-hoi.md`); upstream chốt mỗi hạng là một biến thể đặt được riêng, `fareClasses` chỉ là trường dẫn xuất của API (`ProductSummary.fareClasses`, `docs/guide/hien-thi-hang-ve-may-bay.md`). Hai dòng trong FR-CAT-03 hiện cùng có mặt và nói ngược nhau; `data-model.md` §3.1 và FR-BKG-10 vẫn theo mô hình `attributes.fareClasses`. Code hiện chỉ theo mô hình upstream (mọi test pass).
- FR-BKG-10 (chọn hạng theo chặng, gộp khứ hồi) chưa có code phía Web/Backend, và không có code nào đọc `attributes.fareClasses` (đã grep `src/` và `db/`); nên hai mô hình chưa va chạm ở tầng mã, chỉ ở PRD.
- `docs/spec/data-collection/bao-cao-schema.md`, `docs/spec/hop-dong-tich-hop-backend.md` §387 và các tài liệu agent vẫn ghi "OpenAPI 1.8.0" cho phần agent/strategy: đúng lịch sử, không đổi.
- Merge chưa được commit; entry này cùng các file trên nằm trong cùng commit merge.
