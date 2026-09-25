# Báo cáo thiết kế MVP — Hệ thống gợi ý du lịch

**Ngày:** 17/09/2026 · **Trạng thái:** phương án rút gọn để nhóm xem xét, chưa triển khai.

**Đã thống nhất với người dùng:** giữ Backend, CDP clone và Insider clone thành **3 service riêng**; giữ **bảng riêng cho từng loại sản phẩm**. Các lựa chọn rút gọn khác bên dưới là đề xuất của báo cáo, chưa thay thế hợp đồng API hiện hành.

## 1. MVP cần chứng minh điều gì?

Người dùng đăng nhập, tìm được dịch vụ phù hợp, đặt giả lập một dịch vụ và thấy gợi ý thay đổi theo lần đặt đó. Trợ lý tạo được lịch trình từ sản phẩm có thật. Insider nhận được hồ sơ và danh sách gợi ý để minh họa tích hợp.

**Phương án đề xuất: 3 service, 3 database, 19 bảng.** Backend có 13 bảng, CDP có 2 bảng, Insider có 4 bảng. Giữ việc tách loại sản phẩm nhưng giảm các bảng hỗ trợ, số bước checkout và số job phải vận hành.

| Giữ trong MVP | Cách làm gọn |
|---|---|
| Đăng nhập và cá nhân hóa | Seed tài khoản vào `users`; đăng nhập thông thường; không có `demo_accounts` |
| Catalog, tìm kiếm, sản phẩm tương tự | Dùng catalog hiện có, một model embedding, PostgreSQL + pgvector |
| Recommendation | Đọc lịch sử CDP, tính vector người dùng khi có request; chưa lưu bảng user vector |
| Đặt dịch vụ giả lập | Từ trang chi tiết đi thẳng tới checkout; mỗi đơn có một dòng dịch vụ |
| Phòng theo ngày | Một giá/phòng/đêm; một đơn vị tồn mỗi đêm; cửa sổ trượt 30 đêm |
| Trợ lý lịch trình | Một yêu cầu tạo một kế hoạch; thông tin bổ sung được gửi lại trong yêu cầu sau; không lưu hội thoại vào DB |
| Insider clone | Giữ bốn API và các quy tắc clone của handbook; một script đồng bộ có thể chạy bằng tay |
| Đánh giá | Giữ baseline, Recall@20, NDCG@10 và kiểm tra luồng đặt → gợi ý |

**Chưa làm:** giỏ hàng, đơn nhiều dịch vụ/nhiều điểm đến, thanh toán thật, hủy/hoàn tiền cho khách, tồn ghế bay, phân bổ tồn thành phần combo, giá theo mùa, hệ thống hàng đợi phân tán, dashboard quản trị. API hủy event nội bộ của CDP vẫn cần cho bù trừ checkout lỗi.

## 2. Dữ liệu nằm ở đâu?

![Sơ đồ MVP: ba service, ba database và luồng trao đổi](so-do-mvp.svg)

| Thành phần | Sở hữu dữ liệu | Gọi sang đâu? |
|---|---|---|
| **Backend / `ota_app`** | Sản phẩm, giá, lịch phòng, tài khoản, đơn đặt, vector | Gọi CDP qua `CdpClient`; gọi Insider qua `InsiderClient` |
| **CDP clone / `cdp`** | Hồ sơ, consent và lịch sử hành vi | Cung cấp API cho Backend và script seed |
| **Insider clone / `insider`** | Bản sao hồ sơ/gợi ý, định danh và tương tác kênh | Nhận dữ liệu từ script đồng bộ của Backend |

Web chỉ gọi Backend. Mỗi service chỉ truy cập database của mình; không JOIN hay đặt khóa ngoại xuyên database. Search, Recommendation và Agent là module trong Backend, không phải service mới.

