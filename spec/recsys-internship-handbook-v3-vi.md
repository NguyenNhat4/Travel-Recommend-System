# Xây dựng Sản phẩm Gợi ý Du lịch

**V-OTA · Vinpearl Travel — Sổ tay Chương trình Thực tập**

Chào mừng các bạn. Trong sáu tuần tới, các bạn sẽ xây dựng một bản demo đặt dịch vụ du lịch chạy được thật, với một recommendation engine nằm ở trung tâm: khách hàng có thể tìm kiếm, đăng nhập, nhận gợi ý cá nhân hóa, trò chuyện với một trợ lý lên kế hoạch chuyến đi, và đặt dịch vụ.

Năm tuần dành để xây dựng. Tuần thứ sáu dành để viết báo cáo và trình bày. Code freeze vào thứ Năm của Tuần 5.

Stack: Java 21 với Spring Boot, PostgreSQL kèm extension pgvector, và một frontend web. Python chỉ dùng cho các script thu thập dữ liệu và đánh giá.

---

## 1. Ý tưởng, gói gọn trong một trang

Tìm kiếm thông thường khớp theo từ. Nếu khách hàng gõ "nghỉ dưỡng biển cho gia đình" và không mô tả nào chứa đúng những từ đó, họ nhận được một trang trống và họ rời đi.

Tìm kiếm ngữ nghĩa (semantic search) khớp theo *ý nghĩa*. Một embedding model đọc văn bản và biến nó thành một dãy số — thường là 384 hoặc 768 số — gọi là một vector. Model được huấn luyện sao cho những đoạn văn bản có ý nghĩa tương tự sẽ tạo ra những dãy số tương tự. "Beach resort for families" và "Vinpearl Resort Nha Trang - Deluxe Ocean View" nằm gần nhau dù không chia sẻ từ nào.

Gợi ý (recommendation) chính là pipeline đó, với *khách hàng* đóng vai trò câu truy vấn. Lấy tất cả sản phẩm họ đã xem hoặc đã đặt, tra vector của từng sản phẩm, lấy trung bình, và bạn có một điểm đại diện cho gu của người đó. Những sản phẩm gần nhất chính là gợi ý của bạn.

Trợ lý lịch trình lại cũng chính là pipeline đó, được bọc trong một cuộc hội thoại. "Lên kế hoạch ba ngày ở Nha Trang cùng trẻ nhỏ" trở thành vài lượt tìm kiếm mà kết quả của chúng được một LLM sắp xếp thành một kế hoạch.

**Một engine, ba khuôn mặt.** Hãy ghi nhớ điều đó — đó là thứ giữ cho dự án này không biến thành ba dự án riêng biệt.

```
[User Query] ──> [Embedding Model] ──> [Query Vector]
                                              │
                                              ▼
[Products] ──> [Embedding Model] ──> [Vector Database] ──> [Top K Results]
```

```
user_vector = normalise( Σ weight(event) × decay(cách đây bao lâu) × vector(product) )
```

---

## 2. Những gì các bạn sẽ xây dựng

Năm phần, một hệ thống.

| Phần | Là gì |
| --- | --- |
| **1. Nền tảng dữ liệu** | Kho hàng du lịch thật được thu thập trong Tuần 1, cộng với bản clone chạy được của CDP và Insider — hai nền tảng mà hệ thống này nằm ở giữa trong môi trường production |
| **2. Recommendation engine** | Embeddings, vector search, user profiles. `/search`, `/similar`, `/recommendations` |
| **3. Tài khoản và cá nhân hóa** | Đăng nhập, session, và gợi ý khác nhau cho từng khách hàng đã đăng nhập |
| **4. Trợ lý lịch trình** | Một giao diện chat gợi ý kế hoạch du lịch theo từng ngày, xây dựng trên chính search engine của các bạn |
| **5. Trang demo và luồng đặt dịch vụ** | Browse → search → detail → cart → checkout → confirmation, đầu cuối |

### Thứ gắn kết tất cả lại với nhau

Khi một khách hàng đặt dịch vụ trong bản demo của các bạn, lần đặt đó trở thành một event. Event đó nuôi user vector. Trang gợi ý tiếp theo thay đổi.

**Đặt một khách sạn ở Nha Trang, rồi nhìn gợi ý chuyển sang vé máy bay và vé tham quan.** Riêng vòng lặp đó, được demo trực tiếp, có giá trị hơn bất kỳ slide nào bạn có thể làm. Hãy xây dựng hướng tới nó một cách có chủ đích — đó là lý do luồng đặt dịch vụ nằm trong phạm vi dự án.

### Thứ tự xây dựng

| Thứ tự | Sản phẩm bàn giao | Mốc |
| --- | --- | --- |
| 0 | Thu thập dữ liệu · CDP clone · Insider clone | Tuần 1 |
| 1 | `/search` và `/similar` · khung web · đăng nhập | Tuần 2 |
| 2 | `/recommendations` · luồng đặt dịch vụ · vòng lặp phản hồi | Tuần 3 |
| 3 | Trợ lý lịch trình · trang chủ cá nhân hóa | Tuần 4 |
| 4 | Hoàn thiện, tích hợp, đánh giá | Tuần 5 |

### Nếu bị chậm tiến độ

Không có tuần dự phòng, và phạm vi này là lớn. Hãy cắt bỏ theo thứ tự sau, từng thứ một:

1. Diversity re-ranking và tinh chỉnh index
2. Nghiên cứu ablation thu hẹp lại còn hai biến
3. Hybrid keyword + vector search
4. Giỏ hàng — đi thẳng từ trang chi tiết sản phẩm sang checkout
5. Chế độ khách hàng ngủ đông (dormant)
6. Trợ lý lịch trình trở thành single-turn (một câu hỏi, một kế hoạch) thay vì hội thoại

**Không bao giờ được bỏ:** tìm kiếm, gợi ý, đăng nhập, vòng lặp phản hồi từ đặt dịch vụ đến gợi ý, hoặc bộ khung đánh giá. Năm thứ đó chính là bản demo.

### Ngoài phạm vi

Thanh toán thật, xác nhận đặt chỗ thật gửi cho bất kỳ ai, tự huấn luyện mạng nơ-ron của riêng mình, và bất cứ thứ gì ghi vào CDP hay Insider production. Hãy đưa chúng vào đề xuất Tuần 6 của các bạn.

---

## 3. Tuần 1: nền tảng dữ liệu và các bản clone nền tảng

Nhiệm vụ đầu tiên của các bạn là thu thập kho hàng du lịch thật và nạp vào một cơ sở dữ liệu có hình dạng giống cách CDP của V-OTA lưu trữ dữ liệu.

### Bốn nguồn

| Nguồn | Cho bạn thứ gì | Ưu tiên |
| --- | --- | --- |
| **vinpearl.com** | Kho hàng Vinpearl thật — khách sạn, resort, vé VinWonders, golf, combo — với nội dung sản phẩm tiếng Việt do chính công ty viết. Là catalog liên quan nhất mà bạn có thể có, và là thứ bản demo của bạn nên phô diễn. | Bắt đầu từ đây |
| **booking.com** | Độ phủ rộng về lưu trú trên khắp các điểm đến Việt Nam, thuộc tính có cấu trúc phong phú, phân loại nhất quán | Cao |
| **agoda.com** | Độ phủ mạnh ở châu Á - Thái Bình Dương, thường tốt hơn các trang toàn cầu với các cơ sở nội địa Việt Nam | Cao |
| **trip.com** | Vé máy bay song song với lưu trú, cộng thêm điểm tham quan — hữu ích cho gợi ý xuyên danh mục ở Tuần 3 | Trung bình |

