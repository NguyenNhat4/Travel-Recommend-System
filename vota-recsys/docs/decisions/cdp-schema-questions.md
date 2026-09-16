# CDP schema — câu hỏi cần xác nhận (Week 1)

> Spec §4.2 và §13: "Mirror CDP của V-OTA **field for field**. Chỗ nào không chắc thì **hỏi, đừng
> tự đặt** — field không tồn tại ở upstream là cái bẫy cho người tích hợp sau này."
> Handbook §17 đặt việc này vào **thứ Hai**.

Mỗi câu hỏi dưới đây ghi kèm **giá trị đang giả định**, để code vẫn chạy được khi chưa có câu trả
lời, và để giả định đó nhìn thấy được thay vì nằm im trong parser. Khi có câu trả lời: sửa giả
định, ghi ngày + người trả lời vào cột cuối, và nếu giả định sai thì mở một migration mới (không
sửa `001`/`002` đã apply).

**Cách dùng:** hỏi trong stand-up thứ Hai. Nếu đến thứ Tư vẫn chưa ai trả lời được câu nào thì
giữ nguyên giả định và ghi rõ trong `data-collection/README.md` rằng field đó là giả định của
nhóm, chưa phải contract.

---

## A. Bảng `products`

| # | Câu hỏi | Giả định hiện tại | Ảnh hưởng nếu sai | Trả lời |
|---|---|---|---|---|
| A1 | `products` thật có `available_from` / `available_to` không, và với một phòng khách sạn bán theo đêm thì hai field đó nghĩa là gì? Cửa sổ còn phòng, hay thời hạn hiệu lực của giá? | Đang set = cửa sổ của `quote_context` đã crawl (checkin → checkout). Sản phẩm không phụ thuộc ngày (vé, golf) để `NULL`. | Week 3 filter "còn chỗ" sẽ hiểu sai ngữ nghĩa | |
| A2 | `source_ref` là **scalar** trong §4.2, nhưng một product sau dedup có 2–4 nguồn. CDP thật lưu nguồn ở đâu — một field scalar, hay một bảng mapping như `product_sources`? | `products.source_ref` = `source_ref` của member `is_primary` (nguồn thắng field `name`); toàn bộ mapping nằm ở `product_sources`. | Người tích hợp sau sẽ mất thông tin nguồn phụ | |
| A3 | `unit_price NUMERIC(14,2)` — CDP lưu giá **một đêm**, giá **toàn bộ kỳ nghỉ**, hay giá chưa/đã gồm thuế & phí? | Giá 1 đêm / 1 vé / 1 lượt, đã gồm thuế nếu nguồn công bố kiểu đó, `attributes.priceIncludesTax` ghi lại điều đã biết. | So sánh giá giữa các nguồn sai lệch hệ thống | |
| A4 | `currency CHAR(3) NOT NULL` — CDP có lưu giá ngoại tệ gốc, hay chỉ VND đã quy đổi? | Chỉ VND. Giá gốc + tỷ giá + `as_of` giữ ở `products_normalised` và `crawl_runs.stats.fx`. | Mất khả năng audit giá gốc | |
| A5 | `attributes` JSONB — CDP có khoá key theo taxonomy không, và có registry key chính thức không? Tên key là camelCase (`starRating`) hay snake_case? | camelCase đúng như §5.2, validator từ chối key ngoài registry. | Week 2/3 query JSONB bằng tên key sai | |
| A6 | `quality_score` và `images[]` — §4.2 gọi là "cột hỗ trợ, không thuộc contract CDP". Xác nhận CDP thật **không** có hai cột này? | Không có ở CDP; chỉ tồn tại local. | Dư cột khi thay bằng CDP thật | |
| A7 | `destination` là text tự do hay enum/foreign key tới bảng destination của CDP? Nếu là enum thì danh sách 15 giá trị §6.1 có khớp? | Text tự do, giá trị lấy đúng 15 tên §6.1, không map được → `'unknown'`. | Value không khớp upstream | |

## B. Bảng `profiles`

| # | Câu hỏi | Giả định hiện tại | Ảnh hưởng nếu sai | Trả lời |
|---|---|---|---|---|
| B1 | `lifecycle_stage` — tập giá trị chính xác? Handbook nói `new/active/dormant/churned`, nhưng ngưỡng ngày cụ thể do CDP định nghĩa hay do consumer tự tính? | `new` (0 booking), `active` (≤90 ngày), `dormant` (91–365), `churned` (>365). Ngưỡng khai trong `config.yaml`. | Segment sai → recommendation strategy sai | |
| B2 | `vinclub_tier` — danh sách tier thật của VinClub? | `none / silver / gold / platinum / diamond`, phân phối giảm dần. | Giá trị bịa lọt vào demo | |
| B3 | `purchased_verticals TEXT[]` — giá trị là taxonomy (`hotel`,`flight`,…) hay tên vertical kinh doanh riêng? | Đúng 5 taxonomy §5.1. | Cross-category Week 3 đọc sai | |
| B4 | `days_since_last_booking` — CDP tự tính (materialised) hay consumer tính? Tính mốc từ ngày booking hay ngày sử dụng? | Materialised, mốc = `timestamp` của purchase event gần nhất, so với `--now`. | Lệch ngày giữa hệ thống | |
| B5 | `home_city` — dùng tên thành phố tự do, hay cùng vocabulary với `destination`? | Cùng vocabulary §6.1 cộng thêm vài thành phố nguồn không nằm trong 15. | Filter theo home_city vỡ | |
| B6 | 4 cờ opt-in (`gdpr/email/sms/push`) — `gdpr_optin=false` có nghĩa chặn **tất cả** kênh (như Insider) hay chỉ chặn marketing? | Chặn tất cả, đúng như handbook §3 nói về Insider. | Vi phạm consent | |

