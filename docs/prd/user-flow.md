# User Flow & Experience Design — V-OTA Platform

Tài liệu này đặc tả toàn bộ hành trình trải nghiệm người dùng (User Journey), các sơ đồ luồng thao tác (User Flows), kiến trúc điều hướng (Site Architecture & Route Map) và thiết kế wireframe cho các màn hình chính của nền tảng V-OTA.

---

## 1. Hành Trình Người Dùng Theo Persona (User Journeys)

Hệ thống được tối ưu hóa cho 4 luồng trải nghiệm chính tương ứng với các nhóm người dùng:

```
[Khách truy cập] ──> [Định danh / Đăng nhập] ──> [Khám phá / Tìm kiếm] ──> [Lập lịch trình AI] ──> [Đặt dịch vụ] ──> [Nhận gợi ý chặng kế tiếp]
```

### 1.1. Hành trình Khách nghỉ dưỡng gia đình (Persona P1)
1. **Khám phá:** Truy cập trang chủ, nhìn thấy các resort ven biển có hồ bơi trẻ em và không gian xanh kèm lý do gợi ý *"Phù hợp cho chuyến đi gia đình"*.
2. **Tìm kiếm:** Gõ *"resort yên tĩnh gần biển có buffet sáng"*, nhận kết quả các khu nghỉ dưỡng đã được lọc sẵn tiện ích gia đình.
3. **Đặt phòng:** Chọn phòng Family Suite, tiến hành xác nhận đặt phòng.
4. **Hậu mãi tức thì:** Màn hình xác nhận ngay lập tức hiển thị gợi ý vé máy bay khứ hồi và vé tham quan công viên giải trí tại điểm đến vừa đặt.

### 1.2. Hành trình Khách du lịch tự túc / Trải nghiệm (Persona P3)
1. **Tiếp cận:** Vào mục Trợ lý Lịch trình (AI Assistant), yêu cầu *"Lập lịch trình 3 ngày khám phá ẩm thực và văn hóa Hội An - Đà Nẵng ngân sách tiết kiệm"*.
2. **Tương tác AI:** Trợ lý AI phân tích ý định, gửi lại lịch trình chia theo buổi với các địa điểm nổi tiếng kèm thẻ sản phẩm homestay và tour trải nghiệm thực tế.
3. **Điều chỉnh:** Bấm vào thẻ sản phẩm để xem chi tiết đánh giá và ảnh, yêu cầu AI đổi một điểm tham quan buổi chiều.
4. **Thêm vào giỏ & Đặt:** Lưu toàn bộ các sản phẩm đã chọn trong lịch trình vào giỏ hàng và tiến hành thanh toán một lần.

---

## 2. Bản Đồ Điều Hướng & Danh Mục Màn Hình (Route Table)

| Tuyến đường (Route) | Tên màn hình | Mục đích chính | Thành phần cốt lõi |
|---|---|---|---|
| `/` | **Trang chủ (Home)** | Khám phá ban đầu, tìm kiếm nhanh, khối gợi ý cá nhân hóa | Hero Search Bar, Category Nav, Personalized Carousels, Trending Destinations |
| `/search` | **Kết quả tìm kiếm** | Hiển thị kết quả tìm kiếm ngữ nghĩa và bộ lọc đa chiều | Query Header, Filter Sidebar, Sort Controls, Product Grid Cards, Pagination |
| `/products/:id` | **Chi tiết sản phẩm** | Thông tin đầy đủ về phòng, vé, tour; trạng thái khả dụng | Image Gallery, Attribute Badges, Availability Calendar, Pricing, Add-to-Cart CTA |
| `/assistant` | **Trợ lý Lịch trình** | Tương tác trò chuyện với AI Agent để tạo và tùy chỉnh kế hoạch | Chat Stream, Intent Chips, Day-by-Day Timeline, Grounded Product Cards |
| `/checkout` | **Thanh toán / Đặt chỗ** | Xem lại đơn, nhập thông tin liên lạc, chọn phương thức thanh toán, bấm Thanh toán để chuyển sang trang Stripe | Cart Items Summary, Guest Info Form, Price Breakdown, Payment Method Selector, Pay CTA |
| `/booking/:referenceCode` | **Xác nhận đơn hàng** | Hiển thị đơn theo trạng thái: đang giữ chỗ (đồng hồ đếm ngược, tiếp tục thanh toán), đã xác nhận (mã đặt chỗ, gợi ý chặng tiếp), thanh toán thất bại, hết hạn, đã huỷ; huỷ đơn | Booking Status Card, Next Best Action Recommendations (Flight, Tours) |
| `/profile` | **Hồ sơ & Lịch sử** | Quản lý thông tin cá nhân, lịch sử đơn hàng và chuyến đi | User Preferences, Booking History, Saved Items |

