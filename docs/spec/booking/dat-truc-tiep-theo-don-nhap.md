# Đặt trực tiếp qua đơn nháp, giỏ hàng chỉ còn tour và tiện ích, giỏ của khách chưa đăng nhập

- Ngày: 2026-10-01
- Phục vụ: FR-BKG-01, FR-BKG-02, FR-BKG-05, FR-BKG-08, FR-BKG-10, FR-BKG-13, FR-AGT-04, FR-CDP-01, FR-USR-03 (`docs/prd/requirements.md`); AC-BKG-01, 02, 05, 09, 11, 13, 14, 15, 16, 17.
- Đề xuất PRD đã áp dụng: `docs/prd/update-archive/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md` (mihhquan chốt 2026-10-01).
- Kế hoạch: `docs/plan/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md`.
- Tài liệu nền, không lặp lại ở đây: bộ luật đoàn khách và dòng giá ở `checkout-nhieu-buoc-hanh-khach.md`; giữ chỗ, Stripe, huỷ ở `so-do-luong-dat-cho-thanh-toan.md`; phiên và BFF ở `../hop-dong-tich-hop-auth.md`.

## 1. Tóm tắt

1. Giỏ hàng chỉ nhận `attraction`, `golf`, `combo`. Thêm `hotel`, `flight` vào giỏ bị từ chối.
2. Mọi sản phẩm đặt được đều có nút **Đặt ngay**. Bấm thì Backend tạo một **đơn nháp** chỉ gồm lần đặt đó, Web mở trang thanh toán `/checkout?draft=<mã>`.
3. Đặt ngay không bao giờ thanh toán kèm giỏ. Giỏ chỉ được thanh toán từ nút Thanh toán ở trang giỏ (`/checkout` không có `draft`).
4. Đơn nháp có hiệu lực 30 phút. Hết hạn: khách sạn, vé máy bay không giữ gì; tour và tiện ích vẫn còn trong giỏ.
5. Khi tạo đơn nháp, các mục vào giỏ được của nó được chép vào giỏ. Vì vậy mọi trường hợp không hoàn thành thanh toán đều để lại tour và tiện ích trong giỏ.
6. Khách chưa đăng nhập dùng được giỏ và Đặt ngay; dữ liệu nằm trong Redis 3 ngày và được gộp vào tài khoản khi đăng nhập. Tạo đơn và thanh toán cần đăng nhập.

## 2. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Trang thanh toán | `/checkout`, ba bước Hành khách → Dịch vụ → Xem lại và thanh toán. Đặt chỗ là một phần của quá trình này |
| Đơn nháp (booking draft) | Tập mục của một lần Đặt ngay, chưa phải đơn. Không giữ chỗ, không trừ tồn kho |
| Loại đặt trực tiếp | `hotel`, `flight` |
| Loại vào giỏ được | `attraction`, `golf`, `combo` |
| Chủ giỏ | Người đã đăng nhập (`cdp_user_id`) hoặc khách chưa đăng nhập (`guestId`) |
| `guestId` | Mã khách chưa đăng nhập do BFF phát, dạng `g_` + 22 ký tự base64url. Khác `anon_id` của phiên: sống 3 ngày, không phụ thuộc phiên 30 phút |

## 3. Luật theo loại sản phẩm

| Mã | Luật |
|---|---|
| R-DIR-01 | `POST /cart/items` với sản phẩm `hotel` hoặc `flight`: `422 DIRECT_BOOKING_ONLY`, `details {productId, taxonomy}`. Giỏ không đổi, không ghi `add_to_cart` |
| R-DIR-02 | Web chỉ hiện nút Thêm vào giỏ khi `taxonomy` thuộc loại vào giỏ được. Luật nằm ở một hàm duy nhất phía Web (`isCartEligible(taxonomy)`) và một hằng duy nhất phía Backend (`DIRECT_BOOKING_TAXONOMIES`) |
| R-DIR-03 | Mọi sản phẩm đặt được có nút Đặt ngay, kể cả loại vào giỏ được |
| R-DIR-04 | Migration xoá các mục giỏ `hotel`, `flight` có từ trước (giỏ không được chứa hai loại này) |

