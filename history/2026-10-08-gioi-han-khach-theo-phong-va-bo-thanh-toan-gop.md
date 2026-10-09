# Giới hạn khách khách sạn theo phòng; trợ lý bỏ "Thanh toán tất cả"

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: backend | frontend | contract | docs | db

## Mục tiêu

Yêu cầu: 9 khách là đúng cho 1 phòng, đặt 2 phòng thì tối đa phải là 18 (ảnh chụp thanh "Số lượng" ở trang chi tiết khách sạn ghi "Tối đa 9 khách mỗi lần đặt"). Luật 9 khách nằm trong PRD (FR-BKG-08) nên đi qua đề xuất `docs/prd/update-archive/2026-10-08-gioi-han-khach-theo-phong.md`, mihhquan chốt 2026-10-08. Mã yêu cầu: FR-BKG-01, FR-BKG-08.

Quyết định đã chốt trong đề xuất:
- Khách sạn: 9 khách mỗi phòng, 9 phòng mỗi mục (cao nhất 81 khách), vẫn không vượt `maxOccupancy` (cắt ở 9).
- Vé máy bay, vé tham quan, golf, combo: giữ 9 khách mỗi mục.
- Trần đoàn ở checkout bằng trần của mục lớn nhất trong đơn; đơn có mục không phải khách sạn thì 9.
- Trợ lý: bỏ nút "Thanh toán tất cả", mỗi mục thanh toán riêng (trước mắt).

## File thay đổi

PRD và đề xuất:
- `docs/prd/requirements.md` — sửa: FR-BKG-01 (bỏ đơn nháp từ "Thanh toán tất cả"), FR-BKG-08 (trần theo loại dịch vụ).
- `docs/prd/user-flow.md` — sửa: §1.2 bước 4, §3.2 (lưu đồ), §4.2 (wireframe, chú thích nút đặt).
- `docs/prd/update-archive/2026-10-08-gioi-han-khach-theo-phong.md` — thêm: đề xuất, trạng thái đã áp dụng (chưa được git theo dõi nên dùng `mv`, không `git mv`).

Contract (không đổi version 1.19.0, xem Quyết định):
- `src/shared/contracts/schemas/booking.yaml` — sửa: `GuestCounts` (`adults` ≤ 81, `children` ≤ 80, mô tả), `AddCartItemRequest`.
- `src/shared/contracts/paths/booking.yaml` — sửa: mô tả `POST /cart/items`.
- `src/shared/contracts/schemas/common.yaml` — sửa: thêm reason `ROOMS_TOO_MANY` vào `ValidationFieldError`.
- `src/shared/contracts/tests/validate_contract.py` — sửa: ca âm của `GuestCounts` theo trần mới.
- `src/shared/contracts/tests/booking-rules-cases.json` — sửa: thêm 7 ca cart và 5 ca checkout dùng chung hai phía.
- `src/frontend/src/types/api.gen.ts` — sửa: tái sinh bằng `openapi-typescript`.

DDL (cả ba nơi, `AGENTS.md` §6):
- `db/migrations/0009_booking_draft_party_per_room.sql` — thêm: `booking_draft_items_party_size` ≤ 81, `booking_travelers_position_range` 1–81; idempotent.
- `db/init/01_vota.sql`, `db/vota_schema.sql` — sửa: hai ràng buộc trên (hai file giữ byte-identical).
- `docs/spec/DATABASE_SCHEMA.md` — sửa: DDL và ERD của `booking_draft_items`.
- `db/verify.sql` — sửa: dòng kiểm đơn nháp từ ≤ 9 thành ≤ 81. `app.cart_items` giữ ≤ 9 (giỏ không nhận khách sạn).

Backend:
- `src/backend/app/domain/booking/party.py` — sửa: `MAX_ROOMS`, `room_capacity`, `item_party_cap`, `order_party_cap`.
- `src/backend/app/domain/booking/party_rules.py` — sửa: `check_cart_guests` (trần theo phòng, `ROOMS_TOO_MANY`), `check_party(max_party=)`, `_check_hotel` (9 khách mỗi phòng kể cả khi không công bố sức chứa), `check_checkout` (trần của đơn, khách sạn trên 9 khách không gộp với dịch vụ khác).
- `src/backend/app/application/booking/messages.py` — sửa: câu thông báo `PARTY_TOO_LARGE` theo ngữ cảnh và `ROOMS_TOO_MANY`.
- Test: `tests/unit/domain/booking/test_party_rules.py` (harness tính trần từ giỏ), `tests/unit/application/booking/test_checkout_travelers.py` (câu thông báo, reason mới), `tests/integration/test_booking_postgres.py` (đoàn 18 người, ràng buộc `position`).

