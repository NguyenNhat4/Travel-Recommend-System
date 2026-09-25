# Project Brief — V-OTA Travel Recommendation Platform

Tài liệu này xác định tầm nhìn, vấn đề cốt lõi, mục tiêu sản phẩm, phạm vi hệ thống và các tiêu chuẩn định hướng cho toàn bộ nền tảng V-OTA (Virtual Online Travel Agency).

---

## 1. Bối cảnh & Vấn đề Cần Giải Quyết

### 1.1. Bối cảnh thị trường
Các nền tảng du lịch trực tuyến (OTA) truyền thống vận hành dựa trên cơ chế tìm kiếm từ khóa cứng nhắc và danh mục phân loại tĩnh. Người dùng hiện đại có nhu cầu tìm kiếm phức tạp hơn, mang tính ngữ cảnh (như *"nghỉ dưỡng biển yên tĩnh cho gia đình có trẻ nhỏ"*, *"tour khám phá ẩm thực giá hợp lý"*), nhưng các công cụ truyền thống chỉ trả về kết quả rỗng hoặc không khớp nếu mô tả sản phẩm thiếu từ khóa chính xác.

### 1.2. Các vấn đề cốt lõi
1. **Tìm kiếm từ khóa cứng nhắc (Keyword Mismatch):** Không nắm bắt được ngữ nghĩa và ý định thực sự của người dùng, dẫn đến tỷ lệ thoát trang cao khi truy vấn không khớp chính xác từ ngữ trong cơ sở dữ liệu.
2. **Gợi ý thiếu ngữ cảnh và rời rạc (Cold & Generic Recommendations):** Các danh mục gợi ý trên trang chủ thường mang tính đại trà, thiếu khả năng giải thích lý do gợi ý ("because") dựa trên lịch sử hành vi, bối cảnh thời gian hoặc giai đoạn chuẩn bị chuyến đi của từng khách hàng.
3. **Trải nghiệm lập lịch trình phân mảnh:** Người dùng phải chuyển đổi liên tục giữa nhiều công cụ ghi chú, bản đồ và trang đặt chỗ. Các trợ lý AI thông thường thì hay gặp hiện tượng bịa đặt (hallucination), đề xuất các địa điểm hoặc mức giá không có thật trong kho hàng.
4. **Thiếu khả năng kết nối dữ liệu hành vi thời gian thực:** Dữ liệu hành vi người dùng (xem trang, thêm giỏ, tương tác) không được cập nhật tức thì vào hồ sơ khách hàng để phản hồi ngay trong phiên duyệt web hoặc kích hoạt các kênh tiếp cận phù hợp.

---

## 2. Tầm Nhìn Sản Phẩm & Giải Pháp Đề Xuất

### 2.1. Tầm nhìn
Xây dựng V-OTA thành nền tảng du lịch thông minh thế hệ mới, nơi tìm kiếm ngữ nghĩa, gợi ý cá nhân hóa và trợ lý lập lịch trình thông minh cùng vận hành trên một nền tảng dữ liệu thực duy nhất, mang lại trải nghiệm liền mạch từ lúc nảy sinh ý tưởng đến khi hoàn tất chuyến đi.

### 2.2. Kiến trúc giải pháp: "Một Engine, Ba Khuôn Mặt"
Toàn bộ trải nghiệm khám phá và đề xuất của V-OTA xoay quanh một lõi **Recommendation & Semantic Vector Engine** thống nhất:

```
[ Truy vấn ngôn ngữ tự nhiên ] ──┐
                                  ├──> [ Cohere Embed + Weaviate ] ──────> [ Kết quả tìm kiếm ngữ nghĩa ]
[ Hồ sơ & Hành vi người dùng ]  ──┤
                                  ├──> [ Candidate Generation & Rerank ] ──> [ Gợi ý cá nhân hóa có giải thích ]
[ Hội thoại với Trợ lý AI ]    ──┘
                                  └──> [ Intent Extraction + Tool Calls] ──> [ Lịch trình từ 100% kho hàng thật ]
```

