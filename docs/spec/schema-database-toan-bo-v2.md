# Schema toàn bộ hệ thống · Phiên bản 2

**Ngày 18/09/2026 · Thiết kế đầy đủ trong phạm vi dự án · Chưa migrate, chưa bật tracking.**

[Mở bản HTML có sơ đồ và tra cứu trường](schema-database-toan-bo-v2.html) · [Bản V1](schema-database-toan-bo.html) · [6 sản phẩm mẫu người dùng cung cấp](evidence/catalog-template-v2.json)

V2 mở rộng bản V1 để trả lời ba câu hỏi: **cần lấy dữ liệu nào, lấy ở đâu, dùng để làm gì?** Có đúng **3 database, 44 bảng**: `ota_app` 33 bảng, `cdp` 6 bảng, `insider` 5 bảng. V1 có 31 bảng; V2 thêm 13 bảng hỗ trợ truy nguồn, hành vi, định danh, chuyến đi và đo lường. Đây là đích thiết kế đầy đủ; không phải yêu cầu làm 44 bảng trước khi demo MVP.

Các bảng/cột cũ kế thừa **bản thiết kế V1**, không phải xác nhận schema runtime. Các bảng mới và API `/v2` dưới đây là **đề xuất local cần chốt hợp đồng**, không khẳng định đây là field của CDP V-OTA thật. Code trong `src/data_collection/cdp` còn khác thiết kế ba service; OpenAPI chung hiện là khung. Không sửa migration hay API đang chạy trong lần bổ sung tài liệu này.

## 1. Website có tracking mọi hành động không?

**Website có thể theo dõi đầy đủ các hành động có ý nghĩa trong hành trình người dùng. Mỗi hành động cần có định nghĩa rõ ràng trước khi thu thập.** CDP nhận lịch sử có cấu trúc; Recommendation chỉ chọn những tín hiệu hữu ích từ lịch sử đó.

| Lớp dữ liệu | Ví dụ | Nơi sinh / lưu | Cách sử dụng |
|---|---|---|---|
| Nội dung catalog | Phòng, giá quan sát, ảnh, tiện ích | Crawler → `ota_app` | Search, hiển thị, kiểm dữ liệu |
| Hành vi giao diện | Card thực sự xuất hiện, mở chi tiết, xem bao lâu, đổi bộ lọc | Web → Backend → `cdp.activity_events` | Phân tích hành trình, đo exposure, tín hiệu quan tâm |
| Sự kiện nghiệp vụ | Thêm giỏ thành công, đặt thành công | Backend → CDP | Tín hiệu đáng tin cho Recommendation |
| Hồ sơ tổng hợp | Điểm đến gần nhất, tổng đơn, vòng đời | Job đọc lịch sử → `cdp.profiles` | Cá nhân hóa và phân nhóm |
| Tương tác kênh | Email mở/click/bounce/unsubscribe | Insider clone seed/simulator | Kiểm hợp đồng kênh và consent |

**Không bật autocapture toàn bộ DOM.** MVP và V2 này không gửi từng lần rê chuột, từng phím gõ, nội dung input, DOM snapshot, session replay, mật khẩu, JWT, thẻ thanh toán, tên khách lưu trú hay nguyên văn chat vào event. Cuộn trang được tổng hợp theo mốc; tìm kiếm ghi khi submit; thời gian xem gửi bản tổng hợp. Các hạn chế này giúp event có ý nghĩa và tránh dữ liệu ngoài mục đích.

Hai bảng CDP cũ giữ vai trò của chúng: `events` chứa bốn loại lõi theo hợp đồng tham chiếu; `profiles` chứa snapshot hồ sơ. V2 thêm `activity_events`, `web_sessions`, `identity_links`, `consent_history`. Không đưa tên event mới vào enum lõi một cách âm thầm.

## 2. Sơ đồ luồng và quyền sở hữu dữ liệu

```text
Catalog JSON + raw cache ──> Loader ──> ota_app
                                         ↑
Web ── REST/JWT ──> Backend ───────────────┤ tài khoản, catalog, giỏ, booking
 │                    │                  └ recommendation + vector
 │                    │
 └ tracking SDK ──> /api/v2/tracking/events
                      │ validate + consent + identity + durable queue
                      └ tracking_outbox ── CdpClient ──> CDP activity_events
                                                              │
                                  4 loại lõi + đã định danh ──┤ projection
                                                              ↓
                                                           events
                                              profiles <── job đọc lịch sử
                                                              │
Backend recommendation <──── CdpClient đọc core + engagement ───┘
          │
          └ Batch + consent ── InsiderClient ──> Insider clone
```

Web không giữ service token và không ghi thẳng CDP/Insider. Backend chỉ dùng DB `ota_app`; CDP và Insider chỉ dùng DB riêng. Không có SQL JOIN/FK xuyên database. Đường purchase tiếp tục dùng journal đồng bộ/bù trừ của V1; `tracking_outbox` chỉ dành cho tracking, search và cart, không âm thầm đổi transaction booking.

### Những phần khác V1

| Nhóm | Bổ sung / thay đổi | Lý do |
|---|---|---|
| Truy nguồn | `product_sources`, `product_field_lineage` | Một sản phẩm có nhiều nguồn, biết nguồn nào thắng và phép biến đổi nào đã chạy |
| Snapshot nguồn | `product_price_observations`, `product_rating_observations` | Không trộn giá khác ngày/quyền lợi; chỉ thu điểm đánh giá tổng hợp |
| Chuyến đi | `trip_contexts`; đổi ràng buộc `booking_groups.event_group_id` | Một chuyến có thể có nhiều checkout ở những ngày khác nhau |
| Delivery | `tracking_outbox` | Backend đã nhận thì có thể gửi tiếp sau lỗi CDP |
| Đo recommendation | `recommendation_requests`, `recommendation_items` | Biết danh sách đã trả, model, vị trí, impression và click thực tế |
| Tracking/định danh | Bốn bảng CDP mới | Lưu event mở rộng, thời gian xem, phiên, khách ẩn danh, consent |
| Đồng bộ kênh | `insider_sync_runs` | Đo số request, byte/user, thời gian, lỗi và khách bị chặn |

