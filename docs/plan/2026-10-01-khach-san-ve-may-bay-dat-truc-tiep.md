# Kế hoạch: khách sạn và vé máy bay đặt trực tiếp qua đơn nháp, giỏ hàng chỉ còn tour và tiện ích

- Ngày: 2026-10-01
- Phục vụ: FR-BKG-01 (viết lại), FR-BKG-02, FR-BKG-05, FR-BKG-08, FR-BKG-10, FR-BKG-13, FR-AGT-04, FR-CDP-01, FR-USR-03 (`docs/prd/requirements.md`); AC-BKG-01…12 giữ hành vi, thêm AC-BKG-13, AC-BKG-14, AC-BKG-15, AC-BKG-16, AC-BKG-17.
- Đề xuất PRD: `docs/prd/update-archive/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md` — **đã chốt và đã áp dụng vào PRD (mihhquan, 2026-10-01, trả lời từng câu Q1–Q14 và các câu phụ)**.
- Spec: `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md` (viết 2026-10-01). Khi spec và kế hoạch này khác nhau ở chi tiết thiết kế, spec thắng.
- Người làm: mihhquan / Claude Code, nhánh `feat/booking`
- Lịch sử: `history/2026-10-01-de-xuat-va-plan-khach-san-ve-may-bay-dat-truc-tiep.md`

Kế hoạch theo các câu trả lời của người dùng (bảng "Các quyết định đã chốt" trong đề xuất). Cách gọi: `/checkout` là **trang thanh toán** gồm ba bước; đặt chỗ là một phần của quá trình đó.

## Vì sao đổi

Giỏ hàng lưu lâu dài và gom mọi thứ khách từng thêm. Với khách sạn và vé máy bay, giá và chỗ trống đổi liên tục nên mục trong giỏ cũ dần: khách chỉ biết giá đã đổi khi bấm Thanh toán (`409 PRICE_CHANGED`), mục cũ rơi ra ngoài cửa sổ đặt chỗ 30 ngày làm hỏng cả đơn, và "Đặt ngay" một phòng lại thanh toán kèm những mục bỏ giỏ từ trước vì `POST /bookings` lấy toàn bộ giỏ.

## Mô hình đích

| Nhóm | `taxonomy` | Thêm vào giỏ | Đặt ngay | Khi không hoàn thành thanh toán |
|---|---|---|---|---|
| Lưu trú | `hotel` | Không | Đơn nháp | Không giữ lại |
| Di chuyển | `flight` | Không | Đơn nháp | Không giữ lại |
| Tour và trải nghiệm | `attraction`, `golf` | Có (như hiện nay) | Đơn nháp | Nằm lại trong giỏ |
| Tiện ích khác | `combo` | Có (như hiện nay) | Đơn nháp | Nằm lại trong giỏ |

```
Giỏ (tour, tiện ích):   [Thêm vào giỏ] → app.carts → /cart → /checkout → POST /bookings
Đặt trực tiếp (mọi loại): [Đặt ngay] → POST /booking-drafts (30 phút) → /checkout?draft=<mã> → POST /bookings {draftId}
                                          └─ chép mục tour, tiện ích vào app.carts (nếu chưa có)
```

"Không hoàn thành thanh toán" gồm: rời trang thanh toán trước khi bấm Thanh toán, rời trang Stripe, thẻ bị từ chối đủ 3 lần (`PAYMENT_FAILED`), hết hạn giữ chỗ (`EXPIRED`), hoặc huỷ đơn chưa trả tiền.

**Vì sao chép vào giỏ ngay lúc bấm Đặt ngay, không đợi lúc khách bỏ dở:** Web không bắt được mọi kiểu bỏ dở (đóng tab, mất mạng, đơn nháp tự hết hạn, bỏ ngang ở trang Stripe). Chép ngay lúc tạo đơn nháp thì một luật phủ được mọi trường hợp trên: mục đã ở trong giỏ từ đầu và chỉ bị gỡ khi đơn `CONFIRMED` (luật sẵn có ở `settlement.py`). Đơn `PAYMENT_FAILED`, `EXPIRED`, `CANCELLED` không gỡ gì khỏi giỏ.

| | Giỏ hàng (giữ, thu hẹp) | Đơn nháp (mới) |
|---|---|---|
| Nhận loại nào | `attraction`, `golf`, `combo` | Mọi loại |
| Phạm vi | Mọi thứ khách từng thêm | Đúng một lần đặt: một sản phẩm, một hành trình bay (một chiều hoặc khứ hồi), hoặc cả lịch trình của trợ lý khi bấm Thanh toán tất cả (Q2) |
| Tuổi thọ | Đã đăng nhập: không hết hạn. Chưa đăng nhập: 3 ngày từ lần sửa gần nhất (`GUEST_BOOKING_TTL_DAYS`, Q4b) | 30 phút từ lúc tạo (`BOOKING_DRAFT_TTL_MINUTES`, Q3) |
| Nơi lưu (Q4) | Đã đăng nhập: `app.carts`. Chưa đăng nhập: Redis | Đã đăng nhập: `app.booking_drafts`. Chưa đăng nhập: Redis |
| Số lượng | Một giỏ mỗi người | Nhiều đơn nháp, mỗi cái có mã riêng (mỗi tab một đơn nháp) |
| Thêm mục | Cộng dồn bất kỳ lúc nào | Chỉ lúc tạo. Sau đó chỉ sửa số khách, số lượng, ngày của từng mục, hoặc bỏ một mục |
| Kết thúc | Xoá mục khi đơn `CONFIRMED` | Xoá khi tạo đơn giữ chỗ, hoặc khi quá hạn |
| Khi hết hạn (Q3) | — | Khách sạn, vé máy bay: không giữ gì, khách đặt lại từ đầu (Q3b). Tour, tiện ích: còn trong giỏ |