- **Semantic Search (Tìm kiếm ngữ nghĩa):** Chuyển đổi truy vấn tự nhiên thành vector đa chiều, truy xuất sản phẩm tương đồng về mặt ý nghĩa thay vì so khớp chuỗi ký tự đơn thuần.
- **Personalized Recommendation (Gợi ý cá nhân hóa):** Dựa trên vector sở thích người dùng (User Profile Vector) tổng hợp từ lịch sử tương tác, phân loại theo hành trình chuyến đi (Trip-based) và cung cấp lý do gợi ý minh bạch (`because`).
- **Grounded Itinerary Assistant (Trợ lý lập lịch trình có căn cứ):** Mô hình tác tử AI (Agent) thấu hiểu nhu cầu qua hội thoại, lập kế hoạch chi tiết từng ngày và bắt buộc chỉ sử dụng các sản phẩm, phòng nghỉ, chuyến bay thực sự có thể đặt được từ kho dữ liệu (Grounding Rule).

---

## 3. Mục Tiêu Sản Phẩm (Product Objectives & KPIs)

### 3.1. Mục tiêu định tính
- **Trải nghiệm tìm kiếm tự nhiên:** Người dùng tìm được đúng sản phẩm mong muốn bằng bất kỳ cách diễn đạt tự nhiên nào.
- **Cá nhân hóa theo ngữ cảnh:** Mỗi người dùng, tại mỗi thời điểm trong vòng đời chuyến đi (trước, trong, sau đặt chỗ), nhìn thấy trang chủ và các gợi ý phù hợp nhất.
- **Độ tin cậy tuyệt đối:** Trợ lý ảo không bịa đặt sản phẩm, giá tiền hay tình trạng phòng/vé; mọi đề xuất đều dẫn trực tiếp đến giỏ hàng hoặc trang thanh toán.
- **Khép kín vòng lặp phản hồi:** Hành vi mua hoặc quan tâm sản phẩm lập tức cập nhật lại gợi ý cho các chặng tiếp theo (ví dụ: đặt xong khách sạn sẽ tự động gợi ý vé máy bay và hoạt động tại địa phương đó).

### 3.2. Chỉ số thành công cốt lõi (Core Metrics)
1. **Search Relevance (NDCG@10, Recall@K):** Đo lường mức độ phù hợp của kết quả tìm kiếm ngữ nghĩa so với ý định truy vấn.
2. **Recommendation Click-Through Rate (CTR):** Tỷ lệ tương tác vào các khối gợi ý cá nhân hóa trên Trang chủ, Trang chi tiết và Trang xác nhận đơn hàng.
3. **Agent Grounding Rate (100%):** Tỷ lệ các sản phẩm trong lịch trình do AI sinh ra khớp hoàn toàn với cơ sở dữ liệu thật và còn trạng thái sẵn sàng phục vụ.
4. **Cross-Sell Conversion Rate:** Tỷ lệ người dùng tiếp tục đặt thêm dịch vụ (vé máy bay, hoạt động) sau khi đã đặt chỗ ở (khách sạn/resort).
5. **System Latency:** Thời gian phản hồi API tìm kiếm và gợi ý dưới 250ms; thời gian phản hồi tin nhắn trợ lý AI dưới 3s (với streaming phản hồi đầu tiên < 1s).

---

## 4. Phạm Vi Hệ Thống (Scope Boundaries)

### 4.1. Trong phạm vi (In-Scope)
- **Cổng thông tin & Khám phá (Frontend Web App):** Giao diện responsive cho phép tìm kiếm, duyệt danh mục, xem gợi ý theo persona, tương tác chat lập lịch trình và thanh toán qua trang Stripe Checkout ở chế độ test (không có giao dịch tiền thật).
- **Dịch vụ Backend & API:** Quản lý danh mục sản phẩm (Catalog), xử lý tìm kiếm lai (Hybrid / Semantic Search), hệ thống gợi ý (Recommendation Engine), quản lý đơn hàng (Booking/Checkout: giữ chỗ, thanh toán Stripe, huỷ và hoàn tiền), quản lý người dùng & phiên đăng nhập.
- **Trợ lý AI Lập Lịch Trình (Itinerary Assistant):** Điều phối hội thoại đa lượt, trích xuất thực thể, gọi công cụ tìm kiếm và tổng hợp lịch trình có cấu trúc (Structured Output).
- **Hệ thống Dữ liệu Khách hàng (CDP Clone):** Thu thập và lưu trữ toàn diện sự kiện hành vi (`page_view`, `product_view`, `search`, `add_to_cart`, `purchase`), duy trì hồ sơ hợp nhất (Unified Profile).
- **Hệ thống Tương tác Cá nhân hóa (Insider Clone):** Đồng bộ thuộc tính và phân khúc người dùng, hỗ trợ kích hoạt thông điệp đa kênh (On-site banner, Notification trigger).
- **Quy chuẩn Kiểm thử & Đánh giá:** Bộ khung kiểm thử hợp đồng (OpenAPI), kiểm thử tích hợp cơ sở dữ liệu, và công cụ đánh giá thuật toán RecSys/Agent độc lập.

