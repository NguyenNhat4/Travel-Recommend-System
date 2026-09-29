# Hợp đồng tích hợp Itinerary Assistant

> **Nguồn sự thật:** [OpenAPI 1.2.0](../../src/shared/contracts/openapi.yaml) quyết định endpoint, HTTP status, enum và required/optional. Tài liệu này giải thích cách tích hợp; khi có khác biệt, OpenAPI thắng. Xem thêm [payload MVP tối thiểu](mvp-minimal-fields-1.2.0.md).

**Phiên bản tài liệu:** 1.2.0

**Người tạo:** NhatNM

**Bên sử dụng:** Team Web

**Bên phụ thuộc:** Team Recommendation/Search và Backend Booking

**Giao thức:** REST/JSON qua HTTP

**Xác thực:** JWT Bearer Token, không bắt buộc với người dùng ẩn danh

**Mã hóa:** UTF-8

**Tiền tệ mặc định:** VND

**Cập nhật:** `2026-09-29`

**Múi giờ:** `Asia/Ho_Chi_Minh`

---

## 1. Phạm vi trách nhiệm

### 1.1. Team Agent chịu trách nhiệm

- Trích xuất yêu cầu chuyến đi từ câu tiếng Việt hoặc tiếng Anh.
- Phát hiện thông tin còn thiếu và đặt câu hỏi làm rõ.
- Gọi Search, Recommendation và Similar (chỉ ở lượt đổi món, §2.5) qua port của tầng application; không truy cập trực tiếp bảng dữ liệu của team khác. Với dữ liệu thật, tool gọi engine trong cùng tiến trình với Backend (`ITINERARY_DATA_MODE=inprocess`), không gọi ngược HTTP API của chính Backend (§2). "Giao thức" ở đầu tài liệu là giao thức giữa Web và Agent (§4).
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
- Lọc theo điểm đến, taxonomy, giá và snapshot `available`.
- Trả đề xuất cá nhân hóa cho người dùng đã đăng nhập.
- Cung cấp `productId` ổn định và điểm liên quan.
- Đảm bảo chất lượng và độ trễ của kết quả tìm kiếm.
- Lọc theo snapshot `available` khi request có `availableOnly=true`; không tuyên bố tồn kho theo ngày hoặc số khách.

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

Planner có ba tool: `search_products`, `get_recommendations` và `get_similar_products` (chỉ được mời ở lượt đổi món, §2.5); schema tham số và response lấy từ OpenAPI (`application/itinerary/tool_contracts.py`), gateway kiểm cả hai chiều. Gateway chỉ khai báo cho LLM tool có port được cấu hình; lời gọi tới tool chưa cấu hình trả `TOOL_NOT_ALLOWED`. Tool đi qua port `application/ports/itinerary_tools.py`, do ba adapter cùng hiện thực:

| `ITINERARY_DATA_MODE` | Adapter | Cách lấy dữ liệu |
|---|---|---|
| `fixture` | `infrastructure/clients/itinerary_fixture_clients.py` | 50 sản phẩm mock; mặc định development/test |
| `inprocess` | `application/itinerary/engine_tools.py` (`InProcessItineraryTools`) | Gọi engine Search, Recommendation, Similar và catalog trên `app.state` trong cùng tiến trình; engine được lấy lại mỗi lần gọi nên theo kịp mỗi lần RecSys làm mới. Dùng khi chạy dữ liệu thật |
| `http` | `infrastructure/clients/itinerary_http_clients.py` | Tuỳ chọn: gọi endpoint §2.1, §2.4, §2.5 qua HTTP tới `ITINERARY_SERVICE_BASE_URL`, để hoàn tác hoặc khi tách Agent thành service riêng. Runner golden (`src/evaluation/agent/golden.py`) luôn dùng adapter này |

`inprocess` và `http` trả cùng hình dạng, đúng response của route: route và adapter `inprocess` dùng chung `recommendation_response`, `destination_list`; hai adapter dùng chung `search_tool_payload`. Endpoint ở §2.1, §2.4, §2.5 là bề mặt công khai của engine và là thứ mode `http` gọi. Tool tìm sản phẩm tương tự cho lượt đổi món (§2.5) đã chốt 2026-09-29, `docs/prd/update-archive/2026-09-28-tool-similar-cho-agent.md`.

### 2.1. API semantic search

