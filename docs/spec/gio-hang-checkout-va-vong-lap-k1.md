# Giỏ hàng, Checkout và vòng lặp gợi ý K1 — đặc tả kỹ thuật

**Phạm vi:** `src/backend/app/{domain,application,infrastructure,api}/booking*`, `src/backend/app/application/catalog/`,
`src/frontend/src/services/booking.ts` và các màn hình dùng nó.
**Phục vụ:** FR-BKG-01…04, FR-REC-02, FR-CAT-02; AC-BKG-01, AC-REC-02 (`docs/prd/requirements.md`).
**Nguồn sự thật khi tài liệu này lệch:** `src/shared/contracts/` (API), `db/vota_schema.sql` (DDL),
`docs/spec/hop-dong-tich-hop-backend.md` §7 (hành vi), `docs/spec/hop-dong-tich-hop-cdp.md` §5 (ghi purchase).

Tài liệu này giải thích **triển khai đã có trong code**, không phải hợp đồng đang thương lượng — đọc để biết
sửa chỗ nào, không phải để tra cứu chữ ký API (tra `contracts-guide.md` cho việc đó).

---

## 1. Bài toán và vì sao nó khó trước đây

Mục tiêu K1 (handbook §2, §10): khách đặt một khách sạn ở X, quay lại trang chủ, thấy gợi ý chuyển sang vé
máy bay và vé tham quan ở X. Trước bản vá này, vòng lặp đó là **giả**:

- Trang chi tiết đọc catalog cứng của frontend (29 sản phẩm), không có `productId` thật.
- Giỏ và đơn chỉ sống trong React state; backend không có `/cart*`, `/bookings*`.
- `purchase` không bao giờ được ghi vào `cdp.events`, nên `/recommendations` (đọc thẳng `cdp.events` mỗi
  request) không có gì để đổi.
- Trang xác nhận gọi một hàm mô phỏng (`calculateRecommendations`) thay vì gọi engine.

Engine gợi ý (`application/recommendation/`) đã đúng từ trước — nó đọc lịch sử không cache, nên purchase vừa
ghi có hiệu lực ngay ở request kế tiếp. Việc cần làm chỉ là **nối** phần giỏ/checkout còn thiếu vào đúng chỗ.

---

## 2. Bản đồ module

```
domain/booking/          luật thuần: đơn vị đặt được, cửa sổ ngày, lịch trống, thành tiền, mã tham chiếu
  errors.py                 BookingError và các lớp con — mỗi lớp map 1-1 sang một ErrorCode của contract
  rules.py                  bookable_product, ensure_open, calendar_open, line_total, reference_code, event_group_id

application/ports/       giao diện application phụ thuộc; infrastructure hiện thực
  product_catalog.py        ProductCatalog: get / get_many / children
  cart_repository.py        CartRepository: load / add / update / remove
  booking_repository.py     BookingRepository: reference_taken / save / find

application/booking/     use case
  cart.py                    CartService — thêm/sửa/xoá giỏ, gọi domain rules trước khi ghi
  checkout.py                Checkout, GetBooking — kiểm giỏ, ghi CDP, lưu booking, đọc lại đơn
  views.py                    chiếu Cart/Booking sang dict đúng hình dạng CartResponse/BookingResponse

application/catalog/
  use_cases.py                GetProductDetail — dựng variants[] cho property/route
  views.py                     product_summary / product_detail (ProductSummary, ProductDetail)

infrastructure/persistence/
  postgres_catalog.py          PostgresProductCatalog (SELECT cdp.products qua DATABASE_URL — vota_app)
  postgres_cart.py             PostgresCartRepository (app.carts, app.cart_items)
  postgres_bookings.py         PostgresBookingRepository (app.bookings, app.booking_items)

api/v1/routes/
  catalog.py                   GET /products/{id}   (công khai)
  cart.py                      GET|POST /cart, /cart/items, PATCH|DELETE /cart/items/{id}   (bắt buộc JWT)
  bookings.py                  POST /bookings, GET /bookings/{referenceCode}                  (bắt buộc JWT)
```

Frontend:

```
services/booking.ts        gọi 6 endpoint trên qua apiFetch (BFF); ApiError bọc Error Envelope;
                            isOpen/firstOpenDate lặp lại đúng luật lịch trống của domain/booking/rules.py
                            để hiển thị trước khi gửi request
context/TravelContext.tsx  cart, cartTotal, addToCart/removeFromCart/updateCartItem (async),
                            createBooking, loadBooking — nguồn sự thật là backend, không phải state cục bộ
components/detail/         ProductDetailView: gọi GET /products/{id}, hiện variants[] để chọn
components/cart/, checkout/, confirmation/   dùng dữ liệu backend; ConfirmationView gọi /recommendations thật
```