Frontend:
- `src/frontend/src/components/checkout/checkoutRules.ts` — sửa: `MAX_ROOMS`, `roomCapacity`, `itemPartyCap`, `orderPartyCap`, `checkParty(maxParty)`, `checkHotel`, `checkCheckout` (đơn trộn), `messageFor`.
- `src/frontend/src/components/checkout/guestCounts.ts` — sửa: bộ đếm khách sạn theo trần của số phòng, bớt phòng bị chặn khi không đủ chỗ, `partyCartRequest` chia đoàn khách sạn theo 9 khách mỗi phòng.
- `src/frontend/src/components/checkout/allocation.ts`, `useCheckout.ts`, `TravelersStep.tsx`, `ServicesStep.tsx` — sửa: trần đoàn theo đơn (`partyCap`), tối đa 9 phòng, dòng "Tối đa N khách mỗi đơn".
- `src/frontend/src/features/search/tripContext.ts` — sửa: `MAX_ROOMS`, `maxGuestsFor`, `parseTripContext` theo số phòng.
- `src/frontend/src/features/catalog/landing/GuestsPopover.tsx` — sửa: trần theo phòng, phòng không bớt được khi đoàn không vừa, chú thích "Tối đa 9 khách mỗi phòng, 9 phòng mỗi lần đặt."
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx`, `useFloatingWidget.ts`, `src/frontend/src/components/assistant/AssistantResultPanel.tsx`, `src/frontend/src/hooks/useAssistantCart.ts` — sửa: bỏ nút và hàm "Thanh toán tất cả"; `useBookItinerary` nhận một mục.
- Test: `tests/unit/{guestCounts,tripContext,checkoutRules,useAssistantCart,assistantResultPanel}.test.*` — sửa; `tests/unit/guestsPopover.test.tsx` — thêm; `tests/e2e/widget-opening.spec.ts` — sửa (nút không còn).

Tài liệu:
- `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md`, `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md`, `docs/spec/hop-dong-tich-hop-backend.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/hop-dong-tich-hop-cdp.md`, `docs/spec/product.md`, `docs/guide/doc-code-ui-tro-ly.md` — sửa theo luật mới.

## Quyết định

- Không tăng version contract: chỉ nới `maximum` của `GuestCounts` và thêm một `reason` mới (client gặp reason lạ thì hiển thị `message`, theo contract), không đổi hình dạng dữ liệu. Nếu muốn ghi nhận bằng minor version thì phải sửa `main.py`, `test_search_contract.py` và `api.gen.ts`.
- Reason mới `ROOMS_TOO_MANY` cho trường hợp quá 9 phòng, thay vì dùng lại `PARTY_TOO_LARGE` với câu chữ sai nghĩa.
- Hạng phòng không công bố sức chứa nay bị chặn ở 9 khách mỗi phòng (trước đây bỏ qua luật này, D7), để "9 khách mỗi phòng" đúng với cả phòng không có `maxOccupancy`.
- Khách sạn trên 9 khách trong đơn có dịch vụ khác bị từ chối ở checkout (`PARTY_TOO_LARGE`, trường `itemDetails`). Với UI không xảy ra (trợ lý không còn gộp), nhưng gọi thẳng API vẫn tạo được đơn nháp trộn và không có luật này thì đoàn khai chỉ ≤ 9 trong khi khách sạn 18.
- Không đụng `POST /search`: `travelContext.rooms` vẫn bị bỏ qua và `guests` lọc theo tổng khách so với sức chứa một phòng.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS (115 schemas, 93 fixture, ca âm mới).
- `.venv/bin/python -m pytest -q src/backend/tests --ignore=src/backend/tests/integration`: pass.
- `RUN_POSTGRES_INTEGRATION=1 .venv/bin/python -m pytest -q src/backend/tests/integration/test_booking_postgres.py`: 10 passed (gồm test mới).
- `make db-migrate` áp `0009` lên Postgres local; chạy lại file migration lần hai không lỗi (idempotent). `make verify-db`: dòng `booking draft party size 1..81` và `cart party size 1..9` PASS; hai dòng FAIL là lệch dữ liệu local có trước (`profiles = 2000` ra 2002, `max events per user <= 15` ra 214), không liên quan thay đổi này.
- Frontend (từ `src/frontend`): `node_modules/.bin/tsc --noEmit` sạch; `eslint .` 0 lỗi (2 cảnh báo cũ ở `ItineraryMap.tsx`); `vitest run tests/unit`: pass, gồm các ca dùng chung hai phía (khách sạn 2 phòng 18 người hợp lệ, 1 phòng 10 người bị chặn, 10 phòng bị chặn).
- Trình duyệt thật (`localhost:3000`, trang chi tiết một khách sạn): 1 phòng khoá nút `+` ở 9 khách; thêm phòng thứ 2 mở tới 18 (15 người lớn + 3 trẻ em), nút `Phòng −` khoá vì 18 khách không vừa 1 phòng; ảnh chụp đã xem.

## Còn lại / rủi ro

- Backend đang chạy ở `:8000` (Docker) là bản cũ nên chưa kiểm đầu-cuối đặt phòng 18 khách trên trình duyệt; luật được kiểm bằng ca dùng chung, unit và integration. Cần dựng lại container backend trước khi demo.
- Tìm kiếm khách sạn với nhiều phòng/đoàn đông (ví dụ 2 phòng 18 khách) có thể không ra kết quả: `POST /search` đối chiếu tổng khách với sức chứa một phòng và bỏ qua `rooms`. Lệch này có từ trước (ví dụ 2 phòng 6 khách có thể loại nhầm hạng phòng sức chứa 3); muốn sửa thì chia khách theo số phòng ở `routes/search.py` qua đề xuất riêng.
- Chưa chạy Playwright e2e đầy đủ; chỉ sửa kỳ vọng ở `widget-opening.spec.ts`.
