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
POST /api/v1/search
{"query": "khu nghỉ dưỡng", "destination": "Nha Trang", "taxonomy": "hotel", "limit": 50,
 "travelContext": {"guests": {"adults": 2, "children": 1}}}
```

#### Query parameters

`query` là bắt buộc; còn lại tùy chọn theo `SearchRequest`. Agent không lấy `limit` từ LLM: server cố định `limit=50` (tối đa contract) cho mọi search — `hotel` để luật ít di chuyển AC-AGT-04 có nhiều vị trí khách sạn mà chọn, loại khác để chuyến dài đủ hoạt động cho cả buổi sáng lẫn chiều sau khi vé nhiều ngày và bản trùng bị loại khỏi slot — `k=10` cho `get_recommendations` (§2.4), ở hằng `HOTEL_SEARCH_LIMIT`/`SEARCH_LIMIT`/`RECOMMENDATION_K` trong `agents/steps/tool_planning.py`, nên mọi mode nhận cùng số ứng viên. Adapter HTTP gọi `POST /search` (route duy nhất nhận số khách), adapter `inprocess` truyền thẳng vào engine; cả hai chuyển cùng bộ tham số `taxonomy`, `destination`, `limit`, `offset`, `origin`, `priceMin`, `priceMax`, `starRatingMin`, `availableOnly` và `travelContext.guests` (`engine_tools.SEARCH_ENGINE_ARGUMENTS`), bỏ `cutoff` và `diagnostics` khỏi kết quả, và không bao giờ gắn danh tính người dùng (không JWT, không `cdpUserId`). `sort`, `includeVariants` và ngày trong `travelContext` engine chưa dùng nên không chuyển. Các giá trị filter do server đặt, không lấy từ LLM: `_validated_args` đặt `priceMax`/`starRatingMin` của search `hotel` từ constraints, bỏ `priceMin`/`priceMax` khi không có trần giá khách sạn (ngân sách cả chuyến không phải filter từng sản phẩm), và đặt `travelContext.guests` (filter sức chứa một phòng, contract 1.16.0) cho search `hotel` từ `intent.party`, là số khách mỗi phòng khi cả đoàn chia tối đa 9 phòng (`ceil(tổng / 9)`, chốt 2026-10-09), không phải cả đoàn; loại khác không mang `travelContext`. Agent vẫn hậu kiểm các ràng buộc sau retrieval.

**Nội dung `query`.** `query` chỉ mang phần ngữ nghĩa của lời gọi: loại nơi hoặc hoạt động, phong cách, và gợi ý `search_hints` của đúng taxonomy (`domain/itinerary/search_hints.py`: tiện ích khách sạn từ `hotel_attributes = true`, gia đình có trẻ nhỏ, `interests`, tên trong `specific_hotel`/`specific_activity`, viết đúng nhãn mà text embed của catalog dùng). Không chứa số, giá, ngân sách, ngày, số ngày/đêm, số người, số sao, tên điểm đến hay phủ định, vì hai lý do: text embed của catalog không có các thông tin đó nên chúng chỉ làm nhiễu xếp hạng, và query plan của `/search` đọc chúng thành filter từng sản phẩm ("ngân sách 5 triệu" → `priceMax` 5 triệu cho mỗi sản phẩm). `TOOL_PLAN_PROMPT` yêu cầu planner viết như vậy và payload planner chỉ còn `intent` rút gọn (`destination`, `interests`, `partyType`, `hasChildren`) cùng `search_hints`; server không chỉ dựa vào prompt: `_validated_args` chạy `search_query_text` cắt mọi cụm trên (tái dùng parser giá/số khách/phủ định của `/search`), thêm gợi ý còn thiếu, và query rỗng sau khi cắt thì thành danh từ loại kèm gợi ý ("khách sạn", "điểm tham quan", "sân golf"); search không lọc loại thì giữ tên điểm đến. Hàm lũy đẳng nên kiểm lại một plan đã kiểm vẫn ra đúng plan đó.

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

- **Chỉ mời ở lượt đổi món.** Tool và đoạn gợi ý thêm vào prompt lập plan chỉ đưa cho LLM khi lượt có `previous_selection` (sản phẩm đã hiển thị ở lượt `COMPLETED` trước, lưu phía server) và gateway có port Similar. Payload lập plan của mọi lượt vẫn mang ngữ cảnh chung (`llm_context`, `docs/prd/architecture.md` §3), trong đó có `previous_selection` (rỗng ở lượt đầu); khi mời Similar, khoá này chỉ giữ `productId`, `name`, `taxonomy`. Tên sản phẩm là dữ liệu, không phải instruction. Lượt đầu giữ nguyên bộ tool và prompt như trước.
- **Sản phẩm gốc chỉ lấy từ `previous_selection`.** Lời gọi có `productId` ngoài danh sách đó bị bỏ; log ghi lý do bỏ, không ghi id.
- **Giới hạn.** Tối đa 2 lời gọi similar mỗi lượt, khử trùng theo sản phẩm gốc. `limit` do server cố định ở mức tối đa của contract (20), không lấy từ LLM. Similar vẫn nằm trong trần 5 lời gọi mỗi lượt (gợi ý prompt nói rõ điều này): plan quá 5 lời gọi vì similar thì server bỏ lời gọi similar cuối cho tới khi vừa trần, không huỷ cả lượt; plan quá trần mà không còn similar để bỏ vẫn là `INVALID_TOOL_PLAN` như trước. Request có JWT mà plan thiếu `get_recommendations` thì server chèn lời gọi đó, và nếu plan đã đủ 5 thì bỏ bớt một lời gọi similar.
- **Lưới an toàn.** Gợi ý prompt yêu cầu LLM vẫn lập `search_products` cho loại đang đổi và các loại khác chuyến đi cần; server không chỉ dựa vào prompt. Khi planner đề xuất lời gọi similar (kể cả lời gọi vừa bị bỏ), với mỗi loại đang đổi (taxonomy của sản phẩm gốc có trong `previous_selection`, trừ loại người dùng đã loại trừ) mà plan chưa có `search_products` cùng loại hoặc không lọc loại, server thêm `search_products(taxonomy=<loại đó>)` tất định cho điểm đến đã chuẩn hóa (query là danh từ loại kèm gợi ý, §2 "Nội dung `query`"). Sản phẩm gốc bịa không cho biết loại: plan không còn `search_products` nào thì server thêm `search_products(query=<điểm đến đã chuẩn hóa>)`. Plan chỉ có sản phẩm gốc bịa vì vậy thành đúng lời gọi search đó, cộng `get_recommendations` nếu request có JWT. `get_recommendations` bắt buộc được xếp chỗ trước; mỗi search của lưới an toàn cần chỗ thì bỏ một lời gọi similar. Hết chỗ mà không còn similar để bỏ thì search theo loại được bỏ qua (plan lúc đó như plan không có similar, không huỷ lượt), còn plan không có `search_products` nào là `INVALID_TOOL_PLAN`. Plan không đề xuất similar giữ nguyên như trước. Id lời gọi được đánh số lại liên tục (`call-0`, `call-1`…) sau khi lọc; kiểm lại một plan đã kiểm cho ra đúng plan đó.
- **Lỗi mềm.** Similar là best-effort. `PRODUCT_NOT_FOUND` (404) và `PRODUCT_NOT_INDEXED` (409) nghĩa là "không có phương án", luôn mềm. Similar không dùng được (`SEARCH_UNAVAILABLE` 503, `TOOL_TIMEOUT`; ở mode `http` còn có mọi lỗi 5xx, kể cả 500 dạng text mà adapter đọc thành `INVALID_TOOL_RESPONSE` kèm `httpStatus`, và lỗi kết nối `TOOL_HTTP_ERROR`) mềm khi có ít nhất một lời gọi `search_products` trả dữ liệu; không có thì xử lý như lỗi tool thường (§4.6). Response 2xx sai hợp đồng vẫn là lỗi vĩnh viễn. Nhờ vậy similar hỏng không đẩy lượt đổi món sang thử lại rồi `FALLBACK`, ở cả hai mode.
- **Kết quả.** Kết quả similar vào cùng tập ứng viên với Search, gắn nhãn nguồn `SEARCH` (`ItemSource` không thêm giá trị) và qua cùng bước hậu kiểm. Similar không lọc theo điểm đến, nên sản phẩm lệch điểm đến của chuyến bị bỏ lặng lẽ, không sinh warning. Tên, giá, `productId` lấy nguyên từ response engine (§5). `compose` vẫn xếp theo luật cố định, không ưu tiên riêng kết quả similar cho ô đang đổi, nên món mới có thể đến từ search của lưới an toàn thay vì từ similar.

| `ITINERARY_DATA_MODE` | Cách lấy sản phẩm tương tự |
|---|---|
| `fixture` | Cùng taxonomy trong 50 sản phẩm mock, còn chỗ, bỏ chính nó và anh em cùng cha, cùng điểm đến xếp trước, tối đa `limit`; id lạ trả 404 `PRODUCT_NOT_FOUND` |
| `inprocess` | Use case `GetSimilarProducts` trên `app.state`, cùng use case với route; thêm `requestId` như route |
| `http` | `GET /products/{productId}/similar?limit=` (id được URL-encode), **không** gửi `Authorization` |

Similar không mang danh tính người dùng ở mọi mode: endpoint trả giống nhau cho mọi người dùng (`hop-dong-tich-hop-backend.md` §4.3).

### 2.6. Phạm vi search mặc định theo category

Phục vụ FR-AGT-02, FR-AGT-03.

`TOOL_PLAN_PROMPT` yêu cầu planner mặc định tìm hai category mọi chuyến đi dùng — `hotel` và `attraction` (tour/tham quan) — mỗi loại một lời gọi `search_products` cho điểm đến, thay vì chỉ tìm `hotel`; `golf` chỉ khi người dùng nhắc tới golf (`tool_planning.wants_golf`: câu chat lượt này, các lượt trước của người dùng, `interests`, `specific_activity`; "golf", "đánh gôn", "sân gôn"). Không ai nhắc thì `validated_plan` bỏ mọi search golf planner tự thêm (trace 2026-10-08: gia đình có bé ở TP.HCM). Planner chỉ bỏ hotel/attraction khi người dùng chủ động yêu cầu loại trừ (`constraints.exclude_taxonomies`).

Server không chỉ dựa vào prompt: `validated_plan` có lưới an toàn tất định chạy sau lưới an toàn Similar (§2.5) — với mỗi category trong `{hotel, attraction}` (thêm `golf` khi người dùng nhắc tới) không nằm trong `exclude_taxonomies` mà plan chưa có `search_products` cùng loại (hoặc một `search_products` không lọc `taxonomy`, vì search không lọc loại đã trả kết quả hỗn hợp mọi loại), server thêm `search_products(taxonomy=<loại đó>)` tất định cho điểm đến đã chuẩn hóa (query là danh từ loại kèm gợi ý). Best-effort như mọi lưới an toàn khác: hết trần 5 lời gọi mỗi lượt (§2.5) thì bỏ qua phần category còn thiếu, không huỷ lượt và không lỗi. Không có điểm đến chuẩn hóa (`intent.destination` trống) thì bỏ qua lưới này.

### 2.7. Vé máy bay trong lịch trình

Phục vụ FR-AGT-02, FR-AGT-03, AC-AGT-02, AC-AGT-03 (chốt 2026-10-06, đề xuất `docs/prd/update-archive/2026-10-06-ve-may-bay-trong-lich-trinh-va-vi-tri.md`).

- **Nơi đi.** `TripIntent.origin` (contract 1.18.0, tuỳ chọn). `extract` trích từ câu ("từ Hà Nội", "bay từ Đà Nẵng"); thiếu thì hỏi cùng câu hỏi gộp ngày đi/số người/ngân sách và là ô `origin` của form gợi ý. Không bắt buộc, như ngân sách. "Đã có vé", "đi ô tô" đưa `flight` vào `exclude_taxonomies`; hỏi rõ vé máy bay đặt `constraints.require_flight`.
- **Tra cứu tất định, không qua planner.** Node `tool` chạy `application/itinerary/flights.flight_options` song song với các lời gọi của planner, qua `CatalogPort.list_products` (GET /products): tuyến về điểm đến có `originCity` là nơi đi, tuyến về nơi đi có `originCity` là điểm đến, rồi chuyến của từng tuyến (`parentProductId`, gồm vé khứ hồi dưới tuyến chiều đi). Nơi đi được đưa về tên catalog (alias "Sài Gòn" → "TP. Hồ Chí Minh", rồi `originCity` của tuyến) và ghi lại vào `intent.origin`. Kết quả ở `state.flight_options`, không vào `tool_results`/`candidates`: chặng về đến nơi đi chứ không phải điểm đến, và bay ngày cuối chứ không phải ngày khởi hành. Tra lỗi chỉ mất chặng bay (`FLIGHT_UNAVAILABLE`), không mất lượt.
- **Chọn vé** (`domain/itinerary/flights.choose_flights`, luật trong AC-AGT-02): đi ngày `startDate`, về ngày `startDate + days − 1`; vé khứ hồi khớp cả hai ngày trước, không có thì ghép hai chặng một chiều; bay thẳng trước, rồi giá thấp, rồi đi sớm/về muộn; bỏ chuyến hết chỗ hoặc không có giá. Không tra khi chưa có nơi đi, đã loại trừ, nơi đi trùng điểm đến hoặc chuyến 1 ngày (trừ `require_flight`).
- **Response.** `itinerary.flights[]` (`ItineraryFlight`: `product`, `direction` OUTBOUND/RETURN/ROUND_TRIP, `date`, `returnDate`, `passengers`, `source`). `estimatedTotal` cộng `unitPrice × passengers` mỗi vé; vé không bị bỏ vì vượt ngân sách. Lý do không có (đủ) vé ở `warnings`: `FLIGHT_NO_ORIGIN`, `FLIGHT_NO_ROUTE`, `FLIGHT_NO_FLIGHT_ON_DATES`, `FLIGHT_ONE_WAY_ONLY`, `FLIGHT_UNAVAILABLE`; loại trừ, chuyến trong ngày và nơi đi trùng điểm đến không cảnh báo. Lời diễn giải có mục **Vé máy bay** do hệ thống viết từ `flights` và các warning đó; LLM không nói về vé.
- **Grounding.** `validate_plan` kiểm mỗi vé đúng bằng `summary` của chuyến đã tra trong lượt (`flight_candidates`), có giá và còn bán. `summary` giữ thêm các khoá thẻ vé (`airline`, `flightNumber`, `departureAt`/`arrivalAt`, `departureTimeLocal`/`arrivalTimeLocal`, `nonstop`, `tripType`, `returnDate`, `returnFlight`, sân bay, thành phố đi/đến).
- **Xếp lịch theo giờ bay** (AC-AGT-02, chốt 2026-10-07, đề xuất `docs/prd/update-archive/2026-10-07-xep-lich-theo-gio-bay.md`).
  - Vé được chọn trước khi xếp lịch.
  - Ngày đến chỉ có hoạt động ở buổi bắt đầu từ 90 phút sau giờ hạ cánh. Ngày về chỉ có hoạt động ở buổi kết thúc trước
    giờ cất cánh ít nhất 150 phút.
  - Hai ngày này có slot `activityType: TRANSFER`, `product: null` ở buổi hạ cánh/cất cánh.
  - Giờ đọc từ `arrivalAt`/`arrivalTimeLocal` của chặng đi và `departureAt`/`departureTimeLocal` của chặng về (vé khứ
    hồi: `returnFlight.departureAt`).
  - Khung buổi và luật chi tiết: `docs/spec/agent/nghiep-vu/xep-lich.md`. Contract không đổi.
- **Lịch trình ít di chuyển** (AC-AGT-04, chốt 2026-10-07, đề xuất `docs/prd/update-archive/2026-10-07-lich-trinh-it-di-chuyen.md`).
  - Agent cần `attributes.latitude`/`longitude` trong kết quả Search/Recommendation của khách sạn, điểm tham quan và golf
    (đã có). Toạ độ tâm thành phố bị coi là chưa rõ vị trí; Team Data nên đánh dấu độ chính xác ở nguồn.
  - Luật chi tiết: `docs/spec/agent/nghiep-vu/xep-lich.md` mục "Tối ưu quãng đường". Warning mới `PLAN_CRITERIA`
    (`code` là chuỗi tự do).
  - **Nhiều khách sạn** (chốt 2026-10-07, đề xuất `update-archive/2026-10-07-toi-uu-quang-duong-nhieu-khach-san.md`,
    contract 1.19.0): `itinerary.stays[]` (1–2 `ItineraryStay`, theo `fromNight`) liệt kê khách sạn theo đêm; đổi khách
    sạn chỉ với chuyến từ 5 ngày, một lần, mỗi khách sạn ≥ 2 đêm. `itinerary.stay` = `stays[0]` cho client cũ. Ngày đổi
    có slot `TRANSFER` "Trả phòng, chuyển sang khách sạn mới."
  - **Ngân sách và phương án khác** (chốt 2026-10-08, đề xuất
    `update-archive/2026-10-08-khach-san-theo-ngan-sach-va-phuong-an-khac.md`): có ngân sách thì chỉ chọn lịch vừa ngân
    sách (gồm vé), không lịch nào vừa thì lịch rẻ nhất. Warning mới `STAY_OPTIONS`: mục "Phương án khác" trong
    `message` (tổng km của lịch, tối đa 3 dòng "thêm/bớt X ₫ → bớt/thêm Y km", vượt ngân sách bao nhiêu). Người dùng
    chọn bằng "lấy phương án N".
  - **Hàng thẻ chọn phương án** (contract 1.20.0, chốt 2026-10-08, đề xuất
    `update-archive/2026-10-08-chon-phuong-an-bang-nut.md`): `ItineraryCompleted.stayOptions = {distanceKm, options[]}`;
    mỗi option có `index`, `kmDelta`, `moneyDelta`, `overBudget` và `itinerary` (lịch đầy đủ, để client xem trước không
    gọi server). Vắng mặt khi không có phương án. Khi có `stayOptions`, `message` không còn mục chữ "Phương án khác"
    (warning `STAY_OPTIONS` vẫn giữ cho client cũ). Request `selectStayOption: {index}` (cần `conversationId`, không cần
    `message`) đổi sang phương án đó qua node `apply_option`: không tìm lại, không gọi LLM, response `COMPLETED` với lịch
    đã báo và `stayOptions` mới (lịch vừa bỏ thành một phương án), **không có `message`** và không thêm lượt hội thoại;
    archive cập nhật câu trả lời gần nhất (`update_last_turn`) thay vì thêm tin nhắn (chốt 2026-10-08, đề xuất
    `update-archive/2026-10-08-bam-the-doi-ngay.md`). Câu gõ "lấy phương án N" đi cùng node nhưng có lời đáp ngắn do code
    dựng và thêm lượt như thường. `finalize` kiểm cả lịch của từng phương án (`option_grounding`).
- **Vị trí trình duyệt** chỉ ở Web (spec Frontend §4.8): toạ độ không vào request, state hay log của agent.

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

`destination` và `days` là dữ liệu nghiệp vụ bắt buộc để bắt đầu retrieval và lập kế hoạch, nhưng không bắt buộc có sẵn trong request đầu tiên. Khi thiếu một hoặc cả hai, Agent trả `NEEDS_CLARIFICATION`, lưu phần intent đã biết cùng lịch sử chat gần đây theo `conversationId` và không gọi Search, Recommendation hoặc Catalog. Khi đã đủ điểm đến và số ngày, Agent hỏi **gộp một câu, một lần** những gì còn thiếu trong ngày đi (`startDate`), số người (`party`) và ngân sách (`budget`): trả `NEEDS_CLARIFICATION` với `missingFields` là tập con của `["startDate", "party", "budget"]` và chưa gọi tool (AC-AGT-01). Câu hỏi gộp bằng câu chữ chỉ hỏi một lần mỗi hội thoại. Từ lượt sau, còn thiếu `startDate` hoặc `party` (người dùng trả lời một phần, nói chưa chốt hay "không biết") thì Agent trả `NEEDS_CLARIFICATION` kèm `clarificationForm` ở mỗi lượt cho tới khi đủ, không gọi tool; `budget` không bắt buộc, thiếu thì lập lịch với `budget = null`. "Chưa chốt ngày" không miễn ngày đi. Agent không tự điền `startDate` khi người dùng không nói ngày. Ngày không nêu năm dùng năm hiện tại theo giờ Việt Nam: nếu LLM trích ra năm cũ hơn (ví dụ `2023-09-20` cho "20/9") thì backend sửa về năm nay (`2026-09-20`); ngày không bị từ chối dù đã qua. Yêu cầu chỉ gồm `intentOverride` (chip sửa tay) không bị hỏi thêm. Trước bước này, `classify` phân luồng lượt chat: đặt chỗ, thanh toán, chèn lệnh hoặc đòi secret là ngoài phạm vi và bị từ chối (400 `VALIDATION_ERROR`) mà không trích intent. Trước cả LLM của `classify`, luật tất định lọc tin nhắn rác (NFR-SEC-04): gõ bậy, ký tự lặp, toàn ký hiệu trả `NEEDS_CLARIFICATION` 200 với câu cố định "Mình chưa hiểu ý bạn"; tục tĩu không kèm yêu cầu hợp lệ bị từ chối như chèn lệnh; cả hai không gọi LLM. Mỗi người gửi (user đăng nhập theo `cdp_user_id`, khách theo IP) gửi tối đa 10 tin/60 giây, vượt ngưỡng trả 429 `TOO_MANY_ATTEMPTS` kèm `Retry-After` (chi tiết: `docs/spec/agent/langgraph-nodes.md` mục "Guardrail tầng 1"). MVP không tự phát hiện ngôn ngữ để tránh kết quả không ổn định; thứ tự ưu tiên là `context.language` tường minh, ngôn ngữ đã lưu của conversation, rồi `vi`.

#### API stream cho UI demo

```http
POST /api/v1/assistant/itineraries/stream
Accept: text/event-stream
```

Request giống `POST /assistant/itineraries`. Stream phát lần lượt `run.started`, `graph.topology`, các `node.completed`, rồi `run.completed` hoặc `run.failed`. Event chỉ chứa ID node, thứ tự, trạng thái, thời lượng và response công khai; không chứa raw graph state, prompt, token hoặc credential. Vì HTTP status đã được gửi khi mở SSE, lỗi phát sinh sau đó nằm trong payload `run.failed.httpStatus`.

`GET /api/v1/assistant/status` trả readiness, graph version, data mode (`fixture` | `inprocess` | `http` | `disabled`) và số sản phẩm nếu adapter biết (`fixture`: 50; `inprocess`: số search unit trong index RecSys đang phục vụ, `null` khi RecSys chưa nạp). `fixture` chỉ được bật mặc định ở development/test; ngoài development/test mặc định là `disabled`, nên staging/production phải đặt `ITINERARY_DATA_MODE` tường minh (`inprocess` khi chạy dữ liệu thật).

#### API lịch sử hội thoại

- `GET /api/v1/assistant/conversations?page=1&pageSize=20`: danh sách hội thoại mới nhất trước.
- `GET /api/v1/assistant/conversations/{conversationId}`: transcript đầy đủ và response có cấu trúc đã lưu.
- Hai endpoint bắt buộc JWT hợp lệ, luôn lọc theo `cdp_user_id`; hội thoại không thuộc user hiện tại trả `404 CONVERSATION_NOT_FOUND`.

### 4.2. Response hoàn chỉnh

Payload MVP chỉ bắt buộc `status`, `conversationId`, `itinerary` và `warnings`. Các trường `intent`, `message`, `searchResults` và `metadata` là tùy chọn.

`message` là lời diễn giải lịch trình hiển thị trong khung chat, do node `narrate` viết (LLM; dự phòng bằng luật). Dạng: dòng đầu `**Tiêu đề**`, khi lượt này đổi thông tin chuyến đi thì câu ngay sau đó ghi nhận thay đổi ("Mình ghi nhận đổi ngày đi thành 15/10/2026. Lịch trình mình gợi ý như sau:"; backend tự chèn nên luôn đúng), rồi các mục in đậm: nơi nghỉ, từng ngày, chi phí dự kiến, lưu ý. Quy tắc grounding: sản phẩm chỉ được nhắc bằng link `[Tên](product:<productId>)` với `productId` có trong `itinerary` (backend thay nhãn bằng tên canonical và chặn id lạ); mọi số tiền đến từ dữ liệu sản phẩm (`unitPrice`, `priceUnit`) hoặc `estimatedTotal` qua placeholder, LLM không được tự viết số tiền; cách ghi giá khi không có giá xem đoạn dưới. `itinerary.title` bằng tiêu đề này.

Điểm tham quan hoặc golf không có giá (hoặc `ticketed=false`) được diễn giải là "tham quan tự do" (người dùng chốt ngày
01/10/2026) và tính 0 đ vào `estimatedTotal`, kèm warning `FREE_ENTRY_ASSUMED` (`docs/prd/architecture.md` §3, đề xuất
`docs/prd/update-archive/2026-10-01-diem-tham-quan-tu-do-tinh-0-vao-tong.md`). Khách sạn không có giá vẫn ghi "giá đang
cập nhật" và làm tổng tiền thành `null`.
Gói hoặc tour nhiều ngày không xếp vào slot. Chúng được trả trong `searchResults` của `COMPLETED` (tối đa 2 gói mỗi
loại, đối chiếu grounding như `FALLBACK`), và `message` có mục cố định "Gói nhiều ngày để bạn cân nhắc riêng" hỏi
người dùng có muốn thêm không. Bấm link của gói thì mở trang chi tiết sản phẩm.

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

Nếu `estimatedTotal=null`, `budgetStatus` bắt buộc là `UNKNOWN` và cần warning. Backend tính tổng khi đủ căn cứ; LLM không tính hoặc sửa giá. Điểm tham quan tự do tính 0 đ, không phải "thiếu căn cứ".

Từ 1.23.0 (chốt 2026-10-09, `docs/prd/update-archive/2026-10-09-khach-san-theo-so-phong-cho-doan-dong.md`): mỗi `itinerary.stays[]` có `rooms` (1–9) = `ceil(người lớn / attributes.priceAdults)` của khách sạn đó, trẻ em ở cùng phòng; tiền khách sạn trong `estimatedTotal` và `costBreakdown.stays` = giá × `nights` × `rooms`. Khách sạn cần quá 9 phòng không được chọn; khách sạn thiếu `priceAdults` tính 1 phòng và có warning `STAY_ROOMS_UNKNOWN` (kèm `productId`). `validate_plan` tính lại `rooms` từ candidate, không tin giá trị trong plan. Search `hotel` gửi `travelContext.guests` là số khách **một phòng** (`ceil(tổng / 9)`), không phải cả đoàn.

Từ 1.21.0 (chốt 2026-10-09, `docs/prd/update-archive/2026-10-09-ngan-sach-du-tinh.md`): khi `estimatedTotal` khác `null`, `itinerary.costBreakdown = {flights, stays, activities}` chia tổng theo vé máy bay, khách sạn và hoạt động (tự do 0 đ), cộng lại đúng bằng `estimatedTotal`; vắng khi tổng chưa biết. Backend tính cùng chỗ với tổng (`planning.price_plan`) và `validate_plan` kiểm cả phần chia. Không có khoản ước tính ngoài sản phẩm.

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

**Form cho tới khi đủ trường bắt buộc (đề xuất `docs/prd/update-archive/2026-10-05-classify-route-clarify.md`, đã áp dụng).**
Tool chỉ chạy khi đủ `destination`, `days`, `startDate`, `party`; `budget` không bắt buộc. Ngày đi/số người/ngân sách được
hỏi gộp một lần bằng câu chữ; từ lượt sau, còn thiếu `startDate` hoặc `party` (kể cả khi người dùng trả lời một phần) thì
response là `NEEDS_CLARIFICATION`, `clarification_reason = "suggest_form"`, kèm `clarificationForm`, ở mỗi lượt cho tới khi đủ.

**Hai lượt hỏi rồi chuyển sang form gợi ý (AGENTS.md §8, đề xuất `docs/prd/update-archive/2026-09-29-form-goi-y-thong-tin-chuyen-di.md`, đã áp dụng).**
Backend đếm `clarification_rounds` theo hội thoại (0, 1, 2…), chỉ tăng khi `missingFields` còn `destination` hoặc `days`:

- Vòng 1 (`clarification_rounds` từ 0 lên 1): hỏi bằng câu chữ như trên, `clarification_reason` = `null`.
- Vòng ≥ 2 mà vẫn thiếu `destination`/`days`: `clarification_reason = "suggest_form"`, câu `question` mời tinh chỉnh (không hỏi lại y hệt),
  và response có thêm field tuỳ chọn `clarificationForm`:

  ```json
  {
    "status": "NEEDS_CLARIFICATION",
    "conversationId": "conv-01JXYZ",
    "question": "Mình đã điền sẵn một vài gợi ý cho chuyến đi bên dưới. Bạn chỉnh lại theo nhu cầu rồi bấm xác nhận giúp mình nhé.",
    "missingFields": ["days"],
    "clarificationForm": {
      "fields": ["destination", "days", "startDate", "party", "budget"],
      "defaults": {
        "destination": "Hà Nội", "startDate": "2026-09-29", "days": 1,
        "party": {"type": null, "adults": 2, "children": 0}, "budget": null,
        "interests": [], "pace": null
      },
      "startDateMin": "2026-09-29"
    }
  }
  ```

  `clarificationForm.fields` liệt kê mọi trường bắt buộc của chuyến đi (không chỉ trường còn thiếu), để người dùng sửa lại cả
  những gì đã nói nếu muốn. `defaults` ưu tiên giá trị người dùng đã cung cấp; trường còn lại dùng gợi ý: `days` = 1,
  `startDate` = hôm nay theo giờ Việt Nam (không được sớm hơn `startDateMin`), `party` = 2 người lớn, `budget` = `null`
  (không giới hạn), `destination` = điểm đến đầu tiên trong `supported_destinations` nếu hội thoại đã từng gọi tool.
  Frontend tự nạp danh sách điểm đến cho ô chọn (`GET /destinations`, chỉ hiện vài điểm đến tiêu biểu, không đổ hết catalog)
  và chặn tại chỗ: số ngày trong 1–7, `startDate ≥ startDateMin`. Bấm xác nhận dựng một câu yêu cầu hoàn chỉnh và **gửi
  ngay** như một lượt chat bình thường (không dùng `intentOverride`). `suggestedValues` giữ nguyên hành vi cũ, không đổi.

**Giá trị không hợp lệ thì hỏi lại (đề xuất `docs/prd/update-archive/2026-09-30-bao-loi-dau-vao-khong-hop-le.md`, đã áp dụng; thay `2026-09-30-hoi-lai-khi-ngay-di-da-qua.md`).**
Không hợp lệ gồm: `startDate` sớm hơn hôm nay theo giờ Việt Nam, `days` ngoài 1–7, `party.adults` < 1 hoặc `party.children` < 0,
`budget` < 0 (giới hạn số lấy từ contract), và điểm đến không có trong catalog. Đây **không phải lỗi**: agent trả
`NEEDS_CLARIFICATION` (HTTP 200) với `clarification_reason = "invalid_input"`, trường sai bị xoá khỏi `knownIntent` và có trong
`missingFields`, các trường hợp lệ khác được giữ. Nguồn giá trị gồm câu chat, chip `intentOverride` và intent đã lưu từ lượt
trước. Ngày đi quá xa (ngoài cửa sổ mở bán) không thuộc nhóm này: vẫn đi tới `NO_RESULTS` kèm gợi ý ngày gần nhất (§4.4).

- **Không gọi thêm tool để kiểm hợp lệ.** Ngày, số ngày, số người, ngân sách kiểm ngay ở `extract` (không gọi Search).
  Điểm đến kiểm ở node `tool` bằng danh sách điểm đến catalog (`list_destinations`, chưa gọi Search), rồi `evaluate` bỏ qua và
  `route_after_evaluate` đi thẳng `clarify`.
- **Dạng câu trả lời:** `question` có dòng đầu `**<tiêu đề>**` (in đậm) nêu cái gì sai, các dòng sau nêu lý do và một gợi ý cụ thể
  rồi mời người dùng trả lời. Nhiều trường sai cùng lúc thì một tiêu đề chung, mỗi trường một dòng.
- **LLM viết câu** (node `clarify`; `ConversationalAnswer.title` là tiêu đề, `message` là phần thân). Backend đưa sẵn
  `invalid_inputs` (ngày dạng dd/mm/yyyy), `today`, `valid_ranges` (từ contract), `supported_destinations`, `form_shown` để LLM
  chỉ chép lại, không tự nghĩ ra ngày hay điểm đến. Không có `title` thì backend dùng tiêu đề cố định ("Ngày khởi hành không
  hợp lệ", "Số ngày không hợp lệ", "Số người không hợp lệ", "Ngân sách không hợp lệ", "Điểm đến chưa được hỗ trợ"; nhiều trường:
  "Thông tin chuyến đi chưa hợp lệ"). LLM lỗi hoặc quá thời gian thì cả câu là câu cố định vi/en cùng dạng.
- **Gợi ý theo trường:** ngày đi → "chọn từ hôm nay (dd/mm/yyyy) trở đi"; điểm đến → danh sách điểm đến hỗ trợ (kèm
  `suggestedValues.destination`); số ngày → khoảng 1–7 (kèm `suggestedValues.days`); số người/ngân sách → giá trị tối thiểu hợp lệ.
- **Còn thiếu điểm đến/số ngày:** câu vẫn nêu giá trị sai (ví dụ "di ngay 28 thang9" khi hôm nay là 30/9); `clarification_rounds`
  vẫn tăng và từ vòng 2 vẫn kèm `clarificationForm` (điền sẵn hôm nay, không dùng ngày đã qua).
- Số người lớn rất lớn hay ngân sách rất cao vẫn hợp lệ theo contract và vẫn lập lịch.
- Ngày năm cũ LLM trích (ví dụ "20/9" thành 2023-09-20) vẫn sửa về năm nay trước khi kiểm, nên "20/9" nói vào ngày 30/9 là ngày
  đã qua và bị hỏi lại, không tự đẩy sang năm sau.

**Dòng tiêu đề in đậm cho mọi câu trả lời (đề xuất `docs/prd/update-archive/2026-09-30-tieu-de-cho-moi-cau-tra-loi.md`, đã áp dụng).**
Dòng đầu của câu trợ lý nói với người dùng là `**Tiêu đề**` (khoảng 3–8 từ, không dấu chấm cuối, cùng ngôn ngữ với câu) **tóm tắt cả
câu**, các dòng sau là phần chi tiết. Không có field mới: tiêu đề nằm trong chuỗi `question`, `message` hoặc `error.message`.

| Trường hợp | Tiêu đề (vi) | Ai viết |
|---|---|---|
| Thiếu cả điểm đến và số ngày | Cần biết điểm đến và số ngày | LLM (dự phòng cố định) |
| Thiếu điểm đến | Bạn muốn đi đâu? | LLM (dự phòng cố định) |
| Thiếu số ngày | Chuyến đi kéo dài mấy ngày? | LLM (dự phòng cố định) |
| Hỏi gộp ngày đi, số người, ngân sách | Thêm vài chi tiết cho chuyến đi | LLM (dự phòng cố định) |
| Hỏi lại lần hai kèm `clarificationForm` | Điền nhanh thông tin chuyến đi | LLM (dự phòng cố định) |
| Thông tin mâu thuẫn | Thông tin chuyến đi chưa khớp nhau | LLM (dự phòng cố định) |
| Điều kiện bắt buộc không xác minh được | Chưa xác minh được yêu cầu của bạn | LLM (dự phòng cố định) |
| Điều kiện bắt buộc không có sản phẩm nào | Theo lý do (ví dụ "Khách sạn ở Hà Nội chưa mở bán cho ngày đi"); dự phòng: Chưa có sản phẩm đáp ứng yêu cầu bắt buộc | Cố định, có tham số |
| Giá trị không hợp lệ | theo trường (ở trên) | LLM (dự phòng cố định) |
| Muốn đổi mà chưa nói đổi thành gì ("đổi ngày", "đổi địa điểm") | Bạn muốn đổi thành gì? (LLM đặt tiêu đề theo trường đang hỏi) | LLM (dự phòng cố định) |
| Nói loại nơi thay vì tên điểm đến ("đi biển", "biển Hà Nội") | Chọn điểm đến hợp ý bạn (LLM đặt tiêu đề theo loại, ví dụ "Chọn điểm đến có biển") | LLM (dự phòng cố định) |
| Ngoài phạm vi (`error.message`, 400) | Ngoài phạm vi hỗ trợ | LLM (dự phòng cố định) |
| Đầu vào bị guardrail chặn (chèn lệnh, đòi secret, tục tĩu thuần) (`error.message`, 400) | Mình chưa thể hỗ trợ yêu cầu này | Cố định |
| Tin nhắn rác: gõ bậy, ký tự lặp, toàn ký hiệu (`question`, 200) | Mình chưa hiểu ý bạn | Cố định |
| `NO_RESULTS` không khớp sản phẩm | Chưa tìm thấy sản phẩm phù hợp | Cố định |
| `NO_RESULTS` do ngày đi ngoài thời gian mở bán | Chưa có sản phẩm mở bán cho ngày này | Cố định |
| `FALLBACK` | Chưa dựng được lịch trình hoàn chỉnh | Cố định |
| Chào hỏi, cảm ơn | Không có tiêu đề | — |
| `COMPLETED` | Do LLM đặt theo chuyến đi (dự phòng: "Lịch trình {days} ngày ở {destination}"); nằm ở dòng đầu `message` và ở `itinerary.title` | LLM (dự phòng cố định) |
| Các lỗi hệ thống khác | Không áp dụng (khung lỗi riêng) | — |

- LLM trả `title` cùng `message`; backend ghép `**title**` + xuống dòng + `message`, trim dấu `*`/khoảng trắng thừa và cắt tối đa 80 ký tự.
  Không có `title` hoặc LLM lỗi thì dùng tiêu đề cố định của trường hợp đó (bảng trên).
- Backend cắt dòng tiêu đề khỏi tin nhắn trợ lý cũ khi đưa lịch sử lại cho LLM (`llm_context`), để mô hình không bắt chước hay trả
  lời tiêu đề; bản lưu và `final_answer` giữ nguyên tiêu đề.

**Giọng văn.** Mọi câu LLM viết ở `clarify` và `converse` ấm áp, 2–4 câu (từ chối và trò chuyện 1–3 câu): nói ngắn vì sao cần
thông tin, cho ví dụ cách trả lời khi cần, không nêu tên sản phẩm. `ConversationalAnswer.message` tối đa 1.000 ký tự. Câu của
`compose` (COMPLETED/NO_RESULTS/FALLBACK) không đổi; lời diễn giải của `COMPLETED` do `narrate` viết (xem §4.2), giọng ấm áp như một người lập kế hoạch du lịch, mỗi lựa chọn có lý do cụ thể.

**Lượt trò chuyện và khám phá (contract 1.24.0, FR-AGT-06, chốt 2026-10-10).** Trước khi người dùng đồng ý lập lịch, trợ lý
không hỏi thông tin chuyến và không gửi `clarificationForm`:

- Câu hỏi về một nơi ("Hà Nội có gì?", "khách sạn nào có hồ bơi?") trả `NEEDS_CLARIFICATION` có `searchResults`: tối đa 4 sản
  phẩm thật từ Search của lượt đó (hỏi chung thì 2 điểm tham quan và 2 khách sạn, hỏi riêng chỗ ở thì 4 khách sạn), mỗi thẻ
  một lý do đúng trên toàn bộ kết quả (nhiều đánh giá nhất, điểm cao nhất, giá thấp nhất, tham quan tự do). `question` nhắc từng
  sản phẩm bằng `[Tên](product:<productId>)`; client đặt thẻ ngay sau dòng đầu tiên nhắc nó. Số trong câu do backend điền.
  Lần đầu khám phá một điểm đến, câu cuối hỏi "Bạn có muốn mình lên lịch … không?".
- Lượt trò chuyện, khám phá và việc ngoài phạm vi có `suggestions` (tối đa 3 nút, khác mẫu câu, không lặp lượt trước, luôn có
  một nút đi tiếp). Việc ngoài phạm vi (đặt vé hộ, huỷ đơn, chuyện ngoài du lịch) là câu trả lời 200, không còn là lỗi 400; chỉ
  đầu vào bị guardrail chặn (chèn lệnh, đòi secret, chỉ có tục tĩu) mới trả `VALIDATION_ERROR` 400.
- Đồng ý lập lịch: câu xin lập lịch, nút lập lịch, sửa form/chip, "ok" sau lời mời, hoặc câu có thông tin chuyến ngoài điểm
  đến ("Hà Nội 3 ngày"). Sau đó đi luồng hỏi gộp và form như trên. Đổi sang nơi khác ngay sau lời mời ("Thôi, Hà Nội thì
  sao?") không phải đồng ý: trợ lý khám phá nơi mới.
- Form có ô `interests` (sở thích khách sạn, chọn nhiều, không bắt buộc) với lựa chọn trong `clarificationForm.interestOptions`;
  Web ghép lựa chọn vào câu xác nhận "ưu tiên khách sạn có …". Sở thích là ưu tiên khi tìm khách sạn, không loại khách sạn
  thiếu dữ liệu tiện ích.
- Nơi người dùng chê ("chán, Đà Nẵng đi rồi") không được gợi ý lại trong hội thoại, kể cả trong `suggestions`.
- Sau khi có lịch, "đổi khách sạn" chưa nói hướng thì trả `NEEDS_CLARIFICATION` liệt kê các phương án khách sạn đã tính, kèm
  `suggestions` "Lấy phương án N: …" (gửi lại câu này là đổi ngay như `selectStayOption`). "Đổi chuyến bay" thì liệt kê chuyến
  khác cùng ngày của từng chặng, mỗi chuyến một nút ("Về chuyến VJ167 lúc 21:45"); gửi nút đó, hoặc "chuyến về muộn hơn/sớm
  hơn/rẻ hơn", thì trả `COMPLETED` với chuyến đã chọn. Không còn chuyến nào khác trong ngày thì gợi ý đổi ngày.

### 4.4. Response không có kết quả

```json
{
  "status": "NO_RESULTS",
  "conversationId": "conv-01JXYZ",
  "message": "Hiện chưa có sản phẩm ở Hà Nội mở bán cho ngày 01/12/2026. Bạn có thể chọn một trong các gợi ý bên dưới.",
  "suggestions": ["Đi Hà Nội 3 ngày từ ngày 24/10/2026", "Đi Phú Quốc 3 ngày", "Đi Nha Trang 3 ngày"]
}
```

Agent không lấp kết quả rỗng bằng sản phẩm do LLM tự tạo, và không tự đổi ràng buộc hay điểm đến thay người dùng
(điều kiện bắt buộc chưa đáp ứng vẫn đi nhánh `NEEDS_CLARIFICATION`, xem §4.4.1). Để người dùng không gặp ngõ cụt, `message` và
`suggestions` do backend dựng tất định từ dữ liệu thật của lượt đó, không do LLM viết:

- `message` nêu ngày đi khi lý do phổ biến nhất khiến sản phẩm bị loại là ngày nằm ngoài cửa sổ mở bán
  (`PRODUCT_DROPPED_DATE`); các lý do khác dùng câu chung.
- `suggestions` tối đa 3 mục, mỗi mục là một câu yêu cầu **gửi được nguyên văn** làm lượt chat tiếp theo, theo thứ tự:
  1. ngày khởi hành gần `startDate` nhất mà có sản phẩm thật đang mở bán (không sớm hơn hôm nay, không muộn hơn
     `availableTo`), dạng `Đi <điểm đến> <n> ngày từ ngày dd/mm/yyyy`;
  2. gợi ý bỏ ràng buộc đang bật (khách sạn cụ thể, giá, số sao, hoạt động cụ thể, loại dịch vụ đã loại trừ);
  3. tối đa hai điểm đến khác trong catalog, nhiều sản phẩm nhất trước, dạng `Đi <điểm đến> <n> ngày`.
  Không có mục nào thì trả một câu gợi ý chung.
- Frontend hiện `suggestions` thành chip dưới bong bóng trả lời ở tin nhắn mới nhất; bấm chip gửi ngay câu đó.

#### 4.4.1. Vì sao không có sản phẩm (điều kiện bắt buộc, lịch trình thiếu chỗ ở)

Người dùng hỏi "không có hotel à", "sao không có khách sạn" thì lượt đó đi đường thường (`extract` đặt
`require_hotel`, `tool` tìm lại); câu trả lời phải nêu **lý do thật** chứ không phải câu chung. `evaluate` tóm tắt
lý do theo từng taxonomy không còn candidate (`drop_summary`, `retrieval.drop_summary`, cùng luật loại với
`collect`): số sản phẩm đúng điểm đến đã tìm thấy rồi bị loại, lý do phổ biến nhất, cửa sổ mở bán (khi loại vì
ngày), ngày khởi hành gần nhất còn bán; hoặc `count = 0` khi tìm riêng loại đó mà không ra gì.

- **Điều kiện bắt buộc không có sản phẩm** (`NEEDS_CLARIFICATION`): `question` là câu cố định có tham số theo lý do,
  không gọi LLM. Ví dụ ngày: "**Khách sạn ở Hà Nội chưa mở bán cho ngày đi** Mình tìm thấy 10 khách sạn ở Hà Nội,
  nhưng dữ liệu hiện chỉ nhận đặt trong khoảng 15/10/2026–16/10/2026, không khớp chuyến của bạn từ 02/10/2026 đến
  04/10/2026. Bạn muốn dời ngày khởi hành sang 15/10/2026, hay giữ ngày và lập lịch không kèm khách sạn?". Lý do khác:
  vượt giá tối đa, không đạt tiêu chí (sao/tiện ích), không có tên đã nêu, tạm ngừng bán, không có sản phẩm nào.
  Không biết lý do thì giữ câu chung "Chưa có sản phẩm đáp ứng yêu cầu bắt buộc". Field tuỳ chọn `suggestions`
  (OpenAPI 1.13.0, tối đa 3) cùng ngữ nghĩa với `NO_RESULTS`: ngày gần nhất `Đổi ngày khởi hành sang dd/mm/yyyy` (câu đổi rõ ràng: "Đi … từ ngày …" sau một chuyến đã có ngày bị LLM đọc thành mâu thuẫn),
  gợi ý nới đúng yêu cầu bị vướng, và với khách sạn `Đi <điểm đến> <n> ngày, không cần khách sạn`. Agent vẫn không
  tự nới điều kiện thay người dùng.
- **Lịch trình dựng được nhưng không có chỗ ở** (`COMPLETED`, chuyến ≥ 2 ngày, có tìm khách sạn): `warnings` có
  `NO_STAY_AVAILABLE` với `message` nêu lý do (cửa sổ mở bán và ngày gần nhất khi loại vì ngày). Lời diễn giải có mục
  "**Chưa có khách sạn**" do backend chèn trước mục chi phí; LLM được báo `no_stay_explained` để không tự nói lý do.
- Cảnh báo `PRODUCT_DROPPED_DATE` của từng sản phẩm ghi cửa sổ mở bán thật ("Chỉ mở bán từ 15/10/2026 đến
  16/10/2026, không khớp ngày khởi hành."); lý do loại khác giữ câu chung.
- Cảnh báo `PRODUCT_DROPPED_DUPLICATE` (node `filter`, AC-AGT-04, chốt 2026-10-08): một mục cho mỗi điểm tham quan bị bỏ
  vì trùng nơi với điểm khác, `productId` là mã bị bỏ, `message` "Bỏ "X" vì trùng với "Y"." (Y là tên mã được giữ). Trùng
  nhận ra bằng luật (cùng tên) hoặc LLM (chỉ thấy mã + tên, chỉ trả cặp mã có trong danh sách); giữ mã nào do luật
  (Search trước Recommendation, rẻ hơn, mã nhỏ hơn). Contract không đổi: `ItineraryWarning.code` là chuỗi tự do.

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

`message` của `FALLBACK` do backend dựng bằng luật (`composition.fallback_message`, không gọi LLM), tiêu đề cố định "Chưa dựng được lịch trình hoàn chỉnh", thân nêu **lý do thật** của lượt đó: tool nào lỗi (ví dụ "Phần gợi ý cá nhân hoá đang trả dữ liệu lỗi nên mình chưa dùng được", "Mình chưa tải được kết quả tìm điểm tham quan ở Đà Nẵng"), hoặc vì sao không xếp được lịch ("chỉ tìm thấy 2 combo, chưa có khách sạn hay điểm tham quan để xếp vào lịch"), rồi đếm những gì đã tìm được và mời xem thẻ. Web hiện mỗi sản phẩm trong `searchResults` thành một thẻ gọn dưới câu trả lời (PRD `user-flow.md` §4.2).

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
| 401 | `INVALID_TOKEN` hoặc `TOKEN_EXPIRED` | Có gửi JWT nhưng token không hợp lệ |
| 404 | `CONVERSATION_NOT_FOUND` | Không tìm thấy cuộc hội thoại |
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
12. `compose` ưu tiên sản phẩm nguồn Search (gồm cả Similar, cùng nhãn `SEARCH`) hơn Recommendation cho cùng một chỗ trong lịch trình (stay hoặc slot hoạt động): một sản phẩm Recommendation chỉ được chọn khi không còn ứng viên Search nào khả dụng cho chỗ đó, kể cả khi ứng viên Search đắt hơn. Khi lịch trình có ít nhất một mục nguồn `RECOMMENDATION`, response kèm warning `RECOMMENDATION_FALLBACK` để acknowledge rõ với người dùng đây là gợi ý, không phải kết quả tìm kiếm; `source`/`because` của từng mục (§4.2, `ItemSource`) vẫn là căn cứ cá nhân hóa hay phổ biến theo `strategy` của `get_recommendations` (§2.4).

---

## 6. Quy tắc hội thoại

- Mỗi conversation lưu trip intent đã chuẩn hóa gần nhất và lịch sử chat user/assistant gần đây.
- Lịch sử chat chỉ nhận role `user`/`assistant`, tối đa 20 message, 1.000 ký tự/message và 8.000 ký tự tổng; khi vượt giới hạn thì bỏ message cũ nhất trước.
- **Mọi** lượt gọi LLM (`classify`, `extract`, chọn tên điểm đến và lập tool plan ở `tool`, `converse`, `clarify`) nhận cùng ngữ cảnh hội thoại: lịch sử chat trong giới hạn trên, chuyến đi đã chốt (intent, ràng buộc), sản phẩm đã cho xem và câu hỏi gần nhất của trợ lý. Nhờ phần tóm tắt, thông tin của lượt cũ vẫn còn khi message cũ bị cắt. Ngữ cảnh là dữ liệu không tin cậy, không phải instruction, và message mới nhất vẫn có quyền cao hơn. Ngữ cảnh được diễn giải sẵn: chuyến đi đã chốt là một dòng tóm tắt, tin trợ lý cũ là ghi chú ngắn theo nghĩa ("gửi lịch trình Hà Nội 3 ngày: …") thay vì cả bài kèm giá; câu hỏi gần nhất giữ nguyên văn khi ngắn (`docs/spec/agent/langgraph-nodes.md`, mục "Ngữ cảnh cho LLM").
- Hội thoại lưu thêm giai đoạn trò chuyện/khám phá (FR-AGT-06): đã đồng ý lập lịch chưa, lời mời đang chờ, điểm đến đã mời,
  số lần "không biết" liên tiếp và nút gợi ý lượt trước (`docs/spec/agent/state-fields.md`). Hội thoại lưu trước 2026-10-10
  đã hỏi gộp hoặc đã có lịch thì coi như đã đồng ý.
- Tin nhắn mới chỉ cập nhật các trường người dùng thay đổi rõ ràng.
- “Đổi thành Đà Nẵng” chỉ thay `destination`.
- “Tăng ngân sách lên 20 triệu” chỉ thay `budget`.
- Thực hiện tìm kiếm lại khi điểm đến, ngày, ngân sách, số người hoặc sở thích thay đổi.
- Lượt `COMPLETED` lưu thêm `previous_selection` (`productId`, `name`, `taxonomy` của sản phẩm đã hiển thị). Lượt sau dùng danh sách này làm danh sách cho phép khi loại sản phẩm người dùng muốn đổi và khi chọn sản phẩm gốc cho Similar (§2.5).
- Không dùng trạng thái hội thoại làm nguồn chính thức cho giá và availability.
- Working memory trong Redis hết hạn sau 24 giờ; archive Postgres của user đăng nhập không tự xoá.
- Conversation thuộc về user đã xác thực (`cdp_user_id` của Bearer hợp lệ), không thuộc về access token: BFF làm mới token khoảng 9 phút một lần và hội thoại phải giữ nguyên qua lần làm mới. Khách không có Bearer dùng chung nhóm `anonymous`; Bearer không xác thực được thì cô lập theo hash của chính token đó.
- Production dùng Redis DB index riêng qua `ITINERARY_REDIS_URL`; dev/test được phép dùng memory trong process khi biến này trống.
- Mỗi lượt của user đăng nhập được ghi best-effort vào `app.conversations`/`app.conversation_messages`; lỗi archive không làm hỏng response. Redis miss có thể phục hồi working state gần nhất từ archive. Khách không được ghi archive.

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
| LLM trình bày lịch trình (`narrate`; quá hạn thì dùng bản dựng bằng luật) | 3 giây |
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

Mỗi lời gọi tool kết thúc trong hạn ghi một dòng `itinerary.tool requestId= name= outcome= code= retryable= durationMs=`, thay cho access log mà mode `http` từng có. Lời gọi quá hạn bị huỷ trước khi tới dòng đó, nên chỉ ghi WARNING `itinerary.tool.timeout requestId= name=`. Ở mode `inprocess`, engine chưa sẵn sàng ghi WARNING `itinerary.tool.unavailable ... reason=not_ready`; engine lỗi bất ngờ ghi cùng dòng đó với tên kiểu lỗi, kèm các frame traceback (file, dòng, mã nguồn) để lần ra bug. Embedding (Cohere) lỗi thì tool trả `SEARCH_UNAVAILABLE` 503 trong vài giây, không chờ tới `TOOL_TIMEOUT`; `error` trong `tool_results` có thêm `reason: embed:<lý do>` (`quota_exhausted` — không retryable, `rate_limited`, `upstream_5xx`, `timeout`, `http_error`), nên lý do hiện ngay ở output node `tool` trên trace. Khoá `reason` chỉ dùng nội bộ, không đi ra API của trợ lý; nơi raise không biết lý do thì bỏ trống khoá này. Các dòng này không ghi tham số tool, thông điệp lỗi hay token.

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