## C. Bảng `events`

| # | Câu hỏi | Giả định hiện tại | Ảnh hưởng nếu sai | Trả lời |
|---|---|---|---|---|
| C1 | `event_name` — tập giá trị đầy đủ? §4.2 liệt kê `purchase/add_to_cart/product_view/search` với ghi chú ngầm là chưa đủ. | Đúng 4 giá trị đó, không thêm. | Event lạ bị consumer bỏ qua | |
| C2 | `event_group_id` — format thật? Ví dụ handbook là `OFF20260810001`. Nó là mã đơn hàng, mã session, hay mã chuyến đi? | Mã đơn: `OFF` + `yyyymmdd` + seq 3 chữ số, 1 group = 1 trip = 1 destination. | Week 3 gom trip sai | |
| C3 | Event `search` có `product_id` không (§4.2 cho phép NULL), và query text lưu ở đâu — `payload`? | `product_id` NULL, query ở `payload.query`. | Mất tín hiệu search | |
| C4 | `product_id` **cố tình không có FK** (§4.2). Xác nhận CDP thật cũng vậy, và event trỏ vào product đã xoá là hành vi mong đợi? | Đúng, không FK; seed cố tình sinh một ít event dangling. | Nếu CDP có FK thì insert sẽ fail khi thay client thật | |
| C5 | `quantity` và `unit_price` trên event — là giá tại thời điểm mua (snapshot) hay tham chiếu về `products`? | Snapshot tại thời điểm mua. | Giá lịch sử bị viết lại | |
| C6 | `using_date` — với hotel là ngày check-in, với flight là ngày bay, với vé là ngày vào cổng? Multi-night thì lưu ngày nào? | Ngày bắt đầu sử dụng; số đêm ở `payload.nights`. | Lịch trình Week 4 sai ngày | |

## D. Ngữ nghĩa destination

| # | Câu hỏi | Giả định hiện tại | Ảnh hưởng nếu sai | Trả lời |
|---|---|---|---|---|
| D1 | **HPH (Cát Bi, Hải Phòng) có nên map về `Hạ Long`?** Hải Phòng là thành phố khác, nhưng HPH là cửa ngõ bay thực tế của Hạ Long và §9 liệt kê HPH trong danh sách chặng bay. `Hải Phòng` không nằm trong 15 destination chuẩn §6.1. | **Có map** HPH → `Hạ Long`, kèm comment trong `config.yaml`. Không có map thì ~25% catalog flight rơi vào `destination='unknown'`. | Product nằm sai destination, hoặc mất khỏi filter | |
| D2 | `Nam Hội An` là destination riêng (§6.1 tách khỏi `Hội An`) — ranh giới ở đâu? Chỉ khu Vinpearl Nam Hội An, hay cả huyện Duy Xuyên/Thăng Bình? | Chỉ khu Nam Hội An (Vinpearl + VinWonders Nam Hội An); phần còn lại → `Hội An`. | Hai destination lẫn vào nhau | |
| D3 | `destination` của một **chuyến bay** là điểm đến hay điểm khởi hành? | Điểm **đến** (`canonical(arrival IATA)`); `originIata` vào `attributes`. Quyết định này cũng chốt invariant §10 "1 trip = 1 destination". | Mỗi trip có 2 destination → filter vô dụng | |
| D4 | `Cam Ranh`/`Bãi Dài`/`CXR` → `Nha Trang` (§6.1 nêu ví dụ này). Xác nhận CDP cũng gộp, chứ không tách Cam Ranh riêng? | Gộp về `Nha Trang`. | Lệch với upstream | |

## E. `users` / `bookings` (demo-only)

| # | Câu hỏi | Giả định hiện tại | Ảnh hưởng nếu sai | Trả lời |
|---|---|---|---|---|
| E1 | `users.password_hash` — Week 2 dùng Spring Security. Thuật toán nào? | **bcrypt** (`BCryptPasswordEncoder` verify trực tiếp được, không cần config thêm). | Week 2 không login được bằng account seed | |
| E2 | `bookings.reference_no` — format mã đặt chỗ thật? | `VP` + `yyyymmdd` + 6 ký tự base32, UNIQUE. | Chỉ ảnh hưởng demo | |
| E3 | `bookings` có cần trạng thái (`confirmed/cancelled/refunded`) không? §4.2 không có cột đó. | Không có; mọi booking coi như confirmed. | Không mô phỏng được huỷ chỗ | |

## F. Câu hỏi vận hành (không thuộc schema nhưng cần trả lời Week 1)

| # | Câu hỏi | Giả định hiện tại | Trả lời |
|---|---|---|---|
| F1 | Đếm 2.000–5.000 product ở **grain** nào — mỗi room type một product, hay mỗi property một product? | **Room-type** (§9: "mỗi room type là 1 product"). Ở grain property trần chỉ ~700 và DoD không thể đạt. | |
| F2 | Ai review schema CDP trong Week 1 (handbook §17 câu 3)? | Chưa có người → mọi giả định trong file này còn mở. | |
| F3 | Có được phép crawl vinpearl.com ở mức 0.5 rps không, hay cần xin phép nội bộ trước? | Được, vì là nội dung của chính công ty; vẫn tôn trọng `robots.txt` và chạy 0.5 rps. | |
| F4 | Tỷ giá dùng để quy đổi ngoại tệ — lấy nguồn nào và chốt ngày nào? | Tỷ giá cố định trong `config.yaml` kèm `as_of`, ghi vào README §12.3. | |