Để chạy demo, có thể dùng **một PostgreSQL instance chứa ba database**, với ba tài khoản được giới hạn quyền theo database. Chỉ `ota_app` cần pgvector. Docker Compose chạy ba API và PostgreSQL; tách máy/database server là việc để sau.

`products.jsonl` chỉ được nạp vào Backend. CDP giữ `productId` trên event; Insider nhận top gợi ý. Không sao chép cả catalog và lịch phòng sang hai database còn lại.

## 3. Bảy bảng sản phẩm, cùng một cách đọc

### 3.1. Các trường chung

Mỗi bảng sản phẩm có `product_id` (UUID, khóa chính), `name`, `destination`, `description`, `image_url`, `available` và `attributes` (JSONB). `available` là cờ đang mở bán/hiển thị theo catalog; **không thay cho lịch còn phòng từng đêm**.

Năm bảng bán dịch vụ có thêm `unit_price` (số nguyên VND, có thể null), `price_unit` (theo enum hợp đồng; phòng là `PER_NIGHT`), `currency='VND'`, `available_from`, `available_to` và `bookable` (boolean, mặc định false). Giá null hoặc loại bán/đơn vị giá chưa rõ thì không checkout. Thuộc tính ít được truy vấn như tiện nghi, ảnh phụ, chính sách được giữ trong `attributes`, chưa tách thành bảng con.

### 3.2. Trường riêng cần có

| Bảng | Đại diện cho | Trường riêng tối thiểu / quy tắc |
|---|---|---|
| `hotel_properties` | Khách sạn/cơ sở lưu trú | `star_rating` dạng số thập phân; không đặt trực tiếp cơ sở |
| `hotel_rooms` | Hạng phòng | `property_product_id` FK → property; `max_occupancy`; `unit_price` là giá/đêm; số lượng phòng mỗi đơn = 1 |
| `flight_routes` | Tuyến bay | `origin`, `destination`; là dữ liệu nhóm, không đặt trực tiếp |
| `flight_services` | Chuyến bay có thể bán giả lập | `route_product_id` FK → route; `departure_at` có thể null; thuộc tính hãng/hạng vé trong JSON |
| `attraction_products` | Vé/tour/địa điểm tham quan | `ticketed` có thể null; chỉ bật `bookable` cho vé/tour đã xác định; POI không bán vé chỉ để khám phá |
| `combo_packages` | Gói dịch vụ | Quyền lợi trong `attributes`; bán cả gói ở một giá; không tự tạo hay trừ tồn các thành phần |
| `golf_products` | Voucher hoặc địa điểm golf | `ticketed` có thể null; chỉ voucher đã xác định mới được bật `bookable` |

**Quan hệ cha–con cần giữ:** phòng thuộc một khách sạn; chuyến bay thuộc một tuyến. Khi nhập dữ liệu, cha và con phải cùng điểm đến theo quy ước catalog. Không suy “có giá” thành “được đặt”.

Ngoài phòng, giá dùng cho **một đơn vị dịch vụ demo đã xác định**. Không tự suy thành giá/người, giá/đêm hoặc giá cho mọi ngày từ giá snapshot nguồn. Dịch vụ thiếu ngày áp dụng hoặc đơn vị giá được giữ ở chế độ xem; Data cần xác nhận fixture trước khi bật checkout.

### 3.3. Vì sao vẫn giữ `catalog_keys`?

`catalog_keys(product_id PK, product_kind, source_ref UNIQUE)` là danh bạ ID nhỏ cho bảy bảng. Nó không chứa nội dung hay giá sản phẩm. Booking và vector cần một nơi tham chiếu `product_id` bằng khóa ngoại, thay vì bảy cột ID tùy chọn.