**Làm vinpearl.com trước, và đừng coi nó chỉ là một trong bốn nguồn.** Đó là nội dung của chính công ty bạn: các mô tả tiếng Việt là đầu vào embedding chất lượng cao nhất bạn có được, các sản phẩm là thứ mà stakeholder nhận ra ngay trong bản demo, và không có rào cản chống bot nào phải vượt qua. Hoàn thành nó trong một hai ngày đầu, và bạn đã có một catalog dùng được trước khi đụng tới bất cứ thứ gì khó hơn.

Ba nguồn còn lại bổ sung độ phủ, giá của đối thủ để so sánh, và kho vé máy bay cùng điểm tham quan giúp việc gợi ý xuyên danh mục có thể demo được. Hãy coi chúng là phần làm giàu trên một nền tảng vốn đã hoạt động.

**Cùng một cơ sở lưu trú xuất hiện trên nhiều trang.** Vinpearl Resort Nha Trang tồn tại trên vinpearl.com, booking.com và agoda.com với tên, mô tả và giá khác nhau. Khử trùng lặp (deduplication) là công việc thật sự — hãy lên kế hoạch cho nó, và quyết định sớm nguồn nào thắng ở từng trường dữ liệu. Một mặc định hợp lý: vinpearl.com cho tên và mô tả, các OTA cho giá và tình trạng còn chỗ.

### Thu thập những gì

Nhắm tới khoảng **2.000–5.000 sản phẩm** trải trên khách sạn, vé máy bay, điểm tham quan và combo, phủ **10–15 điểm đến Việt Nam**. Nhiều hơn thế không thêm được gì ở giai đoạn này — độ rộng của điểm đến quan trọng hơn độ sâu ở bất kỳ điểm đến đơn lẻ nào.

Mỗi sản phẩm cần: tên, mô tả, danh mục, điểm đến, giá, hạng sao hoặc hạng vé, tiện ích hoặc thuộc tính, hình ảnh, và tọa độ nếu có.

**Thu thập dữ liệu sản phẩm, không phải dữ liệu con người.** Bỏ qua đánh giá, tên người đánh giá, và bất cứ thứ gì về từng du khách cá nhân. Nó không hữu ích cho embeddings — văn bản đánh giá mô tả một kỳ nghỉ, không phải sản phẩm — và nó biến cơ sở dữ liệu của bạn thành thứ gắn liền với nghĩa vụ bảo vệ dữ liệu. Điểm đánh giá tổng hợp và số lượng đánh giá thì ổn và hữu ích.

### Ghi chú thực tế

Sinh viên mới ra trường thường đánh giá thấp công sức thu thập và đánh giá quá cao độ sạch của kết quả. Vài điều sẽ giúp bạn tiết kiệm nhiều ngày:

- **Cache mọi trang thô hoặc phản hồi xuống đĩa trước khi parse.** Khi parser của bạn hóa ra sai vào thứ Năm — và điều đó sẽ xảy ra — bạn parse lại từ cache thay vì fetch lại toàn bộ. Riêng thói quen này đáng giá hơn bất kỳ thói quen nào khác.
- **Tự giới hạn tốc độ và kiểm tra `robots.txt`.** Chậm mà chắc thì về đích; hung hăng thì bị chặn, và một lần bị chặn tốn nhiều thời gian hơn phần tiết kiệm được rất nhiều.
- **Làm sao để có thể chạy tiếp được.** Lưu tiến độ, xử lý lỗi theo từng item, và đừng bao giờ để một trang lỗi giết chết một lần chạy đã kéo dài hai tiếng.
- **Hãy chuẩn bị tinh thần dữ liệu sẽ lộn xộn.** Thiếu mô tả, danh mục không nhất quán, giá ở các loại tiền tệ khác nhau, cơ sở trùng lặp trên nhiều trang. Khử trùng lặp và chuẩn hóa mới là phần lớn công việc, không phải việc fetch.
- **Ghi lại từng trường dữ liệu đến từ đâu.** `data-collection/README.md` phải đủ để một người khác tái dựng lại bộ dữ liệu của bạn mà không cần đọc code.

### Đặt giới hạn thời gian

**Nếu đến thứ Tư Tuần 1 bạn vẫn chưa có dữ liệu dùng được, hãy rút lui về phương án dự phòng.** vinpearl.com đáng lẽ phải dễ, nhưng cả ba OTA đều chạy cơ chế chống bot, và mất một tuần ở đây đồng nghĩa mất luôn recommendation engine — thứ mới thật sự là dự án này.

Các phương án dự phòng tốt, cũng đáng dùng làm nguồn bổ sung kể cả khi việc thu thập diễn ra suôn sẻ:

| Nguồn | Bạn nhận được gì |
| --- | --- |
| **Amadeus Self-Service APIs** | Hơn 150.000 khách sạn kèm mô tả, xếp hạng và ảnh, cộng thêm chuyến bay và hoạt động. Có gói test miễn phí, SDK Java chính thức. |
| **Bộ dữ liệu công khai** | Các bộ dữ liệu du lịch trên Kaggle; dữ liệu RecSys 2019 của trivago |
| **OpenStreetMap / Wikivoyage** | Điểm đến, điểm tham quan, points of interest cho trợ lý lịch trình |

### Thứ quan trọng nhất

**Tên và mô tả sản phẩm chính là thứ mà embedding model thực sự đọc.** Nếu chúng ra chung chung hoặc bị cắt cụt, semantic search không thể được demo một cách thuyết phục và phần so sánh model ở Tuần 2 của bạn trở nên vô nghĩa.

Nội dung sản phẩm bằng tiếng Việt là tài sản giá trị nhất của bộ dữ liệu này. Hãy tối ưu việc thu thập cho nó, kiểm tra thủ công một mẫu trước khi tuyên bố Tuần 1 đã xong, và nếu một nguồn cho mô tả tốt hơn hẳn nguồn khác, hãy nghiêng về nguồn đó.

### Hai bản clone nền tảng

Song song với catalog, Tuần 1 tạo ra các bản sao chạy được của hai nền tảng mà hệ thống này sẽ nằm ở giữa trong môi trường production. Các bạn **không** kết nối tới hệ thống thật nào cả — các bạn đang xây các bản thay thế cục bộ hành xử giống chúng.

Đây không phải việc làm cho có. Viết service của bạn dựa trên một bản sao trung thực nghĩa là khi một đội trong tương lai có quyền truy cập production, họ chỉ cần thay một implementation thay vì viết lại công sức của bạn. Viết dựa trên một thứ tự bịa cho tiện nghĩa là họ phải làm lại từ đầu.

#### CDP clone

Về cơ bản chính là cơ sở dữ liệu bạn vốn đang xây, được cấu trúc đúng cách. Nó là **system of record**: hồ sơ khách hàng, đồng thuận (consent), và toàn bộ lịch sử những gì người dùng đã làm.

Bảng và trường phải phản chiếu CDP của V-OTA **chính xác** — cùng tên, cùng kiểu, cùng hình dạng (§6). Chỗ nào không chắc, hãy hỏi thay vì bịa.