```http
GET /api/v1/search?q=khu%20nghỉ%20dưỡng&destination=Nha%20Trang&taxonomy=hotel&limit=10
```

#### Query parameters

`q` là bắt buộc; `destination`, `taxonomy`, `limit`, `offset` là tùy chọn. Tool planner vẫn dùng tên `query`; chỉ adapter HTTP đổi sang `q`, adapter `inprocess` truyền thẳng vào engine. Cả hai chỉ chuyển `taxonomy`, `destination`, `limit`, `offset`, bỏ `cutoff` và `diagnostics` khỏi kết quả, và không bao giờ gắn danh tính người dùng (không JWT, không `cdpUserId`). Search MVP không nhận ngày, party hoặc bộ lọc giá/sao; Agent giữ và hậu kiểm các ràng buộc đó sau retrieval.

#### Response

```json
{
  "results": [
    {
      "productId": "VP-HOTEL-001",
      "name": "Vinpearl Resort Nha Trang",
      "taxonomy": "hotel",
      "destination": "Nha Trang",
      "description": "Khu nghỉ dưỡng ven biển phù hợp gia đình.",
      "unitPrice": 3200000,
      "currency": "VND",
      "priceUnit": "PER_NIGHT",
      "available": true,
      "imageUrl": "https://example.com/hotel.jpg",
      "attributes": {
        "familyFriendly": true,
        "privateBeach": true
      },
      "score": 0.87
    }
  ],
  "total": 1,
  "requestId": "search-01JXYZ"
}
```

### 2.2. Cam kết dữ liệu từ Team Recommendation/Search

1. `productId` là duy nhất và ổn định.
2. `name`, `unitPrice`, `currency` và `available` lấy từ catalog.
3. `destination` được chuẩn hóa theo danh sách tên thống nhất giữa các team.
4. `taxonomy` dùng enum lowercase trong OpenAPI.
5. `available=true` chỉ là snapshot nguồn có trả giá lúc crawl, không xác nhận tồn kho theo ngày hoặc số khách.
6. Nếu không có sản phẩm phù hợp, API trả mảng rỗng; không tự tạo dữ liệu thay thế.
7. Mục tiêu độ trễ p95 của API Search dưới 300 ms.
8. Thay đổi phá vỡ tương thích phải tạo phiên bản API mới.

### 2.3. Enum taxonomy

```text
hotel
flight
attraction
combo
golf
```

### 2.4. API recommendation cá nhân hóa

```http
GET /api/v1/recommendations?destination=Nha%20Trang&k=10
Authorization: Bearer <jwt>
```

#### Response

```json
{
  "cdpUserId": "cdp-user-001",
  "recommendations": [
    {
      "productId": "VP-ATTR-001",
      "name": "VinWonders Nha Trang",
      "taxonomy": "attraction",
      "destination": "Nha Trang",
      "unitPrice": 950000,
      "currency": "VND",
      "priceUnit": "PER_PERSON",
      "available": true,
      "because": []
    }
  ],
  "strategy": "popular"
}
```

`strategy` dùng enum OpenAPI: `cross_vertical`, `recent_activity`, `dormant`, `popular`, `long_term`, `cold_start_content` (hai giá trị cuối bổ sung ở OpenAPI 1.8.0, điều kiện ở `hop-dong-tich-hop-search-recommendation.md` §4.4). Người dùng ẩn danh hoặc chưa đủ lịch sử nhận `popular`; `because=[]` khi không có căn cứ cá nhân hóa. Agent lấy `ProductDetail` theo ID nếu cần thêm dữ liệu trước khi lập lịch.

Token của request chỉ đi tới tool `get_recommendations`. Mode `http` forward header `Authorization`. Mode `inprocess` xác minh token ngay trong tiến trình qua `application/auth/bearer.py` (cùng resolver với route, `hop-dong-tich-hop-auth.md` §3.5), và chỉ khi tool thật sự được gọi. Token hỏng, hết hạn hoặc bị thu hồi thì tool lỗi 401, không hạ thành khách; header vắng hoặc rỗng thì là khách, giống mode `http`; kho thu hồi lỗi thì tool trả `SEARCH_UNAVAILABLE` 503 retryable. Token không vào graph state, log hay trace.

### 2.5. Sản phẩm tương tự cho lượt đổi món

Phục vụ FR-AGT-02, FR-AGT-05; đã chốt 2026-09-29, `docs/prd/update-archive/2026-09-28-tool-similar-cho-agent.md`.