- Mỗi bảng sản phẩm có FK từ `product_id` tới `catalog_keys`.
- `product_kind` có bảy giá trị tương ứng bảy bảng; đây là loại nội bộ. API vẫn dùng năm taxonomy: hotel, flight, attraction, combo, golf.
- Loader tạo registry và bản ghi sản phẩm trong cùng transaction; kiểm mỗi ID có đúng một bảng con và đúng loại. MVP dùng một luồng nhập dữ liệu, chưa có màn hình sửa sản phẩm tùy ý.
- Tạo **view `v_catalog` bằng UNION ALL** để Search/Recommendation đọc cùng một dạng `ProductSummary`; view không phải bảng lưu trữ mới. Mỗi nhánh JOIN registry để lấy nguồn và loại; property/route trả giá null, không đặt được.
- Giữ ID từ JSONL. Nạp lại theo ID phải cập nhật nội dung, không tạo ID mới. Khi ngừng bán, đặt `available=false`; chưa xóa cứng sản phẩm đã được đơn hàng tham chiếu.

## 4. Danh sách 19 bảng

### 4.1. Backend — 13 bảng

| # | Bảng | Các trường chính ngoài bảy bảng đã mô tả |
|---|---|---|
| 1–7 | Bảy bảng sản phẩm ở §3 | Nội dung, loại, giá và quan hệ cha–con |
| 8 | `catalog_keys` | `product_id`, `product_kind`, `source_ref` |
| 9 | `users` | `user_id` UUID PK, `email` UNIQUE, `password_hash`, `full_name`, `cdp_user_id` UNIQUE |
| 10 | `product_vectors` | `product_id` PK/FK → registry, `embedding`, `model_version`; một model và một chiều vector cố định cho một bản chạy |
| 11 | `hotel_room_nights` | PK (`room_product_id`, `stay_date`), `available`, `booking_item_id` nullable; FK → room và booking item |
| 12 | `bookings` | `booking_id` UUID PK, `user_id` FK, `reference_code` UNIQUE, `destination`, `event_group_id`, `total`, `currency`, `contact` JSONB, `idempotency_key`, `request_hash`, `created_at` |
| 13 | `booking_items` | `booking_item_id` UUID PK, `booking_id` FK/UNIQUE, `product_id` FK → registry, `using_date`, `check_out` nullable, `quantity`, `unit_price`, `price_unit`, `line_total`, `product_snapshot` JSONB |

`booking_items.booking_id` UNIQUE giới hạn **một dòng dịch vụ/đơn**. Phòng dùng `using_date=checkIn`, `check_out=checkOut`, `quantity=1`; các dịch vụ khác để `check_out=null`, quantity nguyên ≥ 1. Giữ bảng item để tương thích ID purchase và dễ mở rộng đơn nhiều dòng sau MVP.

Chỉ lưu đơn khi đã xác nhận thành công; trạng thái API có thể trả hằng `CONFIRMED`. Không có bảng trạng thái thanh toán. `UNIQUE(user_id, idempotency_key)` giúp lần gửi lại sau thành công nhận đúng đơn cũ; khác nội dung nhưng cùng key phải báo conflict.

`event_group_id` mặc định là UUID mới cho chuyến đi. Khi đặt tiếp dịch vụ cho cùng chuyến, Web gửi lại ID này; Backend chỉ chấp nhận nhóm đã thuộc người dùng đăng nhập và cùng điểm đến. Như vậy nhiều đơn một dòng vẫn gom được một chuyến mà không cần bảng `booking_groups`.

### 4.2. CDP — 2 bảng

| Bảng | Nội dung tối thiểu |
|---|---|
| `profiles` | `cdp_user_id` PK; lifecycle, thành phố, điểm đến gần nhất, hạng thành viên, tổng số đơn và các opt-in theo hợp đồng CDP |
| `events` | Khóa UNIQUE (`cdp_user_id`, `event_id`); `event_name`, `timestamp`, `product_id`, `taxonomy`, `event_group_id`, `quantity`, `unit_price`, `using_date`, `search_query`, `cancelled_at` |

Giữ tên trường API và cách chống trùng/hủy của hợp đồng CDP đang tham chiếu. `profiles` là snapshot do seed/job ghi; không mặc định tự cập nhật theo mỗi event. Recommendation lấy tín hiệu mới từ `events`.

