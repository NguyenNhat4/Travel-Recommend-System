# Hợp đồng tích hợp Itinerary Assistant

> **MVP 1.2.0:** ưu tiên hiển thị recommendation; [bộ trường tối thiểu](../../src/shared/contracts/MVP.md) và OpenAPI hiện hành thay thế danh sách required/optional cũ bên dưới. Các trường mở rộng vẫn được hỗ trợ nhưng không bắt buộc gửi.

**Phiên bản:** 1.0  
** Người tạo:** NhatNM  
**Bên sử dụng:** Team Web  
**Bên phụ thuộc:** Team Recommendation/Search và Backend Booking  
**Giao thức:** REST/JSON qua HTTP  
**Xác thực:** JWT Bearer Token, không bắt buộc với người dùng ẩn danh  
**Mã hóa:** UTF-8  
**Tiền tệ mặc định:** VND  
**Ngày:** `2026-09-15`  
**Giờ:** `16:42`  
**Múi giờ:** `Asia/Ho_Chi_Minh`

---

## 1. Phạm vi trách nhiệm

### 1.1. Team Agent chịu trách nhiệm

- Trích xuất yêu cầu chuyến đi từ câu tiếng Việt hoặc tiếng Anh.
- Phát hiện thông tin còn thiếu và đặt câu hỏi làm rõ.
- Gọi API Search và Recommendation; không truy cập trực tiếp bảng dữ liệu của team khác.
- Chọn các sản phẩm phù hợp cho từng nhóm trong lịch trình.
- Xây dựng lịch trình theo từng ngày, có thời gian hợp lý.
- Dùng LLM để trình bày các sản phẩm đã được truy xuất.
- Đảm bảo không tạo hoặc bịa sản phẩm.
- Kiểm tra lại sản phẩm, thời gian và tổng chi phí sau khi LLM sinh kết quả.
- Trả về JSON có cấu trúc ổn định cho frontend.
- Lưu ngữ cảnh hội thoại phục vụ việc chỉnh sửa lịch trình.
- Có phương án dự phòng khi LLM không khả dụng.

### 1.2. Team Recommendation/Search chịu trách nhiệm

- Sinh embedding và lập chỉ mục vector cho sản phẩm.
- Semantic search trên danh mục sản phẩm.
- Lọc theo điểm đến, loại sản phẩm, giá và trạng thái còn chỗ.
- Trả đề xuất cá nhân hóa cho người dùng đã đăng nhập.
- Cung cấp `productId` ổn định và điểm liên quan.
- Đảm bảo chất lượng và độ trễ của kết quả tìm kiếm.
- Loại sản phẩm hết chỗ khi request có `availableOnly=true`.

### 1.3. Team Web/Backend chịu trách nhiệm

- Đăng ký, đăng nhập và phát hành JWT.
- Ánh xạ tài khoản web với `cdp_user_id`.
- Trang danh sách và chi tiết sản phẩm.
- Giá và tình trạng còn chỗ chính thức tại thời điểm checkout.
- Giỏ hàng, checkout và xác nhận đặt chỗ.
- Đường dẫn đặt sản phẩm.
- Ghi booking đã hoàn tất thành event trong CDP clone.
- Hiển thị giao diện chat và lịch trình.

### 1.4. Ngoài phạm vi của Team Agent

- Crawl và làm sạch dữ liệu du lịch.
- Sinh embedding hoặc quản lý vector index.
- Truy cập trực tiếp database của team khác.
- Xử lý thanh toán hoặc xác nhận booking thật.
- Thay đổi giá hoặc availability.
- Tự tạo tên khách sạn, chuyến bay, combo hoặc địa điểm tham quan.

---

## 2. Team Agent cần từ Team Recommendation/Search

### 2.1. API semantic search

```http
POST /api/v1/search
Content-Type: application/json
```

#### Request

