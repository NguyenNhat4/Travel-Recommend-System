# Trường dữ liệu sản phẩm agent cần nắm rõ (grounding)

Dành cho ai sửa/tune Itinerary Agent (`src/backend/app/agents`) và cần biết chính xác field nào của một
sản phẩm là thật, field nào bắt buộc, field nào đang "treo" (contract có nhưng backend chưa trả). Tài liệu
này **không tạo quy tắc mới**, chỉ gom lại từ contract/DDL/PRD; lệch thì các nguồn đó thắng, không phải
file này (`AGENTS.md` §7).

Phục vụ FR-AGT-04 (grounding 100%), NFR-REL-01, FR-CAT-01..04 (`docs/prd/requirements.md`).

## 1. Nguyên tắc grounding — trước khi đọc field nào

`docs/prd/architecture.md` §3 và `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §5:

- LLM **không suy đoán dữ liệu sản phẩm**. Mọi `productId`, `name`, `unitPrice`, `imageUrl`... trong lịch
  trình phải được **chép nguyên trạng** từ kết quả tool (Search/Recommendation/Catalog), không phải do LLM
  viết ra hoặc tính lại.
- Backend tự tính `estimatedTotal`; thiếu giá thì tổng là `null` + `budgetStatus: UNKNOWN` + warning —
  **không** coi thiếu giá là 0.
- `available=true` chỉ là snapshot lúc crawl, **không xác nhận còn chỗ**. Không được diễn giải field thiếu
  thành `false`/`0`.
- Nguồn sự thật cho field và required/optional là `src/shared/contracts/schemas/catalog.yaml` (qua
  `openapi.yaml`) — ví dụ JSON trong các file `docs/spec/hop-dong-tich-hop-*.md` chỉ minh hoạ, có thể cũ hơn
  contract.

## 2. `ProductSummary` — thẻ sản phẩm agent nhận từ Search/Recommendation

Định nghĩa: `src/shared/contracts/schemas/catalog.yaml` (`ProductSummary`). Đây là field agent thấy trong
`tool_results`/`candidates` và chép vào `itinerary.stay.product`, `slots[].product`.

### 2.1. Bắt buộc (8 trường, luôn có)

| Trường | Ý nghĩa | Cạm bẫy |
|---|---|---|
| `productId` | Khoá duy nhất, ổn định | Mọi sản phẩm hiển thị có thể đặt được phải có `productId` thật tồn tại — đây là định nghĩa của grounding (FR-AGT-04) |
| `name` | Tên hiển thị | Chép nguyên văn, LLM không được sửa/rút gọn ra tên khác |
| `taxonomy` | `hotel · flight · attraction · combo · golf` | Enum lowercase; sản phẩm phải thuộc đúng điểm đến người dùng yêu cầu |
| `destination` | Nhãn du lịch đã chuẩn hoá ("Nha Trang") | **Không phải tên tỉnh**; lấy danh sách hợp lệ qua `GET /destinations`, không tự đoán |
| `unitPrice` | Giá snapshot VND cho **một đơn vị theo `priceUnit`** | `null` không nghĩa là miễn phí; không nhân ngày nếu `priceUnit` không phải `PER_NIGHT` |
| `currency` | Đơn vị tiền | MVP luôn VND |
| `priceUnit` | `PER_NIGHT · PER_PERSON · PER_PACKAGE` (suy từ taxonomy lúc ingest) | **Không có default** — thiếu thì phải coi là chưa biết, không tự giả định `PER_NIGHT` |
| `available` | Nguồn có trả giá lúc crawl | Đây là snapshot crawl, **không** phải còn chỗ theo ngày/số khách |

### 2.2. Ba trường availability — ba nghĩa khác nhau, đừng gộp

| Trường | Nghĩa | Khi nào có |
|---|---|---|
| `available` | Nguồn có giá lúc crawl (bắt buộc) | Luôn có |
| `availabilityStatus` | Enum kiểm theo `checkIn/checkOut/party` cụ thể | Mặc định `NOT_CHECKED` khi request không kèm ngày/số khách |
| `bookable` | Đặt được cho **một stay cụ thể** đã kiểm | `null` khi chưa kiểm; agent dùng để quyết định một mục là product card hay activity note (không giá, không nút) |

### 2.3. Tuỳ chọn hay dùng

| Trường | Ghi chú |
|---|---|
| `availableFrom`, `availableTo` | Khoảng ngày nguồn ghi nhận; `null` là chưa biết, không xác nhận tồn kho |
| `imageUrl` | `null` thì client dùng placeholder theo `taxonomy` |
| `rating` | Điểm đánh giá đã chuẩn hoá 0–5 — **khác** `attributes.starRating` (hạng sao). Cùng thang 0–5 nhưng khác nghĩa, đừng dùng chung icon |
| `reviewCount` | Số lượt đánh giá |
| `brand` | "Vinpearl", "independent"... |
| `status` | `ACTIVE`/`INACTIVE` (soft delete) — sản phẩm `INACTIVE` không xoá khỏi catalog vì `because[].productName` của recommendation cần giữ tên dù sản phẩm đã ngừng bán |
| `priceAsOf` | Thời điểm quan sát giá; không dùng `generatedAt` thay cho trường này |
| `attributes` | Xem mục 3 |
| `description` | Mô tả catalog cho agent đọc, giữ nguyên, không chứa chỉ dẫn hệ thống |

Field `description`/`attributes` là hai field **nặng nhất** khi chép vào response lịch trình (20–40KB/lịch
3 ngày, theo `docs/spec/agent/field-review.md` §2.1) — FE hiện chỉ đọc bốn khoá attributes
(`beachfront`, `oceanView`, `pool`, `ticketed`) và một chỗ đọc `description` thô. Cắt việc này **chưa có
quyết định**, xem field-review.md.

## 3. `ProductAttributes` — ba trạng thái, không phải hai

Từ `catalog.yaml` (`ProductAttributes`): key **có mặt và `true`** = nguồn xác nhận có; key **có mặt và
`false`** = nguồn xác nhận **không** có; **key vắng mặt** = không biết. Tầng serialization đã loại các key
`false` trước khi trả JSON, nên response agent nhận được chỉ còn `true` hoặc vắng mặt — **không được coi
key vắng mặt là `false`**, và không cần tự lọc `false` ở tầng agent (đã bị strip từ trước).

Hai khoá agent cần chú ý riêng vì ảnh hưởng cấu trúc lịch trình, không phải chỉ hiển thị:

- `attributes.level` (`property · room · route · flight`): phân tầng cha/con. `property`/`route` là tầng
  cha (`is_bookable=false`, có vector, ra kết quả `/search`); `room`/`flight` là tầng con (đặt chỗ thật).
  Thiếu trường này (attraction, combo, golf) mặc định là tầng cha.
- `attributes.parentProductId`: chỉ có ở tầng con, trỏ về `productId` của cha.
- `attributes.ticketed`: `false` thì ẩn CTA đặt chỗ ở frontend (điểm công cộng, không bán vé).

## 4. `ProductDetail` — khi agent phải hydrate thêm

`ProductDetail` = `ProductSummary` + bắt buộc thêm `description`, `attributes`, `availableFrom`,
`availableTo` (luôn có, không `null`). Agent gọi lấy `ProductDetail` theo `productId` khi `ProductSummary`
từ search thiếu dữ liệu cần để kiểm điều kiện hoặc lập lịch (ví dụ cần `attributes.durationMinutes`,
`starRating`, `parentProductId` để xếp lịch — các field này agent đọc từ `candidates`/`details` trong
`AgentState`, không đọc từ response trả cho client).

## 5. `ItineraryResponse` — field bắt buộc theo `status`

Nguồn: `src/shared/contracts/schemas/itinerary-agent.yaml`, tóm tắt theo
`docs/spec/mvp-minimal-fields-1.2.0.md`.

| `status` | Bắt buộc | Field hay bị hiểu nhầm |
|---|---|---|
| `COMPLETED` | `status`, `conversationId`, `itinerary`, `warnings` | `itinerary.estimatedTotal=null` **phải** kèm `budgetStatus: UNKNOWN` (constraint `allOf/if` trong schema) |
| `NEEDS_CLARIFICATION` | `status`, `conversationId`, `question` | `missingFields` là tập con `["destination","days","startDate","party","budget"]`; chưa gọi tool |
| `NO_RESULTS` | `status`, `conversationId`, `message` | Không lấp bằng sản phẩm LLM tự tạo |
| `FALLBACK` | `status`, `conversationId`, `message`, `searchResults` | Chỉ dùng khi Search **vẫn có** sản phẩm thật để hiển thị, không dùng khi Search lỗi (lỗi thật đi qua `ErrorResponse`, không phải `status`) |

Mỗi `ItinerarySlot`: `time`, `product`, `note` bắt buộc. `product=null` nghĩa là ActivityNote (không giá,
không nút) và khi đó `activityType` bắt buộc; `product` khác `null` thì `source` bắt buộc
(`SEARCH`/`RECOMMENDATION`) và `activityType` phải `null`.

### 5.1. Field contract có nhưng backend chưa từng trả (đừng dựa vào lúc code)

Theo `docs/spec/agent/field-review.md` §2.2, các field sau **hợp lệ theo schema** nhưng FE đọc mà backend
chưa bao giờ điền — luôn kiểm code hiện tại trước khi giả định đã có:

`suggestedValues` (NEEDS_CLARIFICATION), `suggestions` (NO_RESULTS), `startTime`/`endTime` của slot,
`itinerary.title`/`days[].title`, `metadata` (`personalised`, `searchRequestIds`, `generatedAt`,
`requestId`).

## 6. Nguồn gốc thật của field — DB `cdp.products`

Field API trên đều dựng từ **đúng 13 cột** của `cdp.products` (không hơn — thuộc tính khác biệt theo loại
nằm trong `attributes` JSONB): `product_id`, `name`, `taxonomy`, `destination`, `description`,
`attributes`, `unit_price`, `currency`, `available`, `available_from`, `available_to`, `image_url`,
`source_ref`. Chi tiết: `docs/spec/PRODUCT_SCHEMA.md` §3, DDL ở `docs/spec/DATABASE_SCHEMA.md`.

Các khái niệm agent hay cần (`variant`, `is_bookable`, `is_search_unit`, `is_recommendable`,
`parent_product_id`, toạ độ, `province`, `star_rating`, `review_score`) **không lưu trong bảng** — đều là
view `catalog.product_meta` suy ra từ 13 cột trên. Agent không đọc DB trực tiếp (đi qua Search/Recommendation
API theo `docs/prd/architecture.md` §2 quy tắc 7); mục này chỉ để hiểu field API từ đâu ra khi cần debug dữ
liệu lệch.

Combo là một dòng `cdp.products` bình thường (`taxonomy=combo`); thành phần nằm ở `catalog.combo_items`
(bảng riêng, không nằm trong `ProductSummary`) — agent muốn liệt kê "combo gồm những gì" phải gọi endpoint
trả `combo_items`, không tự bịa từ `description`.

## 7. Tham chiếu nhanh

| Muốn biết | Xem |
|---|---|
| Field nào bắt buộc/tuỳ chọn mới nhất | `src/shared/contracts/schemas/catalog.yaml`, `schemas/itinerary-agent.yaml` |
| Payload tối thiểu MVP | `docs/spec/mvp-minimal-fields-1.2.0.md` |
| Quy tắc grounding đầy đủ | `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §5, `docs/prd/architecture.md` §3 |
| Field nào `AgentState` đang giữ, node nào đọc | `docs/spec/agent/state-fields.md` |
| Field nào đang review để giữ/bỏ/gộp (chưa quyết) | `docs/spec/agent/field-review.md` |
| Field DB gốc | `docs/spec/PRODUCT_SCHEMA.md`, `docs/spec/DATABASE_SCHEMA.md` |