CDP không đặt FK tới catalog Backend; lịch sử có thể tham chiếu sản phẩm không còn bán. Event đã hủy phải bị loại khỏi Recommendation. Không cần bảng product, booking hay vector trong CDP.

### 4.3. Insider — 4 bảng

| Bảng | Nội dung tối thiểu |
|---|---|
| `insider_profiles` | `profile_id` PK; `attributes` JSONB chứa bản sao consent và top gợi ý; `updated_at` |
| `identifiers` | (`identifier_type`, `identifier_value`) UNIQUE; `profile_id` FK; ánh xạ ID khách/email/điện thoại về hồ sơ |
| `insider_events` | `event_id` PK, `profile_id` FK, `event_name`, `timestamp`, `payload` JSONB, `expires_at` |
| `channel_events` | `event_id` PK, `profile_id` FK, `channel`, `event_name`, `timestamp`, `payload` JSONB; seed email/push/SMS để export |

Giữ bốn endpoint trong handbook: upsert, identity, profile, export. Giữ kiểm tra header, giới hạn lô 1.000 user/5 MB, append mảng trừ khi `not_append=true`, cập nhật identifier cùng kiểu và quy tắc giá trị rỗng. Event custom có TTL 90 ngày, purchase 730 ngày; lọc event hết hạn khi đọc, dọn bằng script khi cần.

Đây là phạm vi clone **theo handbook của dự án**, không phải tuyên bố đã kiểm chứng API Insider production hiện tại. `gdpr_optin=false` chặn mọi kênh; các opt-in theo kênh cũng phải được tôn trọng. Demo chỉ mô phỏng tương tác, không gửi email/SMS thật.

## 5. Lịch phòng: chỉ một bảng bổ sung

Giá nằm ngay trên `hotel_rooms.unit_price`; không có `hotel_room_prices`. Lịch nằm trên `hotel_room_nights`; không có bảng riêng cho kỳ lưu trú của booking.

Đặt `D` là ngày hiện tại theo `Asia/Ho_Chi_Minh`. Cửa sổ bán là **[D, D+30)**. Check-in ≥ D; check-out > check-in và ≤ D+30. Đêm checkout không chiếm tồn.

| Quy tắc | Cách thực hiện MVP |
|---|---|
| Một hạng phòng = một đơn vị tồn/đêm | Một khóa duy nhất (`room_product_id`, `stay_date`); không quản lý số phòng vật lý |
| Giá | `tổng = unit_price × số đêm`; không nhân thêm quantity phòng |
| Còn phòng | Đủ tất cả dòng lịch trong kỳ, tất cả còn mở; room và property còn hoạt động, room được bật `bookable` |
| Đặt thành công | Các đêm trong kỳ chuyển `available=false`, cùng trỏ tới `booking_item_id` |
| Không mất lịch khi seed lại | Chỉ thêm ngày thiếu; không ghi đè đêm đã khóa hay thay giá vận hành do nạp lại catalog |
| Sang ngày mới | Script/cron thêm đủ phần thiếu trong [D, D+30); giữ các dòng cũ phục vụ đối chiếu |
| Script chưa chạy / thiếu ngày | Trả không đủ dữ liệu để đặt, không tự coi ngày thiếu là còn phòng |

Ví dụ fixture: giá 1.000.000 VND/đêm, nhận phòng 18/09 và trả 21/09 → khóa các đêm 18, 19, 20; tổng 3.000.000 VND. Ngày 21 vẫn có thể nhận khách khác. Đây là giá demo minh họa, không phải báo giá nhà cung cấp.

Theo bản thống kê catalog ngày 17/09, có 4.646 room; seed toàn bộ cần **139.380 dòng lịch active**. Có thể chạy thử một tập room nhỏ đã chọn trước khi nạp đủ. Khi ngày trôi qua, bảng giữ lịch sử nên tổng số dòng có thể lớn hơn con số active này.

