# Giới hạn khách của khách sạn theo số phòng; trợ lý không còn "Thanh toán tất cả"

- Ngày: 2026-10-08
- Người đề xuất: mihhquan / Claude
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-10-08 (áp dụng vào PRD cùng ngày)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.5 FR-BKG-01 (ý "Đặt ngay") và FR-BKG-08; `docs/prd/user-flow.md` §1.2 bước 4, §3.2 (lưu đồ), §4.2 (wireframe và chú thích nút đặt)
- Mã FR/NFR: FR-BKG-01, FR-BKG-08

## Lý do

**A. Giới hạn khách.** FR-BKG-08 đặt trần 9 khách cho cả một mục. Với khách sạn, 9 chỉ hợp lý cho một phòng: khách đặt 2 phòng bị chặn ở 9 người, trong khi hai phòng phải chứa được 18 người.

**B. Trợ lý.** Nút "Thanh toán tất cả" của lịch trình gộp khách sạn, vé máy bay, tour thành một đơn nháp. Khi khách sạn được nới theo A, một đơn gộp có thể vừa có khách sạn 18 khách vừa có vé máy bay chỉ nhận 9. Người dùng quyết định (2026-10-08): trước mắt trợ lý không cho thanh toán tất cả cùng một lượt, mỗi mục thanh toán riêng. Như vậy không còn đơn trộn nào từ trợ lý.

## Nội dung đề xuất

**A. FR-BKG-08**, hiện tại: "Khách khai đoàn một lần: 1–9 người, ít nhất 1 người lớn; …"

Thay bằng: "Khách khai đoàn một lần, ít nhất 1 người lớn. Dịch vụ tính theo người (vé máy bay, vé tham quan, golf): tối đa 9 người mỗi mục. Khách sạn: tối đa 9 người mỗi phòng, tức tối đa 9 × số phòng mỗi mục (số phòng tối đa mỗi mục giữ 9, nên cao nhất 81 khách), vẫn không vượt sức chứa `maxOccupancy` của hạng phòng khi có. Đoàn khai ở bước Hành khách có trần bằng trần của mục lớn nhất trong đơn. Đơn có mục không phải khách sạn thì trần là 9. …"

Phần còn lại giữ nguyên, gồm: mỗi phòng có ít nhất 1 người lớn, combo giữ giới hạn riêng. Vé máy bay tối đa 9 người (người dùng xác nhận 2026-10-08).

**B. FR-BKG-01**, hiện tại: "…hoặc bấm "Thanh toán tất cả" ở một lịch trình do trợ lý lập (lưu trú và hoạt động cùng một đơn nháp)."

Bỏ ý này: đơn nháp chỉ tạo khi khách bấm "Đặt ngay" ở một sản phẩm hoặc chọn một hành trình bay (một chiều hoặc khứ hồi).

**B. user-flow.md**
- §1.2 bước 4: "Tự đặt từng mục ngay trên lịch trình, hoặc bấm Thanh toán tất cả để … thanh toán một lần." → "Đặt từng mục ngay trên lịch trình; mỗi mục thanh toán riêng."
- §3.2: bỏ nhánh "hoặc 'Thanh toán tất cả'" ở nút `I`.
- §4.2: bỏ `[Thanh toán tất cả]` khỏi wireframe; chú thích nút đặt bỏ câu về `[Thanh toán tất cả]`.

Ghi chú: đây là quyết định "trước mắt". Khi cần thanh toán gộp lại sẽ có đề xuất riêng. Vé khứ hồi chọn ở trang chuyến bay không bị ảnh hưởng.

## Thay đổi source sau khi chốt

**A (khách sạn)**
- `src/shared/contracts/schemas/booking.yaml` (`GuestCounts`: mô tả, `maximum` của `adults` và `children`), `paths/booking.yaml`; chạy `validate_contract.py`. Nới lỏng, tương thích ngược, có thể cần tăng minor version.
- `src/backend/app/domain/booking/party.py`, `party_rules.py` (`check_party`, `check_cart_guests`, các chỗ dùng `MAX_PARTY`), `application/booking/messages.py`.
- `db/vota_schema.sql`, `db/init/01_vota.sql`, thêm migration idempotent: bỏ hoặc nới `CHECK (adults + children <= 9)` ở `app.booking_draft_items`. `app.cart_items` giữ 9 (giỏ không nhận khách sạn từ 2026-10-01). Cập nhật `docs/spec/DATABASE_SCHEMA.md`.
- `src/shared/contracts/tests/booking-rules-cases.json`: thêm ca "2 phòng 18 khách", "1 phòng 10 khách", "đơn có vé máy bay trên 9 khách". Cập nhật test backend và frontend.
- Frontend: `features/search/tripContext.ts` (`MAX_PARTY_SIZE`, đọc từ URL), `features/catalog/landing/GuestsPopover.tsx` (chú thích "Tối đa 9 khách mỗi phòng"), `components/checkout/guestCounts.ts`, `checkoutRules.ts`.

**B (trợ lý)**
- Frontend: bỏ nút "Thanh toán tất cả" ở `features/itinerary/widget/WidgetPlanPanel.tsx`, `components/assistant/AssistantResultPanel.tsx` và đường gọi tương ứng (`hooks/useAssistantCart.ts`, `useFloatingWidget.ts`, `context/TravelContext.tsx`); cập nhật test (`tests/e2e/widget-opening.spec.ts`, `tests/unit/bookingService.test.ts`).
- Backend giữ nguyên: `POST /booking-drafts` vẫn nhận nhiều mục (khứ hồi, đặt lại đơn) và `allowPartial` vẫn dùng cho đặt lại.
- Spec: `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md` (dòng "Trợ lý"), `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` (R-CRT-01, D6), `docs/spec/product.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/hop-dong-tich-hop-backend.md` (§ nhắc "Thanh toán tất cả"), `docs/spec/hop-dong-tich-hop-cdp.md` (dòng `add_to_cart`).

## Đã trả lời

- Số phòng tối đa mỗi mục là 9, nên trần cao nhất của một mục khách sạn là 81 khách (người dùng, 2026-10-08).
- Vé máy bay tối đa 9 người; trợ lý không còn "Thanh toán tất cả" (người dùng, 2026-10-08).

Người dùng chốt đề xuất ngày 2026-10-08. PRD đã cập nhật: `requirements.md` FR-BKG-01, FR-BKG-08; `user-flow.md` §1.2 bước 4, §3.2, §4.2.