---

## 3. FR-CAT-02: chỉ đơn vị đặt được mới vào giỏ

`catalog.product_meta.is_bookable` (view SQL, xem `PRODUCT_SCHEMA.md` §4) coi `property` và `route` là **không
đặt được** — chỉ hạng phòng (`room`) và chuyến bay cụ thể (`flight`) mới `is_bookable = true`. `Product.is_bookable`
(`domain/catalog/models.py`) tính lại đúng công thức đó trong Python, không phụ thuộc view lúc runtime của giỏ:

```python
@property
def is_bookable(self) -> bool:
    return self.level not in ("property", "route") and self.attributes.get("ticketed") is not False and self.unit_price is not None
```

`domain/booking/rules.bookable_product()` gọi thuộc tính này trước bất kỳ thao tác giỏ nào. Gửi `productId` của
một property (khách sạn) thẳng vào `POST /cart/items` nhận **`400 VALIDATION_ERROR`**, `details.reason =
"NOT_BOOKABLE_LEVEL"`, message tiếng Việt "Vui lòng chọn một hạng phòng hoặc chuyến bay cụ thể để đặt."

Vì vậy `GET /products/{id}` (`application/catalog/use_cases.GetProductDetail`) khi trả một property hoặc route
phải kèm `variants[]` — danh sách con `is_bookable` còn bán, sắp theo giá tăng dần:

```python
if not product.is_bookable:
    variants = sorted(
        (child for child in await self.catalog.children(product.product_id)
         if child.is_bookable and child.available and child.unit_price is not None
         and (child.available_to is None or child.available_to >= today)),
        key=lambda child: (child.unit_price, child.available_from or today, child.name),
    )
```

Đây là trường mới duy nhất thêm vào contract (`ProductDetail.variants[]`, `schemas/catalog.yaml`) — tương thích
ngược, không đổi field nào có sẵn. Frontend (`ProductDetailView.tsx`) bắt buộc chọn một phần tử của `variants[]`
trước khi bấm "Thêm vào giỏ"/"Đặt ngay"; nếu sản phẩm tự đặt được (vé, combo, golf) thì `variants` rỗng và chính
nó là đơn vị đưa vào giỏ.

---

## 4. AC-BKG-01: kiểm lịch trống, không chỉ cửa sổ bán

Hai lớp kiểm tra riêng, cả hai đều nằm ở `domain/booking/rules.py` và chạy **cả lúc thêm giỏ lẫn lúc checkout**
(giá và lịch có thể đổi giữa hai bước):

1. **Cửa sổ bán** — `using_date` phải nằm trong `[available_from, available_to]`.
2. **Lịch 30 ngày** (`attributes.availability`, chỉ có ở `room`, `attraction`, `golf`) — mọi đêm/ngày dùng phải
   là `"1"` trong `calendar`. Hotel kiểm `nights` đêm liên tiếp từ `using_date`; loại khác kiểm đúng
   `using_date`.

```python
def calendar_open(availability: dict | None, start: date, days: int) -> bool:
    if not isinstance(availability, dict):
        return True                      # không có lịch (property, flight, combo…) → không chặn
    calendar, first = availability.get("calendar"), availability.get("from")
    i = (start - date.fromisoformat(str(first))).days
    return 0 <= i and i + days <= len(calendar) and all(c == "1" for c in calendar[i:i + days])
```

Cùng thuật toán với `open_nights()` trong `src/data_collection/seed/catalog_meta.py` — seed và runtime đọc
lịch giống hệt nhau. Vi phạm trả **`409 PRODUCT_UNAVAILABLE`**; ra ngoài cửa sổ bán trả **`422
DATE_OUT_OF_RANGE`** kèm `availableFrom`/`availableTo`.

Frontend lặp lại đúng công thức này ở `services/booking.ts` (`isOpen`, `firstOpenDate`) để tô đỏ/ẩn lựa chọn
**trước** khi gửi request — nhưng đây chỉ là hiển thị trước; backend luôn kiểm lại, không tin client.

---

## 5. Checkout: thứ tự bắt buộc và bù trừ

`application/booking/checkout.Checkout.__call__` theo đúng thứ tự `hop-dong-tich-hop-cdp.md` §5:

```
1. Load giỏ, chặn nếu rỗng (400 CART_EMPTY)
2. Với mỗi dòng: bookable_product() → so giá với snapshot lúc thêm giỏ (409 PRICE_CHANGED nếu lệch)
                 → ensure_open() (409/422 nếu hết chỗ)
3. Dựng PurchaseEvent cho mỗi dòng, TẤT CẢ dùng chung MỘT event_group_id mới (§6 bên dưới)
4. commit_with_purchase_events(cdp, events, lambda: bookings.save(booking))
     — ghi purchase sang CDP TRƯỚC
     — commit thành công → lưu app.bookings + app.booking_items, xoá giỏ, CÙNG một transaction Postgres
     — CDP lỗi → không có gì được ghi, 500 INTERNAL_ERROR retryable=true, giỏ giữ nguyên
     — CDP ghi được nhưng bước 4 lỗi → cdp.cancel_purchases(events) rồi 500 (bù trừ, không để booking
       thiếu event)
5. Trả BookingResponse — event đã có trong CDP TRƯỚC KHI response này rời server, nên
   GET /recommendations gọi ngay sau đó (K1) đã thấy lượt đặt.
```

`commit_with_purchase_events` (`application/booking/purchase_events.py`) đã tồn tại từ trước bản vá này nhưng
chưa có ai gọi — đây là mảnh ghép còn thiếu duy nhất ở tầng use case.

---

## 6. Vì sao chỉ một `event_group_id` mỗi checkout

Handbook và `hop-dong-tich-hop-backend.md` §7.2 (bản gốc) mô tả gom nhóm theo **điểm đến** — giỏ nhiều điểm đến
thì mỗi điểm đến một `eventGroupId`. Nhưng DDL (`db/vota_schema.sql`) ràng buộc:

```sql
CREATE TABLE app.bookings (
    ...
    event_group_id   text NOT NULL UNIQUE,   -- một booking = một event_group_id
    ...
);
```

`app.bookings` là 1-1 với `event_group_id`. Không đổi DDL thì không thể tách nhiều mã cho một booking. Quyết
định: **theo DDL** — một checkout sinh một mã `WEB<YYYYMMDD><6 ký tự>` (`domain/booking/rules.event_group_id`),
dùng chung cho mọi `BookingGroup` trong response (mỗi nhóm vẫn tách theo `destination` để hiển thị, chỉ
`eventGroupId` là chung). Đã cập nhật `docs/spec/hop-dong-tich-hop-backend.md` §7.2 theo hướng này; không lệch
PRD vì đây là chọn giữa hai tài liệu kỹ thuật cùng cấp (DDL thắng theo AGENTS.md mục 2).

Hệ quả cần nhớ khi sửa code sau này: đặt tiếp một dịch vụ cho **cùng chuyến** ở một checkout **khác** sẽ sinh
`event_group_id` mới — engine gợi ý coi đó là chuyến riêng. Đây là hạn chế đã biết, chưa xử lý (mục "Còn lại"
trong `history/2026-09-24-noi-vong-dat-cho-goi-y-k1.md`).

---

## 7. Vì sao `line_total` không đọc từ DB

`app.booking_items.line_total` là cột **sinh tự động**:

```sql
line_total  numeric(14,2) GENERATED ALWAYS AS (unit_price * quantity) STORED,
```

Cột này không nhân số đêm — đúng cho vé/chuyến bay nhưng sai cho khách sạn. Backend không bao giờ đọc cột
này để trả về client; `application/booking/views.booking_line_total()` luôn tính lại bằng
`domain/booking/rules.line_total(unit_price, price_unit, quantity, nights)`, cùng công thức với giỏ
(`cart_view`) — `PER_NIGHT` mới nhân `nights`, mọi đơn vị khác bỏ qua (đúng `hop-dong-tich-hop-backend.md`
§2.6). Không sửa DDL vì cột sinh này không lỗi về mặt lưu trữ, chỉ không đủ dùng để hiển thị trực tiếp.

---

## 8. Error Envelope: domain lỗi → HTTP

`domain/booking/errors.py` định nghĩa một cây lỗi (`BookingError` và các lớp con), mỗi lớp mang đúng
`code` là một `ErrorCode` của contract. `api/errors.py` có một handler riêng (`booking_error`) map `code` sang
HTTP status theo đúng bảng `hop-dong-tich-hop-backend.md` §8.2:

```python
_BOOKING_STATUS = {
    "VALIDATION_ERROR": 400, "CART_EMPTY": 400, "PRODUCT_NOT_FOUND": 404, "CART_ITEM_NOT_FOUND": 404,
    "BOOKING_NOT_FOUND": 404, "PRODUCT_UNAVAILABLE": 409, "PRICE_CHANGED": 409, "DATE_OUT_OF_RANGE": 422,
    "INTERNAL_ERROR": 500,
}
```