## 6. Checkout gọn, giữ tính đúng của lịch phòng

### 6.1. Luồng thành công

1. Web gửi một `productId`, quantity, ngày dùng; phòng có check-in/check-out; kèm thông tin liên hệ, giá đã thấy và một idempotency key giữ nguyên khi gửi lại cùng yêu cầu.
2. Backend lấy người dùng từ JWT; mở transaction và khóa dòng `users` của người đó để hai request checkout đồng thời của cùng người không tạo hai đơn cho cùng key. Kiểm tra đơn đã có theo key trước khi tiếp tục; cùng key khác `request_hash` thì từ chối.
3. Đọc và khóa bản ghi sản phẩm được mua; kiểm quyền bán, giá và ngày. Với phòng, khóa các dòng lịch theo thứ tự ngày bằng `SELECT FOR UPDATE`, rồi kiểm lại đủ đêm và chưa bị chiếm. Hai khách khác nhau tranh cùng đêm thì chỉ một giao dịch được đặt.
4. Tạo booking + một booking item, lưu giá/tên/đơn vị giá tại lúc đặt và khóa các đêm trong cùng transaction. Nếu giá khác giá Web đã thấy, trả lỗi để người dùng xác nhận lại; không âm thầm đổi tổng.
5. Gọi CDP **đồng bộ trước commit** với `eventId=purchase:{bookingItemId}`. UUID item sinh mới cho mỗi lần thử đã thất bại và rollback; gửi lại một lời gọi CDP của cùng lần thử giữ nguyên event ID. Với phòng, `unitPrice` là giá/đêm, `quantity=1`, `usingDate=checkIn`; tổng nhiều đêm lấy từ booking, không suy từ event hiện chưa có số đêm.
6. CDP xác nhận event đang có hiệu lực → commit booking, trả xác nhận. Web gọi lại Recommendation; Backend đọc lịch sử mới, không dùng cache cũ.

MVP kiểm các ràng buộc liên bảng trong một hàm checkout và các kiểm tra tích hợp; chưa dựng bộ constraint trigger phức tạp. Vẫn giữ PK/FK/UNIQUE, giá không âm, quantity hợp lệ và CHECK `booking_item_id IS NULL OR available=false` trên lịch. Hàm checkout phải kiểm item đúng room và liên kết đúng toàn bộ tập ngày.

### 6.2. Các lỗi cần xử lý

| Tình huống | Hành vi tối thiểu |
|---|---|
| Hết một đêm / sai ngày / loại không bán | Không tạo đơn; báo rõ nguyên nhân |
| CDP báo lỗi hoặc timeout | Rollback booking và lịch; ghi request ID và các event ID để kiểm tra/bù trừ nếu CDP đã nhận |
| CDP thành công, DB xác nhận commit thất bại | Hủy purchase qua API CDP; rollback lịch |
| Mất kết nối, chưa biết commit thành công hay chưa | Dùng kết nối mới tra đơn theo user + idempotency key; có đơn thì trả lại đơn, chắc chắn không có mới bù trừ. Nếu chưa tra được, báo đang cần kiểm tra; không tự tạo đơn mới hay hủy event |
| Đã thành công nhưng Web không nhận response | Gửi lại cùng key trả đơn cũ; không ghi thêm purchase |
| Hủy event cũng lỗi / tiến trình chết giữa hai bước | Ghi log lỗi để đối soát thủ công; sửa xong mới tiếp tục ca demo liên quan |

**Đánh đổi MVP:** chưa có outbox, journal hay worker tự khôi phục. Hai service không commit nguyên khối; purchase mồ côi vẫn có thể xảy ra và làm sai gợi ý đến khi được hủy. Lưu request ID, event ID và booking item ID trước lời gọi CDP; người vận hành kiểm booking và event bằng công cụ nội bộ rồi hủy event mồ côi. Không log token, thông tin liên hệ hoặc toàn payload. Nếu cần tự phục hồi sau crash, đó là bước nâng cấp tiếp theo.