Thông tin hành khách (họ tên, ngày sinh, giấy tờ) vẫn chỉ nằm trong bộ nhớ của trang thanh toán như quy định hiện có (`hop-dong-tich-hop-frontend.md` §4.5); giỏ và đơn nháp chỉ lưu sản phẩm, ngày, số lượng, số khách.

Giữ nguyên: trang `/cart`, header, thanh tab mobile; checkout ba bước và bộ luật đoàn khách (FR-BKG-08); dòng giá; giữ chỗ 30 phút và một đơn giữ chỗ mỗi người (FR-BKG-05); Stripe, webhook, đối soát, huỷ và hoàn tiền; xuất vé mô phỏng; ghi `purchase` sang CDP.

## Thiết kế

### API (contract 1.13.0, chỉ thêm)

| Endpoint | Việc |
|---|---|
| `POST /booking-drafts` (mới) | Body `{ items: [{productId, usingDate, quantity?, nights?, guests?}], allowPartial?, fromBooking? }`. Kiểm từng mục như `POST /cart/items` (tồn tại, `is_bookable`, còn bán, ngày trong cửa sổ, luật số khách R-CRT-01…05). Trả `201 BookingDraft`. Ghi `add_to_cart` cho từng mục được nhận. Mục `attraction`, `golf`, `combo` được chép vào giỏ nếu giỏ chưa có mục cùng `productId` và `usingDate` |
| `GET /booking-drafts/{draftId}` (mới) | Trả `BookingDraft` với giá và `available` lấy lại từ catalog. Của người khác hoặc không có: `404 BOOKING_DRAFT_NOT_FOUND`. Quá hạn: `410 BOOKING_DRAFT_EXPIRED`; `details` cho biết đơn nháp có mục nào đang nằm trong giỏ để Web dẫn khách về giỏ hoặc về trang sản phẩm |
| `PATCH /booking-drafts/{draftId}/items/{itemId}` (mới) | Sửa ngày, số lượng, số đêm, số khách; ghi lại snapshot giá. Cùng body và luật như `PATCH /cart/items/{id}` |
| `DELETE /booking-drafts/{draftId}/items/{itemId}` (mới) | Bỏ một mục khỏi lần đặt (trang thanh toán dùng cho mục không còn đặt được). Bỏ mục cuối thì xoá đơn nháp |
| `POST /cart/items` (sửa hành vi) | Sản phẩm `hotel` hoặc `flight`: `422 DIRECT_BOOKING_ONLY`, không ghi giỏ, không ghi `add_to_cart` |
| `POST /bookings` (thêm trường) | `draftId` tuỳ chọn. Có: thanh toán đơn nháp đó. Không có: thanh toán giỏ như hiện nay |

- `BookingDraft`: `draftId`, `expiresAt`, `items[]`, `itemCount`, `subtotal`, `total`, `currency`, `rejectedItems[]`. **`items[]` dùng lại schema `CartItem`**: `cartItemId` là mã mục, dùng chung cho mục giỏ và mục đơn nháp. Nhờ vậy `CheckoutItemDetail.cartItemId` và `ValidationFieldError.cartItemId` không đổi, bộ luật và phần đưa lỗi về đúng thẻ dịch vụ của checkout chạy được với cả hai nguồn.
- `allowPartial: true` (trợ lý dùng): mục không đặt được bị bỏ qua và trả trong `rejectedItems[]` kèm mã lỗi; không mục nào được nhận thì `409`. Mặc định `false`: một mục lỗi thì cả request lỗi.
- `fromBooking: <referenceCode>` (nút "Đặt lại", Q7): lấy mục từ đơn `PAYMENT_FAILED` hoặc `EXPIRED` của chính người dùng; khi có thì không gửi `items`.
- Mã lỗi mới trong `ErrorCode`: `DIRECT_BOOKING_ONLY` (422), `BOOKING_DRAFT_NOT_FOUND` (404), `BOOKING_DRAFT_EXPIRED` (410).
- `POST /cart/items` từ chối thứ trước đây nhận là đổi hành vi trong v1. Không đổi schema, và nằm trong nội dung đề xuất (AC-BKG-15); ghi rõ trong mô tả endpoint.
- Sửa mô tả ở `schemas/catalog.yaml` (đặt vé theo `productId` của hạng vé: qua đơn nháp) và `paths/events.yaml` (`add_to_cart` do `POST /cart/items` và `POST /booking-drafts` ghi).