## 4. Đơn nháp

### 4.1. Tạo

`POST /booking-drafts`, body có đúng một trong hai: `items` (1–20 mục) hoặc `fromBooking` (§7).

| Mã | Luật |
|---|---|
| R-DRF-01 | Mỗi mục được kiểm như khi thêm giỏ: sản phẩm tồn tại, `is_bookable`, còn bán, `usingDate` trong cửa sổ, luật số khách R-CRT-01…05 (`checkout-nhieu-buoc-hanh-khach.md` §5.5). Không áp R-DIR-01: đơn nháp nhận mọi loại |
| R-DRF-02 | Hai mục cùng `productId` và `usingDate` trong một request: `400 VALIDATION_ERROR`, `reason: DUPLICATE_ITEM` |
| R-DRF-03 | `allowPartial: false` (mặc định): mục đầu tiên vi phạm làm cả request lỗi với mã của vi phạm đó (`PRODUCT_NOT_FOUND`, `PRODUCT_UNAVAILABLE`, `DATE_OUT_OF_RANGE`, `VALIDATION_ERROR`); không tạo gì |
| R-DRF-04 | `allowPartial: true`: mục vi phạm bị bỏ và trả trong `rejectedItems[] {productId, usingDate, code, message}`. Không mục nào được nhận: `409 PRODUCT_UNAVAILABLE`, `details.rejectedItems` |
| R-DRF-05 | `expiresAt = createdAt + BOOKING_DRAFT_TTL_MINUTES` (mặc định 30), không gia hạn |
| R-DRF-06 | Snapshot giá người lớn và trẻ em ghi theo giá catalog lúc tạo |
| R-DRF-07 | Mỗi chủ giỏ có tối đa 5 đơn nháp còn hạn; tạo cái thứ 6 thì xoá cái cũ nhất. Đơn nháp đã hết hạn của chủ giỏ đó được dọn trong cùng lần tạo |
| R-DRF-08 | Chép vào giỏ theo §5; ghi sự kiện theo §9 |

### 4.2. Đọc, sửa

| Mã | Luật |
|---|---|
| R-DRF-10 | `GET /booking-drafts/{draftId}`: giá, `available` và `fares` lấy lại từ catalog ở mỗi lần đọc (giống `GET /cart`). Snapshot không đổi khi đọc |
| R-DRF-11 | Đơn nháp không có, hoặc của chủ giỏ khác: `404 BOOKING_DRAFT_NOT_FOUND`. Không phân biệt hai trường hợp |
| R-DRF-12 | Quá `expiresAt`: `410 BOOKING_DRAFT_EXPIRED`, `details.items[] {productId, taxonomy, inCart}`; `inCart` cho biết mục đó đang có trong giỏ của chủ giỏ. Web dùng để dẫn khách về giỏ hoặc về trang sản phẩm |
| R-DRF-13 | `PATCH /booking-drafts/{draftId}/items/{cartItemId}`: cùng body và luật với `PATCH /cart/items/{cartItemId}`; ghi lại snapshot bằng giá hiện tại (khách đã thấy giá mới). Không đổi giỏ |
| R-DRF-14 | Không thêm được mục vào đơn nháp đã có: muốn đặt thêm thì bấm Đặt ngay lại. `DELETE /booking-drafts/{draftId}/items/{cartItemId}` bỏ một mục (trang thanh toán dùng cho mục không còn đặt được, như với giỏ); không đổi mục giỏ đã chép. Bỏ mục cuối cùng thì đơn nháp bị xoá và response có `items` rỗng |

### 4.3. Hết hạn và dọn