Ghi nhận idempotency chỉ nằm trên đơn đã commit; đây không phải cơ chế lưu bền mọi lần checkout thất bại. Sau lỗi không rõ kết quả, phải dùng lại key và kiểm trạng thái trước khi bắt đầu một yêu cầu mới.

## 7. Gợi ý, Agent và đồng bộ Insider

### 7.1. Search và Recommendation

- Search đọc `v_catalog` + `product_vectors`, lọc điểm đến/loại/khả dụng và trả các trường card tối thiểu; chi tiết thuộc tính chỉ lấy khi mở sản phẩm hoặc Agent cần.
- Recommendation đọc tối đa 500 event gần nhất qua CDP, bỏ event đã hủy và ID không còn sản phẩm/vector hợp lệ. Tính vector người dùng từ các vector sản phẩm, có trọng số theo loại event và thời gian.
- Dùng `eventGroupId` xác định các danh mục đã mua trong chuyến hiện tại; ưu tiên gợi ý danh mục còn thiếu tại cùng điểm đến. Sau khi đặt phòng, fixture phải cho thấy thêm vé/chuyến bay phù hợp, không chỉ một danh sách phòng khác.
- Khách chưa có lịch sử hoặc CDP lỗi → `strategy=popular`, `because=[]`. Danh sách phổ biến có thể là file seed tính từ tập lịch sử huấn luyện; chưa cần bảng `product_popularity` hay API thống kê CDP mới. Nêu rõ fallback này không cập nhật realtime.
- Mỗi `because` dựa trên event thực. Có kỳ lưu trú thì kiểm lịch phòng; không có kỳ thì chỉ hiển thị giá tham khảo, không khẳng định còn phòng.

### 7.2. Agent

Một yêu cầu → trích xuất điểm đến/ngày/sở thích → gọi Search/Recommendation → sắp lịch → Backend kiểm ID, ngày, giá và tính tổng. Thiếu dữ kiện thì hỏi lại; Web gửi đầy đủ ngữ cảnh cần thiết trong yêu cầu tiếp theo. Không cần bảng conversation trong MVP.

Giữ các trạng thái `COMPLETED`, `NEEDS_CLARIFICATION`, `NO_RESULTS`, `FALLBACK`. Mọi sản phẩm phải có thật; giá thiếu thì tổng là chưa xác định, không coi là 0. Agent không tự checkout và không tự tạo nguồn cung.

### 7.3. Insider

Script do Backend sở hữu đọc danh sách `users` demo → lấy profile/consent từ CDP → gọi Recommendation → upsert bản sao hồ sơ và top gợi ý sang Insider. Gửi `not_append=true` cho mảng gợi ý để chạy lại thay danh sách cũ. Thiếu profile/consent thì bỏ qua kích hoạt, không mặc định opt-in.

Chạy script bằng tay cho demo; sau này mới lên lịch. Tắt Insider không chặn Search/booking. Bản MVP chưa đồng bộ mọi event CDP sang Insider; seed riêng event có TTL và tương tác kênh để kiểm hành vi clone. Khi consent thay đổi, cần chạy lại đồng bộ trước khi mô phỏng kích hoạt kênh.

## 8. Những gì được giảm so với báo cáo chi tiết

| Bản chi tiết | Phương án MVP |
|---|---|
| Bảng tiện nghi, giá/ngày quan sát, quyền lợi combo riêng | Để thuộc tính ít dùng trong JSON; chưa quản lý tồn thành phần combo |
| `hotel_room_prices` | Giá nằm trên `hotel_rooms` |
| `carts`, `cart_items` | Đi thẳng từ sản phẩm tới checkout |
| `booking_groups` | Một điểm đến/đơn; giữ `event_group_id` ngay trên booking |
| `booking_room_stays` | Check-in/check-out nằm trên booking item |
| `checkout_requests`, `checkout_purchase_journal` | Key/hash trên đơn thành công; bù trừ và đối soát thủ công khi lỗi |
| `product_popularity` | File baseline/fallback của bản demo |
| `assistant_conversations` | Agent nhận đủ ngữ cảnh trong mỗi yêu cầu |
| Sơ đồ 31 bảng của phương án chi tiết | 19 bảng; không tính view `v_catalog`, file fixture hay revision của Alembic |

