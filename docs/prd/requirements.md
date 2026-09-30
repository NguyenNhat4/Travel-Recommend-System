# Requirements & Specifications — V-OTA Platform

Tài liệu này đặc tả chi tiết toàn bộ các yêu cầu chức năng (Functional Requirements), yêu cầu phi chức năng (Non-Functional Requirements) và tiêu chí nghiệm thu (Acceptance Criteria) cho nền tảng V-OTA.

---

## 1. Yêu Cầu Chức Năng (Functional Requirements)

### 1.1. Phân Hệ Danh Mục Sản Phẩm (Catalog Management)
- **FR-CAT-01 (Mô hình hóa đa dạng sản phẩm):** Hệ thống phải hỗ trợ các loại hình du lịch cốt lõi: Khách sạn / Resort (`hotel_property`, `hotel_room`), Chuyến bay (`flight_route`, `flight_instance`; gồm một chiều và khứ hồi có hai chặng, ngày cố định và giá tổng), Hoạt động / Vé tham quan (`experience`), và Gói dịch vụ (`combo`).
- **FR-CAT-02 (Cấu trúc phân cấp và đơn vị đặt chỗ):**
  - Chỉ các đơn vị cụ thể (`hotel_room`, `flight_instance`, `experience`, `combo`) mới có trạng thái đặt chỗ được (`is_bookable = true`).
  - Điểm lưu trú tổng quan (`hotel_property`) chỉ mang tính hiển thị thông tin và là đơn vị tìm kiếm (`is_search_unit = true`), không đặt chỗ trực tiếp trên property mà đặt qua phòng con.
- **FR-CAT-03 (Lịch khả dụng & Định giá):**
  - Quản lý cửa sổ mở bán (`available_from`, `available_to`) và trạng thái phòng/vé trống theo từng ngày (`attributes.availability`).
  - Hỗ trợ cơ sở định giá đa dạng (`per_night`, `per_person`, `per_package`).
  - Vé khứ hồi là `flight_instance` (`level: flight`, `tripType: roundTrip`), ngày sử dụng là ngày đi, ngày về nằm trong sản phẩm. Hạng vé có bằng chứng (`cabinClass`, gồm phổ thông/thương gia) tạo biến thể đặt được riêng theo hành trình và ngày; không đổi ID vé cũ, không suy hạng hoặc tự tạo giá. Giá là tổng hành trình cho một người lớn.
- **FR-CAT-04 (Gói kết hợp - Combo Handling):** Hỗ trợ tách bóc và truy xuất chi tiết các thành phần trong combo (phòng ở, vé máy bay, vé vui chơi) với tỷ lệ tin cậy và căn cứ trích xuất rõ ràng.

### 1.2. Phân Hệ Tìm Kiếm Ngữ Nghĩa (Semantic Search Engine)
- **FR-SRC-01 (Tìm kiếm đa phương thức):** Hỗ trợ cả tìm kiếm từ khóa truyền thống và tìm kiếm ngữ nghĩa (Semantic Search) bằng ngôn ngữ tự nhiên tiếng Việt.
- **FR-SRC-02 (Vector Embedding):** Hệ thống phải tự động vector hóa mô tả sản phẩm, tiện ích, đặc điểm nổi bật bằng Cohere `embed-multilingual-v3.0` (1024 chiều) và lưu trong collection `Product` của Weaviate. Chỉ vector hóa sản phẩm có `is_search_unit = true`; truy vấn phải dùng `input_type=search_query`, nạp dùng `input_type=search_document`.
- **FR-SRC-03 (Bộ lọc đa chiều - Faceted Filtering):** Cho phép kết hợp tìm kiếm ngữ nghĩa với các bộ lọc có cấu trúc:
  - Địa điểm (Điểm đến, thành phố, khu vực).
  - Khoảng ngân sách (Giá tối thiểu, giá tối đa).
  - Đánh giá sao, phân loại dịch vụ.
  - Ngày khởi hành / Thời gian nhận phòng.