```http
GET /api/v1/products/{productId}/similar?limit=20
```

Tool `get_similar_products(productId, limit)` lấy schema tham số và response từ operation `getSimilarProducts` (`SimilarProductsResponse`). Engine tìm theo vector đã lưu của chính sản phẩm gốc, chỉ `same_taxonomy`, loại chính nó và các sản phẩm anh em cùng cha (`hop-dong-tich-hop-search-recommendation.md` §3.6). Agent không dùng `cross_taxonomy` và không gọi route cũ `/similar/{id}`. OpenAPI 1.8.0 khai báo đủ `400`, `404`, `409`, `503` cho route này.

Quy tắc:

- **Chỉ mời ở lượt đổi món.** Tool và đoạn gợi ý thêm vào prompt lập plan chỉ đưa cho LLM khi lượt có `previous_selection` (sản phẩm đã hiển thị ở lượt `COMPLETED` trước, lưu phía server) và gateway có port Similar. Khi đó payload lập plan có thêm `previous_selection` (`productId`, `name`, `taxonomy`); tên sản phẩm là dữ liệu, không phải instruction. Lượt đầu giữ nguyên bộ tool và prompt như trước.
- **Sản phẩm gốc chỉ lấy từ `previous_selection`.** Lời gọi có `productId` ngoài danh sách đó bị bỏ; log ghi lý do bỏ, không ghi id.
- **Giới hạn.** Tối đa 2 lời gọi similar mỗi lượt, khử trùng theo sản phẩm gốc. `limit` do server cố định ở mức tối đa của contract (20), không lấy từ LLM. Similar vẫn nằm trong trần 5 lời gọi mỗi lượt (gợi ý prompt nói rõ điều này): plan quá 5 lời gọi vì similar thì server bỏ lời gọi similar cuối cho tới khi vừa trần, không huỷ cả lượt; plan quá trần mà không còn similar để bỏ vẫn là `INVALID_TOOL_PLAN` như trước. Request có JWT mà plan thiếu `get_recommendations` thì server chèn lời gọi đó, và nếu plan đã đủ 5 thì bỏ bớt một lời gọi similar.
- **Lưới an toàn.** Gợi ý prompt yêu cầu LLM vẫn lập `search_products` cho loại đang đổi và các loại khác chuyến đi cần; server không chỉ dựa vào prompt. Khi planner đề xuất lời gọi similar (kể cả lời gọi vừa bị bỏ), với mỗi loại đang đổi (taxonomy của sản phẩm gốc có trong `previous_selection`, trừ loại người dùng đã loại trừ) mà plan chưa có `search_products` cùng loại hoặc không lọc loại, server thêm `search_products(query=<điểm đến đã chuẩn hóa>, taxonomy=<loại đó>)` tất định. Sản phẩm gốc bịa không cho biết loại: plan không còn `search_products` nào thì server thêm `search_products(query=<điểm đến đã chuẩn hóa>)`. Plan chỉ có sản phẩm gốc bịa vì vậy thành đúng lời gọi search đó, cộng `get_recommendations` nếu request có JWT. `get_recommendations` bắt buộc được xếp chỗ trước; mỗi search của lưới an toàn cần chỗ thì bỏ một lời gọi similar. Hết chỗ mà không còn similar để bỏ thì search theo loại được bỏ qua (plan lúc đó như plan không có similar, không huỷ lượt), còn plan không có `search_products` nào là `INVALID_TOOL_PLAN`. Plan không đề xuất similar giữ nguyên như trước. Id lời gọi được đánh số lại liên tục (`call-0`, `call-1`…) sau khi lọc; kiểm lại một plan đã kiểm cho ra đúng plan đó.
- **Lỗi mềm.** Similar là best-effort. `PRODUCT_NOT_FOUND` (404) và `PRODUCT_NOT_INDEXED` (409) nghĩa là "không có phương án", luôn mềm. Similar không dùng được (`SEARCH_UNAVAILABLE` 503, `TOOL_TIMEOUT`; ở mode `http` còn có mọi lỗi 5xx, kể cả 500 dạng text mà adapter đọc thành `INVALID_TOOL_RESPONSE` kèm `httpStatus`, và lỗi kết nối `TOOL_HTTP_ERROR`) mềm khi có ít nhất một lời gọi `search_products` trả dữ liệu; không có thì xử lý như lỗi tool thường (§4.6). Response 2xx sai hợp đồng vẫn là lỗi vĩnh viễn. Nhờ vậy similar hỏng không đẩy lượt đổi món sang thử lại rồi `FALLBACK`, ở cả hai mode.
- **Kết quả.** Kết quả similar vào cùng tập ứng viên với Search, gắn nhãn nguồn `SEARCH` (`ItemSource` không thêm giá trị) và qua cùng bước hậu kiểm. Similar không lọc theo điểm đến, nên sản phẩm lệch điểm đến của chuyến bị bỏ lặng lẽ, không sinh warning. Tên, giá, `productId` lấy nguyên từ response engine (§5). `compose` vẫn xếp theo luật cố định, không ưu tiên riêng kết quả similar cho ô đang đổi, nên món mới có thể đến từ search của lưới an toàn thay vì từ similar.