Truy cập nó qua một interface `CdpClient`, không bao giờ chạm thẳng vào bảng. Một implementation bây giờ, đọc cục bộ. Một implementation thứ hai sau này, đọc production. Interface đó là dòng code giá trị nhất trong cả dự án.

#### Insider clone

Một service nhỏ tách riêng, phơi ra đúng bề mặt API thật của Insider. Trong khi CDP clone là một cơ sở dữ liệu, thì cái này là một **nền tảng giả lập** — nó nhận dữ liệu, kiểm tra hợp lệ theo đúng cách Insider làm, lưu lại, và trả về hiển thị.

Hãy cho nó những endpoint sau:

| Endpoint | Hành vi cần tái hiện |
| --- | --- |
| `POST /user/v1/upsert` | Chèn hoặc cập nhật thuộc tính và event của khách hàng. Tối đa 1.000 user mỗi request, body 5 MB. Thuộc tính dạng mảng mặc định sẽ *append* trừ khi gửi `not_append: true`. |
| `PATCH /user/v1/identity` | Đổi một identifier trong khi vẫn giữ lịch sử. Một user mỗi request, không batching. `old_identifier` và `new_identifier` phải cùng kiểu. |
| `POST /user/v1/profile` | Trả về hồ sơ đã lưu của một khách hàng |
| `POST /raw/v1/export` | Trả về các event tương tác kênh trong một khoảng ngày |

Và những quy tắc sau, vì chúng là những thứ gây đau trong production:

- Header `X-PARTNER-NAME` phải viết thường, `X-REQUEST-TOKEN` phải có mặt, nếu không thì từ chối với 403
- Custom event hết hạn sau 90 ngày; purchase sau 730 ngày. Event cũ hơn đơn giản là biến mất.
- `gdpr_optin: false` nghĩa là khách hàng không nhận được gì cả, qua bất kỳ kênh nào
- Gửi `""` hoặc `null` **không** xóa một thuộc tính — nó lưu lại giá trị rỗng

**Tại sao phải ép cả những phần khó chịu?** Một stub chấp nhận mọi thứ thì chẳng dạy bạn điều gì và giấu mọi lỗi cho tới ngày tích hợp. Một bản clone từ chối lô 1.001 user hoặc lặng lẽ append vào mảng mới là thứ khiến client của bạn thực sự đúng. Riêng quy tắc hết hạn 90 ngày tồn tại để dạy một sự thật kiến trúc quan trọng nhất ở đây: **lịch sử đặt dịch vụ dài hạn nằm ở CDP, không nằm ở Insider.** Ai đọc lịch sử từ Insider sẽ âm thầm mất phần lớn dữ liệu.

Hãy seed nó với dữ liệu tương tác kênh — email mở, click, bounce, hủy đăng ký — để nó có thứ gì đó mà export ngược lại.

**Giữ nó nhỏ gọn.** Một người, thứ Năm và thứ Sáu Tuần 1. Đó là một service mỏng trên vài bảng kèm quy tắc kiểm tra hợp lệ; nó không phải một sản phẩm thứ hai.

---

## 4. Kiến trúc

```
┌─────────────── DEMO WEB APP ────────────────┐
│  Home (personalised)   Search    Product    │
│  Cart    Checkout      Confirmation         │
│  Login / Register      Chat assistant       │
└───────────────────┬─────────────────────────┘
                    │ REST + JWT
                    ▼
┌──────────────── SPRING BOOT SERVICE ────────────────┐
│                                                     │
│  AuthController            BookingController        │
│  SearchController          RecommendationController │
│  ChatController ──────┐                             │
│                       │ calls its own search        │
│  ┌────────────────────▼──────────────────────────┐  │
│  │  EmbeddingService ──> pgvector ──> Top-K      │  │
│  │  UserProfileBuilder ──> user vector           │  │
│  └───────────────────────────────────────────────┘  │
│                       │                             │
│  CdpClient ───────────┴─────────── InsiderClient    │
│  ← cả hai đều là interface, đều có thể thay cho production │
└────────┬──────────────────────────────┬─────────────┘
         ▼                              ▼
┌──── CDP CLONE (Postgres) ────┐  ┌─── INSIDER CLONE ────┐
│  products · profiles         │  │  POST /user/v1/upsert│
│  events · bookings           │  │  PATCH /identity     │
│  users · product_vectors     │  │  POST /raw/v1/export │
│                              │  │                      │
│  system of record            │  │  attributes · events │
│  full history                │  │  90-day TTL          │
└──────────────────────────────┘  └──────────────────────┘
         ▲                                ▲
         │ bookings trở thành events      │ gợi ý
         └──── vòng lặp phản hồi          └──── dưới dạng attributes
```

---

## 5. Lựa chọn kỹ thuật

| Tầng | Lựa chọn | Vì sao |
| --- | --- | --- |
| Backend | Java 21 + Spring Boot 3.x | Chuẩn của đội |
| Thư viện AI | Spring AI | Xử lý cả embeddings lẫn chat model. Một thư viện cho cả hai — đừng mang thêm thư viện thứ hai vào. |
| Embedding | Multilingual ONNX sentence transformer, chạy trong JVM | Chạy cục bộ, không gọi mạng mỗi request, không tốn phí theo lượt gọi |
| Chat model | Một LLM qua chat interface của Spring AI | Cần API key và ngân sách chi phí — nêu vấn đề ngay Tuần 1 |
| Lưu trữ vector | PostgreSQL + pgvector | Một cơ sở dữ liệu cho mọi thứ |
| Xác thực | Spring Security + JWT | Chuẩn mực, tài liệu tốt, không cần dịch vụ bên thứ ba |
| Frontend | Chọn một và đừng đổi. React, hoặc Thymeleaf nếu đội mạnh về phía server. | Cái nào đưa được một trang lên màn hình trong Tuần 2 |
| Thu thập dữ liệu | Python | Chỉ Tuần 1 |
| Hạ tầng | Docker Compose + GitHub Actions | Một lệnh khởi động mọi thứ |

### ⚠️ Embedding model là lựa chọn duy nhất bạn không được sai

Catalog là tiếng Việt. Model mà mọi tutorial đều dùng, `all-MiniLM-L6-v2`, chỉ hỗ trợ tiếng Anh và sẽ cho kết quả gần như ngẫu nhiên trên dữ liệu này. Hãy thử nghiệm những model sau trong Tuần 2:

- **`intfloat/multilingual-e5-base`** (768 chiều) — truy xuất đa ngôn ngữ mạnh, mặc định tốt
- **`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`** (384) — nhỏ hơn và nhanh hơn
- **`BAAI/bge-m3`** — chất lượng tốt nhất, nặng nhất

Số chiều được lưu trong schema cơ sở dữ liệu của bạn. Đổi model về sau đồng nghĩa với index lại toàn bộ. **Hãy quyết định bằng đo đạc trong Tuần 2.**

---

## 6. Mô hình dữ liệu

Phản chiếu CDP của V-OTA từng trường một. Chỗ nào không chắc, hãy hỏi thay vì bịa — một trường không tồn tại ở hệ thống thượng nguồn là cái bẫy cho bất cứ ai tích hợp hệ thống này về sau.

### CDP clone