- **FR-SRC-04 (Xử lý không có kết quả):** Khi truy vấn không có kết quả khớp chính xác, hệ thống phải đề xuất các sản phẩm có độ tương đồng ngữ nghĩa gần nhất hoặc gợi ý điều chỉnh từ khóa tìm kiếm.

### 1.3. Phân Hệ Gợi Ý Cá Nhân Hóa (Recommendation Engine)
- **FR-REC-01 (Sinh danh mục theo ngữ cảnh - Candidate Generation):**
  - Người dùng ẩn danh / Chưa đăng nhập: Gợi ý các sản phẩm thịnh hành (`trending`), phổ biến theo điểm đến hoặc ưu đãi mùa lễ hội.
  - Người dùng có hồ sơ: Gợi ý dựa trên vector lịch sử tương tác, phân khúc hành vi và mức chi tiêu trung bình.
- **FR-REC-02 (Khép kín vòng lặp sau mua - Trip-based Next Best Action):**
  - Khi người dùng vừa đặt phòng khách sạn tại điểm đến X, hệ thống phải ưu tiên gợi ý vé máy bay đến X và các hoạt động trải nghiệm tại X.
- **FR-REC-03 (Khả năng giải thích minh bạch - Explainable Recs):** Mọi đề xuất cá nhân hóa trên giao diện phải đi kèm lý do rõ ràng trong trường `because` (Ví dụ: *"Dành cho bạn vì bạn vừa xem các resort tại Phú Quốc"*, *"Phù hợp với chuyến du lịch gia đình"*).
- **FR-REC-04 (Tái sắp xếp - Reranking):** Sắp xếp thứ tự danh sách sản phẩm dựa trên trọng số kết hợp giữa độ liên quan ngữ nghĩa, mức độ ưa chuộng của cộng đồng và tính khả dụng của sản phẩm.

### 1.4. Phân Hệ Trợ Lý AI Lập Lịch Trình (Itinerary AI Assistant)
- **FR-AGT-01 (Hội thoại đa lượt):** Trợ lý có khả năng duy trì ngữ cảnh trò chuyện, làm rõ nhu cầu du lịch (thời gian, địa điểm, số người, ngân sách, phong cách du lịch). Người dùng đã đăng nhập có thể xem danh sách, mở lại và tiếp tục các hội thoại của chính mình; khách chưa đăng nhập chỉ có ngữ cảnh tạm thời 24 giờ và không có lịch sử lâu dài.
- **FR-AGT-02 (Gọi công cụ nghiệp vụ - Tool Calling):** Trợ lý tương tác trực tiếp với API hệ thống thông qua các công cụ: tìm kiếm sản phẩm, kiểm tra lịch trống, tính toán chi phí dự kiến.
- **FR-AGT-03 (Lập lịch trình cấu trúc - Structured Itinerary):** Kết quả phản hồi phải trả về lịch trình theo từng ngày (Day-by-Day), phân chia các buổi sáng - trưa - chiều - tối, bao gồm địa điểm, thời gian di chuyển ước tính và danh sách sản phẩm đề xuất.
- **FR-AGT-04 (Nguyên tắc Grounding 100%):** Mọi mục sản phẩm trong lịch trình có thể đặt được phải tương ứng với một `productId` thật tồn tại trong catalog, có giá cụ thể và đường dẫn chuyển tiếp vào trang chi tiết hoặc giỏ hàng.
- **FR-AGT-05 (Điều chỉnh linh hoạt):** Người dùng có thể yêu cầu đổi phòng, đổi điểm tham quan hoặc rút ngắn/kéo dài số ngày trong lịch trình qua hội thoại tiếp theo. Khi người dùng muốn đổi một sản phẩm đã hiển thị mà không nêu tên thay thế, trợ lý có thể tìm sản phẩm tương tự sản phẩm đó: sản phẩm gốc chỉ lấy từ lịch trình lượt trước, kết quả cùng loại (taxonomy).