| `ITINERARY_DATA_MODE` | Cách lấy sản phẩm tương tự |
|---|---|
| `fixture` | Cùng taxonomy trong 50 sản phẩm mock, còn chỗ, bỏ chính nó và anh em cùng cha, cùng điểm đến xếp trước, tối đa `limit`; id lạ trả 404 `PRODUCT_NOT_FOUND` |
| `inprocess` | Use case `GetSimilarProducts` trên `app.state`, cùng use case với route; thêm `requestId` như route |
| `http` | `GET /products/{productId}/similar?limit=` (id được URL-encode), **không** gửi `Authorization` |

Similar không mang danh tính người dùng ở mọi mode: endpoint trả giống nhau cho mọi người dùng (`hop-dong-tich-hop-backend.md` §4.3).

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

OpenAPI cung cấp API chi tiết sản phẩm:

```text
GET /api/v1/products/{productId}
```

`ProductSummary` MVP không bắt buộc có `bookingUrl`. Web điều hướng bằng `productId` theo route giao diện đã thống nhất; Agent không tự tạo URL ngoài contract.

### 3.3. Kiểm tra trước checkout

Trước khi tạo booking, Web/Backend phải kiểm tra lại:

- Sản phẩm còn tồn tại.
- Giá hiện tại.
- Tình trạng còn chỗ.
- Ngày sử dụng.
- Số lượng khách.

Giá và `available` trong lịch trình chỉ là snapshot tham khảo. Giá và availability tại checkout là dữ liệu chính thức.

### 3.4. Bàn giao sang booking

Team Agent trả `ProductSummary` chứa `productId`. Team Web chịu trách nhiệm điều hướng sang trang chi tiết hoặc checkout. Agent không trực tiếp tạo booking.

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
| `message` | Có điều kiện | Yêu cầu bằng ngôn ngữ tự nhiên |
| `intentOverride` | Có điều kiện | Patch intent có cấu trúc; chỉ dùng cùng `conversationId` khác null |
| `context.language` | Không | `vi` hoặc `en`; nếu thiếu backend dùng `vi`. Giá trị tường minh được lưu theo conversation và dùng cho các lượt sau |

Request hợp lệ khi có `message`, hoặc có đồng thời `conversationId` và `intentOverride`. `message` có tối đa 1.000 ký tự.

`destination` và `days` là dữ liệu nghiệp vụ bắt buộc để bắt đầu retrieval và lập kế hoạch, nhưng không bắt buộc có sẵn trong request đầu tiên. Khi thiếu một hoặc cả hai, Agent trả `NEEDS_CLARIFICATION`, lưu phần intent đã biết cùng lịch sử chat gần đây theo `conversationId` và không gọi Search, Recommendation hoặc Catalog. MVP không tự phát hiện ngôn ngữ để tránh kết quả không ổn định; thứ tự ưu tiên là `context.language` tường minh, ngôn ngữ đã lưu của conversation, rồi `vi`.

#### API stream cho UI demo

```http
POST /api/v1/assistant/itineraries/stream
Accept: text/event-stream
```

Request giống `POST /assistant/itineraries`. Stream phát lần lượt `run.started`, `graph.topology`, các `node.completed`, rồi `run.completed` hoặc `run.failed`. Event chỉ chứa ID node, thứ tự, trạng thái, thời lượng và response công khai; không chứa raw graph state, prompt, token hoặc credential. Vì HTTP status đã được gửi khi mở SSE, lỗi phát sinh sau đó nằm trong payload `run.failed.httpStatus`.