Mặc định hiển thị **cây quan hệ cha–con**: mỗi bảng xuất hiện một lần dưới cha chính, có thể mở/thu nhánh và bấm tên để xem cột. Bật “Hiện khóa liên kết” nếu cần PK/FK. Với bảng có nhiều cha/tham chiếu, các liên kết còn lại nằm trong phần mở rộng bên dưới cây; chúng không bị xóa khỏi schema. Nhánh profiles → events dùng cùng ID, **không phải FK** và event vẫn có thể tồn tại trước profile. ERD chứa toàn bộ cột/đường nối được thu gọn riêng để mở khi cần.

## 3. Mẫu hiện tại có những gì?

Mẫu người dùng gửi có **6 sản phẩm, 4 taxonomy, 6 product kind**. Không coi đây là thống kê toàn bộ catalog 10.000 sản phẩm.

| Mẫu | Taxonomy / level | Bảng đích | Lưu ý |
|---|---|---|---|
| Junior Suite Vinpearl Phú Quốc | `hotel / room` | `hotel_rooms` | Thiếu description, thiếu parentProductId |
| Meliá Vinpearl Danang Riverfront | `hotel / property` | `hotel_properties` | Có điểm tổng hợp 8.6/10 và 1.225 lượt; không phải khách sạn cha của mẫu room |
| Tuyến Nha Trang → Hà Nội | `flight / route` | `flight_routes` | Giá từ/theo tháng, không phải vé của một chuyến có tồn ghế |
| 9G2953 Nha Trang → Phú Quốc | `flight / flight` | `flight_services` | Có parentProductId nhưng parent đó không nằm trong 6 mẫu |
| VinWonders Nha Trang | `attraction` | `attraction_products` | Có nhiều giá và giờ mở cửa cần đối chiếu ngữ cảnh |
| VinWonders + Safari Phú Quốc | `combo` | `combo_packages` | Chưa có danh sách component chuẩn; metadata POI có dấu hiệu ghép lệch |

`golf_products` vẫn giữ từ V1; **chưa có mẫu golf trong file vừa gửi** nên không tuyên bố đã kiểm mapping golf. API taxonomy vẫn là `hotel`, `flight`, `attraction`, `combo`, `golf`; phân biệt property/room và route/flight bằng `product_kind`.

### Các trường cấp gốc và cách nhập

| JSON hiện tại | Kiểu mong đợi | Yêu cầu | Đích / ý nghĩa |
|---|---|---|---|
| `productId` | UUID string | Bắt buộc | ID ổn định, registry + đúng một subtype |
| `name` | string | Bắt buộc | Tên hiển thị và text embedding |
| `taxonomy` | enum | Bắt buộc | Chuẩn hóa, không dùng chuỗi nhãn tiếng Việt làm mã |
| `destination` | string | Bắt buộc | Điểm đến chuẩn; flight là điểm đến cuối |
| `description` | string hoặc null | Mục tiêu đủ, cho phép fixture thiếu | Không bịa mô tả nguồn; text builder có fallback thuộc tính |
| `attributes` | object | Bắt buộc | Thuộc tính đúng từng loại; snapshot + cột chuyên biệt |
| `unitPrice` | integer VND hoặc null | Cần cho giá hiển thị/đặt | Giá quan sát; cần price_unit và bối cảnh mới so sánh được |
| `currency` | mã 3 chữ | Bắt buộc nếu có giá | Chuẩn VND; giữ giá gốc/tỷ giá khi quy đổi |
| `available` | boolean | Theo template hiện tại | Trạng thái được nguồn công bố; không là tồn realtime |
| `availableFrom`, `availableTo` | ISO date hoặc null | Có điều kiện | Không có thông tin thì null; không tự coi là vô hạn |
| `imageUrl` | URL hoặc null | Mục tiêu đủ | Ảnh chính; thư viện ảnh ở attributes.images |
| `sourceRef` | string | Bắt buộc | Nguồn truy vết và khử trùng lặp |

HTML có ma trận **tất cả key cấp gốc và từng key trực tiếp trong `attributes` của cả 6 mẫu**, kèm kiểu quan sát, ví dụ, cột/JSON path đích. Object con được giữ nguyên và kiểm theo cấu trúc: `fieldSources` là map field → source, `pricesByDate` là map date → amount, `otaPrices` là map OTA → amount, `policies` là map tiêu đề → nội dung, `monthlyPrices` là map tháng → amount. Không flatten key ngày hoặc tên website thành cột database.

Các cột chuẩn hóa là nguồn đọc nghiệp vụ; `attributes` giữ snapshot của các key được phép để truy nguồn. Nếu cột và snapshot khác nhau, loader phải ghi transformation/lineage. `v_catalog` dựng lại 13 field Product cho API; đây là view, không thêm bảng `products` thứ tám.

`product_sources` giữ registry nguồn và thông tin lần lấy gần nhất. Mỗi row `product_field_lineage` giữ đường dẫn/hash cache, parser version và thời điểm của **chính lần quan sát đó**; crawl lại không ghi đè bằng chứng cũ. Price/rating observation liên kết lineage tương ứng khi có. Mẫu cũ không có cache thì ghi thiếu bằng chứng, không tuyên bố có thể tái dựng từ trang gốc.

## 4. Những thông tin cần bổ sung khi thu thập catalog