### 1.5. Phân Hệ Đặt Hàng & Thanh Toán (Booking & Checkout)
- **FR-BKG-01 (Quản lý giỏ hàng & Đơn hàng tạm thời):** Cho phép người dùng lưu trữ nhiều dịch vụ (khách sạn, vé máy bay, trải nghiệm) trong cùng một lịch trình.
- **FR-BKG-02 (Quy trình xác nhận đơn hàng):**
  - Kiểm tra trạng thái khả dụng của từng sản phẩm trong khoảng thời gian sử dụng trước khi tạo đơn.
  - Tính tổng giá trị đơn hàng, hiển thị chi tiết phụ phí và thuế (nếu có).
  - Kiểm tra đạt thì tạo đơn ở trạng thái giữ chỗ `PENDING_PAYMENT`. Số tiền tính từ catalog tại thời điểm tạo đơn, không nhận từ client.
- **FR-BKG-03 (Xử lý giao dịch & Bù trừ):**
  - Thu tiền qua Stripe Checkout (VND, thẻ) theo FR-BKG-06.
  - Chỉ chuyển đơn sang `CONFIRMED` khi Stripe xác nhận đã thu tiền: qua webhook có chữ ký hợp lệ, hoặc do Backend tự hỏi lại Stripe. Việc trình duyệt quay về từ trang Stripe không phải bằng chứng thanh toán.
  - Ghi sự kiện `purchase` sang CDP ngay trước khi lưu `CONFIRMED` vào `app.bookings`. Khi tiền đã thu mà lưu đơn lỗi thì **không huỷ** sự kiện, mà thử lại cho tới khi đơn được xác nhận (Stripe gửi lại webhook, job đối soát chạy lại).
  - Huỷ sự kiện `purchase` (`cancel_purchase`) khi khách huỷ đơn đã xác nhận (FR-BKG-07), để gợi ý không dùng chuyến đã huỷ.
- **FR-BKG-04 (Trang xác nhận & Kích hoạt gợi ý tiếp nối):** Sau khi đơn chuyển `CONFIRMED`, hiển thị mã đặt chỗ, tóm tắt chuyến đi và lập tức hiển thị các sản phẩm gợi ý bổ trợ cho chặng tiếp theo.
- **FR-BKG-05 (Giữ chỗ):** Đơn `PENDING_PAYMENT` giữ giá và thành phần trong 30 phút. Mỗi người dùng có tối đa một đơn đang giữ chỗ; tạo đơn mới khi còn đơn giữ chỗ thì bị từ chối kèm mã đơn cũ để tiếp tục hoặc huỷ. Hết hạn mà chưa trả tiền thì đơn chuyển `EXPIRED`. Giữ chỗ không trừ tồn kho. Giỏ hàng giữ nguyên cho tới khi đơn `CONFIRMED`.
- **FR-BKG-06 (Thanh toán Stripe theo mô hình MoR và xử lý thất bại):** V-OTA là Merchant of Record, thu toàn bộ tiền đơn bằng một tài khoản Stripe ở test mode. Trang thanh toán cho khách chọn phương thức; hiện chỉ hỗ trợ Stripe. Chỉ khi khách điền đủ thông tin, chọn phương thức và bấm Thanh toán thì hệ thống mới tạo đơn giữ chỗ và chuyển sang trang Stripe. Thẻ bị từ chối thì khách thử lại trong cùng phiên, tối đa 3 lần; lần thứ 3 thì đơn chuyển `PAYMENT_FAILED`. Stripe không phản hồi khi tạo phiên thì không tạo đơn và trả lỗi cho phép thử lại. Phân biệt thông báo cho lỗi nghiệp vụ (thẻ bị từ chối, không đủ số dư, xác thực 3DS thất bại) và lỗi kỹ thuật (cổng thanh toán không phản hồi, lỗi hệ thống).
- **FR-BKG-07 (Khách huỷ và hoàn tiền):** Khách huỷ cả đơn. Đơn chưa trả tiền: huỷ ngay, đóng phiên thanh toán. Đơn đã trả tiền: hoàn 100% qua Stripe nếu huỷ trước 00:00 (giờ Việt Nam) của ngày liền trước ngày sử dụng sớm nhất; quá hạn thì không huỷ trực tuyến. Huỷ lặp lại trả về kết quả cũ, không hoàn tiền hai lần.