| Mã | Luật |
|---|---|
| R-DRF-20 | Đơn nháp hết hạn không thanh toán được (`POST /bookings` trả `410 BOOKING_DRAFT_EXPIRED`) |
| R-DRF-21 | Khách sạn, vé máy bay của đơn nháp hết hạn không được giữ lại ở đâu. Web hiện "Phiên thanh toán đã hết hạn" và dẫn về trang sản phẩm (khách sạn) hoặc `/flights` (vé máy bay); khách chọn lại và bấm Đặt ngay để có đơn nháp mới với giá mới |
| R-DRF-22 | Tour, tiện ích của đơn nháp hết hạn vẫn nằm trong giỏ (§5). Web dẫn về `/cart` |
| R-DRF-23 | Bản ghi đơn nháp hết hạn của người đã đăng nhập bị xoá ở lần tạo đơn nháp kế tiếp của người đó (R-DRF-07) và bởi job đối soát đơn (xoá bản ghi hết hạn quá 1 ngày). Của khách chưa đăng nhập: Redis tự xoá theo TTL 3 ngày |

## 5. Chép vào giỏ khi Đặt ngay

Mục đích: khách không hoàn thành thanh toán thì tour, tiện ích nằm lại trong giỏ, dù rời đi bằng cách nào (đóng tab, bỏ ngang ở Stripe, thẻ bị từ chối, hết hạn giữ chỗ, huỷ đơn chưa trả).

| Mã | Luật |
|---|---|
| R-CPY-01 | Khi tạo đơn nháp, mỗi mục được nhận có `taxonomy` thuộc loại vào giỏ được: nếu giỏ của chủ giỏ **chưa có** mục cùng `productId` và `usingDate` thì thêm một mục giỏ với cùng số lượng, số khách, số đêm và snapshot giá |
| R-CPY-02 | Giỏ đã có mục cùng `productId` và `usingDate`: giữ nguyên mục giỏ, không cộng dồn, không ghi đè |
| R-CPY-03 | Việc chép nằm trong cùng thao tác ghi với việc tạo đơn nháp (cùng transaction với người đã đăng nhập). Chép không ghi thêm sự kiện |
| R-CPY-04 | Sửa mục của đơn nháp (R-DRF-13) không đổi mục giỏ đã chép |
| R-CPY-05 | Đơn `CONFIRMED` gỡ khỏi giỏ các mục cùng `productId` và `usingDate` với mục của đơn (luật sẵn có ở `settlement.py`, áp cho đơn từ giỏ lẫn đơn từ đơn nháp). Đơn `PAYMENT_FAILED`, `EXPIRED`, `CANCELLED` không gỡ gì |
| R-CPY-06 | Giỏ của khách chưa đăng nhập đã đủ 20 mục thì bỏ qua việc chép mục vượt, không làm lỗi việc tạo đơn nháp |

## 6. Thanh toán (`POST /bookings`)

| Mã | Luật |
|---|---|
| R-CHK-01 | Có `draftId`: thanh toán đúng các mục của đơn nháp đó. Không có `draftId`: thanh toán toàn bộ giỏ như hiện nay. Hai nguồn không bao giờ trộn |
| R-CHK-02 | `itemDetails[].cartItemId` là mã mục của nguồn đang thanh toán (mục giỏ hoặc mục đơn nháp) |
| R-CHK-03 | Kiểm luật, tính dòng giá, so snapshot (`PRICE_CHANGED`), gọi Stripe, một đơn giữ chỗ mỗi người: giữ nguyên trình tự ở `checkout-nhieu-buoc-hanh-khach.md` §8.3 |
| R-CHK-04 | Đơn nháp không thuộc người gọi: `404 BOOKING_DRAFT_NOT_FOUND`. Hết hạn: `410 BOOKING_DRAFT_EXPIRED` |
| R-CHK-05 | Đơn tạo từ đơn nháp: đơn nháp bị xoá trong cùng transaction ghi đơn giữ chỗ. Stripe lỗi hoặc ghi đơn lỗi thì đơn nháp còn nguyên |
| R-CHK-06 | `POST /bookings` luôn cần đăng nhập. Khách chưa đăng nhập bấm Thanh toán thì Web mở hộp đăng nhập ngay trên trang (không tải lại, thông tin đã nhập còn), rồi gửi lại request; BFF gộp dữ liệu khách trước khi chuyển tiếp (§8.4) |