`GET /api/v1/assistant/status` trả readiness, graph version, data mode (`fixture` | `inprocess` | `http` | `disabled`) và số sản phẩm nếu adapter biết (`fixture`: 50; `inprocess`: số search unit trong index RecSys đang phục vụ, `null` khi RecSys chưa nạp). `fixture` chỉ được bật mặc định ở development/test; ngoài development/test mặc định là `disabled`, nên staging/production phải đặt `ITINERARY_DATA_MODE` tường minh (`inprocess` khi chạy dữ liệu thật).

### 4.2. Response hoàn chỉnh

Payload MVP chỉ bắt buộc `status`, `conversationId`, `itinerary` và `warnings`. Các trường `intent`, `searchResults` và `metadata` là tùy chọn.

```json
{
  "status": "COMPLETED",
  "conversationId": "conv-01JXYZ",
  "itinerary": {
    "days": [
      {
        "day": 1,
        "slots": [
          {
            "time": "AFTERNOON",
            "product": {
              "productId": "VP-HOTEL-001",
              "name": "Vinpearl Resort Nha Trang",
              "taxonomy": "hotel",
              "destination": "Nha Trang",
              "unitPrice": 3200000,
              "currency": "VND",
              "available": true
            },
            "note": "Nhận phòng và nghỉ ngơi."
          },
          {
            "time": "EVENING",
            "product": null,
            "activityType": "FREE_TIME",
            "note": "Tự do khám phá khu vực ven biển."
          }
        ]
      }
    ],
    "estimatedTotal": null,
    "currency": "VND",
    "budgetStatus": "UNKNOWN"
  },
  "warnings": [
    {
      "code": "TOTAL_UNKNOWN",
      "message": "Chưa đủ đơn vị và số lượng để tính tổng chi phí.",
      "productId": null
    }
  ]
}
```

Nếu `estimatedTotal=null`, `budgetStatus` bắt buộc là `UNKNOWN` và cần warning. Backend tính tổng khi đủ căn cứ; LLM không tính hoặc sửa giá.

### 4.3. Response cần hỏi thêm

```json
{
  "status": "NEEDS_CLARIFICATION",
  "conversationId": "conv-01JXYZ",
  "question": "Bạn muốn đi thành phố nào?",
  "missingFields": ["destination"],
  "knownIntent": {
    "destination": null,
    "startDate": null,
    "days": 3,
    "party": null,
    "budget": null,
    "interests": [],
    "pace": null
  }
}
```

Payload tối thiểu chỉ bắt buộc `status`, `conversationId`, `question`. Thông tin bắt buộc tối thiểu để lập lịch gồm điểm đến và số ngày từ 1 đến 7. Mỗi lượt chỉ hỏi một câu rõ ràng; các trường còn lại có thể để trống.

### 4.4. Response không có kết quả

```json
{
  "status": "NO_RESULTS",
  "conversationId": "conv-01JXYZ",
  "message": "Hiện chưa có sản phẩm phù hợp tại Quy Nhơn trong khoảng giá này.",
  "suggestions": ["Tăng ngân sách", "Chọn điểm đến khác", "Bỏ điều kiện gần biển"]
}
```

Agent không lấp kết quả rỗng bằng sản phẩm do LLM tự tạo.

### 4.5. Response suy giảm

Khi Search vẫn trả sản phẩm thật nhưng Agent không thể dựng lịch trình, API có thể trả HTTP 200 với `FALLBACK`:

```json
{
  "status": "FALLBACK",
  "conversationId": "conv-01JXYZ",
  "message": "Chưa thể dựng lịch trình; bạn có thể xem các sản phẩm phù hợp bên dưới.",
  "searchResults": {
    "hotel": [],
    "flight": [],
    "attraction": []
  }
}
```

Nếu rule-based planner dựng được itinerary hợp lệ và vượt qua grounding validation, API có thể trả `COMPLETED` kèm warning cho biết đã dùng fallback.

### 4.6. Response lỗi

Lỗi thực sự không nằm trong `ItineraryResponse` và không dùng `status: ERROR` trong body HTTP 200. API trả HTTP 4xx/5xx với `ErrorResponse` dùng chung:

```json
{
  "error": {
    "code": "SEARCH_UNAVAILABLE",
    "message": "Không thể tải sản phẩm vào lúc này.",
    "retryable": true,
    "requestId": "agent-01JXYZ"
  }
}
```