| Bảng | Phản chiếu | Chứa gì |
| --- | --- | --- |
| `products` | CDP catalog | Tất cả danh mục sản phẩm |
| `profiles` | CDP Profile Store | `lifecycle_stage`, `days_since_last_booking`, `lifetime_order_count`, `vinclub_tier`, `purchased_verticals`, `home_city`, `last_destination`, các trạng thái opt-in |
| `events` | CDP Event Store | Lượt xem, tìm kiếm, đặt dịch vụ — bao gồm cả những event do chính bản demo của bạn tạo ra |
| `users` (chỉ dành cho demo) | — | Thông tin đăng nhập, liên kết tới một `cdp_user_id` |
| `bookings` (chỉ dành cho demo) | — | Những gì đã được đặt trong bản demo |
| `product_vectors` | — | Lưu trữ pgvector |

### Insider clone

| Bảng | Chứa gì |
| --- | --- |
| `insider_profiles` | Thuộc tính nhận qua Upsert, khóa theo identifier. Đây là bản sao của Insider — **cố tình** là một tập con của những gì CDP nắm giữ. |
| `insider_events` | Event nhận qua Upsert, hết hạn sau 90 ngày (730 với purchase) |
| `channel_events` | Email mở, click, bounce, hủy đăng ký; push và SMS. Được seed sẵn, và export ngược lại qua `/raw/v1/export`. |
| `identifiers` | Ánh xạ `cdp_user_id`, email và số điện thoại về một profile, để endpoint identity PATCH có thứ để thao tác |

**Sự phân tách giữa hai bên chính là trọng tâm.** CDP giữ mọi thứ mãi mãi; Insider giữ một tập con trong 90 ngày. Xây đúng như vậy và ràng buộc đó sẽ tự dạy bạn.

```json
// Product
{
  "productId": "382ae67c-c8d9-4c51-ad04-f2acabfbf5b9",
  "name": "Vinpearl Resort Nha Trang - Deluxe Ocean View",
  "taxonomy": "hotel",              // hotel | flight | combo | attraction | golf
  "destination": "Nha Trang",
  "description": "...",
  "attributes": { "starRating": 5, "oceanView": true, "familyFriendly": true },
  "unitPrice": 3400000,
  "currency": "VND",
  "available": true,
  "availableFrom": "2026-09-15",
  "availableTo": "2027-03-31",
  "imageUrl": "...",
  "sourceRef": "amadeus:HTNHA001"   // dữ liệu này đến từ đâu
}
```

```json
// UserEvent — luôn khóa theo cdp_user_id
{
  "cdpUserId": "VP0092381",
  "eventName": "purchase",          // purchase | add_to_cart | product_view | search
  "timestamp": "2026-08-10T14:22:00Z",
  "productId": "382ae67c-...",
  "taxonomy": "hotel",
  "eventGroupId": "OFF20260810001", // gom nhóm một chuyến đi — bạn cần cái này ở Tuần 3
  "quantity": 2,
  "unitPrice": 3400000,
  "usingDate": "2026-10-02"
}
```

### Seed lịch sử khách hàng

Việc scrape cho bạn sản phẩm, không cho bạn khách hàng. Bạn vẫn cần khách hàng với lịch sử đặt dịch vụ hợp lý, nên hãy sinh ra họ — nhưng sinh cho tử tế, vì dữ liệu ngẫu nhiên khiến một recommender hỏng trông vẫn có vẻ ổn:

- **Chuyến đi, không phải event rời rạc.** Việc đặt dịch vụ đi thành cụm: khách sạn, rồi vé máy bay cho cùng khoảng ngày, rồi vé tham quan — cùng chia sẻ một `event_group_id`. Đây là toàn bộ cơ sở của gợi ý xuyên danh mục.
- **Một chuyến đi, một điểm đến.** Nếu không, việc lọc theo điểm đến trông sẽ vô dụng.
- **Độ phổ biến theo luật lũy thừa (power-law).** Một số ít sản phẩm chiếm phần lớn lượt đặt. Đây là điều khiến baseline theo độ phổ biến trở nên khó đánh bại.
- **Khách hàng thưa thớt.** Phần lớn chỉ có 1–5 event mỗi năm. Nếu ai cũng có năm mươi event, cold start không bao giờ được kích hoạt và bạn sẽ không xây nó.
- **Các giai đoạn vòng đời.** Một số mới, một số đang hoạt động, một số ngủ đông sáu tháng, một số đã rời bỏ.
- **Những rìa lộn xộn.** Thiếu mô tả, khách hàng đã opt-out, event trỏ tới sản phẩm đã bị xóa.

**Kiểm tra tỉnh táo:** nếu baseline theo độ phổ biến cho điểm gần bằng không, dữ liệu của bạn quá ngẫu nhiên. Nếu không gì đánh bại được nó, dữ liệu quá tập trung.

---

## 7. Hình dạng response của API — thiết kế phần này trong Tuần 2

API của bạn nuôi web app, trợ lý chat, và về sau là một job phân phối thật. Nó phải tự giải thích được, và phải giữ cho nhỏ — Upsert của Insider chấp nhận khoảng 5 KB mỗi khách hàng, đó là lý do bạn trả về top 3 đến 5 kèm tên và link thay vì top 50.

```json
GET /recommendations?k=3        // Authorization: Bearer <jwt>

{
  "cdpUserId": "VP0092381",
  "generatedAt": "2026-09-12T10:14:22Z",
  "modelVersion": "multilingual-e5-base-v1.2",
  "strategy": "cross_vertical",
  "nextVertical": "flight",
  "destination": "Nha Trang",
  "recommendations": [
    {
      "rank": 1,
      "productId": "7c2f...",
      "name": "Vé máy bay Hà Nội - Cam Ranh",
      "taxonomy": "flight",
      "priceString": "1.890.000",
      "imageUrl": "...",
      "score": 0.81,
      "because": [
        { "productName": "Vinpearl Resort Nha Trang - Deluxe Ocean View",
          "event": "purchase", "daysAgo": 3, "contribution": 0.62 }
      ]
    }
  ],
  "diagnostics": {
    "eventsUsed": 14,
    "coldStart": false,
    "excludedVerticals": ["hotel"],
    "latencyMs": 47
  }
}
```

Mảng `because` không phải đồ trang trí. Khi một gợi ý trông có vẻ sai, nó là ranh giới giữa một cuộc tranh cãi và một chẩn đoán. Hãy hiển thị nó cả trên UI nữa — khách hàng tin tưởng gợi ý hơn khi họ thấy được lý do, và stakeholder hiểu hệ thống nhanh hơn.

---

## 8. Xác thực và cá nhân hóa

Xác thực tồn tại ở đây vì một lý do: **để bản demo có thể cho những người khác nhau thấy những gợi ý khác nhau.** Hãy giữ nó đơn giản đúng như vậy.

- Đăng ký và đăng nhập, email và mật khẩu, băm bằng BCrypt
- JWT phát hành khi đăng nhập, gửi dưới dạng Bearer token, hạn ngắn
- Mỗi dòng user ánh xạ tới một `cdp_user_id`, đó là cách recommendation engine nhận diện họ
- Seed sẵn vài tài khoản demo với lịch sử dựng sẵn khác nhau — một khách hay đi Nha Trang, một khách lần đầu, một người ngủ đông sáu tháng, một người hoàn toàn không có lịch sử