## 7. Đặt lại (`fromBooking`)

`POST /booking-drafts {"fromBooking": "<referenceCode>"}`.

| Mã | Luật |
|---|---|
| R-RBK-01 | Đơn phải thuộc người gọi và đang `PAYMENT_FAILED` hoặc `EXPIRED`. Không thấy: `404 BOOKING_NOT_FOUND`. Trạng thái khác: `400 VALIDATION_ERROR`, `field: fromBooking`, `reason: NOT_REBOOKABLE` |
| R-RBK-02 | Mục của đơn nháp mới lấy `productId`, `usingDate`, số lượng, số đêm và số người lớn, trẻ em từ mục của đơn; giá tính lại theo catalog hiện tại |
| R-RBK-03 | Luôn chạy như `allowPartial: true`: mục không còn bán nằm trong `rejectedItems` |
| R-RBK-04 | Thông tin hành khách của đơn cũ không được chép sang (ngày sinh và giấy tờ không trả qua API); khách nhập lại ở trang thanh toán |
| R-RBK-05 | Cần đăng nhập (đơn luôn thuộc một tài khoản) |

## 8. Khách chưa đăng nhập

### 8.1. Định danh

Phiên khách của BFF (`vota_sid`, `anon_id`) chết sau 30 phút không hoạt động hoặc khi đóng trình duyệt, nên không dùng làm khoá cho dữ liệu 3 ngày. BFF phát thêm một cookie riêng:

| Cookie | Nội dung | HttpOnly | Secure | SameSite | Path | Max-Age |
|---|---|---|---|---|---|---|
| `vota_guest` | `guestId` (`g_` + 22 ký tự base64url, 128 bit ngẫu nhiên) | Có | Như `vota_sid` | `Lax` | `/` | `GUEST_BOOKING_TTL_DAYS` ngày (mặc định 3) |

| Mã | Luật |
|---|---|
| R-GST-01 | BFF phát `vota_guest` khi một request tới `/api/v1/cart*` hoặc `/api/v1/booking-drafts*` đến từ phiên chưa đăng nhập mà chưa có cookie. Request ghi (POST, PATCH, DELETE) đặt lại Max-Age |
| R-GST-02 | Với phiên chưa đăng nhập, BFF chuyển tiếp các request đó kèm `X-Service-Token` và `X-Guest-Id: <guestId>`. Client không tự đặt được hai header này (BFF xoá header cùng tên từ trình duyệt) |
| R-GST-03 | Backend chỉ tin `X-Guest-Id` khi `X-Service-Token` hợp lệ và giá trị khớp `^g_[A-Za-z0-9_-]{22}$`. Thiếu Bearer và thiếu cặp header hợp lệ: `401 UNAUTHENTICATED` như hiện nay. Có Bearer thì Bearer thắng, `X-Guest-Id` bị bỏ qua |
| R-GST-04 | `guestId` không được ghi xuống PostgreSQL, không vào log dạng đầy đủ (log 8 ký tự đầu), không gửi sang CDP, Insider, Stripe |
| R-GST-05 | CSRF, kiểm `Origin` của BFF áp như mọi request ghi khác (`hop-dong-tich-hop-auth.md` §7); khách có phiên `anonymous` nên có `csrfToken` |

### 8.2. Lưu trữ (Redis)

Redis riêng cho đặt chỗ (`BOOKING_REDIS_URL`, DB index riêng). Không cấu hình thì chạy trong bộ nhớ một tiến trình, chỉ cho development và test; production từ chối khởi động, cùng quy ước với `AUTH_REDIS_URL`.

