# Hợp đồng tích hợp CDP

**Phiên bản:** 1.0  
**Người tạo:** mihhquan  
**Bên cung cấp:** CDP clone (`src/cdp_clone`)  
**Bên sử dụng:** Team Backend (qua `CdpClient`), Team Data (seed), Team Recommendation  
**Giao thức:** REST/JSON qua HTTP, chỉ trong mạng nội bộ  
**Xác thực:** `X-Service-Token`  
**Mã hóa:** UTF-8  
**Prefix:** `/cdp/v1`  
**Ngày:** `2026-09-16`  
**Múi giờ:** lưu và trả UTC

> **Cập nhật 20/09/2026 — đọc trước.** Tuần 1 CDP clone **không chạy như service HTTP**: nó là schema `cdp` trong database `vota`, Backend vào qua `CdpClient` với adapter `LocalCdpClient` và connection riêng `CDP_DATABASE_URL` (handbook §6, `AGENTS.md` §6, `docs/DATABASE_SCHEMA.md`). Vì vậy §3 (bề mặt API), §8 (`X-Service-Token`) và §9.2 (thứ tự khởi động) **chưa áp dụng ở tuần 1** — chúng là hợp đồng cho `HttpCdpClient` khi lên CDP thật hoặc khi tuần 3–4 cần test adapter HTTP. Mọi phần còn lại (§1.1–§1.4, §2, §4 quy tắc ghi nền, §5 bù trừ `purchase`, §6 đọc lịch sử, §10, §12) vẫn nguyên giá trị vì chúng nói về *hành vi*, không phải *giao thức*. Xem §13.
>
> Tài liệu này chốt cách hành vi người dùng đi từ Web tới CDP clone và cách Backend đọc lại để gợi ý. Luồng đã chốt là **Web → Backend → CDP**: Web không bao giờ gọi CDP clone.
>
> Bản máy đọc được: `src/shared/contracts/cdp-clone.openapi.yaml` (CDP clone) và `src/shared/contracts/openapi.yaml` (endpoint Backend liên quan). Khi tài liệu này và OpenAPI mâu thuẫn, **OpenAPI thắng** và tài liệu phải được sửa.

---

## 1. Phạm vi trách nhiệm

### 1.1. CDP clone chịu trách nhiệm

- Là **system of record** cho `events` và `profiles` (handbook §3, §6), trong PostgreSQL riêng.
- Giữ event vĩnh viễn, không TTL. TTL 90/730 ngày là việc của Insider clone.
- Kiểm tra trường bắt buộc theo `eventName`; một event sai thì không ghi event nào của request đó.
- Chống trùng theo `(cdpUserId, eventId)`.
- Huỷ event (đánh dấu, không xoá) để Backend bù trừ khi booking thất bại.
- Chỉ nhận request có `X-Service-Token` hợp lệ.

### 1.2. Backend chịu trách nhiệm

- Là **cổng duy nhất** giữa Web và CDP clone. Mọi truy cập đi qua port `CdpClient`; không đọc database của CDP clone.
- Xác thực JWT người dùng và tự điền `cdpUserId`, `timestamp`, `eventId`.
- Lấy `taxonomy` và `unitPrice` từ catalog, không tin giá trị client gửi.
- Ghi `purchase` đồng bộ và bù trừ khi commit booking lỗi (§5).
- Ghi hành vi duyệt web ở nền, không để CDP làm chậm hay làm lỗi request (§4).
- Đọc lịch sử có giới hạn và có đường lui khi CDP lỗi (§6).
- Chuyển tiếp `X-Request-ID` sang CDP clone.

### 1.3. Web chịu trách nhiệm

- Gọi `POST /api/v1/events` với `product_view` khi người dùng **thật sự mở** trang chi tiết. Không gọi khi prefetch, SSR hay render phía server.
- Không gửi event `search`, `add_to_cart`, `purchase`: Backend tự ghi khi xử lý `/search`, `/cart/items`, `/bookings`.
- Không biết URL hay token của CDP clone.

### 1.4. Team Agent chịu trách nhiệm

- Tìm kiếm **không gắn danh tính** (`hop-dong-tich-hop-itinerary-assistant.md` §2.1), để lượt tìm của Agent không bị ghi thành hành vi người dùng: mode `inprocess` gọi engine Search trong tiến trình, không qua route nên không ghi event `search`; mode `http` gọi `/api/v1/search` **không kèm JWT**.