| Dữ liệu cần lấy / xác nhận | Có trong mẫu? | Cách thu / xử lý | Mức ưu tiên |
|---|---|---|---|
| Parent của room | Không | ID khách sạn nhà cung cấp → mapping property; nếu chưa có parent thì chờ resolve, không tạo FK đoán | P0 import room |
| Parent của flight | Có ID, ngoài mẫu | Tra full catalog và kiểm origin/destination; tuyến Nha Trang–Hà Nội không phải parent của chuyến đi Phú Quốc | P0 import flight |
| Mô tả tiếng Việt room | Thiếu | Lấy từ Vinpearl; hoặc dựng có nhãn derived từ thuộc tính đã xác minh | P0 chất lượng |
| fetchedAt, cache path, hash, parser version | Chưa có | Crawler ghi khi cache trang trước parse; không backfill timestamp bịa | P0 tái dựng |
| Nguồn từng field + phép biến đổi | Chỉ một phần | `product_field_lineage`; ưu tiên tên/mô tả Vinpearl khi có giá trị đáng tin, OTA cho giá/khả dụng đúng offer | P0 tái dựng |
| Đơn vị và ngữ cảnh giá | Không đủ | Ngày đi, số đêm, số người, rate plan, thuế/phí, loại vé/quyền lợi, thời điểm quan sát | P0 trước so sánh giá |
| Live availability | Không đủ | API nguồn được phép hoặc lịch mock được gắn nhãn; không biến crawl thành realtime | P0 trước đặt |
| Hạng vé / cabin / hành lý | Chưa có trong mẫu flight | Lấy từ offer cụ thể nếu cung cấp vé có thể đặt; giữ null nếu chỉ là lịch tham khảo | P1 mở rộng flight |
| Thang điểm `tripRating` | Không ghi rõ | Xác nhận nguồn; không tự mặc định 5 từ một con số 4.5 | P1 chất lượng |
| Thành phần combo | Chưa có ID chuẩn | Parse quyền lợi + review tay → combo_components; UNMAPPED đến khi xác minh | P0 trước tính đã mua danh mục |
| Giờ mở cửa, ngày áp dụng, timezone | Chỉ có văn bản | Giữ raw; chuẩn hóa lịch có nguồn/ngày xác minh nếu Assistant dùng để lập lịch | P1 itinerary |
| Giá trị giá vé trẻ em bằng 0 | Có nhưng mơ hồ | Xác minh miễn phí hay không có giá; giữ raw 0, canonical null nếu chưa biết | P0 tính giá |
| Loại đối tượng attraction/golf | Chưa rõ ở mọi bản ghi | TICKET/TOUR/POI hoặc VOUCHER/VENUE; chỉ loại đã xác minh có thể đặt | P0 booking |

**Giữ quy tắc phòng của V1:** `hotel_room_prices` là giá mock cố định/đêm; `hotel_room_nights` là một đơn vị tồn mock/room/đêm, cửa sổ 30 ngày trượt. `pricesByDate` được giữ trong quan sát nguồn để tham khảo, không tự ghi đè giá mock mỗi ngày. `ratePlans` hiện chỉ có tên, chưa phải các offer độc lập có giá, ID, tồn và chính sách đầy đủ.

### Những mâu thuẫn đã thấy trong chính mẫu

1. Property có `fieldSources.description=booking.com`, nhưng `descriptionSource` ghi dựng tiếng Việt từ thuộc tính. Cần ghi riêng nguồn dữ kiện Booking và transformation dựng tiếng Việt; không mô tả là bản dịch nguyên văn đã xác minh.
2. VinWonders Nha Trang có `openingHours=08:30–20:00`, nhưng policies ghi mở 09:00. Đánh dấu CONFLICT và xác minh ngày áp dụng trước khi dùng để cam kết lịch trình.
3. Combo Phú Quốc có `venue=VinWonders Phú Quốc` trong khi `poiName=Vinpearl Safari Phú Quốc`. Không gán một tọa độ, điểm review hoặc giờ mở cửa đó cho toàn bộ combo. Kiểm từng component.
4. Cùng tên VinWonders nhưng giá Vinpearl và Trip khác nhau chưa chứng minh cùng hạng vé, ngày, đối tượng hay quyền lợi. Không lấy min rồi coi là giá tốt nhất.
5. `priceObservedAt` chỉ có ngày; `datesSeen` là dữ liệu nhìn thấy ở nguồn. Chưa có đủ ngày/giờ bay có timezone và tồn ghế. `available=true` không giải quyết khoảng trống này.

Mẫu gốc được lưu để truy vết, không chỉnh sửa âm thầm. Không thu review cá nhân; chỉ dùng điểm tổng hợp, thang điểm, số lượt và nguồn của chúng.

## 5. Danh mục event đầy đủ cho website

Các hàng **P0** phục vụ MVP. **P1** giúp đo và cải thiện Recommendation. **P2** chỉ làm khi tính năng tương ứng có trong sản phẩm. Tên ngoài bốn loại lõi là đề xuất V2; properties dưới đây là **các trường bổ sung ngoài envelope chung**.

| Event | Nơi phát / trigger chính xác | Properties cần lấy | Ưu tiên / dùng cho |
|---|---|---|---|
| `page_view` | Web, route thực sự hiển thị; mỗi lần điều hướng một pageViewId | pageType, pagePath | P1 / funnel |
| `search` | Backend sau query do user submit được xử lý; không phát cho tool nội bộ của Agent | query đã lọc, filters, resultCount, searchRequestId | P0 / ý định; core |
| `filter_changed` | Web, user bấm áp dụng hoặc kết thúc thay đổi được debounce | filterName, giá trị hợp lệ, searchRequestId | P1 / ý định tìm |
| `sort_changed` | Web, áp dụng sắp xếp mới | sortKey, searchRequestId | P1 / ưu tiên giá/điểm |
| `product_impression` | Web, card vào viewport đạt quy tắc hiển thị | listId, productId, rank, sourceSurface, requestId nếu từ gợi ý | P1 / mẫu số exposure |
| `product_click` | Web, click card/link sản phẩm | productId, listId, rank, sourceSurface, requestId | P1 / chọn kết quả; chưa là lượt xem thành công |
| `product_view` | Web, trang chi tiết đã render sản phẩm thành công | productId, pageViewId, sourceSurface | P0 / core, tín hiệu yếu |
| `product_engagement` | Web, gửi snapshot cộng dồn lúc checkpoint/ẩn trang/đổi route | productId, pageViewId, sequence, visibleMs, activeMs, maxScrollPercent, endReason | P1 / đánh giá mức quan tâm |
| `gallery_opened` | Web, mở thư viện ảnh | productId, imageIndex | P2 / quan tâm bổ sung |
| `product_section_opened` | Web, mở tiện ích/chính sách/vị trí | productId, section enum | P2 / mối quan tâm; không gửi DOM text |
| `travel_dates_changed` | Web, user xác nhận khoảng ngày | productId nếu có, checkIn, checkOut hoặc usingDate | P1 / bối cảnh chuyến |
| `party_changed` | Web, user xác nhận số khách | adults, childrenCount, rooms | P1 / nhu cầu nhóm; không thu ngày sinh trẻ em |
| `availability_checked` | Backend, kiểm tồn xong | productId, kỳ sử dụng, available, checkedAt, mode mock/live | P1 / grounding |
| `wishlist_added`, `wishlist_removed` | Backend sau cập nhật thành công, nếu có wishlist | productId | P2 / sở thích; chưa có bảng wishlist trong phạm vi V2 |
| `add_to_cart` | Backend sau transaction thêm giỏ thành công | productId, quantity, usingDate, nights, cartId | P0 nếu có giỏ / core |
| `cart_item_updated`, `cart_item_removed` | Backend sau mutation giỏ thành công | productId, cartItemId, quantity/date mới, action | P1 / funnel; xóa giỏ chưa chắc ghét sản phẩm |
| `checkout_started` | Backend tạo checkout attempt hợp lệ | checkoutId, productIds, eventGroupId nếu đã chọn | P1 / funnel |
| `purchase` | Backend theo journal V1; chỉ dùng sau xác nhận hợp lệ/đối soát | bookingId, bookingItemId, productId, quantity, unitPrice, currency, usingDate, nights, checkOut, lineTotal | P0 / core; tín hiệu mạnh |
| `checkout_failed` | Backend xác định thất bại | checkoutId, errorCode allowlist | P1 / kỹ thuật và funnel; không là tín hiệu không thích |
| `booking_cancelled` | Backend sau nghiệp vụ hủy thực sự thành công, nếu triển khai | bookingId, bookingItemIds, reasonCode | P2 / cần hợp đồng hủy/refund; V1 chưa có |
| `recommendation_served` | Backend trả danh sách | requestId, strategy, modelVersion, productIds | P1 / log phục vụ, không là impression |
| `recommendation_dismissed` | Web qua Backend xác nhận user chủ động ẩn | requestId, productId, reason enum nếu user chọn | P2 / tín hiệu âm rõ ràng |
| `login_succeeded`, `logout` | Backend xác thực thành công / kết thúc phiên | authMethod enum; không credentials | P1 / ranh giới identity |
| `consent_changed` | Backend sau user lưu lựa chọn | consentId, purpose, granted, policyVersion | P0 quản lý consent / audit, không sở thích |
| `assistant_request` | Backend nhận yêu cầu user đã xử lý consent | conversationId, intent enum, destination/category/budget đã lọc | P2 / ý định, không nguyên văn chat |
| `assistant_product_clicked` | Web, chọn sản phẩm trong trả lời | conversationId, messageId, productId | P2 / attribution |
| `itinerary_saved` | Backend xác nhận lưu nếu có tính năng | itineraryId, productIds, destination | P2 / cần hợp đồng lưu lịch trình riêng |