| Key | Kiểu | TTL | Nội dung |
|---|---|---|---|
| `guest:cart:{guestId}` | string (JSON) | `GUEST_BOOKING_TTL_DAYS`, đặt lại mỗi lần ghi | `{cartId, updatedAt, items[]}`; mỗi mục có cùng trường với một dòng `app.cart_items` |
| `guest:draft:{draftId}` | string (JSON) | `GUEST_BOOKING_TTL_DAYS` | `{draftId, guestId, createdAt, expiresAt, items[]}` |
| `guest:drafts:{guestId}` | set | `GUEST_BOOKING_TTL_DAYS` | Các `draftId` của khách, để giới hạn số đơn nháp và để gộp |

| Mã | Luật |
|---|---|
| R-GST-10 | Giỏ khách có tối đa 20 mục; vượt thì `400 VALIDATION_ERROR`, `reason: CART_FULL` |
| R-GST-11 | "3 ngày" là thời gian Redis giữ dữ liệu. Hiệu lực thanh toán của đơn nháp khách vẫn là 30 phút (R-DRF-05, R-DRF-20); bản ghi còn lại sau đó chỉ để trả `410` kèm `details` |
| R-GST-12 | Luật loại sản phẩm, luật số khách, cách tính dòng giá của giỏ và đơn nháp khách giống hệt của người đã đăng nhập (cùng use case, khác adapter lưu trữ) |
| R-GST-13 | Response giỏ và đơn nháp của khách có `cdpUserId: null` |

### 8.3. Gộp khi đăng nhập

`POST /guest-bookings/merge`, chỉ BFF gọi: `X-Service-Token` + `Authorization: Bearer <token của tài khoản vừa đăng nhập>`, body `{"guestId": "g_…"}`.

| Mã | Luật |
|---|---|
| R-MRG-01 | Mục giỏ khách mà giỏ tài khoản chưa có (theo `productId` + `usingDate`) được thêm vào `app.cart_items`. Mục trùng: chỉ giữ một, là mục đang có trong tài khoản; mục của khách bị bỏ |
| R-MRG-02 | Đơn nháp khách còn hạn được chuyển vào `app.booking_drafts` với **cùng `draftId`** và cùng `expiresAt`, để trang thanh toán đang mở dùng tiếp. Đơn nháp đã hết hạn bị bỏ. Giới hạn 5 đơn nháp còn hạn (R-DRF-07) áp sau khi chuyển |
| R-MRG-03 | Xong thì xoá `guest:cart:*`, `guest:draft:*`, `guest:drafts:*` của `guestId` đó |
| R-MRG-04 | Idempotent: gọi lần hai với cùng `guestId` không tìm thấy gì và trả kết quả rỗng |
| R-MRG-05 | Ghi sự kiện theo §9. Response `{mergedCartItems, skippedDuplicates, mergedDrafts}` |
| R-MRG-06 | Mục giỏ khách có sản phẩm không còn trong catalog bị bỏ, không làm lỗi việc gộp |

### 8.4. BFF

| Mã | Luật |
|---|---|
| R-BFF-01 | Request tới `/api/v1/cart*`, `/api/v1/booking-drafts*`, `/api/v1/bookings*` từ phiên **đã đăng nhập** mà còn cookie `vota_guest`: BFF gọi gộp (§8.3) trước, rồi mới chuyển tiếp request; response xoá cookie `vota_guest` |
| R-BFF-02 | Gộp lỗi (Backend không phản hồi hoặc 5xx): giữ cookie để lần sau thử lại, vẫn chuyển tiếp request, ghi log |
| R-BFF-03 | Đăng xuất không xoá `vota_guest` và không tạo dữ liệu khách từ giỏ của tài khoản |

Hệ quả: Web không cần gọi gộp. Sau khi đăng nhập, Web tải lại giỏ (`GET /cart`) như hiện nay và nhận giỏ đã gộp.

## 9. Sự kiện CDP