Những tài khoản seed đó chính là kịch bản demo của bạn. Đăng nhập lần lượt từng tài khoản và cho thấy trang chủ thay đổi ra sao là cách minh chứng rõ ràng nhất rằng cá nhân hóa hoạt động.

**Đừng xây:** OAuth provider, xác minh email, luồng đặt lại mật khẩu, phân cấp vai trò. Không thứ nào trong số đó minh chứng được điều gì về gợi ý.

---

## 9. Trợ lý lịch trình

Trợ lý gợi ý kế hoạch du lịch theo từng ngày. "Gợi ý lịch trình 3 ngày ở Nha Trang cho gia đình có trẻ nhỏ" → một kế hoạch với các sản phẩm thật, đặt được.

**Quyết định thiết kế quan trọng: LLM không tự bịa ra khách sạn. Nó gọi search engine của bạn.**

Điều này quan trọng vì ba lý do. Mọi sản phẩm trong kế hoạch đều là thật và đặt được, nên bản demo không sụp đổ khi ai đó bấm vào. Trợ lý trở thành một bên tiêu thụ mọi thứ bạn đã xây thay vì là một dự án riêng. Và nó suy giảm một cách êm ái — nếu LLM chậm hoặc không khả dụng, bạn vẫn có thể hiện kết quả tìm kiếm bên dưới.

```
Tin nhắn của khách hàng
        ↓
LLM trích xuất ý định → { destination, days, party, interests }
        ↓
Service của bạn chạy vài lượt tìm kiếm — lưu trú, điểm tham quan, ăn uống
        ↓
Tùy chọn trộn thêm /recommendations nếu khách hàng đã đăng nhập
        ↓
LLM sắp xếp các kết quả thật thành một kế hoạch theo từng ngày
        ↓
Kế hoạch được render kèm giá thật và link đặt dịch vụ hoạt động được
```

**Giữ nó hẹp.** Nó lên kế hoạch chuyến đi. Nó không trả lời câu hỏi chung chung, không xử lý việc đặt chỗ, không duy trì hội thoại dài. Một trợ lý tập trung luôn chạy được thắng một trợ lý mở rộng thỉnh thoảng mới chạy.

Ghi chú thực tế: đặt API key trong configuration, không bao giờ trong repository. Đặt giới hạn chi tiêu ngay Tuần 1. Cache lại phản hồi trong lúc phát triển để bạn không phải trả tiền test lại cùng một prompt năm mươi lần. Nếu chi phí hoặc độ trễ thành vấn đề, phương án dự phòng là single-turn — một câu hỏi, một kế hoạch, không hội thoại.

---

## 10. Luồng đặt dịch vụ

Browse → search → product detail → cart → checkout → confirmation. Không thanh toán thật. Form checkout thu thập thông tin và trang xác nhận hiển thị một mã tham chiếu.

Điều quan trọng nằm ở bước cuối: một lần đặt hoàn tất sẽ **ghi một event vào bảng `events`**, khóa theo `cdp_user_id`, với một `event_group_id` gom nhóm chuyến đi.

Đó chính là vòng lặp phản hồi ở §2. Đặt một khách sạn, refresh trang chủ, thấy gợi ý chuyển sang vé máy bay. Xây phần này ở Tuần 3 và test sớm — đó là khoảnh khắc bản demo của bạn thành công hay không.

---

## 11. Từng tuần một

Các bảng theo tuần dưới đây được tổ chức theo workstream, không theo cá nhân. Năm luồng chạy song song:

| Workstream | Bao gồm |
| --- | --- |
| **Data** | Thu thập, cơ sở dữ liệu, interface `CdpClient`, bộ dựng văn bản biến một sản phẩm thành một câu đáng để embed |
| **Search** | Embedding service, đánh index vector, schema pgvector, `/search` và `/similar` |
| **Backend** | `/recommendations` và User Profile Builder, xác thực, booking API, chat backend |
| **Web** | Trang demo: home, search, product detail, cart, checkout, confirmation, login, chat UI |
| **Evaluation** | Bộ khung đánh giá, chỉ số, baseline, và kiểm tra chất lượng dữ liệu |

Tuần 1 thì khác. Việc thu thập dữ liệu chặn mọi thứ khác, nên Search và Backend gia nhập workstream Data cho tới thứ Tư rồi mới nhận mảng riêng của mình từ thứ Năm.

### Tuần 1 — Nền tảng dữ liệu

**Mục tiêu:** một cơ sở dữ liệu đầy kho hàng du lịch thật, các bản clone chạy được của cả hai nền tảng, và embedding đầu tiên đã chạy.

| Workstream | Công việc |
| --- | --- |
| **Data** | Dẫn dắt việc thu thập (§3). Xây pipeline, cache phản hồi thô, xử lý giới hạn tốc độ và lỗi, khử trùng lặp và chuẩn hóa. CDP clone: schema khớp CDP thật từng trường một, nạp catalog cộng với lịch sử khách hàng đã seed. |
| **Search** | Hỗ trợ thu thập từ thứ Hai đến thứ Tư. Từ thứ Năm: làm cho `POST /embed` chạy được — export một model đa ngôn ngữ sang ONNX, nối với Spring AI, xác nhận độ tương đồng hợp lý trên các câu tiếng Việt. |
| **Backend** | Hỗ trợ thu thập từ thứ Hai đến thứ Tư. Từ thứ Năm: định nghĩa interface `CdpClient` và `InsiderClient` cùng hợp đồng OpenAPI cho toàn bộ endpoint. |
| **Web** | Dựng project frontend, chạy được, deploy được. Wireframe cho mọi trang. Đừng chờ API — xây dựa trên stub. |
| **Evaluation** | Bộ sinh lịch sử khách hàng (§6). Cài đặt các chỉ số kèm unit test. Thứ Năm–thứ Sáu: Insider clone (§3) — bốn endpoint và các quy tắc kiểm tra hợp lệ khiến nó hành xử như hàng thật. |

**Đọc:** Google Recommendation Systems course phần 1–2 · Stanford CS224N Lecture 1 · Sentence-Transformers introduction.

**Thứ Sáu:** workstream Data trình bày CDP clone — bao nhiêu sản phẩm, những danh mục nào, những điểm đến nào, với tên tiếng Việt thật hiển thị được, và một khách hàng có các event gom lại thành một chuyến đi. Insider clone minh chứng ba điều: một Upsert hợp lệ thành công, một lô 1.001 user bị từ chối, và một thuộc tính mảng bị append trong tình huống đáng lẽ không nên. Mọi người trình bày độ tương đồng cosine giữa ba cụm từ du lịch tiếng Việt do chính mình viết.

### Tuần 2 — Tìm kiếm và trang web

| Workstream | Công việc |
| --- | --- |
| **Data** | Hoàn thiện bộ dựng văn bản. Câu mô tả khách sạn và câu mô tả chuyến bay không nên được dựng theo cùng một cách, và điều này quan trọng hơn cả việc chọn model. |
| **Search** | Nạp toàn bộ product vector vào pgvector kèm metadata. `GET /search?q=` và `GET /similar/{productId}`. |
| **Backend** | Đăng ký, đăng nhập, JWT. Các tài khoản demo đã seed. |
| **Web** | Home, trang kết quả tìm kiếm, chi tiết sản phẩm, đăng nhập. Nối với endpoint thật khi chúng xuất hiện. |
| **Evaluation** | So sánh model — gán nhãn thủ công khoảng 80 cặp truy vấn tiếng Việt → sản phẩm và đo các ứng viên. Lập bảng và đưa ra khuyến nghị. |