---

## 3. Sơ Đồ Luồng Thao Tác Cốt Lõi (Core User Flows)

### 3.1. Luồng Khám Phá & Tìm Kiếm Ngữ Nghĩa (Search Flow)

```mermaid
flowchart TD
    A[Người dùng tại Trang chủ] --> B[Nhập câu truy vấn tự nhiên]
    B --> C{Loại truy vấn?}
    C -->|Từ khóa truyền thống| D[Full-text / Facet Search]
    C -->|Ngữ nghĩa / Mô tả| E[Vector Embedding Search]
    D --> F[Hợp nhất kết quả & Reranking]
    E --> F
    F --> G[Hiển thị trang /search]
    G --> H[Người dùng tinh chỉnh bộ lọc: Giá, Sao, Vị trí]
    H --> I[Cập nhật kết quả tức thì]
    I --> J[Chọn sản phẩm -> Mở /products/:id]
    J --> K[Ghi nhận sự kiện product_view sang CDP]
```

### 3.2. Luồng Trợ Lý AI Lập Lịch Trình (Itinerary Assistant Flow)

```mermaid
flowchart TD
    A[Mở màn hình /assistant] --> H{Đã đăng nhập?}
    H -->|Có| L[Xem danh sách hội thoại của chính mình]
    L --> M[Chọn hội thoại cũ hoặc tạo hội thoại mới]
    H -->|Không| B[Nhập yêu cầu lịch trình hoặc chọn gợi ý]
    M --> B
    B --> C[Backend trích xuất Intent: Điểm đến, Thời gian, Ngân sách]
    C --> D[Gọi Tool Search truy xuất sản phẩm thật từ Catalog]
    D --> E{Có sản phẩm phù hợp?}
    E -->|Có| F[LangGraph cấu trúc lịch trình từng ngày]
    E -->|Thiếu| G[Mở rộng điều kiện tìm kiếm hoặc hỏi thêm người dùng]
    F --> H[Stream phản hồi + Render thẻ sản phẩm Grounded]
    H --> I[Người dùng bấm 'Xem chi tiết' hoặc 'Thêm vào chuyến đi']
    I --> J[Chuyển trực tiếp sang Giỏ hàng / Đặt chỗ]
```

### 3.3. Luồng Đặt Chỗ & Khép Kín Vòng Lặp Cá Nhân Hóa (Booking & Recs Loop)

> Ở `/checkout`, khách làm lần lượt ba việc: (1) điền đủ thông tin liên lạc; (2) chọn phương thức thanh toán; (3) bấm **Thanh toán**.
>
> - **Phương thức thanh toán.** Trang hiển thị danh sách phương thức. Hiện chỉ hỗ trợ **Stripe** (thẻ, test mode); phương thức này được chọn sẵn. Các phương thức khác (ví điện tử, chuyển khoản, cổng ngân hàng nội địa…) nếu có hiển thị thì ở dạng vô hiệu hoá kèm nhãn "Sắp có", không chọn được. Danh sách để mở rộng về sau mà không đổi luồng.
> - **Chưa rời trang khi chưa bấm Thanh toán.** Điền thông tin và chọn phương thức chỉ là thao tác trên `/checkout`, không gọi Stripe và không tạo đơn. Nút **Thanh toán** bị vô hiệu hoá cho tới khi thông tin liên lạc hợp lệ và đã chọn phương thức.
> - **Bấm Thanh toán mới sang Stripe.** Khi bấm, Web gọi Backend; Backend kiểm giỏ, tạo đơn giữ chỗ 30 phút và Stripe Checkout Session, rồi Web chuyển trình duyệt sang trang Stripe để nhập thẻ. Nút hiện trạng thái đang xử lý và chặn bấm lặp. Nếu Backend hoặc Stripe lỗi thì khách ở lại `/checkout` với thông báo lỗi và bấm lại được.
> - **Quay về.** Xong trên Stripe (thành công, thất bại hoặc khách bấm quay lại), trình duyệt về `/booking/:referenceCode`; trạng thái đơn do Backend quyết định, không do việc quay về.