`product_impression` và `product_click` dùng `sourceSurface=recommendation` để đo gợi ý; không đồng thời phát thêm một bản sao khác tên để cộng hai lượt. Response Recommendation cần trả `requestId`, rank và modelVersion cho Web. Card vào viewport ví dụ ít nhất 50% diện tích trong 1 giây là **ngưỡng thử nghiệm cấu hình**, không chuẩn bắt buộc. Một `(pageViewId,listId,productId)` chỉ tính một impression đủ điều kiện; điều hướng mới được tính mới.

Sản phẩm xem là ID đúng thực thể hiện trên trang: trang khách sạn dùng property ID; chọn phòng dùng room ID. `purchase.productId` luôn là ID room/chuyến/vé cụ thể được đặt. Recommendation có mapping property → room để tránh so sai cấp sản phẩm; taxonomy room vẫn là hotel.

## 6. Thời gian xem, idle và chống đếm trùng

Ghi `product_view` một lần khi trang sản phẩm hiển thị. Đừng chờ user rời trang mới ghi lượt xem. Các checkpoint `product_engagement` bổ sung thời gian quan tâm, **không sinh thêm core product_view**.

| Tình huống | Cách đo / xử lý |
|---|---|
| Tab đang hiển thị | Cộng visibleMs theo khoảng thời gian đơn điệu ở client |
| Tab ẩn hoặc rời route | Chốt khoảng hiện tại và tạm dừng; tab nền không cộng |
| Không tương tác lâu | Sau idle timeout, dừng activeMs; visibleMs có thể vẫn tăng. Đây là proxy, đọc yên lặng có thể bị đánh giá thấp |
| Quay lại tab / có tương tác | Mở khoảng đo mới; không cộng thời gian ẩn/idle vào khoảng mới |
| SPA back/forward | pageViewId mới khi thực sự hiển thị lượt mới; tránh double mount tạo hai lượt |
| Nhiều tab | pageViewId riêng; giới hạn đóng góp theo user/product/window ở Recommendation, không dùng heartbeat làm bằng chứng chú ý |
| Gửi checkpoint | Cùng pageViewId; sequence tăng; mỗi checkpoint eventId riêng, retry cùng checkpoint giữ nguyên eventId |
| Nhận checkpoint lệch thứ tự | Lấy max bộ đếm cộng dồn đã kiểm tra; không sum 10s + 20s + 30s thành 60s |
| Reload/retry mạng | UNIQUE producer + subject_key + eventId; duplicate cùng nội dung trả thành công, khác nội dung trả conflict |
| Đóng app/crash | Có thể mất checkpoint cuối; chấp nhận dữ liệu một phần, không bịa duration |

Ví dụ cấu hình ban đầu: checkpoint 15 giây; idle timeout 60 giây; activeMs dưới 3 giây chưa cộng điểm, từ 3–15 giây tín hiệu yếu, từ 15 giây rõ hơn; điểm đóng góp đạt trần ở 120 giây. Đây là **giả thuyết cần đo**, không số đã tối ưu trên khách thật. Dùng `min(activeMs,120000)` khi tính trọng số, vẫn giữ thời gian hợp lệ trong telemetry theo retention. Giới hạn client counters theo thời gian thực đã trôi; không tin duration tùy ý do client gửi.

Mở trang 20 giây rồi để tab nền 30 phút: giữ khoảng 20 giây đã quan sát, không xóa event. Click “Thêm giỏ” và purchase không áp ngưỡng dwell. `purchase > add_to_cart > engaged view > view` là thứ tự trọng số khởi đầu; event audit và lỗi hệ thống có trọng số sở thích bằng 0.

[Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API) cung cấp trạng thái hiển thị; timer trong tab nền có thể bị giới hạn. `visible` không chứng minh user thực sự đọc. Khi trang ẩn có thể dùng [sendBeacon](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/sendBeacon), nhưng giá trị trả về chỉ cho biết trình duyệt nhận xếp hàng, không xác nhận server đã lưu. Nếu auth dùng Bearer header, dùng fetch/keepalive phù hợp; không nhét JWT vào URL/body để lách header. Với cookie cùng origin, collector phải kiểm origin/CSRF và cookie phiên như API tương ứng.