| Thời điểm | Sự kiện |
|---|---|
| Thêm giỏ thành công, đã đăng nhập | `add_to_cart` như hiện nay |
| Tạo đơn nháp, đã đăng nhập | Một `add_to_cart` cho mỗi mục được nhận (`productId`, `taxonomy`, `quantity`, `unitPrice`, `usingDate` theo cùng quy ước với thêm giỏ). Chép vào giỏ không ghi thêm |
| Khách chưa đăng nhập thêm giỏ, tạo đơn nháp | Không ghi (FR-CDP-02) |
| Gộp khi đăng nhập | Một `add_to_cart` cho mỗi cặp (`productId`, `usingDate`) thực sự vào tài khoản: mục giỏ được thêm, và mục của đơn nháp được chuyển. Mục trùng bị bỏ không ghi; một cặp chỉ ghi một lần dù có ở cả giỏ lẫn đơn nháp |
| `PATCH` mục giỏ, mục đơn nháp; đọc; hết hạn | Không ghi |
| `purchase` | Không đổi (`so-do-luong-dat-cho-thanh-toan.md` §6.3) |

CDP lỗi không ảnh hưởng response, như các sự kiện duyệt khác.

## 10. Hợp đồng API (contract 1.13.0, chỉ thêm)

| Endpoint | Auth | Thay đổi |
|---|---|---|
| `GET /cart`, `POST /cart/items`, `PATCH`, `DELETE /cart/items/{cartItemId}` | Bearer **hoặc** khách (R-GST-03) | Nhận khách; `POST` thêm `422 DIRECT_BOOKING_ONLY`; `400 VALIDATION_ERROR reason CART_FULL` với khách |
| `POST /booking-drafts` | Bearer hoặc khách (`fromBooking` cần Bearer) | Mới |
| `GET /booking-drafts/{draftId}` | Bearer hoặc khách | Mới |
| `PATCH`, `DELETE /booking-drafts/{draftId}/items/{cartItemId}` | Bearer hoặc khách | Mới |
| `POST /guest-bookings/merge` | Service token + Bearer | Mới, chỉ BFF gọi; Web không sinh client |
| `POST /bookings` | Bearer | Thêm `draftId` tuỳ chọn; thêm `404 BOOKING_DRAFT_NOT_FOUND`, `410 BOOKING_DRAFT_EXPIRED` |

Schema:

- `CreateBookingDraftRequest`: `items[]` (mỗi mục là `AddCartItemRequest`), `allowPartial` (boolean), `fromBooking` (`ReferenceCode`). `oneOf` bắt buộc `items` hoặc `fromBooking`.
- `BookingDraft`: `draftId`, `cdpUserId` (string hoặc null), `expiresAt`, `items[]` (**dùng lại `CartItem`**; `cartItemId` là mã mục của đơn nháp), `itemCount`, `subtotal`, `total`, `currency`, `rejectedItems[]` (tuỳ chọn).
- `CartResponse.cdpUserId`: cho phép `null` (khách). Đây là nới kiểu của một trường v1, đã nằm trong đề xuất được chốt.
- `CheckoutRequest.draftId`: string, tuỳ chọn.
- `ErrorCode` thêm `DIRECT_BOOKING_ONLY` (422), `BOOKING_DRAFT_NOT_FOUND` (404), `BOOKING_DRAFT_EXPIRED` (410).
- `GuestMergeRequest {guestId}`, `GuestMergeResponse {mergedCartItems, skippedDuplicates, mergedDrafts}`.
- Tham số header `X-Guest-Id` khai báo cho các endpoint nhận khách.

Dùng lại `CartItem` cho mục đơn nháp là chủ ý: `CheckoutItemDetail.cartItemId`, `ValidationFieldError.cartItemId` và bộ luật dùng chung của Web và Backend không phải đổi, và trang thanh toán chạy cùng một code cho hai nguồn.

## 11. Database

- Bảng mới `app.booking_drafts (draft_id, cdp_user_id, created_at, expires_at)` và `app.booking_draft_items` (cùng cột và CHECK với `app.cart_items`, khoá ngoài `draft_id`, `UNIQUE (draft_id, product_id, using_date)`). `draft_id` do Backend cấp (không dùng DEFAULT khi gộp, R-MRG-02).
- Index `booking_drafts (cdp_user_id)`, `(expires_at)`. Quyền `vota_app` như `app.carts`.
- Migration `0007_booking_drafts.sql` (idempotent): tạo bảng, cấp quyền, xoá `app.cart_items` có sản phẩm `hotel`, `flight` (R-DIR-04).
- `db/verify.sql` thêm: giỏ không có `hotel`/`flight`; đoàn khách của mục đơn nháp 1–9 và có người lớn.
- Không có bảng cho khách chưa đăng nhập (R-GST-04). Không có bảng nhật ký job.