```mermaid
flowchart TD
    A[Khách chọn sản phẩm & nhấn 'Đặt ngay'] --> B[Mở trang /checkout]
    B --> C[Điền thông tin liên lạc]
    C --> M[Chọn phương thức thanh toán: hiện chỉ có Stripe]
    M --> P[Bấm 'Thanh toán']
    P --> D[Backend kiểm giỏ, tạo đơn giữ chỗ 30 phút và phiên Stripe]
    D -->|Lỗi Backend hoặc Stripe| B
    D --> S[Chuyển sang trang Stripe: nhập thẻ]
    S -->|Thẻ bị từ chối, dưới 3 lần| S
    S -->|Từ chối lần 3| X1[Đơn PAYMENT_FAILED, giỏ còn nguyên]
    S -->|Quá 30 phút| X2[Đơn EXPIRED, giỏ còn nguyên]
    S -->|Stripe thu tiền| F[Ghi purchase vào CDP, đơn CONFIRMED]
    F --> G[Trang /booking/:referenceCode]
    G --> H[Gợi ý vé máy bay & vé vui chơi cho chuyến đi]
    G -->|Khách huỷ trong hạn| X3[Đơn CANCELLED, hoàn 100%]
```

---

## 4. Thiết Kế Wireframe Các Màn Hình Chính (ASCII Wireframes)

### 4.1. Màn hình Trang Chủ (`/`)
```
+-------------------------------------------------------------------------------+
| [LOGO] V-OTA       Khách sạn   Vé máy bay   Tour   Trợ lý AI   [Tài khoản v]   |
+-------------------------------------------------------------------------------+
|                                                                               |
|   KHÁM PHÁ KỲ NGHỈ TIẾP THEO BẰNG NGÔN NGỮ CỦA BẠN                           |
|   +---------------------------------------------------------------+ +-------+ |
|   | [icon] Bạn muốn trải nghiệm chuyến đi như thế nào hôm nay?    | | TÌM   | |
|   +---------------------------------------------------------------+ +-------+ |
|   Gợi ý nhanh: [Nghỉ dưỡng gia đình] [Khách sạn trung tâm] [Tour ẩm thực]   |
|                                                                               |
+-------------------------------------------------------------------------------+
| GỢI Ý DÀNH RIÊNG CHO BẠN (Dựa trên sở thích nghỉ dưỡng gia đình)              |
| +-------------------------+ +-------------------------+ +-------------------+ |
| | [Ảnh Resort Nha Trang]  | | [Ảnh Villa Phú Quốc]    | | [Ảnh Hotel Đà Nẵng| |
| | Vinpearl Resort & Spa   | | Premier Village Resort  | | Furama Resort     | |
| | 4.8* (1.2k) - Bãi biển  | | 4.9* (850) - Hồ bơi con | | 4.7* (920)        | |
| | 3.200.000 đ/đêm         | | 4.500.000 đ/đêm         | | 2.800.000 đ/đêm   | |
| | (i) Vì bạn thích resort | | (i) Phù hợp gia đình    | | (i) Khách xem lại | |
| +-------------------------+ +-------------------------+ +-------------------+ |
+-------------------------------------------------------------------------------+
| HOÀN THIỆN CHUYẾN ĐI CỦA BẠN (Tiện ích bổ trợ)                                |
| [ Thẻ vé máy bay khứ hồi ]    [ Thẻ vé công viên giải trí ]                   |
+-------------------------------------------------------------------------------+
```

### 4.2. Màn hình Trợ Lý Lịch Trình AI (`/assistant`)
```
+-------------------------------------------------------------------------------+
| [LOGO] V-OTA  >  Trợ lý Lịch trình Thông minh   [Lịch sử] [Lịch trình mới] |
+-------------------------------------------------------------------------------+
|                                    | BẢN XEM TRƯỚC LỊCH TRÌNH                 |
| [AI]: Chào bạn! Mình có thể giúp gì| Nha Trang 3 Ngày 2 Đêm - Gia đình        |
| cho chuyến đi sắp tới?             | --------------------------------------- |
|                                    | NGÀY 1: Nhận phòng & Tắm biển           |
| [User]: Lên giúp mình lịch trình   | 14:00 - Nhận phòng Vinpearl Resort      |
| Nha Trang 3N2Đ cho 2 người lớn,    | +-------------------------------------+ |
| 1 bé 5 tuổi, ngân sách 10 triệu.   | | [Img] Vinpearl Resort & Spa         | |
|                                    | | Giá: 3.200.000 đ - Deluxe Ocean     | |
| [AI]: Dưới đây là kế hoạch chi tiết| | [Xem phòng] [Thêm vào đơn hàng]     | |
| đã được thiết kế phù hợp với lịch  | +-------------------------------------+ |
| sinh hoạt của bé:                  | 18:00 - Ăn tối hải sản Tháp Bà        |
| - Ngày 1: Nhận phòng & nghỉ ngơi   | --------------------------------------- |
| - Ngày 2: Vui chơi tại VinWonders  | NGÀY 2: Khám phá VinWonders             |
| - Ngày 3: Mua sắm & về TP.HCM      | 08:30 - Vé vui chơi trọn gói            |
|                                    | +-------------------------------------+ |
| Bạn có muốn đổi giờ bay hay khách  | | [Img] Vé VinWonders Nha Trang       | |
| sạn khác không?                    | | Giá: 850.000 đ/người                | |
|                                    | | [Đặt vé ngay]                       | |
| +--------------------------------+ | +-------------------------------------+ |
| | Nhập yêu cầu tùy chỉnh...      | | TỔNG CHI PHÍ TẠM TÍNH: 8.900.000 đ      |
| +--------------------------------+ | [ TIẾN HÀNH ĐẶT TRỌN LỊCH TRÌNH ]       |
+-------------------------------------------------------------------------------+
```