| HTTP | Mã lỗi | Ý nghĩa |
|---:|---|---|
| 400 | `VALIDATION_ERROR` | Request rỗng hoặc không đúng schema |
| 400 | `INVALID_TRIP_DURATION` | Số ngày ngoài phạm vi 1–7 |
| 401 | `INVALID_TOKEN` hoặc `TOKEN_EXPIRED` | Có gửi JWT nhưng token không hợp lệ |
| 404 | `CONVERSATION_NOT_FOUND` | Không tìm thấy cuộc hội thoại |
| 422 | `UNSUPPORTED_DESTINATION` | Điểm đến chưa có trong catalog. `details` có `destination`, `supportedDestinations`, `conversationId`; backend lưu phần intent còn lại (bỏ điểm đến) nên gửi lại `conversationId` cùng điểm đến hợp lệ là tiếp tục chuyến đi |
| 503 | `SEARCH_UNAVAILABLE` | Search/Recommendation không khả dụng: engine lỗi, RecSys chưa nạp hoặc đã tắt, upstream HTTP lỗi |
| 503 | `LLM_UNAVAILABLE` | LLM lỗi và không thể trả kết quả dự phòng |
| 500 | `ITINERARY_VALIDATION_FAILED` | Lịch trình không vượt qua grounding validation |

Ở mode `inprocess`, RecSys chưa nạp/đã tắt hoặc engine lỗi bất ngờ làm tool trả `SEARCH_UNAVAILABLE` 503 **retryable**. Graph thử lại một lần; vẫn lỗi thì API trả 503 `SEARCH_UNAVAILABLE` `retryable: true`, hoặc `FALLBACK` nếu vẫn còn kết quả thật (§9 mục 9). Đây là thay đổi có chủ đích so với mode `http` (2026-09-28): ở `http`, lỗi route không được bắt thành 500 dạng text, adapter đọc là `INVALID_TOOL_RESPONSE` không retryable nên không thử lại. Route công khai giữ nguyên hành vi. Nguyên nhân lỗi engine chỉ ghi log, không vào state hay response.

---

## 5. Cam kết grounding từ Team Agent

1. Mọi `productId` khác `null` đều đến từ kết quả tool Search/Recommendation, hoặc Similar khi đổi một sản phẩm đã hiển thị (§2.5; engine trong tiến trình hoặc API HTTP, tuỳ data mode).
2. Tên sản phẩm được sao chép chính xác từ kết quả tìm kiếm.
3. LLM không được tạo hoặc sửa giá.
4. Sản phẩm phải thuộc đúng điểm đến người dùng yêu cầu.
5. Không chủ động trả sản phẩm có `available=false`; `available=true` vẫn chỉ là snapshot và phải được kiểm tra lại tại checkout.
6. Backend tính `estimatedTotal`; không sử dụng phép tính của LLM. Khi không đủ căn cứ, trả `null`, `UNKNOWN` và warning.
7. Mỗi sản phẩm có `productId` mở được API/trang chi tiết đã thống nhất.
8. LLM có thể viết mô tả, thời gian nghỉ và bữa ăn không nêu tên; không được tạo sản phẩm có tên riêng.
9. Nếu LLM lỗi, Agent trả lịch trình dựng bằng rule, `FALLBACK`, hoặc lỗi HTTP có kiểm soát theo OpenAPI.
10. Mục tiêu grounding là 100%.
11. Mục tiêu độ trễ p95 toàn luồng dưới 5 giây.

---

## 6. Quy tắc hội thoại