## 7. Envelope chung và mẫu event dựa trên sản phẩm đã gửi

Envelope Web đề xuất dùng camelCase; bảng lưu dùng snake_case. Chỉ các key allowlist được nhận. `properties` có schema theo `eventName + schemaVersion`, không mở JSON tùy ý.

| Field API | Ai cung cấp | Bắt buộc / quy tắc |
|---|---|---|
| eventId, schemaVersion, eventName | SDK / Backend | Bắt buộc; ID ổn định qua retry |
| occurredAt | Producer | ISO timestamp timezone; Backend kiểm sai lệch |
| pageViewId, pagePath | Web | Bắt buộc với view/engagement; path bỏ query PII |
| sessionId | Backend xác nhận SDK | Bắt buộc với phiên Web có tracking |
| productId | Web đề nghị / Backend xác minh | Bắt buộc với hành vi sản phẩm |
| properties | Producer | Theo loại; requestId + rank phải khớp danh sách server |
| cdpUserId, anonymousId, subjectKey | Backend | Không nhận định danh tùy ý từ body Web |
| producer, taxonomy, receivedAt | Backend/CDP | Server quyết định |
| eventGroupId | Backend | Chỉ gắn khi đã xác minh trip thuộc user |
| consentSnapshot | Backend | Tra trạng thái hiện hành, không tin cờ true do event tự gửi |

Ví dụ **body gửi từ Web**, sử dụng đúng room ID mẫu. Thời gian/UUID phiên bên dưới là dữ liệu minh họa, không phải hành vi đã thu:

```json
{
  "events": [{
    "eventId": "f2606b9e-09e1-4385-bcd9-5d2533e55910",
    "schemaVersion": 2,
    "eventName": "product_engagement",
    "occurredAt": "2026-09-18T03:00:30Z",
    "sessionId": "fded50cb-730b-4c5e-bb4e-8b95c2083e55",
    "pageViewId": "2db91f36-18d8-4be7-9b45-8f4bf717fe76",
    "pagePath": "/rooms/6c36a4fd-7bc0-5688-9d3d-3fc74fcbb41d",
    "productId": "6c36a4fd-7bc0-5688-9d3d-3fc74fcbb41d",
    "properties": {
      "sequence": 2,
      "visibleMs": 30000,
      "activeMs": 24000,
      "maxScrollPercent": 75,
      "endReason": "visibility_hidden"
    }
  }]
}
```

Ví dụ purchase **do Backend tạo sau kiểm nghiệp vụ**: room mẫu giá `5.180.000 VND` được chọn làm giá mock cố định, ở 15–17/10/2026 hai đêm. Đây là kịch bản minh họa sau khi parent/import hợp lệ và lịch mock đã được tạo, không là báo giá hay xác nhận tồn thật.

```json
{
  "eventId": "purchase:cb1e6a9b-98ce-4c32-bf66-9c115f8e97cc",
  "cdpUserId": "DEMO_USER_001",
  "eventName": "purchase",
  "timestamp": "2026-09-18T03:05:00Z",
  "productId": "6c36a4fd-7bc0-5688-9d3d-3fc74fcbb41d",
  "taxonomy": "hotel",
  "eventGroupId": "TRIP_PQ_20261015_001",
  "quantity": 1,
  "unitPrice": 5180000,
  "usingDate": "2026-10-15"
}
```

Payload trên là **core event**. Phần mở rộng V2 nằm trong `activity_events.properties` liên kết `core_event_id`, gồm `bookingId`, `bookingItemId`, `currency=VND`, `nights=2`, `checkOut=2026-10-17`, `lineTotal=10360000`. Không nhét các key mới này vào endpoint V1 trước khi chốt schema. Tổng doanh thu lấy từ booking đã commit; không lấy `quantity × unitPrice` của core event để tính phòng nhiều đêm.

### Kiểu dữ liệu bên trong properties

| Nhóm field | Kiểu / giới hạn đề xuất | Quy tắc |
|---|---|---|
| sequence | integer ≥ 1 | Bắt buộc cho engagement; tăng theo pageViewId |
| visibleMs, activeMs | integer ≥ 0, milliseconds | Bắt buộc cho engagement; activeMs ≤ visibleMs ≤ thời gian đã trôi có thể kiểm tra |
| maxScrollPercent | number trong [0,100] | Giá trị lớn nhất của lượt xem, không cộng các checkpoint |
| endReason | enum | checkpoint / visibility_hidden / route_change / idle; kiểm cả loại và ngữ nghĩa |
| listId, requestId, searchRequestId | string ID tối đa 128 ký tự | Đối chiếu danh sách đã được server phát; không phải campaign tự khai |
| rank | integer ≥ 1 | Vị trí 1-based trong danh sách server |
| sourceSurface | enum | home / search / recommendation / assistant / direct |
| pageType, section, sortKey, filterName | enum theo UI đã chốt | Không nhận text DOM bất kỳ |
| query | string ≤ 500 ký tự sau lọc | Chỉ khi submit; loại thông tin cá nhân nếu user nhập vào tìm kiếm |
| filters | object có schema | Chỉ destination, taxonomy, minPrice, maxPrice, starRating, amenities; validate min ≤ max |
| resultCount, imageIndex | integer ≥ 0 | resultCount từ Backend, imageIndex là 0-based |
| checkIn, checkOut, usingDate | ISO date | checkOut > checkIn; ngày theo timezone điểm đến |
| adults, childrenCount, rooms | integer có giới hạn nghiệp vụ | adults ≥ 1, childrenCount ≥ 0, rooms ≥ 1 |
| quantity, nights | integer ≥ 1 | Bắt buộc có điều kiện theo loại sản phẩm; nights chỉ phòng |
| unitPrice, lineTotal | integer VND ≥ 0 | Chỉ server chốt; currency=VND trong clone |
| bookingId, bookingItemId, checkoutId, cartId, cartItemId | UUID string | Server tạo/kiểm ownership; bắt buộc theo event tương ứng |
| productIds, bookingItemIds | array ID, giới hạn theo nghiệp vụ và 8 KiB/event | Không đưa toàn catalog vào một event |
| available, checkedAt, mode | boolean, ISO timestamp, enum mock/live | Do Backend inventory xác nhận; không lấy từ click Web |
| errorCode, reasonCode, authMethod, intent | enum allowlist | Không nhận stack trace, mật khẩu, prompt hay input tự do |
| consentId, granted, purpose, policyVersion | UUID, boolean, enum, string version | Do consent service xác nhận |
| conversationId, messageId, itineraryId | string ID theo hợp đồng tính năng | Không chứa nguyên nội dung hội thoại hoặc lịch trình trong event |