#### Khách chưa đăng nhập (Q4)

- `/cart*` và `/booking-drafts*` nhận cả khách chưa đăng nhập. Phiên khách của BFF (`anon_id`) chết sau 30 phút không hoạt động nên không dùng làm khoá cho dữ liệu 3 ngày: BFF phát cookie riêng `vota_guest` chứa `guestId` (Max-Age 3 ngày), và chuyển tiếp request của khách kèm `X-Service-Token` + `X-Guest-Id`. Backend chỉ tin `X-Guest-Id` khi service token hợp lệ (spec §8.1).
- `POST /bookings`, `GET /bookings/*`, huỷ đơn vẫn bắt buộc đăng nhập (`401` như hiện nay).
- `CartResponse.cdpUserId` đang là trường bắt buộc; với khách chưa đăng nhập phải cho phép `null`. Đây là nới kiểu của một trường v1, nằm trong nội dung đề xuất.
- Gộp: `POST /guest-bookings/merge` (service token + Bearer, chỉ BFF gọi). BFF tự gọi trước khi chuyển tiếp request giỏ, đơn nháp, đơn đầu tiên của một phiên đã đăng nhập còn cookie `vota_guest`, rồi xoá cookie; Web không phải gọi gì. Backend chép giỏ Redis sang `app.carts` và đơn nháp còn hạn sang `app.booking_drafts` với cùng `draftId` (Q4c: mục giỏ tài khoản chưa có thì thêm; trùng sản phẩm và ngày thì chỉ giữ một, là mục đang có trong tài khoản), ghi `add_to_cart` cho từng mục thực sự được chép, mục trùng bị bỏ thì không ghi (Q4d), rồi xoá mọi khoá Redis của `guestId` đó (spec §8.3, §8.4).
- Khách chưa đăng nhập không sinh sự kiện CDP (FR-CDP-02); mã phiên khách không được ghi xuống PostgreSQL.

### Database

```sql
CREATE TABLE app.booking_drafts (
    draft_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cdp_user_id  text NOT NULL REFERENCES cdp.profiles (cdp_user_id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL
);
CREATE TABLE app.booking_draft_items (
    draft_item_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id       uuid NOT NULL REFERENCES app.booking_drafts (draft_id) ON DELETE CASCADE,
    -- các cột còn lại giống app.cart_items: product_id, quantity, using_date, using_date_to,
    -- unit_price_snapshot, added_at, adults, children, child_unit_price_snapshot và các CHECK tương ứng
    CONSTRAINT booking_draft_items_uq UNIQUE (draft_id, product_id, using_date)
);
```

- Index `booking_drafts (cdp_user_id)` và `(expires_at)`. Quyền cho role `vota_app` như `app.carts`.
- Migration `0007_booking_drafts.sql` (idempotent): tạo hai bảng, cấp quyền, và xoá `app.cart_items` có sản phẩm `hotel` hoặc `flight`: theo luật giỏ không được có hai loại này, đây là dọn mục cũ thêm trước khi có luật (Q10). `app.carts`, `app.cart_items` giữ nguyên cấu trúc.
- `db/verify.sql` thêm hai dòng: giỏ không có mục `hotel`/`flight`; đoàn khách của mục đơn nháp trong khoảng 1–9 và có người lớn.
- Dọn đơn nháp quá hạn: khi tạo đơn nháp mới thì xoá các đơn nháp đã quá hạn của người đó; job đối soát đơn sẵn có xoá phần còn lại. Không thêm bảng nhật ký job (`AGENTS.md` §6.1).
- Mỗi người tối đa 5 đơn nháp còn hạn; tạo cái thứ 6 thì xoá cái cũ nhất.
- Redis cho khách chưa đăng nhập (`BOOKING_REDIS_URL`, DB index riêng như `ITINERARY_REDIS_URL`): khoá `guest:cart:<guestId>`, `guest:draft:<draftId>` và `guest:drafts:<guestId>` đều hết hạn sau `GUEST_BOOKING_TTL_DAYS` (3 ngày, Q4b), giỏ tính từ lần ghi gần nhất. Đơn nháp của khách vẫn mang `expiresAt` 30 phút như mọi đơn nháp: quá 30 phút thì không thanh toán được nữa (`410`), bản ghi còn lại chỉ để trang hết hạn biết dẫn về sản phẩm nào. Giá trị là JSON cùng các trường với dòng `cart_items`. Không có bảng mới cho khách.

### Backend