### 4.2. Ngoài phạm vi (Out-of-Scope)
- Nhận tiền thật: Stripe live mode, cổng thanh toán ngân hàng hoặc ví nội địa. Dự án chỉ dùng Stripe test mode, V-OTA đóng vai Merchant of Record. Cũng ngoài phạm vi: trả tiền cho nhà cung cấp, tự động xử lý tranh chấp (chargeback), hoá đơn VAT.
- Hệ thống quản lý tồn kho thời gian thực liên kết trực tiếp với hãng hàng không / chuỗi khách sạn ngoài (dữ liệu được nạp qua snapshot và cấu hình khả dụng định kỳ).
- Ứng dụng di động native (iOS / Android) — giai đoạn này tập trung vào Web Application chuẩn hóa giao diện di động.

---

## 5. Đối Tượng Người Dùng & Các Persona Điển Hình

Hệ thống được thiết kế để phục vụ các nhóm hành vi du lịch đa dạng:

| Persona | Tên / Định danh | Đặc điểm & Hành vi chính | Nhu cầu tiếp cận trên V-OTA |
|---|---|---|---|
| **P1** | **Khách gia đình / Nghỉ dưỡng** | Thích resort trọn gói, tiện ích cho trẻ nhỏ, bãi biển riêng, ưu tiên an toàn và tiện lợi. | Gợi ý combo phòng + vé tham quan, tìm kiếm theo tiêu chí không gian yên tĩnh, hỗ trợ lịch trình nhẹ nhàng. |
| **P2** | **Khách công tác / Tiện ích** | Đi một mình hoặc theo nhóm nhỏ, cần khách sạn trung tâm gần hội nghị, thủ tục nhanh, đặt sát ngày. | Tìm kiếm theo vị trí và tiện nghi làm việc, gợi ý khách sạn doanh nhân, thủ tục đặt chỗ tối giản. |
| **P3** | **Khách du lịch tự túc / Trải nghiệm** | Ưa thích văn hóa, ẩm thực bản địa, hoạt động ngoài trời mạo hiểm, tối ưu chi phí. | Semantic search cho các hoạt động độc lạ, trợ lý AI gợi ý lịch trình dày dặn khám phá ngóc ngách. |
| **P4** | **Khách săn ưu đãi / Linh hoạt** | Tìm kiếm deal khuyến mãi, combo giá rẻ, thời gian đi linh hoạt tùy theo giá vé máy bay. | Nhận diện ưu đãi trên trang chủ, gợi ý các gói combo tiết kiệm, gợi ý theo khoảng ngân sách. |

---

## 6. Ràng Buộc Kỹ Thuật & Nguyên Tắc Vận Hành

1. **Nguyên tắc Grounding Tuyệt Đối:** Không cho phép LLM tự tạo ra ID sản phẩm, tên địa điểm hư cấu hoặc mức giá giả. Mọi thực thể trong lịch trình phải truy xuất được từ catalog hệ thống.
2. **Phân định Ranh giới Dữ liệu Nghiêm ngặt:**
   - Ứng dụng nghiệp vụ (`app`) và Catalog (`catalog`) không được phép truy cập trực tiếp bằng SQL vào vùng dữ liệu nhạy cảm của CDP (`cdp.events`, `cdp.profiles`). Mọi tương tác phải đi qua lớp cổng dịch vụ `CdpClient`.
   - Hệ thống Insider vận hành như một dịch vụ độc lập, kết nối thông qua giao thức HTTP an toàn.
3. **Single Source of Truth cho Giao tiếp Hệ thống:** File OpenAPI Contract (`src/shared/contracts/openapi.yaml`) là chuẩn mực duy nhất định nghĩa định dạng request/response. Mọi thay đổi logic trao đổi dữ liệu giữa Frontend, Backend và AI đều phải được cập nhật tại Contract trước khi triển khai code.
4. **Kiến trúc Bền vững (Clean Architecture):** Tách bạch rõ rệt giữa Domain Entities, Application Use Cases và Infrastructure Adapters để đảm bảo khả năng nâng cấp từng thành phần (ví dụ: chuyển từ Local Postgres sang Managed Cloud DB, nâng cấp model embedding) mà không ảnh hưởng logic kinh doanh.