**Đọc:** HNSW paper phần 1–3 · MTEB leaderboard, tab multilingual · Spring AI ONNX docs.

**Thứ Sáu:** tìm "nghỉ dưỡng biển cho gia đình" trên chính website và nhận được kết quả hợp lý. Đăng nhập bằng hai tài khoản khác nhau. Chốt một embedding model và số chiều.

### Tuần 3 — Gợi ý và vòng lặp phản hồi ⭐ tuần cốt lõi

Ba điều đặc thù của du lịch làm hỏng một cách triển khai ngây thơ:

1. **Ý định chuyến đi hết hạn.** Sự quan tâm tới Nha Trang biến mất khi chuyến đi kết thúc. Gom nhóm theo `event_group_id`; giảm trọng số mạnh tay với các chuyến đã kết thúc.
2. **Lấy trung bình sẽ gợi ý thêm những thứ y hệt.** Người chỉ đặt khách sạn sẽ nhận thêm khách sạn — trái ngược hoàn toàn với mục đích. Hãy loại trừ những danh mục đã đặt cho chuyến đi này, rồi mới tìm kiếm.
3. **Dữ liệu thưa là chuyện bình thường.** Người ta đặt dịch vụ du lịch một đến ba lần mỗi năm. Đây chính xác là lý do embedding dựa trên ý nghĩa là lựa chọn đúng cho V-OTA và vì sao các phương pháp cần nhiều tương tác mỗi người dùng thì không. Hãy sẵn sàng giải thích điều đó trong bài trình bày của bạn.

| Workstream | Công việc |
| --- | --- |
| **Data** | Gom event thành chuyến đi; suy ra các danh mục đã đặt, điểm đến gần nhất, ngày đi sắp tới |
| **Search** | Tra cứu product vector nhanh — việc lấy trung bình cần điều này |
| **Backend** | User Profile Builder với trọng số và half-life đặt trong config. Bộ lọc loại trừ danh mục. `/recommendations`. Booking API ghi event ngược trở lại. |
| **Web** | Cart, checkout, confirmation. Khu vực cá nhân hóa trên trang chủ. |
| **Evaluation** | Bộ khung: giấu lần đặt gần nhất của mỗi khách hàng, thử dự đoán nó. Baseline: random, most-popular, most-popular-in-destination. Recall@10/20, NDCG@10. |

**Đọc:** ⭐ Airbnb, "Real-time Personalization using Embeddings for Search Ranking" (KDD 2018) — phiên bản đã công bố gần nhất với đúng bài toán của các bạn. Hãy đọc cho tử tế.

**Thứ Sáu:** ⭐ vòng lặp. Đăng nhập, đặt một khách sạn ở Nha Trang, quay lại trang chủ, cho thấy gợi ý đã đổi sang vé máy bay và vé tham quan. Nếu cái này chạy, bản demo chạy.

### Tuần 4 — Trợ lý và cá nhân hóa

| Workstream | Công việc |
| --- | --- |
| **Data** | Làm giàu sản phẩm phục vụ lịch trình — giờ mở cửa, thời lượng, vị trí, để kế hoạch có ý nghĩa |
| **Search** | Các biến thể tìm kiếm mà trợ lý cần: theo điểm đến, theo danh mục, theo ngân sách |
| **Backend** | Chat backend (§9): trích xuất ý định, điều phối tìm kiếm, soạn kế hoạch. Cold start cho khách hàng dưới 3 event. Chế độ dormant. |
| **Web** | Chat UI. Render lịch trình với sản phẩm thật và link đặt dịch vụ hoạt động được. Hiển thị phần giải thích. |
| **Evaluation** | Chạy lại mọi thứ ở quy mô đầy đủ. Kiểm tra tỉnh táo đầu ra của trợ lý: sản phẩm có thật không, có còn chỗ không, có đúng thành phố không? |

**Đọc:** Tài liệu Spring AI chat model · hướng dẫn prompting của nhà cung cấp LLM bạn chọn.

**Thứ Sáu:** hỏi trợ lý một lịch trình ba ngày cho gia đình ở Nha Trang, nhận về một kế hoạch với sản phẩm thật, bấm vào và đặt một cái.

### Tuần 5 — Tích hợp, hoàn thiện, đóng băng

Đây là tuần cuối cùng còn ai viết code. Hãy lên kế hoạch như vậy ngay từ thứ Hai.

**Thứ Hai–thứ Tư:** kiểm thử tích hợp đầu-cuối toàn bộ hành trình. Hybrid keyword + vector search — điều này quan trọng với những cái tên như VinWonders mà embedding xử lý kém. Tinh chỉnh index. Nghiên cứu ablation và chương kết quả. Web: trạng thái rỗng, trạng thái đang tải, trạng thái lỗi, bố cục mobile. Deploy lên staging.

**Cũng thứ Hai–thứ Tư:** khép kín vòng kích hoạt. Một batch job tính gợi ý cho mọi khách hàng và đẩy chúng vào Insider clone dưới dạng attribute, thông qua `InsiderClient` — chia lô 1.000 user, dưới 5 MB, `not_append: true` trên các mảng, loại trừ khách hàng bị chặn. Việc này mất khoảng một ngày khi mà cả client lẫn clone đều đã tồn tại, và nó là thứ khiến kiến trúc trở nên trọn vẹn: CDP vào, gợi ý được tính, Insider ra. Hãy đo và báo cáo các con số — bao nhiêu request, bao nhiêu byte mỗi khách hàng, toàn bộ tập khách hàng mất bao lâu.

**Thứ Năm** — ổn định, rồi đóng băng vào cuối ngày. Không thêm hành vi mới. Đóng bug, xóa các test hay lỗi vặt, hoàn thiện OpenAPI spec, nhờ một người chưa từng chạy dự án làm theo README từ đầu. Gắn tag release.

Mọi con số trong báo cáo Tuần 6 của bạn phải được tái tạo từ bản build đã gắn tag này. Nếu báo cáo và bản demo trực tiếp mâu thuẫn nhau, bài trình bày sẽ sụp đổ — và đây luôn là nguyên nhân.

**Thứ Sáu** — bàn giao sang giai đoạn viết báo cáo. Chạy chỉ số lần cuối · đóng băng kết quả · quay một video demo dự phòng, cả màn hình lẫn âm thanh, toàn bộ hành trình · mỗi workstream viết một trang khi mọi thứ còn tươi mới.

### Tuần 6 — Báo cáo và demo

Tuần này không merge gì cả. Một bug bạn tìm thấy lúc này sẽ đi vào mục "hạn chế đã biết". Biết khi nào nên dừng là một kỹ năng chuyên nghiệp và phần lớn mọi người học nó muộn.

Mười người không thể cùng viết một tài liệu. Mỗi workstream soạn phần của mình, Evaluation sở hữu chương kết quả, một người sở hữu mạch xuyên suốt.