### 1.5. Team Data chịu trách nhiệm

- ~~Seed event lịch sử và profile qua API CDP clone bằng service token, không ghi thẳng vào database.~~ **Đổi 20/09:** tuần 1 CDP clone là database, nên `src/data_collection/seed` ghi thẳng SQL vào `cdp.*` bằng `SEED_DATABASE_URL` (superuser). Đây là job nạp dữ liệu, không phải code app; khi lên CDP thật nó thành job sync gọi `CdpClient`. Quy tắc "code app chỉ đi qua `CdpClient`" ở §1.2 không đổi.
- Bảo đảm `cdpUserId` của 4 tài khoản demo (`docs/product.md` §2) khớp giữa bảng `users` của Backend và dữ liệu seed trong CDP clone.

### 1.6. Ngoài phạm vi

- Ghi hành vi của khách chưa đăng nhập và ghép lịch sử ẩn danh vào tài khoản.
- Rate limit theo người dùng.
- Đẩy dữ liệu sang Insider clone.
- Chuyển `products`, `users`, `bookings`, `product_vectors` vào CDP clone (§11).

---

## 2. Luồng dữ liệu

```text
Web ── JWT ──> Backend /api/v1 ──── CdpClient, X-Service-Token, X-Request-ID ───> CDP clone /cdp/v1 ──> PostgreSQL
                   │                                                                  ^                 (events, profiles)
                   │  Recommendation đọc lịch sử (có giới hạn, có đường lui)          │
                   └──────────────────────────────────────────────────────────────────┘
Seed / job ── X-Service-Token ──────────────────────────────────────────────────────────┘
```

| Event | Phát sinh ở | Backend ghi khi nào | Cách ghi | CDP lỗi thì |
|---|---|---|---|---|
| `product_view` | `POST /api/v1/events` | `productId` có trong catalog | Nền | Bỏ event, ghi log; Web vẫn nhận `202` |
| `search` | `POST /api/v1/search` | Có JWT, `offset = 0`, `query` không rỗng | Nền | Bỏ event, ghi log; response search không đổi |
| `add_to_cart` | `POST /api/v1/cart/items` | Sau khi thêm giỏ thành công | Nền | Bỏ event, ghi log; response giỏ không đổi |
| `purchase` | `POST /api/v1/bookings` | Trước khi commit booking | Đồng bộ | Không tạo booking, trả `500 INTERNAL_ERROR` `retryable: true` |

Thêm giỏ thất bại (`404`, `409`, `422`) không ghi `add_to_cart`. `PATCH`/`DELETE /cart/items` không ghi event.

---

## 3. Bề mặt API CDP clone

> Bề mặt này là **tạm**: chưa có tài liệu API CDP thật của V-OTA (§11). Tên trường giữ theo handbook §6.

| Endpoint | Mục đích |
|---|---|
| `POST /cdp/v1/events` | Ghi 1–100 event |
| `GET /cdp/v1/users/{cdpUserId}/events` | Lịch sử mới nhất trước; lọc `eventName`, `since` (gồm), `until` (không gồm), `includeCancelled` (mặc định `false`); `limit` 1–500, `offset` |
| `PUT /cdp/v1/users/{cdpUserId}/events/{eventId}/cancellation` | Đánh dấu huỷ |
| `GET /cdp/v1/profiles/{cdpUserId}` | Đọc hồ sơ |
| `PUT /cdp/v1/profiles/{cdpUserId}` | Tạo hoặc thay toàn bộ hồ sơ |

### 3.1. `UserEvent`

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `eventId` | string ≤ 128 | Khóa chống trùng, duy nhất theo `cdpUserId` |
| `cdpUserId` | string ≤ 64 | Bắt buộc |
| `eventName` | `purchase` \| `add_to_cart` \| `product_view` \| `search` | Cùng enum với `because[].event` |
| `timestamp` | date-time | Bỏ trống thì CDP dùng thời điểm nhận |
| `productId` | string \| null | Không đối chiếu catalog: handbook §6 yêu cầu có event trỏ tới sản phẩm đã xóa |
| `taxonomy` | enum \| null | |
| `eventGroupId` | string \| null | Gom nhóm chuyến đi |
| `quantity` | integer ≥ 1 \| null | |
| `unitPrice` | number ≥ 0 \| null | VND |
| `usingDate` | date \| null | |
| `searchQuery` | string ≤ 500 \| null | Chờ xác nhận (§11) |
| `cancelledAt` | date-time \| null | Chỉ có trong response. Chờ xác nhận (§11) |