### 4.3. Màn hình Xác Nhận Đơn Hàng & Vòng Lặp Gợi Ý Tiếp Theo (`/booking/:referenceCode`)
```
+-------------------------------------------------------------------------------+
| [LOGO] V-OTA                                                    [Tài khoản v] |
+-------------------------------------------------------------------------------+
|                                                                               |
|   [v] ĐẶT CHỖ THÀNH CÔNG!                                                     |
|   Mã đơn hàng: #VOTA-2026-89412                                               |
|   Đã gửi email xác nhận đến: customer@example.com                             |
|                                                                               |
|   +-----------------------------------------------------------------------+   |
|   | THÔNG TIN CHUYẾN ĐI ĐÃ ĐẶT                                            |   |
|   | Vinpearl Resort & Spa Nha Trang - Phòng Deluxe Hướng Biển             |   |
|   | Nhận phòng: 15/10/2026  -  Trả phòng: 17/10/2026 (2 đêm)             |   |
|   | Tổng thanh toán: 6.400.000 đ                                          |   |
|   +-----------------------------------------------------------------------+   |
|                                                                               |
|   BẠN ĐÃ CÓ VÉ MÁY BAY ĐẾN NHA TRANG CHƯA?                                    |
|   Hệ thống tìm thấy các chuyến bay phù hợp với lịch nhận phòng của bạn:       |
|   +------------------------------------+ +--------------------------------+   |
|   | Vietnam Airlines (SGN -> CXR)      | | Vietjet Air (SGN -> CXR)       |   |
|   | Khởi hành: 08:30 - 15/10/2026      | | Khởi hành: 10:15 - 15/10/2026   |   |
|   | Giá từ: 1.450.000 đ/khách          | | Giá từ: 920.000 đ/khách        |   |
|   | [ Đặt thêm chuyến này ]            | | [ Đặt thêm chuyến này ]        |   |
|   +------------------------------------+ +--------------------------------+   |
|                                                                               |
|   HOẠT ĐỘNG NỔI BẬT GẦN KHÁCH SẠN CỦA BẠN:                                    |
|   [ Thẻ Tour lặn ngắm san hô Hòn Mun ]     [ Thẻ Vé tắm bùn khoáng I-Resort ] |
|                                                                               |
|   [ QUAY VỀ TRANG CHỦ ]                            [ QUẢN LÝ ĐƠN HÀNG NÀY ]   |
+-------------------------------------------------------------------------------+
```

### 4.4. Màn hình Thanh Toán (`/checkout`)
```
+-------------------------------------------------------------------------------+
| [LOGO] V-OTA                                                    [Tài khoản v] |
+-------------------------------------------------------------------------------+
| 1. Thông tin liên lạc                     | Tóm tắt đơn                       |
|   Họ tên      [__________________]        |  Vinpearl Resort - Deluxe (2 đêm) |
|   Email       [__________________]        |  Vé VinWonders x2                 |
|   Số điện thoại [________________]        |  -------------------------------- |
|                                           |  Tổng thanh toán: 6.400.000 đ     |
| 2. Phương thức thanh toán                 |                                   |
|   (o) Stripe - Thẻ thanh toán (test)      |  Giữ chỗ 30 phút sau khi bấm      |
|   ( ) Ví điện tử          [Sắp có]        |  Thanh toán.                      |
|   ( ) Chuyển khoản        [Sắp có]        |                                   |
|                                           |  [        THANH TOÁN        ]     |
|                                           |  Bạn sẽ được chuyển sang Stripe.  |
+-------------------------------------------------------------------------------+
```