```json
{
  "query": "khu nghỉ dưỡng gần biển phù hợp gia đình có trẻ nhỏ",
  "destination": "Nha Trang",
  "category": "HOTEL",
  "startDate": "2026-10-10",
  "endDate": "2026-10-13",
  "party": {
    "adults": 2,
    "children": 1
  },
  "price": {
    "min": 0,
    "max": 5000000,
    "currency": "VND"
  },
  "availableOnly": true,
  "limit": 10
}
```

Ngoại trừ `query`, `availableOnly` và `limit`, các trường còn lại có thể nhận `null`.

#### Response

```json
{
  "results": [
    {
      "productId": "VP-HOTEL-001",
      "name": "Vinpearl Resort Nha Trang",
      "category": "HOTEL",
      "destination": "Nha Trang",
      "description": "Khu nghỉ dưỡng ven biển phù hợp gia đình.",
      "price": {
        "amount": 3200000,
        "currency": "VND",
        "unit": "PER_NIGHT"
      },
      "available": true,
      "imageUrl": "https://example.com/hotel.jpg",
      "bookingUrl": "/products/VP-HOTEL-001",
      "location": {
        "latitude": 12.216,
        "longitude": 109.242
      },
      "openingHours": null,
      "estimatedDurationMinutes": null,
      "attributes": ["family-friendly", "beach", "swimming-pool"],
      "semanticScore": 0.87
    }
  ],
  "total": 1,
  "requestId": "search-01JXYZ"
}
```

### 2.2. Cam kết dữ liệu từ Team Recommendation/Search

1. `productId` là duy nhất và ổn định.
2. `name`, `price`, `available` và `bookingUrl` lấy từ catalog.
3. `destination` được chuẩn hóa theo danh sách tên thống nhất giữa các team.
4. `category` chỉ dùng enum đã thống nhất.
5. Khi `availableOnly=true`, kết quả không chứa sản phẩm hết chỗ.
6. Nếu không có sản phẩm phù hợp, API trả mảng rỗng; không tự tạo dữ liệu thay thế.
7. Mục tiêu độ trễ p95 của API Search dưới 300 ms.
8. Thay đổi phá vỡ tương thích phải tạo phiên bản API mới.

### 2.3. Enum loại sản phẩm

```text
HOTEL
FLIGHT
ATTRACTION
COMBO
GOLF
```

### 2.4. API recommendation cá nhân hóa

```http
GET /api/v1/recommendations?destination=Nha%20Trang&limit=10
Authorization: Bearer <jwt>
```

#### Response

```json
{
  "userId": "cdp-user-001",
  "results": [
    {
      "productId": "VP-ATTR-001",
      "name": "VinWonders Nha Trang",
      "category": "ATTRACTION",
      "destination": "Nha Trang",
      "price": {
        "amount": 950000,
        "currency": "VND",
        "unit": "PER_PERSON"
      },
      "available": true,
      "bookingUrl": "/products/VP-ATTR-001",
      "recommendationScore": 0.82,
      "reason": "Phù hợp với chuyến đi gia đình tại Nha Trang"
    }
  ],
  "strategy": "PERSONALISED"
}
```

Với người dùng ẩn danh hoặc chưa đủ lịch sử, hệ thống có thể trả sản phẩm phổ biến và đặt:

```json
{
  "strategy": "POPULAR_IN_DESTINATION"
}
```

---

## 3. Team Agent cần từ Team Web/Backend

### 3.1. Thông tin xác thực

JWT cần có tối thiểu:

```json
{
  "sub": "web-user-001",
  "cdp_user_id": "cdp-user-001",
  "exp": 1789000000
}
```

Agent API vẫn phải chấp nhận request không có JWT. Người dùng ẩn danh nhận kết quả không cá nhân hóa.

### 3.2. Đường dẫn chi tiết sản phẩm

Mỗi `bookingUrl` phải mở được route frontend tương ứng:

```text
/products/{productId}
```

Team Agent sao chép nguyên giá trị này, không tự xây URL khác.

### 3.3. Kiểm tra trước checkout