Trường bắt buộc theo `eventName`:

| `eventName` | Bắt buộc ngoài `cdpUserId` |
|---|---|
| `search` | `searchQuery` |
| `product_view` | `productId`, `taxonomy` |
| `add_to_cart` | `productId`, `taxonomy`, `quantity` |
| `purchase` | `eventId`, `productId`, `taxonomy`, `eventGroupId`, `quantity`, `unitPrice`, `usingDate` |

### 3.2. Quy ước `eventId` của Backend

| Event | `eventId` |
|---|---|
| `purchase` | `purchase:{bookingItemId}` |
| `product_view`, `search`, `add_to_cart` | `{eventName}:{uuid}` sinh một lần khi nhận request |

### 3.3. Chống trùng và huỷ

1. Gửi lại cùng `(cdpUserId, eventId)` trả `201` với `status: "duplicate"`; bản ghi đầu được giữ, payload mới bị bỏ qua.
2. Huỷ không xoá event. Gọi huỷ lần nữa trả `200` và giữ nguyên `cancelledAt` lần đầu.
3. Event đã huỷ **không xuất hiện** trong lịch sử trừ khi `includeCancelled=true`. Recommendation không bao giờ dùng event đã huỷ.
4. Ghi lại một `eventId` đã huỷ vẫn trả `duplicate` và event vẫn ở trạng thái huỷ.
5. Huỷ event không tồn tại hoặc của khách khác trả `404 NOT_FOUND`.

### 3.4. Profile

Thuộc tính theo handbook §6: `lifecycleStage`, `daysSinceLastBooking`, `lifetimeOrderCount`, `vinclubTier`, `purchasedVerticals`, `homeCity`, `lastDestination`, `emailOptin`, `smsOptin`, `pushOptin`, `gdprOptin`.

- `PUT` thay toàn bộ; trường không gửi thành `null`, `purchasedVerticals` thành `[]`.
- Profile là **snapshot** do seed/job ghi, không tự cập nhật theo event. Recommendation tính từ events, không dựa vào các trường tổng hợp của profile.

### 3.5. Lỗi

Dùng envelope chung của `hop-dong-tich-hop-backend.md` §8.1.

| HTTP | Mã | Khi nào |
|---:|---|---|
| 400 | `VALIDATION_ERROR` | Sai schema, thiếu trường theo `eventName`, trùng `eventId` trong cùng request. `details.fields`, `details.eventIndex` |
| 401 | `INVALID_TOKEN` | Thiếu hoặc sai `X-Service-Token` |
| 404 | `NOT_FOUND` | Huỷ event không tồn tại; profile chưa có |
| 500 | `INTERNAL_ERROR` | Lỗi không lường trước, `retryable: true` |

---

## 4. Ghi hành vi duyệt web

### 4.1. `POST /api/v1/events` (Backend)

```http
POST /api/v1/events
Authorization: Bearer <jwt>    # bắt buộc
Content-Type: application/json

{ "eventName": "product_view", "productId": "5febedf3-74ba-5200-a5ec-2a6ab5162acb" }
```

| Tình huống | Response |
|---|---|
| Hợp lệ | `202`, không body. Không bảo đảm CDP đã lưu |
| Thiếu hoặc sai JWT | `401 INVALID_TOKEN` / `TOKEN_EXPIRED` |
| `productId` không có trong catalog | `404 PRODUCT_NOT_FOUND`, `details.productId`; không ghi event |
| `eventName` khác `product_view`, hoặc có trường lạ | `400 VALIDATION_ERROR` |

`eventName` chỉ nhận `product_view`. Thêm giá trị là thay đổi tương thích ngược nhưng phải cập nhật OpenAPI trước.

### 4.2. Quy tắc ghi nền