### 1.6. Phân Hệ Người Dùng & Xác Thực (User & Authentication)
- **FR-USR-01 (Quản lý danh tính):** Hỗ trợ đăng ký, đăng nhập an toàn qua email/mật khẩu.
- **FR-USR-02 (Hồ sơ & Sở thích):** Lưu trữ thông tin cá nhân, danh sách yêu thích, lịch sử đơn hàng và các tiêu chí ưu tiên du lịch (phong cách, ngân sách, thành viên đi cùng).
- **FR-USR-03 (Quản lý phiên):** Bảo vệ các endpoint nhạy cảm bằng phiên đăng nhập (Session token / Cookie / JWT), đảm bảo phân tách quyền riêng tư giữa các tài khoản.

### 1.7. Phân Hệ Dữ Liệu Khách Hàng (Customer Data Platform - CDP)
- **FR-CDP-01 (Theo dõi sự kiện hành vi - Event Ingestion):** Ghi nhận đầy đủ vòng đời tương tác của người dùng:
  - `page_view`: Người dùng truy cập các trang nội dung.
  - `product_view`: Xem chi tiết sản phẩm cụ thể.
  - `search`: Thực hiện tìm kiếm với từ khóa và bộ lọc.
  - `add_to_cart`: Thêm sản phẩm vào giỏ/lịch trình.
  - `purchase`: Hoàn tất thanh toán đơn hàng.
- **FR-CDP-02 (Hợp nhất danh tính - Identity Stitching) — hoãn, ngoài phạm vi MVP:** Liên kết dữ liệu hành vi từ giai đoạn ẩn danh (`anonymous_id`) sang hồ sơ chính thức (`profile_id`) khi người dùng đăng nhập. Trong MVP, sự kiện hành vi **chỉ được ghi khi người dùng đã đăng nhập** (`cdp.events.cdp_user_id` bắt buộc); khách vãng lai không sinh sự kiện CDP và không có bước gộp lịch sử.
- **FR-CDP-03 (Hồ sơ khách hàng 360):** Tự động tính toán các thuộc tính tổng hợp: tổng chi tiêu, danh mục quan tâm nhiều nhất, điểm đến gần nhất, tần suất tương tác.

### 1.8. Phân Hệ Tương Tác Cá Nhân Hóa Đa Kênh (Multi-channel Engagement)
- **FR-ENG-01 (Đồng bộ phân khúc):** Phân loại người dùng vào các nhóm hành vi (Gia đình, Công tác, Thích trải nghiệm, Săn ưu đãi).
- **FR-ENG-02 (Kích hoạt thông điệp theo ngữ cảnh):** Hiển thị banner chương trình khuyến mãi và gợi ý phù hợp trên giao diện dựa trên phân khúc người dùng được định danh.

---

## 2. Yêu Cầu Phi Chức Năng (Non-Functional Requirements)

### 2.1. Hiệu Năng & Độ Trễ (Performance & Latency)
- **NFR-PERF-01 (API Response Time):**
  - Các API tìm kiếm sản phẩm và gợi ý cá nhân hóa phải phản hồi trong thời gian $\le 250\text{ ms}$ ở phân vị p95.
  - Các API truy xuất chi tiết sản phẩm và danh mục phải phản hồi trong thời gian $\le 100\text{ ms}$.
- **NFR-PERF-02 (AI Assistant Response Time):**
  - Thời gian bắt đầu xuất luồng văn bản (First token latency) của Trợ lý AI phải $\le 1.0\text{ s}$.
  - Tổng thời gian hoàn tất một phản hồi lịch trình phức tạp phải $\le 4.0\text{ s}$.