Trước khi tạo booking, Web/Backend phải kiểm tra lại:

- Sản phẩm còn tồn tại.
- Giá hiện tại.
- Tình trạng còn chỗ.
- Ngày sử dụng.
- Số lượng khách.

Giá trong lịch trình chỉ là ước tính. Giá tại checkout là dữ liệu chính thức.

### 3.4. Bàn giao sang booking

Team Agent trả về `productId` và `bookingUrl`. Team Web chịu trách nhiệm điều hướng từ mục trong lịch trình sang trang chi tiết hoặc checkout. Trong MVP v1, Team Agent không trực tiếp tạo booking.

---

## 4. API do Team Agent cung cấp

### 4.1. Tạo hoặc tiếp tục lịch trình

```http
POST /api/v1/assistant/itineraries
Authorization: Bearer <jwt>
Content-Type: application/json
```

JWT là tùy chọn.

#### Request

```json
{
  "conversationId": null,
  "message": "Lên lịch 3 ngày ở Nha Trang cho gia đình 2 người lớn và 1 trẻ em, ngân sách 15 triệu",
  "context": {
    "language": "vi"
  }
}
```

| Trường | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `conversationId` | Không | Tiếp tục một cuộc hội thoại trước đó |
| `message` | Có | Yêu cầu bằng ngôn ngữ tự nhiên |
| `context.language` | Không | Nếu thiếu, hệ thống tự phát hiện ngôn ngữ |

### 4.2. Response hoàn chỉnh

```json
{
  "status": "COMPLETED",
  "conversationId": "conv-01JXYZ",
  "intent": {
    "destination": "Nha Trang",
    "startDate": null,
    "days": 3,
    "party": {
      "adults": 2,
      "children": 1
    },
    "budget": {
      "amount": 15000000,
      "currency": "VND"
    },
    "interests": ["biển", "hoạt động cho trẻ nhỏ"],
    "pace": "RELAXED"
  },
  "itinerary": {
    "title": "Lịch trình gia đình 3 ngày tại Nha Trang",
    "days": [
      {
        "day": 1,
        "title": "Nhận phòng và khám phá biển",
        "items": [
          {
            "startTime": "14:00",
            "endTime": "15:00",
            "type": "HOTEL",
            "productId": "VP-HOTEL-001",
            "productName": "Vinpearl Resort Nha Trang",
            "description": "Nhận phòng và nghỉ ngơi.",
            "price": {
              "amount": 3200000,
              "currency": "VND",
              "unit": "PER_NIGHT"
            },
            "imageUrl": "https://example.com/hotel.jpg",
            "bookingUrl": "/products/VP-HOTEL-001"
          },
          {
            "startTime": "16:00",
            "endTime": "18:00",
            "type": "FREE_TIME",
            "productId": null,
            "productName": null,
            "description": "Nghỉ ngơi và tự do tham quan bãi biển.",
            "price": null,
            "imageUrl": null,
            "bookingUrl": null
          }
        ]
      }
    ],
    "estimatedTotal": {
      "amount": 12350000,
      "currency": "VND"
    },
    "budgetStatus": "WITHIN_BUDGET"
  },
  "warnings": [],
  "metadata": {
    "personalised": true,
    "searchRequestIds": ["search-01JABC", "search-01JDEF"],
    "generatedAt": "2026-09-15T08:00:00Z"
  }
}
```

### 4.3. Response cần hỏi thêm

```json
{
  "status": "NEEDS_CLARIFICATION",
  "conversationId": "conv-01JXYZ",
  "question": "Bạn muốn đi thành phố nào?",
  "missingFields": ["destination"],
  "knownIntent": {
    "days": 3,
    "party": {
      "adults": 2,
      "children": 1
    }
  }
}
```

Mỗi lần chỉ hỏi một câu rõ ràng. Thông tin bắt buộc tối thiểu gồm:

- Điểm đến.
- Số ngày.

Ngày cụ thể, ngân sách, số người và sở thích có thể để trống hoặc dùng giá trị mặc định đã thống nhất.