- Mỗi conversation lưu trip intent đã chuẩn hóa gần nhất và lịch sử chat user/assistant gần đây.
- Lịch sử chat chỉ nhận role `user`/`assistant`, tối đa 20 message, 1.000 ký tự/message và 8.000 ký tự tổng; khi vượt giới hạn thì bỏ message cũ nhất trước.
- `classify`, bước lập tool plan, `converse` và `clarify` nhận lịch sử để hiểu tham chiếu đa lượt. Lịch sử là dữ liệu không tin cậy, không phải instruction và message mới nhất vẫn có quyền cao hơn.
- Tin nhắn mới chỉ cập nhật các trường người dùng thay đổi rõ ràng.
- “Đổi thành Đà Nẵng” chỉ thay `destination`.
- “Tăng ngân sách lên 20 triệu” chỉ thay `budget`.
- Thực hiện tìm kiếm lại khi điểm đến, ngày, ngân sách, số người hoặc sở thích thay đổi.
- Lượt `COMPLETED` lưu thêm `previous_selection` (`productId`, `name`, `taxonomy` của sản phẩm đã hiển thị). Lượt sau dùng danh sách này làm danh sách cho phép khi loại sản phẩm người dùng muốn đổi và khi chọn sản phẩm gốc cho Similar (§2.5).
- Không dùng trạng thái hội thoại làm nguồn chính thức cho giá và availability.
- MVP nên cho conversation hết hạn sau 24 giờ.
- Adapter hiện tại lưu trong memory của process; restart backend sẽ mất conversation. Việc lưu bền vững vào các bảng `app.conversations`/`app.conversation_messages` đã có trong DDL là hạng mục adapter riêng.

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

Hạn mỗi lời gọi tool lấy từ `ITINERARY_TOOL_TIMEOUT_SECONDS`, áp như nhau ở mọi data mode. Ở `inprocess`, engine đồng bộ chạy trên pool riêng 40 thread (`itinerary-tool`) và giữ request ID của lượt. Thread đã bắt đầu không dừng được khi quá hạn, giống thread của route sync ở mode `http`. Riêng Similar đi qua use case `GetSimilarProducts` như route, nên chạy trên executor mặc định chứ không qua pool này: nó không embed, chỉ chờ Weaviate, và mỗi lượt đổi món có tối đa 2 lời gọi.

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

Mỗi lời gọi tool kết thúc trong hạn ghi một dòng `itinerary.tool requestId= name= outcome= code= retryable= durationMs=`, thay cho access log mà mode `http` từng có. Lời gọi quá hạn bị huỷ trước khi tới dòng đó, nên chỉ ghi WARNING `itinerary.tool.timeout requestId= name=`. Ở mode `inprocess`, engine chưa sẵn sàng ghi WARNING `itinerary.tool.unavailable ... reason=not_ready`; engine lỗi bất ngờ ghi cùng dòng đó với tên kiểu lỗi, kèm các frame traceback (file, dòng, mã nguồn) để lần ra bug. Các dòng này không ghi tham số tool, thông điệp lỗi hay token.

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
- Ít nhất một sản phẩm có `available=false`.
- Ít nhất một trường hợp không có kết quả.

Team Agent cung cấp các response lịch trình mock cho Team Web trước khi pipeline thật hoàn thành.

Team Web cung cấp route giao diện từ `productId`; API chi tiết chuẩn là:

```text
GET /api/v1/products/{productId}
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
9. Search bị lỗi thì Agent trả `SEARCH_UNAVAILABLE` retryable; chỉ dùng `FALLBACK` khi vẫn còn kết quả Search thật để hiển thị. Ở mode `inprocess`, RecSys chưa nạp/đã tắt và lỗi engine bất ngờ đều tính là Search lỗi (§4.6).
10. Mỗi `productId` mở được trang chi tiết thật.
11. Checkout kiểm tra lại giá và availability.
12. Độ trễ p95 toàn luồng dưới 5 giây.
13. Automated grounding test đạt 100%.
14. Frontend mock và backend integration test dùng cùng một OpenAPI contract.

---

## 10. Definition of Done

Itinerary Assistant được xem là hoàn thành khi:

> Khách hàng nhập yêu cầu chuyến đi, nhận lịch trình theo từng ngày chỉ chứa sản phẩm thật từ catalog, có thể mở một sản phẩm bất kỳ và tiếp tục sang luồng booking để kiểm tra lại giá và availability.

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

## 11. Ba schema dùng chung đã khóa

OpenAPI 1.2.0 đã khóa phiên bản đầu tiên của:

1. `SearchRequest` — schema tham số của tool `search_products`; gateway kiểm trước khi gọi Search (§2).
2. `ProductSummary` — Search trả về cho Agent và Web.
3. `ItineraryResponse` — Agent trả về cho Web.

Ba schema được tham chiếu từ `src/shared/contracts/openapi.yaml`. Frontend tạo mock/client từ contract này; backend dùng cùng contract cho validation và contract test. Mọi thay đổi required field, enum hoặc HTTP behavior phải sửa OpenAPI trước, cập nhật fixture và chạy validator.