- **NFR-PERF-03 (Vector Indexing):** Truy vấn tương đồng phải đi qua chỉ mục ANN của Weaviate, cosine: HNSW khi chạy local/self-host, `hfresh` khi gói Weaviate Cloud chỉ cho phép loại này, không quét tuần tự. Ngân sách thời gian của Cohere Embed API cho một truy vấn phải nằm trong giới hạn p95 250 ms ở NFR-PERF-01 — nếu vượt thì phải cache vector của truy vấn lặp lại.

### 2.2. Độ Tin Cậy & Tính Xác Thực (Reliability & Grounding)
- **NFR-REL-01 (Zero Hallucination trên dữ liệu sản phẩm):** 100% các thực thể sản phẩm hiển thị trong lịch trình của AI Assistant phải là sản phẩm có thật, đang hoạt động trong hệ thống.
- **NFR-REL-02 (Tính toàn vẹn dữ liệu giao dịch):** Quy trình tạo đơn và đồng bộ dữ liệu sự kiện phải tuân thủ tính nhất quán cuối cùng (Eventual Consistency), có cơ chế bù trừ khi phát sinh lỗi hệ thống.

### 2.3. Bảo Mật & Ranh Giới Dữ Liệu (Security & Data Isolation)
- **NFR-SEC-01 (Không để lộ thông tin nhạy cảm):** Tuyệt đối không lưu trữ hoặc phản hồi qua API các thông tin bí mật (mật khẩu dạng rõ, API key, token nội bộ).
- **NFR-SEC-02 (Cô lập ranh giới cơ sở dữ liệu):**
  - Các phân hệ nghiệp vụ không được phép cấp quyền truy cập trực tiếp vào vùng dữ liệu nhạy cảm của CDP qua SQL. Mọi thao tác bắt buộc qua cổng dịch vụ (Port/Adapter pattern).
  - Sử dụng cơ chế Role-Based Access Control (RBAC) nghiêm ngặt trong PostgreSQL cho từng role kết nối (`vota_app`, `cdp_writer`, `cdp_reader`).
- **NFR-SEC-03 (Dữ liệu thanh toán):** V-OTA không nhận, lưu hay ghi log dữ liệu thẻ; trang nhập thẻ do Stripe host. Khoá Stripe chỉ nằm ở Backend. Webhook phải được kiểm chữ ký `Stripe-Signature` trước khi xử lý, và xử lý phải idempotent vì Stripe có thể gửi trùng hoặc sai thứ tự.

### 2.4. Khả Năng Mở Rộng & Bảo Trì (Scalability & Maintainability)
- **NFR-MAINT-01 (Clean Architecture):** Mã nguồn Backend phải tuân thủ kiến trúc phân lớp sạch, tách biệt hoàn toàn giữa lớp nghiệp vụ (Domain/Application) và lớp giao tiếp bên ngoài (Infrastructure/Framework).
- **NFR-MAINT-02 (API Contract-First):** Hợp đồng OpenAPI là tiêu chuẩn độc lập, mọi thay đổi giao diện dữ liệu phải được xác thực bằng công cụ tự động trước khi triển khai.

---

## 3. Tiêu Chí Nghiệm Thu Hệ Thống (System Acceptance Criteria)