- `domain/booking/`: hằng `DIRECT_BOOKING_TAXONOMIES = {"hotel", "flight"}` và hàm `is_cart_eligible(taxonomy)`; `BookingDraft` (thêm `created_at`, `expires_at`) dùng lại `CartLine`; `draft.py` có `DraftPolicy(ttl_minutes)` cùng kiểu `HoldPolicy`.
- `application/booking/cart.py`: `add` từ chối loại đặt trực tiếp (`DirectBookingOnly`). Tách phần kiểm một mục (`check_product`, `resolve_cart_guests`, snapshot giá) thành hàm dùng chung cho giỏ và đơn nháp.
- `application/booking/drafts.py` (mới): `BookingDraftService.create / get / update_item / remove_item`. `create` chép mục được vào giỏ sang giỏ trong cùng transaction tạo đơn nháp: giỏ đã có mục cùng sản phẩm và ngày thì giữ nguyên mục giỏ, không cộng dồn. Sửa hoặc bỏ mục trong đơn nháp không đổi giỏ.
- `application/ports/booking_draft_repository.py` (mới); adapter trong `infrastructure/persistence/postgres_booking.py`.
- Khách chưa đăng nhập: port `CartRepository` và `BookingDraftRepository` có thêm adapter Redis (`infrastructure/persistence/redis_guest_booking.py`); use case nhận một "chủ giỏ" là `cdp_user_id` hoặc mã phiên khách và chọn adapter theo đó. Thêm use case `MergeGuestBooking` chạy lúc đăng nhập. `api/deps.py`: dependency mới trả principal hoặc phiên khách cho các route giỏ và đơn nháp; `current_principal` giữ cho route đơn.
- `application/booking/create_hold.py`: nhận `draft_id` tuỳ chọn. Có thì đọc đơn nháp (đúng chủ, còn hạn), không thì đọc giỏ; phần kiểm luật, tính dòng giá, gọi Stripe dùng chung. Đơn tạo từ đơn nháp: **xoá đơn nháp trong cùng transaction ghi đơn giữ chỗ** (thêm `delete_draft` vào `BookingTx`).
- `application/booking/settlement.py`: giữ `clear_cart_items` khi đơn `CONFIRMED`. Đây là bước gỡ bản chép trong giỏ của lần Đặt ngay đã thanh toán xong; không cần code mới.
- `application/booking/errors.py`, `api/errors.py`: ba lỗi mới và câu thông báo; `api/v1/routes/booking.py`, `api/v1/schemas/booking.py`; `core/config.py`: `booking_draft_ttl_minutes` (mặc định 30), `guest_booking_ttl_days` (mặc định 3), `booking_redis_url`; `main.py`: nối dây.
- `application/tracking/behaviour.py`: `track_add_to_cart` gọi thêm từ `BookingDraftService.create`, mỗi mục được nhận một lần, chỉ khi đã đăng nhập (Q5); `PATCH`, `DELETE` và việc chép vào giỏ không ghi thêm sự kiện.

### Frontend

- `services/booking.ts`: thêm `createBookingDraft`, `getBookingDraft`, `updateBookingDraftItem`, `removeBookingDraftItem`; `createBooking` nhận `draftId`. Bốn hàm giỏ giữ nguyên.
- Một hàm `isCartEligible(taxonomy)` dùng chung (đặt cạnh `guestCounts.ts`), phản chiếu luật của Backend; `isCartEligible(product)` ở `AssistantResultPanel.tsx` đổi tên thành `isBookable` để khỏi trùng nghĩa.
- `context/TravelContext.tsx`: giữ phần giỏ. Thêm `startBooking(items, options)`: tạo đơn nháp → `navigate('/checkout?draft=<mã>')`. `addToCart` và `startBooking` bỏ bước bắt đăng nhập (Q4); giỏ được tải cả khi là khách; sau khi đăng nhập hoặc đăng xuất thì tải lại giỏ. `addToCart` với loại đặt trực tiếp thì chuyển sang `startBooking` thay vì gọi API rồi nhận lỗi. Sau `startBooking` gọi `refreshCart` để số đếm giỏ khớp với mục vừa được chép.
- `components/checkout/useCheckout.ts`, `patchQueue.ts`: tách "nguồn" của checkout thành một interface (`items`, `refresh`, `updateItem`), có hai hiện thực: giỏ (như hiện nay) và đơn nháp theo `?draft=`. `createBooking` gửi `draftId` khi nguồn là đơn nháp. Xử lý `410`: màn hình "Phiên thanh toán đã hết hạn"; đơn nháp có khách sạn hoặc vé máy bay thì dẫn về trang sản phẩm hoặc trang tìm vé để đặt lại từ đầu, có tour hoặc tiện ích thì kèm nút về giỏ (Q3, Q3b). `404`: về trang chủ kèm thông báo. Bấm Thanh toán khi chưa đăng nhập: mở hộp đăng nhập ngay trên trang, đăng nhập xong thì gửi tiếp (Q4a); thông tin đã nhập không mất vì trang không tải lại.
- `components/detail/ProductDetailView.tsx`: khách sạn bỏ nút Thêm vào giỏ, chỉ có **Đặt ngay**; tour, golf, combo có **Thêm vào giỏ** và **Đặt ngay** (người dùng xác nhận 2026-10-01). Đặt ngay luôn gọi `startBooking` (Q9) và chỉ thanh toán đúng sản phẩm đó, không kèm mục nào trong giỏ; giỏ chỉ được thanh toán từ nút Thanh toán ở trang giỏ (Q9b).
- `features/flights/results/FlightResultsView.tsx`: một lời gọi `startBooking` cho một hoặc hai chặng, thay cho thêm giỏ từng chặng.
- Trợ lý: `hooks/useAssistantCart.ts` → `useBookItinerary.ts` (một request, `allowPartial: true`, mục bị từ chối gom vào một thông báo); `features/itinerary/widget/WidgetPlanPanel.tsx`, `useFloatingWidget.ts`: một nút **Thanh toán tất cả** cho cả lịch trình (Q2), thay hai nút "Thêm vào giỏ" và "Thanh toán" hiện nay; từng mục vẫn đặt riêng được ngay trên lịch trình. Nút trên thẻ và ghim bản đồ (`ItineraryMap.tsx`): khách sạn, vé máy bay có **Đặt ngay** (Q11); tour, golf, combo có **Thêm vào giỏ** và **Đặt ngay** (Q12); ngày theo lịch trình, số khách theo `intent.party`. Khách sạn chưa có hạng phòng: xem ghi chú Q11c bên dưới.
- BFF (`src/frontend/src/app/api/`): chuyển tiếp mã phiên khách cho các route giỏ và đơn nháp; gọi gộp khi đăng nhập thành công, trước khi phiên khách bị thay.
- `components/confirmation/ConfirmationView.tsx`: "Đặt lại từ giỏ" → **Đặt lại** (`fromBooking`).
- Thanh đầu trang thanh toán (`Header.tsx`, nhánh `isCheckout`): nút quay lại hiện dẫn về `/cart`. Nguồn là đơn nháp thì quay về trang trước; nếu đơn nháp có mục đã nằm trong giỏ thì kèm thông báo "Đã lưu … vào giỏ hàng".
- `components/cart/CartView.tsx`: bỏ khối "Thường được đặt cùng chuyến" và lời gọi `/recommendations` của trang giỏ (Q13); thêm một dòng giải thích ở giỏ trống và dưới tiêu đề: khách sạn và vé máy bay được đặt trực tiếp từ trang sản phẩm.
- `components/common/BecauseLine.tsx`, `WhyPopover.tsx`: nhãn `add_to_cart` "đã thêm vào giỏ" → "đã chọn để đặt" (sự kiện giờ gồm cả bấm Đặt ngay).