Không thêm Kafka/Redis, bảng user vector, hệ thống workflow hoặc job scheduler riêng chỉ để làm demo. Các module có thể được mở rộng sau khi vòng lặp đặt → gợi ý đã chạy đúng.

## 9. Điểm phải điều chỉnh hợp đồng trước khi code

**Báo cáo này chưa sửa OpenAPI hoặc source code.** Working tree hiện có OpenAPI 0.1.0 với `paths: {}`; ref local `origin/data_contract` tại `0f630a2` có OpenAPI 1.3.0 và hợp đồng CDP. Đây là các bản đã đọc trong máy, không phải khẳng định remote mới nhất.

| Chủ đề | Đề xuất MVP cần Web/Backend/Data/Integration thống nhất |
|---|---|
| Checkout | Bổ sung luồng đặt trực tiếp một dịch vụ; hợp đồng hiện tham chiếu giỏ hàng, không mặc định dùng nguyên request cũ |
| Phòng | Thống nhất check-in/check-out, response availability theo ngày, `PER_NIGHT`, quantity=1 và cách báo thiếu lịch |
| Quyền đặt | Trả rõ khả năng đặt/đơn vị giá; property, route, POI hoặc loại chưa rõ phải bị chặn ở Backend |
| Retry checkout | Chốt tên header/field idempotency key, cách trả đơn cũ, lỗi key khác nội dung và trường hợp chưa rõ kết quả |
| Chuyến đi | Cho phép gửi lại `eventGroupId` đã thuộc người dùng và đúng điểm đến để gom nhiều đơn |
| Agent | Chốt cách gửi lại ngữ cảnh khi hỏi thêm; nếu contract vẫn cần `conversationId`, giữ ID tương quan nhưng không hứa lưu state server |
| Tài khoản demo | Seed `users`; bỏ phụ thuộc màn hình/API liệt kê persona; không có `demo_accounts` |
| Mã lỗi | Chốt schema lỗi hiện có cho hết phòng, giá thay đổi, CDP lỗi và cần đối soát; không tự tạo enum riêng trong từng team |

Giữ nguyên nguyên tắc CDP ghi purchase trước commit và hủy bù trừ theo hợp đồng đã đọc. Giữ bề mặt Insider theo handbook. Các đường cắt giỏ hàng/hội thoại được handbook cho phép khi cần thu hẹp, nhưng vẫn cần sửa fixture và generated client tương ứng.

## 10. Thứ tự làm và tiêu chí đủ MVP

| Bước | Sản phẩm bàn giao | Qua bước khi |
|---|---|---|
| 1. Chốt phạm vi và dữ liệu | Request/response tối thiểu, bảy loại sản phẩm, fixture giá/ngày/quyền bán | Cả Web và Backend dùng cùng contract; import lại không sinh ID mới |
| 2. Backend + CDP | Login, catalog, Search, lịch phòng, checkout và purchase | Hai request đặt trùng đêm chỉ một thành công; gửi lại key không sinh đơn/event mới |
| 3. Vòng lặp gợi ý | Recommendation + trang xác nhận tải gợi ý mới | Đặt phòng → event xuất hiện → top gợi ý phản ánh chuyến và danh mục còn thiếu |
| 4. Agent + Insider | Lịch trình một lượt; script sync; bốn API clone | Sản phẩm trong lịch trình có thật; upsert chạy lại không nối dài mảng; identity/TTL/consent/export đúng fixture |
| 5. Đánh giá và demo | Báo cáo chỉ số, bộ fixture lỗi, hướng dẫn chạy | Có kết quả thực đo và ghi rõ giới hạn, không chỉ ảnh màn hình happy path |