| Ngày | Trọng tâm |
| --- | --- |
| **Thứ Hai** | Thống nhất dàn ý, phân công các phần. Bắt đầu viết từ ghi chú hôm thứ Sáu. Khung slide — một câu chuyện, không phải năm bộ slide. |
| **Thứ Ba** | Bản nháp đầy đủ. Mọi hình vẽ lấy từ bản build đã gắn tag. Viết kịch bản demo: chính xác tài khoản nào, chính xác truy vấn nào, chính xác thứ tự nào. Xác nhận video dự phòng chạy được trên máy trình bày. |
| **Thứ Tư** | Rà soát và chỉnh sửa. Dựng slide. Đề xuất "sáu tuần tiếp theo" — mọi thứ đã cắt bỏ, cộng với việc kết nối tới CDP và Insider thật. |
| **Thứ Năm** | Hai lần tổng duyệt đầy đủ, bấm giờ. Mỗi người sở hữu một đoạn ba phút. Những câu hỏi khó: làm sao bạn biết nó hoạt động? nếu khách hàng hoàn toàn mới thì sao? trợ lý có bao giờ bịa ra khách sạn không? |
| **Thứ Sáu** | Ngày demo · retrospective · phản hồi cá nhân |

**Về buổi demo:** chạy trên bản build đã đóng băng, trên một máy bạn kiểm soát được. Giữ video dự phòng mở sẵn ở cửa sổ thứ hai. Biết chính xác bạn đang đăng nhập bằng tài khoản nào và nó sẽ hiện ra cái gì. Một bản demo chết trước mặt stakeholder làm phí năm tuần lao động thật, và nguyên nhân gần như luôn là do môi trường.

---

## 12. Làm sao biết nó hoạt động

| Chỉ số | Nó hỏi điều gì | Mục tiêu |
| --- | --- | --- |
| **Recall@20** | Trong số những gì khách hàng thực sự đã đặt, chúng ta có nó trong top 20 không? | Vượt baseline độ phổ biến một cách rõ rệt |
| **NDCG@10** | Thứ đúng có nằm gần đỉnh không, chứ không chỉ là có mặt? | Vượt baseline |
| **Cross-category rate** | Tỷ lệ gợi ý thuộc danh mục chưa được đặt trong chuyến đi này | Chính là mục đích của `/recommendations` |
| **Availability precision** | Tỷ lệ gợi ý thực sự đặt được | ≥ 95% |
| **Catalog coverage** | Tỷ lệ sản phẩm xuất hiện trong top 20 của ít nhất một người | > 20% |
| **Assistant grounding** | Tỷ lệ mục trong lịch trình là sản phẩm thật, đúng thành phố | 100%. Một khách sạn bịa ra là một bản demo thất bại. |
| **Latency p95** | `/recommendations`, và trợ lý tính đầu-cuối | < 300 ms · < 5 s |

**Phương pháp:** giấu lần đặt gần nhất của mỗi khách hàng, dự đoán nó từ toàn bộ dữ liệu trước đó. Ba baseline bắt buộc: random, most-popular, và most-popular-in-that-destination.

Cái thứ ba quan trọng nhất. Một hệ thống không đánh bại được "cứ gợi ý thứ gì đang phổ biến ở Nha Trang" là một hệ thống không hoạt động, dù code trông tinh vi đến đâu.

**Một lưu ý phải nêu mỗi lần bạn báo cáo một con số:** lịch sử khách hàng là dữ liệu được sinh ra, nên những con số này đo xem pipeline có hoạt động không, chứ không đo nó sẽ chạy thế nào trên khách hàng thật. Hãy nói điều đó trước khi có người hỏi.

**Và một cảnh báo về workstream này.** Với phạm vi lớn như vậy, đánh giá là thứ đầu tiên bị ép — nó vô hình trong một bản demo theo cách mà một trang checkout hỏng thì không. Nó cũng là thứ duy nhất biến "kết quả trông ổn với chúng tôi" thành bằng chứng. Khi lịch trình siết lại, hãy rút việc khỏi evaluation **sau cùng**, không phải đầu tiên.

---

## 13. Những thứ sẽ làm bạn vấp

| Cái bẫy | Vì sao nó xảy ra | Phải làm gì |
| --- | --- | --- |
| Tuần 1 bốc hơi vào việc thu thập | Cơ chế chống bot thực sự khó, và việc parse lộn xộn hơn vẻ ngoài | Cache phản hồi thô để parse lại không tốn gì. Mốc kiểm tra thứ Tư: không có dữ liệu dùng được thì chuyển sang Amadeus hoặc bộ dữ liệu công khai. |
| Insider clone phình thành một sản phẩm | Xây một nền tảng giả lập thú vị hơn mức đáng lẽ nên có | Bốn endpoint, các quy tắc kiểm tra hợp lệ, xong. Hai ngày. Nhiều hơn là một dự án khác. |
| Lịch sử được sinh ra mà không có quy luật | Ngẫu nhiên thì dễ; thực tế thì tốn công | §6. Nếu baseline độ phổ biến cho điểm gần bằng không, dữ liệu sai chứ không phải model sai |
| Trợ lý bịa ra khách sạn | LLM làm vậy khi prompt còn chỗ trống | Nó chỉ sắp xếp những sản phẩm mà search của bạn trả về. Không bao giờ để nó tự đặt tên một sản phẩm. |
| Frontend và backend trôi xa nhau | Hai đội, một hợp đồng | OpenAPI thống nhất từ Tuần 1, stub từ ngày đầu, tích hợp hằng tuần chứ không phải vào cuối |
| Chạm vượt qua `CdpClient` hoặc `InsiderClient` | Lúc đó làm vậy nhanh hơn | Mọi thứ đi qua interface. Chúng là thứ khiến dự án này tái sử dụng được. |
| Dùng embedding model chỉ hỗ trợ tiếng Anh | Đó là mặc định trong mọi tutorial | Thử nghiệm các model đa ngôn ngữ ở Tuần 2 |
| Chỉ gợi ý đúng danh mục đã đặt | Lấy trung bình gây ra điều này về mặt cấu trúc | Bộ lọc loại trừ danh mục, và hãy đo nó |
| Coi ý định chuyến đi là vĩnh viễn | Cấu hình decay sao chép từ ví dụ mua sắm | Gom nhóm theo `event_group_id` |
| Xác thực phình to vượt quá đăng nhập | Đó là bài toán quen thuộc, dễ chịu | Đăng nhập, JWT, tài khoản seed sẵn. Không gì hơn. |
| Hết tuần | Không có đệm, và phạm vi này lớn | Dùng thứ tự ưu tiên ở §2 ngay lần lỡ hẹn thứ Sáu đầu tiên |

**Lời khuyên quan trọng nhất:** khi bạn bị kẹt, hãy nói ra ngay trong ngày. Mọi người ở đây đều mới với việc này. Hỏi vào thứ Ba tốn một tiếng; im lặng vật lộn tới thứ Sáu tốn cả tuần — của bạn và của người đang chờ bạn.

---

## 14. Danh sách tài liệu đọc

*Các liên kết đã được kiểm tra vào tháng 9 năm 2026. Nếu một trang đã chuyển, hãy tìm theo đúng tiêu đề.*

### ⭐ Bắt đầu từ đây

- **"Real-time Personalization using Embeddings for Search Ranking at Airbnb"** — Grbovic & Cheng, KDD 2018 · https://dblp.org/rec/conf/kdd/GrbovicC18.html
- Bài giải thích bằng ngôn ngữ dễ hiểu, phần 1 và 2 — https://medium.com/data-science-collective/how-airbnb-learned-to-understand-listings-via-embeddings-part-1-2d4bddcf4031 · https://joseparreogarcia.substack.com/p/airbnb-listing-embeddings-part-2
- **"150 Successful Machine Learning Models: 6 Lessons Learned at Booking.com"** — KDD 2019. Liều thuốc giải ngắn gọn tốt nhất cho bệnh over-engineering.