#### Nút Thêm vào giỏ: rà từng chỗ

Các chỗ đang có nút Thêm vào giỏ (đã dò trên nhánh `feat/booking`) và cách xử lý. Luật chung: nút Thêm vào giỏ chỉ hiện khi `isCartEligible(taxonomy)`; khách sạn và vé máy bay chỉ có Đặt ngay.

| Chỗ | Hiện tại | Sau thay đổi |
|---|---|---|
| `detail/ProductDetailView.tsx` (nút "Thêm vào giỏ hàng" và "Đặt ngay") | Cả hai nút cho mọi loại | Khách sạn: chỉ Đặt ngay. Tour, golf, combo: cả hai |
| `features/flights/results/FlightResultsView.tsx` | Một nút, thêm từng chặng vào giỏ rồi mở checkout | Một nút Đặt ngay, tạo đơn nháp cho một hoặc hai chặng |
| `assistant/ItineraryMap.tsx` (ghim bản đồ) và `widget/WidgetPlanPanel.tsx` (`onAddToCart`, số lượng cố định 2) | "Thêm vào giỏ" cho mọi sản phẩm | Khách sạn, vé máy bay: **Đặt ngay** (Q11). Tour, golf, combo: **Thêm vào giỏ** và **Đặt ngay** (Q12), ngày của hoạt động và số khách theo `intent.party`. Khách sạn chưa có hạng phòng: ghi chú Q11c |
| `assistant/AssistantResultPanel.tsx` (thẻ sản phẩm, thẻ "Nơi lưu trú", nút "Thêm cả lịch trình vào giỏ") | "Thêm vào giỏ" cho mọi sản phẩm đặt được | Thẻ: cùng luật với ghim bản đồ (Q11, Q12). Nút cả lịch trình: thành "Thanh toán tất cả". Component này hiện không được màn hình nào dùng (chỉ còn dùng `itineraryCartItems`, `isCartEligible`); sửa cho đúng luật hoặc xoá phần giao diện chết, quyết ở bước 5 |
| `cart/CartView.tsx` (khối "Thường được đặt cùng chuyến", `onQuickAdd`) | Thêm nhanh mọi sản phẩm gợi ý vào giỏ | **Bỏ cả khối** (Q13); không còn nút thêm nhanh nào ở trang giỏ |

### Không đổi

- Agent: `src/backend/app/agents/steps/prompts.py` chỉ nhắc "cart" trong danh sách việc ngoài phạm vi của trợ lý; không sửa. Lịch trình vẫn chỉ chứa sản phẩm từ Search/Recommendation/Catalog (NFR-REL-01).
- CDP: contract `cdp-clone.openapi.yaml`, enum sự kiện, `cdp.events` không đổi. Seed lịch sử (`seed_histories.py`, tỷ lệ `add_to_cart`) không đổi, nên bench RecSys không đổi số.
- Header, thanh tab mobile, trang `/cart`, bốn endpoint `/cart*`, schema và mock giỏ.