### 4.4. Response không có kết quả

```json
{
  "status": "NO_RESULTS",
  "conversationId": "conv-01JXYZ",
  "message": "Hiện chưa có sản phẩm phù hợp tại Quy Nhơn trong khoảng giá này.",
  "suggestions": [
    "Tăng ngân sách",
    "Chọn điểm đến khác",
    "Bỏ điều kiện gần biển"
  ]
}
```

Team Agent không được lấp kết quả rỗng bằng sản phẩm do LLM tự tạo.

### 4.5. Response lỗi

```json
{
  "status": "ERROR",
  "error": {
    "code": "SEARCH_SERVICE_UNAVAILABLE",
    "message": "Không thể tải sản phẩm vào lúc này.",
    "retryable": true,
    "requestId": "agent-01JXYZ"
  }
}
```

| HTTP | Mã lỗi | Ý nghĩa |
|---:|---|---|
| 400 | `INVALID_REQUEST` | Request không hợp lệ hoặc nội dung rỗng |
| 400 | `INVALID_TRIP_DURATION` | Số ngày ngoài phạm vi hỗ trợ |
| 401 | `INVALID_TOKEN` | Có gửi JWT nhưng token không hợp lệ |
| 404 | `CONVERSATION_NOT_FOUND` | Không tìm thấy cuộc hội thoại |
| 422 | `UNSUPPORTED_DESTINATION` | Điểm đến chưa có trong catalog |
| 503 | `SEARCH_SERVICE_UNAVAILABLE` | Search API không khả dụng |
| 503 | `LLM_UNAVAILABLE` | LLM lỗi và không thể tạo kết quả dự phòng |
| 500 | `ITINERARY_VALIDATION_FAILED` | Lịch trình không vượt qua bước kiểm tra grounding |

---

## 5. Cam kết grounding từ Team Agent

1. Mọi `productId` khác `null` đều đến từ Search/Recommendation API.
2. Tên sản phẩm được sao chép chính xác từ kết quả tìm kiếm.
3. LLM không được tạo hoặc sửa giá.
4. Sản phẩm phải thuộc đúng điểm đến người dùng yêu cầu.
5. Không chủ động trả sản phẩm hết chỗ.
6. Backend tính `estimatedTotal`; không sử dụng phép tính của LLM.
7. Mỗi sản phẩm có đường dẫn chi tiết hoặc booking hoạt động được.
8. LLM có thể viết mô tả, thời gian nghỉ và bữa ăn không nêu tên; không được tạo sản phẩm có tên riêng.
9. Nếu LLM lỗi, Agent trả lịch trình dựng bằng rule hoặc lỗi có kiểm soát.
10. Mục tiêu grounding là 100%.
11. Mục tiêu độ trễ p95 toàn luồng dưới 5 giây.

---

## 6. Quy tắc hội thoại

- Mỗi conversation lưu trip intent đã chuẩn hóa gần nhất.
- Tin nhắn mới chỉ cập nhật các trường người dùng thay đổi rõ ràng.
- “Đổi thành Đà Nẵng” chỉ thay `destination`.
- “Tăng ngân sách lên 20 triệu” chỉ thay `budget`.
- Thực hiện tìm kiếm lại khi điểm đến, ngày, ngân sách, số người hoặc sở thích thay đổi.
- Không dùng trạng thái hội thoại làm nguồn chính thức cho giá và availability.
- MVP nên cho conversation hết hạn sau 24 giờ.

---

## 7. Yêu cầu phi chức năng

### 7.1. Request tracing

Mọi service truyền tiếp header:

```http
X-Request-ID: 01JXYZ
```

Nếu caller chưa gửi, service đầu tiên sẽ tạo ID.

### 7.2. Ngân sách thời gian

| Hoạt động | Timeout |
|---|---:|
| Một request Search | 1 giây |
| Một request Recommendation | 1 giây |
| LLM trích xuất intent | 2 giây |
| LLM trình bày lịch trình | 3 giây |
| Toàn bộ request Agent | Mục tiêu dưới 5 giây |