1. Request người dùng **không chờ** CDP. Backend đưa event vào hàng đợi trong bộ nhớ rồi trả response.
2. Hàng đợi có giới hạn (`CDP_EVENT_QUEUE_SIZE`, mặc định 1000). Đầy thì bỏ event mới và ghi log `reason=queue_full`.
3. Worker gửi tối đa 100 event mỗi lần gọi CDP, gom theo `X-Request-ID` gốc để truy vết đúng.
4. CDP lỗi thì bỏ lô đó và ghi log; **không retry**, để CDP đang chậm không bị dồn thêm tải.
5. Khi tắt Backend, chờ gửi nốt tối đa 2 giây; phần còn lại bị bỏ và ghi log `reason=shutdown`.
6. Event duyệt web vì vậy có thể **đến trễ vài trăm mili-giây hoặc mất**. Đây là đánh đổi đã chấp nhận.

---

## 5. Ghi `purchase` và bù trừ

`purchase` chỉ ghi khi Stripe **đã thu tiền** (FR-BKG-03, FR-BKG-06). Tạo đơn giữ chỗ (`POST /bookings`) không ghi event nào. Luồng đầy đủ: `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md` §6.3, §7.2c, §9.2.

```text
Webhook checkout.session.completed (hoặc job đối soát thấy phiên đã trả)
1. Khoá đơn, kiểm số tiền; commit payment SUCCEEDED             (DB biết tiền đã về)
2. CdpClient.record_purchases(events), eventId = purchase:{bookingItemId}
                                     ── lỗi ──> KHÔNG huỷ event; đơn giữ PENDING_PAYMENT + payment SUCCEEDED;
                                                webhook trả 500, Stripe gửi lại / job đối soát chạy lại
3. Commit đơn CONFIRMED, xoá các mục đã đặt khỏi giỏ
                                     ── lỗi ──> KHÔNG huỷ event; thử lại như trên (lần sau CDP trả duplicate)

Khách huỷ đơn đã CONFIRMED (trong hạn)
4. Commit CANCELLED + payment REFUND_PENDING → Refund API
5. CdpClient.cancel_purchases(events) ── lỗi ──> log WARNING; job đối soát gọi lại tới khi
                                                ghi được purchase_events_cancelled_at
```

| Tình huống | Kết quả | Người dùng thấy |
|---|---|---|
| Thu tiền, CDP ghi xong, commit xong | Đơn `CONFIRMED`, event khớp | Trang xác nhận |
| CDP lỗi ở bước 2 | Đơn `PENDING_PAYMENT` + payment `SUCCEEDED`; có thể đã có event nếu CDP ghi mà không trả lời kịp | "Đã nhận thanh toán, đang xác nhận đơn"; tự chuyển `CONFIRMED` khi CDP hồi phục |
| Commit lỗi ở bước 3 | Event đã ghi, đơn chưa `CONFIRMED` | Như trên; lần thử lại nhận `duplicate` rồi commit |
| Webhook gửi trùng | Không đổi gì, không có event thứ hai | — |
| Khách huỷ, CDP lỗi ở bước 5 | Đơn `CANCELLED`, event chưa huỷ | "Đã huỷ đơn"; gợi ý có thể còn dùng chuyến này tới khi job huỷ xong |

**Vì sao không bù trừ ở bước 2–3** (khác bản cũ "commit lỗi thì huỷ event"): tiền đã thu nên đơn chắc chắn phải được xác nhận. Theo §3.3 mục 4, ghi lại một `eventId` đã huỷ vẫn trả `duplicate` và event **vẫn huỷ**, nên "huỷ rồi thử lại" sẽ tạo đơn `CONFIRMED` mà Recommendation không bao giờ thấy. Giữ event và thử lại commit thì hai bên sớm muộn cũng khớp (NFR-REL-02). Hàm `commit_with_purchase_events` (ghi → commit → lỗi thì huỷ) vẫn còn trong `application/booking/purchase_events.py` cho đường chưa có tiền; đường sau thanh toán dùng `record_then_commit`.

`LocalCdpClient` (adapter hiện tại) không có cột `cancelledAt` trong DDL clone nên `cancel_purchases` **xoá** event khớp `event_group_id` + `product_id` + `using_date`; `HttpCdpClient` sau này gọi API huỷ của CDP thật (§3.3 mục 2).