| Mã tiêu chí | Kịch bản / Điều kiện kích hoạt | Hành vi kỳ vọng của hệ thống |
|---|---|---|
| **AC-SRC-01** | Người dùng tìm kiếm: *"resort yên tĩnh có hồ bơi riêng"* | Trả về danh sách các resort/khách sạn có mô tả hoặc tiện ích phù hợp về sự yên tĩnh và hồ bơi, sắp xếp theo độ tương đồng ngữ nghĩa. |
| **AC-REC-01** | Người dùng P1 (Gia đình) đăng nhập vào hệ thống | Trang chủ hiển thị khu vực gợi ý với tiêu đề và nội dung phù hợp cho gia đình, mỗi thẻ sản phẩm hiển thị lý do `because` tương ứng. |
| **AC-REC-02** | Người dùng hoàn tất đặt phòng tại Đà Nẵng | Tại trang xác nhận và khi quay lại trang chủ, khối gợi ý ưu tiên hiển thị vé máy bay đến Đà Nẵng và tour tham quan tại Bà Nà / Hội An. |
| **AC-AGT-01** | Người dùng yêu cầu: *"Lập lịch trình 3 ngày 2 đêm tại Nha Trang ngân sách 5 triệu"* | Trợ lý hỏi gộp một câu, một lần, những gì còn thiếu trong ngày đi, số người và ngân sách (không tự đoán ngày). Người dùng trả lời đủ, trả lời một phần hoặc nói chưa chốt; khi đó trợ lý xuất ra lịch trình 3 ngày có cấu trúc; các địa điểm nghỉ ngơi và hoạt động đều là thẻ sản phẩm thật kèm giá rõ ràng và nút bấm xem chi tiết. Câu đầu đã đủ ngày đi, số người và ngân sách thì xuất lịch ngay. Người dùng đã được hỏi một lượt mà câu trả lời vẫn không cho biết điểm đến hoặc số ngày thì trợ lý không hỏi lại bằng câu chữ nữa: nó hiển thị ngay trong khung chat một form thông tin chuyến đi đã điền sẵn giá trị gợi ý (điểm đến, số ngày, ngày khởi hành, số người, ngân sách) kèm một câu mời tinh chỉnh; ô điểm đến chỉ liệt kê vài điểm đến tiêu biểu của catalog. Form chặn giá trị không hợp lệ: số ngày trong khoảng 1–7, ngày khởi hành không trước ngày hôm nay. Người dùng bấm xác nhận thì câu yêu cầu hoàn chỉnh được đặt sẵn vào ô nhập tin nhắn để họ sửa hoặc gửi ngay; gửi đi thì trợ lý coi đó là một yêu cầu đầy đủ và lập lịch, không hỏi thêm. |
| **AC-BKG-01** | Người dùng điền thông tin, chọn Stripe, bấm thanh toán giỏ hàng và trả bằng thẻ test hợp lệ | Chỉ sau khi bấm thanh toán hệ thống mới kiểm tra lịch trống, tạo đơn giữ chỗ và chuyển sang trang Stripe. Sau khi Stripe xác nhận thu tiền: ghi event `purchase` vào CDP, chuyển đơn `CONFIRMED`, hiển thị trang thành công với mã đơn hợp lệ. |
| **AC-BKG-02** | Thẻ bị từ chối 3 lần liên tiếp | Mỗi lần trang Stripe báo lỗi và cho thử lại. Lần thứ 3 đơn chuyển `PAYMENT_FAILED`, không có event `purchase`, giỏ hàng còn nguyên. |
| **AC-BKG-03** | Người dùng không trả tiền trong 30 phút; hoặc bấm thanh toán lần nữa khi đang có đơn giữ chỗ | Đơn chuyển `EXPIRED`, trang thanh toán Stripe không còn dùng được. Trường hợp thứ hai trả `409 BOOKING_PENDING_PAYMENT` kèm mã đơn đang giữ. |
| **AC-BKG-04** | Người dùng huỷ đơn đã thanh toán, còn trong hạn huỷ | Đơn `CANCELLED`, Stripe có một lệnh hoàn toàn bộ tiền, event `purchase` bị huỷ và không còn được dùng cho gợi ý. Huỷ khi quá hạn trả `409 BOOKING_NOT_CANCELLABLE`. |
| **AC-SEC-01** | Mã nguồn hoặc ứng dụng kết nối DB bằng role `vota_app` cố ý truy vấn bảng `cdp.events` | PostgreSQL từ chối quyền truy cập (Permission Denied), ngăn chặn việc rò rỉ hoặc can thiệp dữ liệu trái phép. |