**Các ca nghiệm thu tối thiểu:**

1. Đăng nhập hai tài khoản có lịch sử khác nhau cho gợi ý khác nhau; khách mới có popular fallback.
2. Search, similar và chi tiết dùng đúng ID/giá/loại; POI có giá mock vẫn không được tự bật đặt.
3. Đặt ba đêm khóa đúng ba đêm; ngày checkout còn dùng được; thiếu một đêm thì cả đơn thất bại.
4. Hai người đặt cùng đêm → chỉ một đơn; gửi lại request thành công → đúng một purchase.
5. Chạy lại seed/job không mở lại đêm đã đặt và không thay giá phòng vận hành ngoài ý muốn.
6. Tắt CDP → Search vẫn chạy, Recommendation fallback, checkout không xác nhận; kiểm ca hủy event khi booking thất bại.
7. Đặt xong → gợi ý đổi ngay; event hủy không còn ảnh hưởng; đặt thêm dịch vụ cùng chuyến giữ đúng nhóm.
8. Insider ngừng hoạt động không chặn booking; opt-out không được kích hoạt; event quá TTL không còn được đọc; PATCH identifier giữ lịch sử; export trả đúng khoảng ngày.
9. Agent không bịa sản phẩm/giá; thiếu dữ kiện, không có kết quả và LLM lỗi đều có response rõ ràng.

**Đánh giá vẫn là phần của MVP.** Giấu lần đặt gần nhất, chỉ dùng lịch sử trước thời điểm đó để tạo user vector và baseline; không để purchase bị giấu lọt vào dữ liệu tính phổ biến. So sánh random, most-popular và most-popular-in-destination bằng Recall@20/NDCG@10. Báo thêm cross-category rate, availability precision, coverage, grounding và p95.

Mục tiêu tham chiếu từ handbook: vượt baseline phổ biến, availability precision ≥95%, coverage >20%, grounding 100%, p95 Search/Recommendation <300 ms, Agent <5 giây. Đây là **mục tiêu cần đo, chưa phải kết quả đạt được**. Tách kết quả bình thường và khi CDP timeout; fallback sau timeout dài không thể được tính là đã đạt p95 300 ms. Dữ liệu hành vi seed chỉ đánh giá pipeline trên dữ liệu tổng hợp, không chứng minh hiệu quả trên khách hàng thật.

## 11. Nguồn và cách đọc tiếp

- [Handbook dự án](../recsys-internship-handbook-v3-vi.md): §2 phạm vi/cách cắt giảm, §3 clone, §6 dữ liệu, §10 booking, §12 đánh giá.
- [Báo cáo database và luồng hiện tại](../ba-database-va-luong-du-lieu.html): ranh giới ba service và nguồn dữ liệu.
- [Thiết kế chi tiết trước đó](../thiet-ke-schema-3-service-chi-tiet.md): các ràng buộc/luồng nâng cấp khi MVP cần mở rộng.
- [Rà soát hợp đồng](../ra-soat-hop-dong-2026-09-17.html) và [bằng chứng catalog ngày 17/09](../evidence/catalog-audit-2026-09-17.json): số liệu catalog và khoảng cách với hợp đồng.
- Hợp đồng CDP/MVP đã tham chiếu bằng `git show origin/data_contract:docs/spec/hop-dong-tich-hop-cdp.md` và `git show origin/data_contract:src/shared/contracts/MVP.md`, commit `0f630a2`.

Tài liệu này là **một phương án khác trong thư mục `docs/spec/mvp/`**, không sửa hoặc xóa các báo cáo cũ. Đọc HTML ở `docs/spec/mvp/index.html`; sửa nội dung nguồn ở `docs/spec/mvp/bao-cao-mvp.md`.