## Các bước

| # | Bước | Phụ thuộc | Trạng thái |
|---|---|---|---|
| 0 | Người dùng trả lời hết các câu hỏi; áp dụng vào `docs/prd/`, đổi trạng thái đề xuất, chuyển sang `docs/prd/update-archive/`, ghi `history/` | — | Xong (2026-10-01) |
| 1 | (Xong 2026-10-01) Đọc đủ `docs/spec/product.md` §4.4, §6.7, `hop-dong-tich-hop-frontend.md` §4.4–§4.8 và `hop-dong-tich-hop-auth.md` (§3 phiên khách, BFF). Viết spec `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md`: loại nào đặt trực tiếp, luật tạo và hết hạn đơn nháp, bảng lỗi, luồng hết hạn và "Đặt lại", giỏ và đơn nháp của khách chưa đăng nhập (khoá Redis, cách BFF chuyển mã phiên khách, gộp khi đăng nhập), trường hợp biên. Bổ sung ca vào `src/shared/contracts/tests/booking-rules-cases.json` | 0 | Xong |
| 2 | Contract 1.13.0: `/booking-drafts*`, `BookingDraft`, ba mã lỗi, `draftId`, mô tả `POST /cart/items`, `catalog.yaml`, `events.yaml`; `/cart*` và `/booking-drafts*` cho phép không có token, `CartResponse.cdpUserId` cho phép `null`. Mock mới trong `src/shared/mocks/booking/` (`createBookingDraft.*`, `getBookingDraft.*`, `addCartItem.422-direct-booking-only.json`) và `index.json`; mock giỏ đang dùng khách sạn hoặc vé máy bay đổi sang vé tham quan. Sinh lại `api.gen.ts` (`npm run generate:api-types`). Sửa `validate_contract.py` | 1 | Xong |
| 3 | DDL: `db/vota_schema.sql`, `db/init/01_vota.sql`, migration `0007_booking_drafts.sql`, `db/verify.sql`, `docs/spec/DATABASE_SCHEMA.md`, `src/data_collection/seed/database.py` (thêm hai bảng vào danh sách `--reset`) | 1 | Xong |
| 4 | Backend: domain, `BookingDraftService`, giỏ từ chối loại đặt trực tiếp, port và adapter Postgres, adapter Redis cho khách chưa đăng nhập và `MergeGuestBooking`, `create_hold` hai nguồn, route, DTO, cấu hình, lỗi. Test: unit (`test_booking_flow.py`, `test_checkout_travelers.py`, `test_flight_booking.py`, `fakes/booking.py`), contract (`test_booking_contract.py`), integration Postgres và Redis, kiến trúc | 2, 3 | Xong (2026-10-01) |
| 5 | Frontend: `services/booking.ts`, `startBooking`, checkout hai nguồn, trang chi tiết, vé máy bay, trợ lý, trang đơn, trang giỏ; bỏ bước bắt đăng nhập ở thêm giỏ và Đặt ngay, đăng nhập lúc bấm Thanh toán, BFF chuyển mã phiên khách và gọi gộp. Sửa test vitest liên quan (`productDetailView`, `flightResultsView`, `checkoutView`, `useAssistantCart`, `confirmationView`, `cartView`), thêm test cho hết hạn và "Đặt lại" | 2 (mock), 4 (chạy thật) | Xong (2026-10-01) |
| 6 | Chạy thử toàn luồng trên trình duyệt với Backend thật (`PAYMENT_PROVIDER=fake`) và Postgres đã migrate: tám kịch bản ở mục Nghiệm thu | 4, 5 | Xong một phần (2026-10-01): kịch bản 1, 3, 5, 7, 8 và hai mục "Kiểm thêm" chạy trên stack thật; kịch bản 2, 4, 6 chỉ có test tự động, xem `history/2026-10-01-ap-dung-khach-san-ve-may-bay-dat-truc-tiep.md` |
| 7 | Đồng bộ tài liệu: `hop-dong-tich-hop-backend.md` §7.1, §7.2, §7.4, §8.2; `hop-dong-tich-hop-frontend.md` §4.4–§4.8; `product.md` §4.4, §6, §6.7 (bỏ khối "Thường được đặt cùng" ở giỏ); `hop-dong-tich-hop-cdp.md` (nơi ghi `add_to_cart`); `hop-dong-tich-hop-auth.md` (§3.7 và bảng route cần đăng nhập); `booking/so-do-luong-dat-cho-thanh-toan.md` §6.2, §8; `booking/checkout-nhieu-buoc-hanh-khach.md` §5.5, §6.9, §10.3, §10.5; `docs/guide/hien-thi-hang-ve-may-bay.md` (mục "Giỏ hàng — không đổi"); README backend và frontend; bảng ánh xạ đọc/ghi của monitor (`deployment-plan.md` §5) | 6 | Xong (2026-10-01) |
| 8 | Entry `history/`, báo cáo nghiệm thu, người dùng nghiệm thu | 7 | Entry `history/` xong; chờ người dùng nghiệm thu |