## 12. Backend

Theo phân lớp ở `docs/prd/architecture.md` §2.

- `domain/booking/`: `DIRECT_BOOKING_TAXONOMIES`, `is_cart_eligible`; `BookingDraft`; `DraftPolicy`.
- `application/booking/`: `CartOwner` (người dùng hoặc khách); `CartService` nhận `CartOwner`, từ chối loại đặt trực tiếp; `BookingDraftService` (`create`, `get`, `update_item`, `remove_item`); `MergeGuestBooking`; `CreateBookingHold` nhận `draft_id` tuỳ chọn.
- `application/ports/`: `CartRepository` và `BookingDraftRepository` khoá theo một chuỗi chủ giỏ; `GuestBookingStore` cho việc gộp.
- `infrastructure/persistence/`: adapter Postgres (người dùng) và adapter Redis hoặc bộ nhớ (khách) cho cùng hai port.
- `api/`: dependency `cart_owner` (Bearer → người dùng; service token + `X-Guest-Id` → khách; còn lại 401); route đơn nháp và gộp.
- Cấu hình: `BOOKING_DRAFT_TTL_MINUTES` (30), `GUEST_BOOKING_TTL_DAYS` (3), `BOOKING_REDIS_URL`.

## 13. Frontend

| Màn hình | Thay đổi |
|---|---|
| Trang chi tiết | Khách sạn: chỉ Đặt ngay. Tour, golf, combo: Thêm vào giỏ hàng và Đặt ngay. Đặt ngay gọi `POST /booking-drafts` rồi mở `/checkout?draft=<mã>` |
| `/flights` | Một nút Đặt ngay tạo một đơn nháp cho một hoặc hai chặng |
| Trang thanh toán | Nguồn là giỏ (`/checkout`) hoặc đơn nháp (`/checkout?draft=`). Đơn nháp: đồng hồ "Phiên thanh toán còn mm:ss" theo `expiresAt`; `410` → màn hình hết hạn (R-DRF-21, R-DRF-22); `404` → về trang chủ kèm thông báo. Nút quay lại: nguồn giỏ về `/cart`, nguồn đơn nháp về trang trước |
| Bấm Thanh toán khi chưa đăng nhập | Hộp đăng nhập trên trang; xong thì gửi lại `POST /bookings` |
| Trang giỏ | Bỏ khối "Thường được đặt cùng chuyến" và lời gọi `/recommendations` của trang giỏ. Thêm dòng giải thích khách sạn, vé máy bay được đặt trực tiếp. Khách chưa đăng nhập xem và sửa giỏ được |
| Trợ lý | Một nút **Thanh toán tất cả** (đơn nháp cho mọi mục đặt được, `allowPartial: true`). Thẻ và ghim bản đồ: khách sạn, vé máy bay có Đặt ngay; tour, golf, combo có Thêm vào giỏ và Đặt ngay; ngày theo lịch trình, số khách theo `intent.party` |
| Trang đơn | `PAYMENT_FAILED`, `EXPIRED`: nút **Đặt lại** (`fromBooking`) thay cho "Đặt lại từ giỏ" |
| Nhãn gợi ý | `add_to_cart`: "đã chọn để đặt" |

Thêm giỏ và Đặt ngay không còn bắt đăng nhập. Sau khi đăng nhập hoặc đăng xuất, Web tải lại giỏ.

## 14. Trường hợp biên