### 7.3. Logging

Log có thể chứa:

- Request ID.
- Conversation ID.
- User ID hoặc CDP ID đã pseudonymize.
- Intent đã trích xuất.
- Bộ lọc tìm kiếm.
- Danh sách product ID được trả về.
- Độ trễ.
- Kết quả validation.
- Mã lỗi.

Log không được chứa:

- Mật khẩu.
- JWT token.
- API key.
- Thông tin thanh toán đầy đủ.
- Dữ liệu cá nhân không cần thiết.

### 7.4. Versioning

- Mọi endpoint bắt đầu bằng `/api/v1`.
- Có thể thêm field mới mà không làm hỏng consumer cũ.
- Không xóa hoặc đổi tên field trong v1.
- Thay đổi enum phải thông báo trước khi integration.
- Thay đổi phá vỡ tương thích phải tạo `/api/v2`.

---

## 8. Mock data cần có trước khi tích hợp

Team Recommendation/Search cung cấp:

- Tối thiểu 5 khách sạn.
- Tối thiểu 10 địa điểm tham quan.
- Tối thiểu 3 chuyến bay hoặc dữ liệu mẫu chuyến bay.
- Tối thiểu 2 điểm đến.
- Ít nhất một sản phẩm hết chỗ.
- Ít nhất một trường hợp không có kết quả.

Team Agent cung cấp các response lịch trình mock cho Team Web trước khi pipeline thật hoàn thành.

Team Web cung cấp route placeholder hoạt động được:

```text
/products/{productId}
```

---

## 9. Tiêu chí nghiệm thu tích hợp

1. Yêu cầu tiếng Việt hợp lệ trả về lịch trình ba ngày.
2. Mọi sản phẩm trong lịch trình tồn tại trong kết quả Search.
3. Mọi sản phẩm thuộc đúng điểm đến.
4. Người dùng ẩn danh nhận lịch trình không cá nhân hóa.
5. Người dùng đăng nhập nhận thứ tự ứng viên có cá nhân hóa.
6. Thiếu điểm đến thì Agent trả câu hỏi làm rõ.
7. Điểm đến chưa hỗ trợ trả lỗi có kiểm soát.
8. Search trả rỗng không dẫn đến việc LLM bịa sản phẩm.
9. Search bị lỗi thì Agent trả lỗi retryable hoặc kết quả dự phòng.
10. Mỗi liên kết sản phẩm mở được trang chi tiết thật.
11. Checkout kiểm tra lại giá và availability.
12. Độ trễ p95 toàn luồng dưới 5 giây.
13. Automated grounding test đạt 100%.
14. Frontend mock và backend integration test dùng cùng một OpenAPI contract.

---

## 10. Definition of Done

Itinerary Assistant được xem là hoàn thành khi:

> Khách hàng nhập yêu cầu chuyến đi, nhận lịch trình theo từng ngày chỉ chứa sản phẩm thật và còn khả dụng, có thể mở một sản phẩm bất kỳ và tiếp tục sang luồng booking hiện có.

Luồng demo bắt buộc:

```text
Yêu cầu lịch trình
→ Nhận kế hoạch đã grounding
→ Mở sản phẩm thật
→ Đặt sản phẩm
→ Booking sinh event trong CDP
→ Recommendation của khách hàng thay đổi
```

---

## 11. Ba schema cần chốt đầu tiên

Trước khi các team code độc lập, cần khóa phiên bản đầu tiên của:

1. `SearchRequest` — Team Agent gửi sang Search.
2. `ProductSummary` — Search trả về cho Agent và Web.
3. `ItineraryResponse` — Agent trả về cho Web.

Ba schema này nên được đưa vào một file OpenAPI dùng chung. Frontend tạo mock từ chính file đó; backend cũng dùng nó cho contract test để tránh mỗi team tự hiểu payload theo một cách khác.