Bước 2–3 làm song song được. Bước 4 và 5 làm song song được nếu Frontend dùng mock trước.

Triển khai lên staging: `python db/migrations/run.py --database-url <dsn staging>` chạy `0007` trước khi phát hành Backend mới. Backend cũ vẫn chạy được trên schema mới (chỉ thêm bảng), nên phát hành Backend rồi Web theo thứ tự thường lệ.

## Kiểm tra trước khi báo hoàn thành

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`.
- `python -m pytest -q src/backend/tests` và `RUN_POSTGRES_INTEGRATION=1 python -m pytest -q src/backend/tests/integration/test_booking_postgres.py`; bao phủ `domain` và `application` ≥ 80%.
- Trong `src/frontend`: `npm run typecheck`, `npm run lint`, `npm run test:unit`.
- `make db-migrate`, rồi `db/verify.sql` bằng `SEED_DATABASE_URL`: toàn PASS trừ hai dòng FAIL dự kiến của catalog tổng hợp (`AGENTS.md` §6.5).

## Nghiệm thu (bước 6)

1. **Đặt một phòng** (AC-BKG-01, AC-BKG-15): trang chi tiết khách sạn, kết quả vé máy bay, ghim bản đồ và thẻ của trợ lý không có nút Thêm vào giỏ cho khách sạn, vé máy bay (ở đó là nút Đặt ngay); trang giỏ không còn khối gợi ý. Trang chi tiết khách sạn chỉ có Đặt ngay → ba bước → Stripe giả → đơn `CONFIRMED`; `cdp.events` có một `add_to_cart` và một `purchase`; `app.booking_drafts` không còn dòng của lần đặt này; giỏ không đổi.
2. **Khứ hồi** (AC-BKG-09): `/flights` chọn hai chặng → một đơn nháp hai mục → bước Dịch vụ hiện thẻ "Khứ hồi · 2 chặng".
3. **Giỏ tour** (AC-BKG-05): thêm vé VinWonders và một combo vào giỏ → `/cart` → `/checkout` → thanh toán như hiện nay. Gọi thẳng `POST /cart/items` với một phòng trả `422 DIRECT_BOOKING_ONLY`.
4. **Lịch trình của trợ lý**: Thanh toán tất cả → một đơn nháp có lưu trú và hoạt động theo `intent.party`; mục không đặt được hiện trong một thông báo, các mục còn lại vẫn đặt được.
5. **Không hoàn thành thanh toán** (AC-BKG-16): Đặt ngay một vé tham quan rồi đóng tab → giỏ có vé đó; Đặt ngay một phòng rồi đóng tab → giỏ không có phòng; đặt lịch trình, bấm Thanh toán rồi để đơn `EXPIRED` (và một lần khác cho thẻ bị từ chối 3 lần) → giỏ chỉ có các hoạt động, không có phòng. Quay lại thanh toán xong lần đặt vé tham quan → vé không còn trong giỏ.
6. **Giá đổi** (AC-BKG-13): sửa `unit_price` trong `cdp.products` khi đang ở bước Hành khách → chuyển bước thấy giá mới và thông báo; gọi thẳng `POST /bookings` với snapshot cũ trả `409 PRICE_CHANGED`.
7. **Hết hạn và đặt lại** (AC-BKG-14, AC-BKG-02): đặt `expires_at` về quá khứ → đơn nháp khách sạn báo hết hạn và dẫn về trang khách sạn, không giữ lựa chọn; đơn nháp vé tham quan báo hết hạn và dẫn về giỏ, vé còn nguyên; mở đơn nháp bằng tài khoản khác trả `404`; đơn `PAYMENT_FAILED` có nút Đặt lại mở trang thanh toán với cùng các mục.
8. **Khách chưa đăng nhập** (AC-BKG-17): không đăng nhập, thêm một vé tham quan vào giỏ và Đặt ngay một phòng → cả hai đều được, `cdp.events` không có gì; bấm Thanh toán → hộp đăng nhập, thông tin đã nhập còn; đăng nhập → giỏ tài khoản có vé, thanh toán đi tiếp; mở trình duyệt khác không thấy giỏ hay đơn nháp đó; khoá Redis của giỏ khách có TTL đúng cấu hình.

Kiểm thêm: hai tab đặt hai sản phẩm khác nhau không ảnh hưởng nhau; bấm Đặt ngay một vé tham quan khi giỏ đang có mục khác thì chỉ thanh toán vé đó.

## Rủi ro

| Rủi ro | Xử lý |
|---|---|
| Hai đường vào checkout (giỏ và đơn nháp) làm tăng nhánh phải kiểm | Tách "nguồn" thành một interface ở cả Web và Backend, dùng chung schema mục (`CartItem`) và bộ luật; mỗi ca trong test checkout chạy với cả hai nguồn |
| Combo có lưu trú nhưng vẫn vào giỏ nên vẫn có thể cũ giá | Theo câu trả lời Q1. Giỏ vẫn lấy lại giá mỗi lần đọc và so snapshot lúc thanh toán như hiện nay |
| Khách sạn và vé máy bay mất chỗ "để dành xem sau" | Chấp nhận: người dùng quyết định không làm danh sách lưu xem sau (Q8) |
| `POST /cart/items` từ chối thứ trước đây nhận (đổi hành vi trong v1) | Nằm trong nội dung đề xuất (AC-BKG-15). Web là client duy nhất và được sửa cùng nhánh |
| 30 phút không đủ cho đoàn đông khai giấy tờ; hết hạn là mất lựa chọn khách sạn, vé máy bay | Theo câu trả lời Q3. Trang thanh toán hiện đồng hồ đếm ngược của đơn nháp để khách biết; TTL là cấu hình |
| Khách sửa số khách trong trang thanh toán rồi rời đi: giỏ vẫn giữ số khách lúc bấm Đặt ngay | Chấp nhận; ghi thành luật trong spec. Khách sửa tiếp được ở trang giỏ |
| Giỏ đã có cùng vé và ngày với số khách khác trước khi bấm Đặt ngay | Giữ nguyên mục giỏ, không cộng dồn, không ghi đè; có test |
| Bấm Đặt ngay làm số đếm giỏ tăng dù khách chưa bấm Thêm vào giỏ | Đúng theo câu trả lời Q9. Thông báo khi rời trang thanh toán nói rõ mục đã được lưu vào giỏ |
| Người dùng đang có khách sạn hoặc vé máy bay trong giỏ lúc phát hành bị xoá mục | Đúng luật mới (Q10): hai loại này không được nằm trong giỏ. Môi trường demo, giỏ là dữ liệu tạm; đơn đang giữ chỗ không bị ảnh hưởng |
| Mở giỏ và Đặt ngay cho khách chưa đăng nhập làm rộng bề mặt tấn công (ai cũng ghi được vào Redis) | Giới hạn số mục mỗi giỏ khách và số đơn nháp mỗi phiên; dùng rate limit theo phiên đã có; Redis `noeviction` và DB index riêng |
| Backend tin nhầm mã phiên khách do client tự gửi | Chỉ nhận header này từ BFF; thiết kế ở spec bước 1, đối chiếu `hop-dong-tich-hop-auth.md` trước khi code |
| Gộp khi đăng nhập chạy hai lần (đăng nhập ở hai tab) | Gộp idempotent: chép mục chưa có rồi xoá khoá Redis trong một bước; lần hai không còn gì để gộp |
| Nút Đặt ngay trên thẻ khách sạn của trợ lý gặp khách sạn chưa có hạng phòng (loại không đặt được) | Ghi chú Q11c: phần lịch trình trả về hạng phòng do team trợ lý đang xây, không làm trong đợt này. Nút Đặt ngay chỉ hiện khi sản phẩm đặt được; chưa có hạng phòng thì thẻ giữ lối sang trang chi tiết như hiện nay, Thanh toán tất cả bỏ qua mục đó và báo rõ |
| Bỏ khối gợi ý ở giỏ làm mất một điểm hiện gợi ý (bề mặt `cart` của RecSys) | Theo Q13. Gợi ý ở trang chủ, trang chi tiết và trang đơn vẫn còn; ghi vào `hop-dong-tich-hop-search-recommendation.md` nếu tài liệu đó liệt kê bề mặt giỏ |
| Bảng đơn nháp phình | Giới hạn 5 đơn nháp còn hạn mỗi người, xoá khi tạo mới và trong job đối soát |
| Nhánh `feat/booking` lệch `release-mvp-v2` ở các file checkout | Merge `release-mvp-v2` trước bước 4 |

## Ngoài phạm vi

- Danh sách lưu xem sau cho khách sạn, vé máy bay: người dùng quyết định không làm (Q8).
- **Ghi chú Q11c:** khách sạn trong lịch trình của trợ lý chưa có hạng phòng thì chưa đặt ngay từ thẻ được. Việc lịch trình trả về hạng phòng đặt được thuộc phần team trợ lý đang xây; khi phần đó xong, nút Đặt ngay trên thẻ và Thanh toán tất cả tự dùng được cho khách sạn mà không phải sửa luồng đặt.
- Trang `/profile` và API liệt kê đơn của người dùng (`user-flow.md` §2 có route này nhưng Web và contract chưa có).
- Giữ giá hoặc giữ chỗ thật với nhà cung cấp; tồn kho thời gian thực (`project-brief.md` §4.2).
- Nhắc "bạn đang đặt dở" trên header hoặc qua Insider khi khách rời trang thanh toán.
- Hợp nhất hai bộ persona, dọn phần lặp ở `user-flow.md` §4 (tồn đọng đã ghi ở `AGENTS.md` §6.4 và spec checkout §15.3).