Use case không bao giờ tự dựng `JSONResponse` — nó `raise` đúng lớp lỗi domain, và `install_error_handlers`
(gọi một lần trong `main.py`) là nơi duy nhất biết HTTP. Thêm một lỗi mới: thêm một lớp trong
`domain/booking/errors.py`, một dòng trong `_BOOKING_STATUS`/`_BOOKING_MESSAGES`, xong — không đụng route.

Frontend (`services/booking.ts` `ApiError`) đọc lại đúng `error.code`/`error.message`/`error.retryable` và ném
ra cho component tự quyết định hiển thị (`CheckoutView` hiện `submitError` là chuỗi tiếng Việt thẳng từ
backend, không tự dịch).

---

## 9. Đường dữ liệu đầy đủ một lượt đặt (để debug)

```
FE: mở /product/{id}
  → GET /products/{id}                          [application/catalog/use_cases.py]
  → property/route: hiện variants[], chọn 1 hạng phòng

FE: "Thêm vào giỏ hàng"
  → POST /cart/items { productId: <variant>, usingDate, quantity, nights? }
  → CartService.add: bookable_product() → stay_nights() → ensure_open()
  → PostgresCartRepository.add: INSERT ... ON CONFLICT (cart_id, product_id, using_date) DO UPDATE quantity += …
  → BehaviourTracker.track_add_to_cart() ghi add_to_cart sang CDP Ở NỀN (không chặn response)
  → trả CartResponse đầy đủ (cart_view: giá/tình trạng luôn tải lại từ catalog, không tin snapshot)

FE: "Xác nhận đặt chỗ"
  → POST /bookings { contact, itemDetails[] }
  → Checkout: xem §5 ở trên
  → app.cart_items bị xoá TRONG CÙNG transaction với INSERT app.bookings/app.booking_items
  → trả 201 BookingResponse (đã có purchase trong cdp.events)

FE: điều hướng /booking/{referenceCode}
  → dùng response 201 đang có trong state, hoặc GET /bookings/{referenceCode} nếu tải lại trang
  → SAU KHI đơn hiển thị: GET /recommendations?k=4&destination=<groups[0].destination>
  → RecommendForUser đọc cdp.events KHÔNG CACHE → thấy purchase vừa ghi
  → strategy=cross_vertical, loại bỏ taxonomy đã đặt, because[0] trỏ về sản phẩm vừa mua
```

Muốn quan sát trực tiếp: `SELECT event_name, product_id, event_group_id, using_date FROM cdp.events WHERE
cdp_user_id = '<VP…>' ORDER BY "timestamp" DESC LIMIT 5;` ngay sau một lượt đặt qua UI.

---

## 10. Test map (đọc trước khi sửa)

| Muốn kiểm | File |
|---|---|
| Luật lịch trống, đơn vị đặt được, thành tiền (thuần, không DB) | `src/backend/tests/unit/domain/test_booking_rules.py` |
| Giỏ, checkout, bù trừ, **vòng K1 đầu-cuối trên bản giả** | `src/backend/tests/unit/application/test_booking.py` |
| HTTP status, Error Envelope, auth | `src/backend/tests/unit/api/test_booking_routes.py` |
| Adapter Postgres thật (`RUN_POSTGRES_INTEGRATION=1`) | `src/backend/tests/integration/test_booking_postgres.py` |
| Bản giả dùng chung (CDP ghi+đọc trên cùng kho, giỏ/booking in-memory) | `src/backend/tests/fakes/booking.py` |
| Luật hiển thị lịch trống + mapping response phía FE | `src/frontend/tests/unit/bookingService.test.ts` |

`test_booking.py::test_booking_a_room_turns_recommendations_to_the_rest_of_that_trip` là test quan trọng nhất
trong bộ này — nó dựng `RecommendForUser` thật (không mock) trên cùng `RecordingCdp` mà `Checkout` vừa ghi vào,
và khẳng định đúng AC-REC-02.

---

## 11. Những chỗ cố ý chưa làm

- **Cache user vector** (`[P3]`, spec S5) — chưa cần: p95 đo thật ở local là 143 ms, dưới 300 ms.
- **Gộp `event_group_id` qua nhiều checkout cùng chuyến** — bị chặn bởi DDL (§6); cần đổi schema mới làm được.
- **`POST /events` (`product_view`) và `/products/{id}/similar`** — chưa có route; `DebugPanel.tsx` vẫn đọc
  simulator cũ, chưa nối.
- **Trợ lý AI thêm thẳng khách sạn (property) vào giỏ** — giờ bị backend từ chối (`NOT_BOOKABLE_LEVEL`); người
  dùng phải mở trang chi tiết để chọn phòng. `useAssistantCart.ts` chưa tự chọn hộ.