---

## 6. Đọc lịch sử cho Recommendation

1. Đọc tối đa **500 event** mới nhất cho mỗi lần tính, có thể thu hẹp bằng `since`, để giữ p95 `/recommendations` dưới 300 ms.
2. Không bao giờ dùng event đã huỷ (mặc định CDP đã lọc).
3. CDP lỗi hoặc timeout: `/recommendations` vẫn trả `200` với `strategy: "popular"`, `because: []`, `diagnostics.coldStart: true`, `eventsUsed: 0`. Không trả `500` vì lỗi CDP.
4. Phân biệt "CDP lỗi" với "chưa có lịch sử": cả hai cho `popular`, nhưng chỉ lỗi CDP mới ghi log `WARNING`.
5. Nếu sau này cache lịch sử, phải xoá cache của người dùng ngay khi ghi `purchase` thành công, để khoảnh khắc K1 (đặt xong, gợi ý đổi ngay) vẫn đúng.

---

## 7. Độ sẵn sàng và hiệu năng

| Hạng mục | Quy tắc |
|---|---|
| Timeout gọi CDP | `CDP_TIMEOUT_SECONDS`, mặc định 2 giây, áp cho mọi lời gọi |
| Retry | Không retry trong một request. `purchase` được thử lại nhờ Stripe gửi lại webhook và job đối soát (an toàn nhờ chống trùng); event duyệt web bị bỏ |
| Checkout khi CDP sập | Tạo đơn giữ chỗ và thanh toán vẫn chạy; đơn dừng ở `PENDING_PAYMENT` + payment `SUCCEEDED` tới khi ghi được `purchase`. Đơn `CONFIRMED` không bao giờ thiếu event |
| Search, giỏ, xem sản phẩm khi CDP sập | Không ảnh hưởng |
| Gợi ý khi CDP sập | Đường lui `popular` (§6) |
| `POST /api/v1/bookings` | Vẫn trong ngân sách p95 1 giây, gồm cả lời gọi CDP |

**Adapter đọc tuần 1 (`PostgresCdpReader`, từ 2026-09-28).** Dòng timeout ở trên áp như sau:

- Mọi lần đọc dùng `connect_timeout = max(2, ceil(CDP_TIMEOUT_SECONDS))`. libpq chỉ nhận số giây nguyên và tối thiểu 2.
- Chỉ lần đọc lịch sử theo người dùng (`events_for_user`) thêm `statement_timeout = CDP_TIMEOUT_SECONDS`, đặt bằng `set_config('statement_timeout', …, true)` (tức `SET LOCAL`) trong transaction trước câu `SELECT`. Cách này không ghi đè `options` sẵn có trong `CDP_DATABASE_URL` và đi qua được pooler chế độ transaction (PgBouncer, Neon pooler). `purchase_events` (đọc lô lúc khởi động) không có giới hạn này.
- `all_events(until=None)` (từ 2026-09-29) chỉ dành cho đánh giá offline (`src/evaluation/recsys_bench`), không gọi trong request: đọc lô mọi event, `timestamp < until` nếu có, xếp theo khách, thời điểm, `event_id`; không có `statement_timeout`. Harness kết nối bằng `EVAL_DATABASE_URL` (role `cdp_eval_login` thuộc `cdp_reader`, chỉ đọc).
- Vì hai giới hạn tách nhau, một lần đọc lịch sử có thể mất tới khoảng connect + statement timeout (khoảng 4 giây ở mặc định).
- Lỗi kết nối hoặc timeout (`OperationalError`, `InterfaceError`, `OSError`) thành `CdpUnavailableError`. `RecommendForUser` bắt lỗi này, trả đường lui §6 mục 3 và ghi WARNING `recommend.cdp_unavailable` kèm `requestId` và loại lỗi, không ghi `cdpUserId` (§8 mục 5). Message của `CdpUnavailableError` chỉ lấy dòng đầu, cắt ngắn và xoá DSN/mật khẩu nếu driver in lại.
- Lỗi quyền hoặc SQL **lúc chạy câu lệnh** (`ProgrammingError`, ví dụ `permission denied for table events`) vẫn nổi lên. Lỗi xác thực **lúc kết nối** (sai mật khẩu, `pg_hba` từ chối, role không tồn tại) libpq báo là `OperationalError` thường, không tách được khỏi sự cố, nên cũng rơi về `popular`. Lúc khởi động lỗi này vẫn làm RecSys hỏng rõ ràng, vì bảng phổ biến đọc qua cùng đường kết nối. Nếu mật khẩu bị đổi sau khi backend đã chạy, dấu hiệu duy nhất là WARNING `recommend.cdp_unavailable reason=OperationalError` lặp lại.