Các field `strategy` và `modelVersion` lấy nguyên từ kết quả Recommendation server. Registry mỗi event phải chỉ rõ subset bắt buộc/tùy chọn trong bảng này; key chưa có trong schema bị từ chối thay vì lưu tự do. Khi triển khai, đặc tả registry thành JSON Schema/OpenAPI versioned và fixture tương ứng.

## 8. User, phiên truy cập và chuyến đi

| ID | Ý nghĩa | Vòng đời |
|---|---|---|
| user_id | Tài khoản đăng nhập ở Backend | Ổn định theo tài khoản |
| cdp_user_id | Khách hàng trong CDP | Ánh xạ rõ từ Backend, không dùng email làm ID sự kiện |
| anonymous_id | Ngữ cảnh khách chưa đăng nhập | First-party khi có quyền; xoay khi logout/đổi tài khoản |
| session_id | Phiên truy cập | Ví dụ đóng sau 30 phút không hoạt động; cấu hình được |
| page_view_id | Một lượt route hiển thị | Riêng từng tab/lượt xem |
| event_group_id | Một chuyến đi, một điểm đến | Có thể kéo dài qua nhiều phiên/checkout |
| request_id | Một danh sách Search/Recommendation được trả | Dùng gắn impression/click với đúng model và vị trí |

Anonymous chỉ ghi vào `activity_events` khi được phép; core `events.cdp_user_id` vẫn NOT NULL. Login tạo `identity_links` có phạm vi phiên/thời gian, không sửa khóa chống trùng của event cũ. Không gom mọi lịch sử trên máy dùng chung vào người đăng nhập cuối cùng. MVP có thể chỉ tracking tài khoản đã đăng nhập để chưa cần identity stitching.

Queue Web bị ràng buộc với ngữ cảnh danh tính lúc tạo: trước logout/đổi tài khoản, flush nếu được phép hoặc bỏ event còn chờ; không gửi lại event cũ dưới JWT của user mới. Backend kiểm sessionId thuộc ngữ cảnh hiện tại; retry sau đổi identity bị từ chối hoặc đi qua identity resolver có chứng cứ, không tự gán lại subject_key.

Một event đã có core chỉ được dùng một lần. Khi mở rộng Recommendation cho lịch sử anonymous đã liên kết, đọc activity qua resolver và loại row đã có core_event_id; không tự phát lại toàn bộ anonymous history thành core event. Event xảy ra khi user chưa cho phép cá nhân hóa không được hồi tố thành dữ liệu sở thích sau login.

**Thay đổi V2 ở booking_groups:** bỏ UNIQUE đơn cột event_group_id; giữ UNIQUE `(booking_id,destination)`, thêm FK tới `ota_app.trip_contexts`. Backend kiểm trip thuộc cùng user với booking, đúng destination và kỳ đi. Chỉ giữ lại chuyến đang chọn khi user xác nhận; không tự nối hai kỳ nghỉ vì cùng Phú Quốc. Search/view chưa rõ chuyến để eventGroupId null.

Danh mục đã từng mua trong profile khác danh mục đã mua trong chuyến đang xét. Bộ lọc cross-category lấy purchase hợp lệ của đúng eventGroupId. Combo chỉ đóng góp quyền lợi/danh mục theo components đã VERIFIED, tránh đếm hai lần.

## 9. Ghi nhận đáng tin, API và lỗi

Giữ năm endpoint CDP lõi mô tả ở V1. V2 bổ sung các hợp đồng dưới đây **dưới dạng đề xuất, chưa có implementation**:

| API đề xuất | Quyền gọi | Trách nhiệm |
|---|---|---|
| POST `/api/v2/tracking/events` | Web qua phiên/cookie/JWT của Backend | Nhận event Web allowlist; không nhận purchase do client tự khai |
| POST `/cdp/v2/activity-events` | CdpClient service token | Ingest envelope mở rộng, dedupe, projection lõi khi hợp lệ |
| POST `/cdp/v2/identity-links` | Backend sau auth | Tạo liên kết có chứng cứ và khoảng thời gian |
| POST `/cdp/v2/consents` | Backend consent service | Ghi history + cập nhật snapshot được ánh xạ |
| GET `/cdp/v2/users/{id}/activity-events?cursor=...` | Service đã xác thực/quyền đọc | Lịch sử mở rộng, lọc consent; cursor ổn định |
| GET `/cdp/v2/users/{id}/engagement-summaries` | Recommendation qua CdpClient | Snapshot max theo pageViewId, không cộng checkpoint trùng |
| GET `/cdp/v2/profiles?cursor=...` | Batch/Evaluation đã xác thực | Duyệt toàn tập; không dựa riêng 4 user demo |

`CdpClient` vẫn là ranh giới; mở rộng bằng methods tương ứng sau khi chốt DTO. Không truy cập bảng CDP từ Backend. Lịch sử export cần cursor `(timestamp,id)` hoặc snapshot nhất quán; chỉ lấy 500 event cuối không đủ cho evaluation toàn lịch sử khi tracking dày hơn.

Đề xuất giới hạn collector: tối đa 50 event và 64 KiB UTF-8/request, tối đa 8 KiB/event; SDK batch khoảng 10 event hoặc 5 giây. Đây là cấu hình **khác** giới hạn 100 event/request của CDP V1 và 1.000 user/5 MB của Insider. Cần rate limit theo danh tính và trả Retry-After khi 429.

Envelope sai cấu trúc → 400/422, quá dung lượng → 413, service auth sai → 401/403 theo hợp đồng chốt, quá tốc độ → 429. Batch có envelope hợp lệ trả `202` kèm từng event `accepted/duplicate/rejected/conflict`; accepted nghĩa đã ghi outbox bền vững, không đồng nghĩa CDP đã xử lý. Chỉ retry item chưa được xác nhận; 4xx không retry mù. Timeout/5xx retry backoff+jitter cùng ID; vượt ngưỡng chuyển DEAD có thể phát lại cùng ID.