| Trường hợp | Hành vi |
|---|---|
| Hai tab bấm Đặt ngay hai sản phẩm | Hai đơn nháp độc lập, mỗi tab một `draftId` |
| Bấm Đặt ngay hai lần cùng vé và ngày | Hai đơn nháp; giỏ chỉ có một mục (R-CPY-02) |
| Giỏ đã có cùng vé, ngày với số khách khác | Mục giỏ giữ nguyên; đơn nháp dùng số khách vừa chọn |
| Đơn nháp nhiều mục, một mục hết bán trước khi thanh toán | `GET` trả `product.available: false` cho mục đó; Web khoá nút Thanh toán như với giỏ; `POST /bookings` trả `409 PRODUCT_UNAVAILABLE` |
| Đang có đơn giữ chỗ còn hạn | Tạo đơn nháp vẫn được; `POST /bookings` trả `409 BOOKING_PENDING_PAYMENT` như hiện nay |
| Khách đăng nhập ở trang thanh toán của một đơn nháp khách | BFF gộp trước `POST /bookings`; đơn nháp giữ nguyên `draftId` nên request đi tiếp |
| Khách đăng nhập khi đơn nháp khách đã hết hạn | Đơn nháp bị bỏ khi gộp; `POST /bookings` trả `404 BOOKING_DRAFT_NOT_FOUND`; Web về màn hình hết hạn chung |
| Đăng nhập ở hai tab cùng lúc | Gộp chạy hai lần, lần hai rỗng (R-MRG-04) |
| Đổi sang trình duyệt khác | Không có cookie `vota_guest` nên không thấy giỏ khách; không có cách khôi phục (chủ ý: giỏ khách gắn với trình duyệt) |
| Redis đặt chỗ không phản hồi | Request giỏ, đơn nháp của khách trả `503`; của người đã đăng nhập không bị ảnh hưởng |

## 15. Kiểm thử

| Tầng | Nội dung |
|---|---|
| Unit domain | Loại vào giỏ được; `DraftPolicy`; hết hạn |
| Unit application | `BookingDraftService` (tạo, `allowPartial`, trùng mục, giới hạn 5, chép vào giỏ, sự kiện); `CartService` từ chối loại đặt trực tiếp và chạy với khách; `CreateBookingHold` hai nguồn, xoá đơn nháp; `MergeGuestBooking` (trùng, hết hạn, idempotent, sự kiện); đặt lại |
| Contract | Response của endpoint mới khớp OpenAPI; mock mới qua `validate_contract.py` |
| Integration | Postgres: bảng đơn nháp, xoá cùng transaction với đơn giữ chỗ, migration `0007`. Redis: TTL và khoá của khách |
| Frontend | Nút theo loại sản phẩm; `startBooking`; trang thanh toán hai nguồn; màn hình hết hạn; đăng nhập lúc thanh toán; trang giỏ không còn khối gợi ý; BFF phát cookie khách, chuyển header, gộp |
| Chạy tay | Tám kịch bản trong kế hoạch, mục Nghiệm thu |

## 16. Ghi chú và ngoài phạm vi

- **Q11c — khách sạn trong lịch trình chưa có hạng phòng.** Trợ lý có thể gợi ý khách sạn ở cấp cơ sở lưu trú (không đặt được). Việc lịch trình trả về hạng phòng đặt được thuộc phần team trợ lý đang xây, không làm trong đợt này. Trong lúc chờ: nút Đặt ngay trên thẻ chỉ hiện khi sản phẩm đặt được; chưa có hạng phòng thì thẻ giữ lối sang trang chi tiết như hiện nay; Thanh toán tất cả bỏ mục đó và báo trong `rejectedItems`. Khi phần của team trợ lý xong, không phải sửa gì ở luồng đặt.
- Không làm danh sách lưu xem sau cho khách sạn, vé máy bay (người dùng quyết định).
- Không có thanh toán không cần tài khoản.
- Không ghép lịch sử duyệt ẩn danh vào CDP (`hop-dong-tich-hop-auth.md` §3.7 giữ nguyên); chỉ giỏ và đơn nháp được gộp, và sự kiện chỉ ghi từ lúc đã định danh.