---

## 8. Bảo mật

1. CDP clone **chỉ nằm trong mạng nội bộ**. Không mở cổng service (8100) hay cổng database ra ngoài; khi dev, Postgres chỉ bind `127.0.0.1`.
2. Không có CORS: trình duyệt không bao giờ gọi CDP clone.
3. `X-Service-Token` tối thiểu 32 ký tự, chỉ có ở Backend, seed và job. Không đưa vào code frontend, URL hay log.
4. Ai có token đọc/ghi được lịch sử của mọi khách: đổi token ngay khi nghi lộ (hiện phải đổi đồng thời ở hai bên và khởi động lại).
5. Log không chứa `cdpUserId`, `searchQuery`, token hay payload event. Được phép: `requestId`, `eventName`, số lượng, lý do bỏ, `bookingItemId`.

---

## 9. Vận hành và truy vết

### 9.1. Cấu hình

| Biến | Ở đâu | Ghi chú |
|---|---|---|
| `CDP_DATABASE_URL` | CDP clone | PostgreSQL riêng |
| `CDP_SERVICE_TOKEN` | CDP clone **và** Backend | Phải trùng nhau |
| `CDP_BASE_URL` | Backend | Mặc định `http://localhost:8100` |
| `CDP_TIMEOUT_SECONDS` | Backend | Mặc định `2` |
| `CDP_EVENT_QUEUE_SIZE` | Backend | Mặc định `1000` |

### 9.2. Thứ tự khởi động

1. PostgreSQL của CDP clone → `alembic -c src/cdp_clone/alembic.ini upgrade head`.
2. CDP clone.
3. Seed CDP (events, profiles) và seed Backend (`users` cùng `cdpUserId`), rồi kiểm tra 4 persona.
4. Backend.

Backend khởi động được khi CDP chưa chạy; lúc đó checkout lỗi và gợi ý rơi về `popular` cho tới khi CDP lên.

### 9.3. Truy vết

- Backend chuyển tiếp `X-Request-ID` của request gốc sang mọi lời gọi CDP, kể cả lời gọi từ worker nền.
- CDP clone lặp lại ID trong header response và `error.requestId`.

### 9.4. Thay đổi phiên bản

- Đổi API CDP clone: cập nhật `cdp-clone.openapi.yaml` và fixture trước, rồi adapter Backend, rồi CDP clone. Deploy CDP clone trước Backend khi chỉ thêm trường; ngược lại khi bỏ trường.
- Đổi bảng: sửa `tables.py` và thêm revision Alembic cùng lúc.

---

## 10. Rủi ro còn lại

| Rủi ro | Mức | Xử lý hiện tại |
|---|---|---|
| Event `purchase` mồ côi khi huỷ bù trừ cũng lỗi | Trung bình | Log `ERROR` để huỷ tay |
| Mất event duyệt web khi CDP lỗi, hàng đợi đầy, Backend restart | Thấp | Log; chấp nhận |
| Checkout phụ thuộc CDP | Trung bình | `500` retryable; không có outbox |
| Một token cho mọi caller, chưa có xoay vòng | Trung bình | Chỉ mạng nội bộ |
| Người dùng tự gọi `POST /api/v1/events` hàng loạt | Thấp | `productId` phải có thật; chưa rate limit |
| Seed lệch giữa hai database | Trung bình | Bước kiểm tra 4 persona (§9.2) |
| Khách ẩn danh không được ghi | Thấp | Ngoài phạm vi |

---

## 11. Chờ xác nhận

Cần người hiểu CDP V-OTA rà soát (handbook §17 câu 3). Đến khi có câu trả lời, giữ quy tắc tạm:

| Điểm | Quy tắc tạm |
|---|---|
| Bề mặt API của CDP thật | Năm endpoint §3 |
| Nơi lưu truy vấn của `search` | `searchQuery` |
| Cách huỷ event | Đánh dấu `cancelledAt` |
| Khóa chống trùng | `eventId` do caller sinh |
| Tên trường opt-in | `emailOptin`, `smsOptin`, `pushOptin`, `gdprOptin` |
| Giá trị `lifecycleStage` | `new`, `active`, `dormant`, `churned` |
| ~~Nơi lưu `products`, `users`, `bookings`, `product_vectors`~~ — **đã chốt 20/09** | `products` ở `cdp.products`; `users`, `bookings` ở `app.*`; `product_vectors` ở `catalog.*` — cùng database `vota`, tách bằng schema + role |
| Hợp đồng Agent ghi rõ "không gửi JWT khi gọi `/search`" | Từ 2026-09-28, hợp đồng Agent §2.1 ghi rằng tool tìm kiếm không bao giờ gắn danh tính (`inprocess` không qua route, `http` không kèm JWT). Vẫn cần Web, Backend và Agent duyệt cùng PR (`hop-dong-tich-hop-backend.md` §9) |

---

## 12. Tiêu chí nghiệm thu

1. Web không có URL hay token của CDP clone trong code và biến môi trường.
2. Gọi CDP clone không có hoặc sai `X-Service-Token` trả `401` ở mọi endpoint.
3. Mở trang chi tiết (không phải prefetch) sinh đúng một `product_view`; `productId` lạ trả `404` và không sinh event.
4. `/search` có JWT, `offset = 0` sinh một `search`; trang 2, không JWT, hoặc Agent gọi không sinh event.
5. Thêm giỏ thành công sinh `add_to_cart` với `taxonomy` và `unitPrice` của catalog; thêm giỏ thất bại không sinh event.
6. Tắt CDP clone: search, giỏ, xem sản phẩm vẫn chạy; `/recommendations` trả `200` `strategy: "popular"`; checkout trả `500` `retryable: true` và giỏ còn nguyên.
7. Commit booking lỗi sau khi ghi `purchase`: event có `cancelledAt` và không xuất hiện trong lịch sử mặc định.
8. Gửi lại cùng `purchase:{bookingItemId}` không sinh event thứ hai.
9. Một `X-Request-ID` xuất hiện ở log Backend và log CDP clone cho cùng một thao tác.
10. Ngay sau checkout, `/recommendations` phản ánh `purchase` mới (K1).

---

## 13. Lịch sử quyết định

| Ngày | Quyết định | Lý do |
|---|---|---|
| 2026-09-16 | CDP clone là service riêng, PostgreSQL riêng | Mô phỏng ranh giới production; CDP thật là hệ thống ngoài |
| 2026-09-16 | Bỏ phương án Web gọi thẳng CDP bằng JWT, chuyển sang Web → Backend → CDP | Tránh Web phụ thuộc API tạm của CDP; `add_to_cart` khớp giỏ; `taxonomy`/giá lấy từ catalog; không chia sẻ JWT secret; không mở CDP ra trình duyệt |
| 2026-09-16 | `purchase` ghi đồng bộ trước commit, bù trừ bằng huỷ event | Giữ K1 (event có ngay) và không để booking thiếu event; outbox bị loại vì làm event đến trễ |
| 2026-09-20 | **Thay quyết định 16/09 ở dòng đầu bảng này:** tuần 1 CDP clone là **schema `cdp` trong database `vota`**, không phải service HTTP có PostgreSQL riêng. Backend vẫn chỉ đi qua port `CdpClient`; adapter là `LocalCdpClient` với connection + role riêng (`CDP_DATABASE_URL`, `cdp_writer`) | Handbook §6 "one implementation now, reading locally". Tách database sẽ mất FK và view của `catalog`/`app` sang `cdp.products`, mà `catalog` vẫn phải là bảng local để search p95 < 300 ms. Ranh giới production được mô phỏng bằng role + connection riêng và bằng việc mọi truy cập đi qua port — đổi sang `HttpCdpClient` là thay adapter, không sửa use case. Chi tiết: `history/2026-09-20-database-mock-data-tuan-1.md` |
| 2026-09-20 | Seed ghi thẳng SQL vào `cdp.*` (§1.5) | CDP clone là database ở tuần 1; seed là loader, không phải code app |