Mutation cart và row outbox của nó phải được ghi **cùng transaction Backend**; worker chỉ thấy row sau commit. Search log được tạo sau khi Backend có kết quả. Với core event đã được ghi qua V1, API V2 kiểm cùng nội dung rồi liên kết activity bằng core_event_id, không tạo core thứ hai. Trường hợp mới qua V2 thì activity + core projection ghi cùng transaction trong DB CDP.

Kiểm server: enum event, kiểu/size properties, timestamp, ownership trip, đúng product/taxonomy, quyền tracking, requestId/rank thực sự có trong response. Seed lịch sử cũ đi qua producer `seed` riêng; không nới clock-skew cho Web vì cần seed. Consent bị rút trong lúc event chờ: worker kiểm lại mục đích trước gửi và loại item bị chặn; không chỉ dựa vào snapshot cũ.

**Dedupe delivery và giới hạn tín hiệu là hai việc riêng.** Ghi một logical event một lần bằng eventId; user thật xem lại được tạo lượt mới. Recommendation giới hạn tổng đóng góp lặp trên cùng sản phẩm/cửa sổ để click spam không lấn át purchase.

### Purchase và lỗi giữa hai service

V1 gửi purchase đồng bộ trước commit booking, dùng `checkout_purchase_journal` để bù trừ/đối soát. Không có atomic transaction xuyên hai DB. V2 kế thừa điều này: trong cửa sổ lỗi, event mồ côi vẫn có thể tồn tại cho đến khi đối soát; không tuyên bố exactly-once hoặc nhất quán tức thì. Recommendation cần bỏ cancelled, và Backend hậu kiểm purchase thuộc booking đã CONFIRMED khi đọc các event vừa phát từ ứng dụng. Seed/offline purchase có nguồn riêng, không yêu cầu tồn tại trong booking web.

Cancellation phải loại cả core lẫn activity liên kết khỏi tín hiệu; không xóa audit tùy ý. `PUT .../cancellation` của CDP dùng sửa/bù trừ event, **không thay thế API hủy booking/refund**. Một flow booking mới có key mới; retry cùng checkout giữ nguyên purchase ID.

## 10. Profile, consent, retention và Insider

Job profile phải định nghĩa công thức và thời điểm cập nhật. `lifetime_order_count` đếm booking distinct, không đếm số dòng purchase. `days_since_last_booking` cập nhật theo ngày. `last_destination` lấy đơn hợp lệ gần nhất. `home_city` và `vinclub_tier` từ user/nguồn thành viên hoặc seed, không suy đoán từ click. New/active/dormant/churned dùng ngưỡng cấu hình, ghi config version trong kết quả job.

Consent kênh và quyền thu analytics/cá nhân hóa là hai mục đích cần mapping rõ. `gdpr_optin=false` chặn mọi kênh Insider theo checklist; mỗi kênh còn cần opt-in tương ứng. Null là chưa biết, không là true. V2 đề xuất `analytics` và `personalization` trong consent_history; không tuyên bố CDP thật đã có hai field đó. Giao dịch cần thiết để hoàn thành booking được ghi theo nghiệp vụ đã chốt; không mặc định dùng lịch sử đó cho marketing/cá nhân hóa khi bị chặn.

Rút consent: chặn tracking không cần thiết, xóa hàng đợi Web/outbox cho mục đích bị rút, cập nhật profile và Insider, vô hiệu cache cá nhân hóa. Batch kiểm consent ngay trước gửi; clone kiểm tiếp lúc nhận/kích hoạt. Không sao chép password hash, contact/guest names, input tự do sang Insider.

| Kho | Chính sách trong bản thiết kế |
|---|---|
| CDP core events | Demo giữ lâu dài theo handbook; không áp TTL Insider. Chính sách production/xóa dữ liệu phải chốt riêng |
| activity_events / web_sessions | Đề xuất 90 ngày cho telemetry không liên kết core và session; **activity context liên kết core giữ theo tuổi thọ core**, đặc biệt bookingId/nights/currency của purchase để tái dựng lịch sử. Cleanup kiểm core_event_id trước xóa; không áp TTL đồng loạt |
| identity_links / consent_history | Thời hạn phải theo mục đích và chính sách được chốt; không đặt mặc định vĩnh viễn cho triển khai thật |
| tracking_outbox | Chỉ xóa sau ACK + cửa sổ retry đã chốt; DEAD được review, không tồn vô hạn mặc định |
| Insider events | 90 ngày; purchase 730 ngày theo checklist clone |
| Recommendation logs | Đề xuất 90 ngày cho đo vận hành; snapshot evaluation độc lập gắn build/model |

Insider giữ bốn bảng lõi và `identifier_changes` tùy chọn của V1. Array mặc định append; job gợi ý dùng `not_append:true`, chia lô tối đa 1.000 user và dưới 5 MB, `null`/chuỗi rỗng không dùng để xóa thuộc tính. Clone kiểm header như hợp đồng Insider đã chốt. `insider_sync_runs` ghi số request, byte thực tế, user gửi/bỏ qua, lỗi và thời gian. Các channel event mở/click/bounce/unsubscribe chỉ seed/simulate, không gửi email thật.

## 11. Thông tin mà từng nhóm phải cung cấp

| Nhóm | Cần lấy / tạo | Không nên tự suy ra |
|---|---|---|
| Data | Catalog đúng loại, parent mapping, giá + bối cảnh, raw cache, lineage, tọa độ + precision, rating aggregate, components | Tồn realtime, giờ mở cửa chắc chắn khi nguồn mâu thuẫn, free child ticket từ số 0 |
| Frontend | Trigger semantic, IDs route/list, visibility/engagement, vị trí card, kỳ đi/số khách đã chọn, consent UI | cdpUserId tùy ý, giá chốt, purchase thành công |
| Backend | Auth mapping, eventId nghiệp vụ, ownership chuyến, giá/booking snapshot, validation, queue, requestId recommendation | Cookie anonymous là một người duy nhất trên mọi phiên |
| CDP | Ingest/dedupe, history, profile/consent API, identity scoped, retention, pagination | Enum/field production chưa được xác nhận |
| Recommendation | Text theo loại, trọng số/half-life, tổng hợp dwell, mapping property/room, exclusion theo trip, grounding | Mọi event đều là sở thích dương |
| Evaluation | Lịch sử sinh power-law/thưa, trip đúng đích, holdout, baseline, metric theo build | Chỉ số synthetic là hiệu quả trên khách thật |
| Insider | Merge rules, TTL, consent, identifiers, channel simulation, export | CDP history đầy đủ có thể lấy từ Insider sau TTL |