### Nguồn dữ liệu

- Amadeus Self-Service APIs — https://developers.amadeus.com/self-service — gói test miễn phí, SDK Java, khách sạn + chuyến bay + hoạt động
- Amadeus hotel tutorial — https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/resources/hotels/
- Bộ dữ liệu trivago RecSys Challenge 2019 — https://recsys2019data.trivago.com

### Vector và embeddings

- Sentence-Transformers — https://sbert.net
- MTEB leaderboard — https://huggingface.co/spaces/mteb/leaderboard — tab multilingual
- Stanford CS224N Lecture 1: Word Vectors — tìm tiêu đề này trên YouTube

### Vector search

- HNSW paper — https://arxiv.org/abs/1603.09320 — chỉ phần 1–3
- pgvector — https://github.com/pgvector/pgvector — đọc kỹ phần indexing

### Triển khai Java

- Spring AI — ONNX Embeddings — https://docs.spring.io/spring-ai/reference/api/embeddings/onnx.html — liên kết quan trọng nhất của dự án này
- Spring AI — API overview — https://docs.spring.io/spring-ai/reference/api
- Spring AI — PGVector — https://docs.spring.io/spring-ai/reference/api/vectordbs/pgvector.html
- "Bringing Sentence Transformers to Java: Run all-MiniLM-L6-v2 with ONNX Runtime" — https://medium.com/@nil.joshi860/bringing-sentence-transformers-to-java-run-all-minilm-l6-v2-with-onnx-runtime-73938447342b
- Tham chiếu chạy được: Spring Boot + PGVector + local ONNX — https://github.com/loiane/angular-spring-rag
- Spring Security JWT — https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html

### Hệ gợi ý

- Google — Recommendation Systems crash course — https://developers.google.com/machine-learning/recommendation — bắt đầu từ đây ở Tuần 1
- "Two-Tower Models for Recommendation Systems: A Deep Dive" — https://www.shaped.ai/blog/the-two-tower-model-for-recommendation-systems-a-deep-dive
- "Deep Neural Networks for YouTube Recommendations" — Covington et al., RecSys 2016

### Đánh giá

- RecBole — https://github.com/RUCAIBox/RecBole
- Microsoft Recommenders — https://github.com/recommenders-team/recommenders

### Theo tuần

| Tuần | Được giao |
| --- | --- |
| 1 | Google RecSys course 1–2 · CS224N Lecture 1 · Sentence-Transformers intro |
| 2 | HNSW 1–3 · MTEB multilingual · Spring AI ONNX docs |
| 3 | ⭐ Airbnb KDD 2018 · two-tower deep dive |
| 4 | Spring AI chat docs · hướng dẫn prompting của LLM |
| 5 | pgvector indexing · Booking.com 150 models |
| 6 | — (viết, không đọc) |

---

## 15. Bảng thuật ngữ

| Thuật ngữ | Ý nghĩa |
| --- | --- |
| **Embedding** | Một dãy số biểu diễn văn bản, được sắp xếp sao cho ý nghĩa tương tự cho ra dãy số tương tự |
| **Vector** | Chính dãy số đó |
| **Dimension** | Có bao nhiêu số trong đó — 384 hoặc 768 với các ứng viên của chúng ta |
| **Cosine similarity** | Phép tính cho "hai vector này giống nhau đến mức nào", từ -1 đến 1 |
| **Normalise** | Co giãn một vector về độ dài 1, để phép so sánh đo hướng chứ không đo độ lớn |
| **ANN** | Approximate nearest neighbour — tìm các vector gần nhất một cách gần đúng, nhanh hơn nhiều |
| **HNSW / IVF** | Các thuật toán ANN cụ thể. pgvector hỗ trợ cả hai. |
| **Top-K** | K kết quả tốt nhất |
| **Cold start** | Gợi ý cho người mà bạn không biết gì về họ |
| **Baseline** | Cách làm đơn giản mà bạn phải vượt qua để biện minh cho cách làm phức tạp |
| **Recall@20** | Câu trả lời đúng có nằm đâu đó trong top 20 của chúng ta không? |
| **NDCG** | Giống recall, nhưng thưởng cho việc đặt câu trả lời đúng ở vị trí cao hơn |
| **Ablation** | Tắt một tính năng để đo xem nó đã đóng góp gì |
| **p95 latency** | 95% số request nhanh hơn mức này |
| **Pooling** | Gộp nhiều vector thành một |
| **Grounding** | Buộc LLM chỉ trả lời từ dữ liệu thật bạn đưa cho nó, thay vì bịa ra |
| **JWT** | Một token đã ký chứng minh người gọi là ai |

---

## 16. Bố cục repository

```
vota-recsys/
├── docker-compose.yml
├── insider-clone/              # Tuần 1 — nền tảng giả lập, quy tắc kiểm tra thật
├── data-collection/            # Workstream Data, Tuần 1
│   ├── collectors/             # mỗi nguồn một collector
│   ├── normalise.py
│   ├── seed_histories.py       # lịch sử khách hàng được sinh ra
│   └── README.md               # từng trường dữ liệu đến từ đâu
├── backend/
│   └── src/main/java/.../
│       ├── cdp/
│       │   ├── CdpClient       # ⭐ interface — sau này thay bằng bản production
│       │   └── LocalCdpClient
│       ├── catalog/            # ItemTextBuilder
│       ├── index/              # EmbeddingService, VectorIndexer
│       ├── profile/            # UserProfileBuilder ⭐ phần cốt lõi
│       ├── chat/               # trích xuất ý định, soạn kế hoạch
│       ├── auth/               # JWT, users
│       ├── booking/            # giỏ hàng, checkout, ghi event ngược lại
│       └── api/                # controllers
├── frontend/                   # Workstream Web
├── eval/                       # Evaluation (Python — chỉ chạy offline)
│   ├── splits.py
│   ├── metrics.py
│   └── report.md               # tạo lại hằng tuần
└── docs/
    ├── decisions/
    ├── demo-script.md          # viết ở Tuần 6, tổng duyệt thứ Năm
    └── runbook.md
```

---

## 17. Những câu hỏi mở cho Tuần 1

Hãy nêu những câu này vào thứ Hai để chúng được trả lời thay vì bị mặc định ngầm:

1. **Nhà cung cấp LLM, API key và giới hạn chi tiêu** cho trợ lý lịch trình. Cần tới Tuần 4, nhưng việc mở tài khoản mất thời gian — hãy hỏi ngay Tuần 1.
2. **Framework frontend** — React hay server-rendered? Chọn dựa trên thứ đội đã biết sẵn.
3. **Có ai am hiểu CDP rà soát schema trong Tuần 1 được không?** Sai tên trường bây giờ thì sửa rẻ, về sau thì đắt.
4. **Hệ thống này sẽ được deploy ở đâu** cho buổi demo staging Tuần 5?
5. **Ai là khán giả của buổi demo Tuần 6, và họ muốn thấy gì nhất?** Câu trả lời đó nên định hình những gì được đánh bóng trong Tuần 5.