## 12. Phần nào cần làm trước?

**P0 — MVP chạy xuyên suốt:** giữ catalog, auth, booking, search/recommendation, core events/profiles, CdpClient; sửa dữ liệu parent/giá cần thiết; seed đủ lịch sử; đảm bảo user đặt xong gợi ý thay đổi, duplicate/retry không tạo hai purchase. Giỏ là phần có thể cắt theo checklist; search, login, vòng lặp booking và evaluation không cắt. Anonymous tracking, dwell, impression và toàn bộ 13 bảng bổ sung không phải điều kiện khởi động MVP.

**P1 — Đo được và tái dựng được:** lineage/snapshot nguồn, tracking_outbox, activity_events, thời gian xem và impression, request/rank attribution, profile job/cursor lịch sử, đo lỗi và coverage. Có thể vẫn chỉ dùng tài khoản đã đăng nhập.

**P2 — Mở rộng khi có nhu cầu:** identity anonymous nhiều phiên, detailed UI events, wishlist, hủy/refund thực, itinerary lưu dài hạn. Bảng V2 hiện mô tả tracking cho các event này, không giả vờ đã thiết kế đầy đủ nghiệp vụ wishlist/payment/refund hay tạo bảng cho tính năng chưa được yêu cầu.

## 13. Checklist nghiệm thu thiết kế và triển khai

- Import: tất cả key mẫu có nơi lưu; subtype đúng; parent thiếu bị báo rõ; null không thành 0/true; giá source khác giá mock.
- Tracking: một route một view; tab ẩn không tăng active time; snapshot 10/20/30 giây cho tổng 30; retry cùng ID không nhân event; clock skew bị gắn cờ.
- Attribution: list trả nhưng chưa hiện → không impression; click mở lỗi → có click nhưng không view; requestId/rank sai bị từ chối.
- Identity: anonymous không bị gán vào user khác; logout/đổi tài khoản cắt liên kết; chưa consent không có analytics event.
- Booking: 1 item → 1 purchase; hai đêm vẫn 1 event; tổng tiền lấy booking; retry/cancellation/đối soát đúng; một chuyến nhiều checkout cùng group hợp lệ.
- Consent: false/null chặn activation phù hợp; đổi consent khi queue đang chờ được xử lý; không xuất PII tự do.
- Recommendation: core + activity không đếm đôi; chỉ dùng event được phép, chưa hủy; cold start/fallback chạy được; exclusion theo chuyến.
- Evaluation: Recall@10/20, NDCG@10 và ba baseline; holdout trước khi tính popularity/profile, tránh rò rỉ purchase bị giấu. Đo catalog coverage, availability precision, cross-category và p95 như checklist gốc.
- Mỗi con số thử nghiệm ghi rõ **lịch sử khách hàng là dữ liệu sinh ra**, model/config/data version và build đã gắn tag. Bản tài liệu này không công bố kết quả benchmark.

## 14. Các quyết định cần chốt trước khi viết migration

1. Xác nhận schema CDP thật và chiến lược giữ bốn event lõi + extension V2. `activity_events` là thiết kế local đề xuất.
2. Chọn nguồn consent cho analytics/personalization và mapping sang cờ CDP/Insider hiện có; xác định retention áp dụng.
3. Chốt ownership catalog theo V1 (Backend) vì khác checklist handbook ban đầu (catalog ở CDP).
4. Chốt thay UK của event_group_id và flow user chọn chuyến; đây là thay đổi semantics thực sự.
5. Chốt projection, pagination, giới hạn ingest và các kiểu error trong OpenAPI; không coi các API V2 ở đây là endpoint đã chạy.
6. Xác nhận parent room, component combo, đơn vị/ngữ cảnh giá, thang điểm, giờ mở cửa và metadata POI còn mâu thuẫn.

Các điểm này được ghi để người triển khai biết điều gì còn chưa xác định. Việc tạo tài liệu V2 không chờ duyệt và không thay schema đang dùng.

## 15. Nguồn và cách dựng lại

- Schema nền: `diagrams/schema-database-toan-bo.json`, [thiết kế V1](thiet-ke-schema-3-service-chi-tiet.md), [handbook](recsys-internship-handbook-v3-vi.md).
- Mẫu đầu vào: `evidence/catalog-template-v2.json` (6 bản ghi do người dùng cung cấp, không phải crawl mới). Hash và mapping được ghi vào JSON V2.
- Mô hình đề xuất và mapping: `diagrams/schema_v2_data.py` → `diagrams/schema-database-toan-bo-v2.json`.
- Cây cha–con: `diagrams/schema_tree_v2.py` chọn một quan hệ chính có thật cho mỗi bảng con; 36 quan hệ trên cây và 24 liên kết bổ sung phủ đủ 60 quan hệ của V2, không đổi schema.
- Render sơ đồ: `diagrams/render-schema-v2.cjs` (Node.js + `@viz-js/viz`); dựng trang: `diagrams/render_schema_v2.py` (Python + Markdown).
- Tham khảo cách định nghĩa event: [Segment Track](https://www.twilio.com/docs/segment/connections/spec/track); cơ chế trình duyệt: [Page Visibility](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API), [sendBeacon](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/sendBeacon). Các ngưỡng thời gian, table/API mới là lựa chọn thiết kế trong tài liệu này, không phải yêu cầu từ các nguồn đó.

```bash
python3 docs/spec/diagrams/schema_v2_data.py
# Nếu @viz-js/viz không ở module path, đặt SCHEMA_NODE_MODULES tới thư mục node_modules.
node docs/spec/diagrams/render-schema-v2.cjs
python3 docs/spec/diagrams/render_schema_v2.py
```

HTML mặc định dùng cây cha–con có mở/thu nhánh và lọc theo service; bấm tên bảng để xem chi tiết. ERD đầy đủ có phóng to/kéo nằm trong phần thu gọn. Bộ lọc bảng và ma trận mapping vẫn được giữ. Mọi script chỉ đọc/ghi artifact tài liệu; không kết nối database, không bật tracker, không tải tài nguyên từ CDN.
