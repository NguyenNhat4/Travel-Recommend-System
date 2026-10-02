# Review field của Itinerary Agent: giữ, bỏ, gộp

Phục vụ FR-AGT-01..05 và NFR-PERF-02 (thời gian phản hồi trợ lý) trong `docs/prd/requirements.md`.
**Đã chốt 2026-09-28** (người dùng chọn áp dụng toàn bộ đề xuất trong tài liệu này) và đã sửa code theo
cột "Quyết định" bên dưới — xem `history/2026-09-28-ap-dung-de-xuat-field-review-agent.md`. Hai điểm có
bằng chứng sai lúc viết review, đã sửa lại khi áp dụng: `final_answer` thực ra có bị đọc (mục 3.1) và
khoá `attributes.beachfront` không tồn tại trong contract, đúng phải là `privateBeach` (mục 2.1).

Phạm vi: request/response của `POST /api/v1/assistant/itineraries` (và `/stream`), và 39 field của
`AgentState` (`src/backend/app/agents/state.py`). Bằng chứng lấy bằng grep ai ghi/đọc từng field trong
`src/backend/app` và `src/frontend/src` (code assistant) ngày 2026-09-24, không dựa trên tài liệu cũ.
Bảng tra theo field hiện hành: [state-fields.md](state-fields.md).

## 0. Ràng buộc khi quyết

- **`AgentState` là nội bộ.** PRD (`docs/prd/architecture.md` §3) không liệt kê field state, nên bỏ hoặc
  gộp field state không lệch PRD, không cần đề xuất trong `docs/prd/update/`.
- **Field contract v1 không được xoá hay đổi tên** (AGENTS.md §3). Field contract thừa chỉ có hai lựa
  chọn: backend bắt đầu trả, hoặc giữ optional và FE thôi đọc.
- Field optional trong contract (ví dụ `ProductSummary.description`, `attributes`) thì backend được thôi
  trả mà không sửa contract.

Ký hiệu đề xuất: **Giữ** · **Bỏ** · **Gộp** · **Trả** (backend hiện thực đúng contract) · **FE bỏ đọc**.

## 1. Request

| Field | Ai dùng | Đề xuất | Quyết định |
|---|---|---|---|
| `message` | → `state.query`, mọi prompt LLM | Giữ | Giữ |
| `conversationId` | → `state.conversation_id`, khoá store đa lượt | Giữ | Giữ |
| `intentOverride` | → `state.intent_override`, `classify` ghi đè intent (chip UI) | Giữ | Giữ |
| `context.language` | → `state.language`, prompt và câu cố định | Giữ | Giữ |

Header `Authorization` đi vào `planner(authorization)` cho `/recommendations`, không nằm trong state. Giữ.

## 2. Response

### 2.1. Sản phẩm trong lịch quá nặng

`ProductSummary` trong `itinerary.stay.product` và `slots[].product` được chép từ `SUMMARY_FIELDS`
(`src/backend/app/domain/itinerary/planning.py`), gồm cả `description` và toàn bộ `attributes`.

Kích thước trung bình trong catalog (`cdp.products`, search unit):

| Loại | `description` | `attributes` |
|---|---|---|
| hotel_property | 3.680 ký tự | 2.923 ký tự |
| golf | 666 | 3.163 |
| attraction | 538 | 1.758 |

Một lịch 3 ngày (1 khách sạn, tối đa 6 hoạt động) nặng khoảng 20–40KB, phần lớn là hai field này.

FE (code assistant) chỉ đọc:

- `attributes.beachfront` (sai tên, xem quyết định bên dưới — đúng phải là `attributes.privateBeach`),
  `attributes.oceanView`, `attributes.pool`, `attributes.ticketed`.
- `description` ở một chỗ: `AiFloatingWidget.tsx` dò chữ "biệt thự", "hồ bơi".

Backend (xếp lịch, lọc) đọc thêm `attributes.durationMinutes`, `parentProductId`, `starRating`, nhưng đọc
từ `candidates`/`details` trong state, **không** đọc từ response.

| Field của `ProductSummary` trong lịch | Đề xuất | Quyết định |
|---|---|---|
| `productId`, `name`, `taxonomy`, `destination`, `unitPrice`, `currency`, `priceUnit`, `available` | Giữ (bắt buộc trong contract) | Giữ |
| `availableFrom`, `availableTo`, `imageUrl`, `rating`, `reviewCount` | Giữ (nhỏ, FE hiển thị) | Giữ |
| `attributes` | Cắt còn các khoá FE đọc (`beachfront`, `oceanView`, `pool`, `ticketed`). Muốn FE hiện thời lượng hoặc số sao thì giữ thêm `durationMinutes`, `starRating` (FE hiện chưa đọc) | Cắt còn 4 khoá, **không** `beachfront` — khoá đó không tồn tại trong `ProductAttributes` (`src/shared/contracts/schemas/catalog.yaml`), đúng là `privateBeach`; FE đang đọc nhầm tên nên chưa từng hiển thị. Giữ `oceanView`, `privateBeach`, `pool`, `ticketed`; sửa luôn `AiFloatingWidget.tsx` và `types/travel.ts` dùng đúng `privateBeach`. Không thêm `durationMinutes`/`starRating` (FE chưa đọc) |
| `description` | Bỏ, hoặc cắt còn ~200 ký tự. Nếu bỏ thì `AiFloatingWidget` chuyển sang dùng cờ `attributes` | Bỏ hẳn. `AiFloatingWidget.tsx` (`getHotelVisuals`) bỏ nhánh dò `description`, giữ nhánh theo `name`/`attributes.pool` |

Cắt hai field này không ảnh hưởng grounding: `steps/validation.py` (bước `finalize`) và
`src/evaluation/agent/grounding.py` không đọc `attributes` hay `description`.

**Sửa ngày 2026-10-02.** Danh sách "FE chỉ đọc" ở trên thiếu: `productFromApi` (`src/frontend/src/services/catalog.ts`)
đọc `attributes.latitude`, `attributes.longitude` và `attributes.address` để đặt điểm trên bản đồ lịch trình. Vì bị cắt,
widget đặt mọi điểm ở tâm thành phố (hoặc Nha Trang). `SUMMARY_ATTRIBUTE_KEYS` nay giữ thêm ba khoá này, cùng `starRating`
cho tag khách sạn dựng từ thuộc tính thật (theo đúng điều kiện của quyết định trên: FE có đọc thì giữ). `description` vẫn bỏ.
Entry: `history/2026-10-02-anh-va-toa-do-that-cho-lich-trinh.md`.

### 2.2. Contract có, backend không bao giờ trả, FE vẫn đọc

| Field | FE đọc ở | Hệ quả hiện tại | Đề xuất | Quyết định |
|---|---|---|---|---|
| `suggestedValues` (NEEDS_CLARIFICATION) | `AiFloatingWidget.tsx`, `AssistantResultPanel.tsx` | FE rơi về giá trị cứng "Nha Trang"/3 ngày | Trả: điểm đến lấy từ `supported_destinations`, số ngày 1–7 | Trả, best-effort: `days` luôn có mặt (1–7) khi `days` nằm trong `missing_fields`; `destination` chỉ có khi `state.supported_destinations` đã được nạp (sau lượt đầu gọi `tool`) — lượt hỏi thiếu destination *đầu tiên* của hội thoại (trước khi từng gọi `tool`) vẫn chưa có mảng gợi ý, vì lấy danh sách catalog cần gọi tool bất đồng bộ mà `converse`/`clarify` chưa nối với `tools`. Không mở rộng thêm để giữ rủi ro thấp; ghi lại làm hạn chế đã biết |
| `clarificationForm` (NEEDS_CLARIFICATION, thêm 2026-09-29) | `WidgetChat.tsx`, `AssistantConversation.tsx` qua `TripDetailsForm.tsx` | Trước đó widget nổi không render gì ngoài `question` dạng text cho `NEEDS_CLARIFICATION` — hỏi lại vô hạn khi LLM không trích được `days`/`destination` | Field tuỳ chọn mới (`fields`, `defaults`, `startDateMin`); backend chỉ trả từ vòng hỏi thứ hai trở đi khi vẫn thiếu `destination`/`days` | Đã trả theo đề xuất `docs/prd/update-archive/2026-09-29-form-goi-y-thong-tin-chuyen-di.md` (đã áp dụng). FE hiện form đã điền sẵn; xác nhận đặt câu yêu cầu vào ô nhập, không tự gửi |
| `suggestions` (NO_RESULTS) | `AssistantResultPanel.tsx` | FE hiện câu mặc định | Trả hoặc FE bỏ đọc | Trả: `composition._no_results_suggestions` dựng tối đa 3 gợi ý tất định, câu cố định vi/en trong `messages.py`, theo thứ tự: (1) ngày gần nhất còn bán khi ngày đi nằm ngoài cửa sổ mở bán (`state.nearest_open_date`), (2) bỏ ràng buộc đang bật (`require_hotel`/`specific_hotel`, `hotel_price_max`, `star_rating_min`, `specific_activity`, `exclude_taxonomies`), (3) tối đa 2 điểm đến khác trong catalog, nhiều sản phẩm nhất trước; không có gì thì trả một câu gợi ý chung. Cập nhật 2026-09-29: FE hiện `suggestions` thành chip dưới bong bóng NO_RESULTS ở tin nhắn mới nhất (`SuggestionChips.tsx`), bấm là gửi ngay câu đó |
| `slotId` | `AssistantResultPanel.tsx` (làm React key, có fallback) | Không lỗi | Giữ optional, không làm gì | Giữ, không đổi |
| `startTime`, `endTime` | FE hiển thị nếu có | Luôn trống | Giữ optional; trả khi Data có giờ mở cửa (handbook §11 Tuần 4) | Giữ, không đổi — phụ thuộc dữ liệu Data chưa có |
| `itinerary.title`, `days[].title` | FE có fallback | Luôn trống | Giữ optional | Giữ, không đổi |
| `metadata` (`personalised`, `searchRequestIds`, `generatedAt`, `requestId`) | FE đọc `generatedAt` một chỗ | Không bao giờ có | Giữ optional; trả nếu FE cần hiện "cập nhật lúc" | Giữ, không đổi — chưa có yêu cầu hiển thị "cập nhật lúc" |

### 2.3. Backend trả, FE không dùng

| Field | Đề xuất | Quyết định |
|---|---|---|
| `intent.pace` | Giữ (contract). Backend không dùng `pace` để xếp lịch (`MAX_ACTIVITIES_PER_DAY` cố định) | Giữ, không đổi |
| `warnings[].productId` của `PRODUCT_DROPPED_*` | Giữ; FE hiện chưa đọc warnings từng sản phẩm. Cân nhắc gộp nhiều warning `PRODUCT_DROPPED_*` giống nhau thành một | Giữ, không đổi — việc gộp nhiều warning trùng chỉ là "cân nhắc" tuỳ chọn trong đề xuất gốc, chưa làm |

### 2.4. Giữ nguyên

`status`, `conversationId`, `intent`, `itinerary.stay` (`nights`, `note`, `source`, `because`),
`itinerary.days[].slots[]` (`time`, `activityType`, `note`, `source`, `because`), `bookableCount`,
`estimatedTotal`, `currency`, `budgetStatus`, `priceAsOf`, `warnings`, `question`, `missingFields`,
`knownIntent`, `message`, `searchResults` (FALLBACK). Đều có FE đọc hoặc là field bắt buộc của contract.
Quyết định: giữ nguyên, không đổi.

## 3. AgentState

### 3.1. Bỏ: không ai đọc

| Field | Bằng chứng | Đề xuất | Quyết định |
|---|---|---|---|
| `thread_id`, `scenario_id`, `messages` | Chỉ `initial_state()` của `Scenario` ghi; luồng API không dùng | Bỏ, cùng `Scenario`, `Route`, `initial_state` (chỉ còn `tests/unit/agents/test_lab_copy.py` dùng) | Đã bỏ, cùng `Scenario`/`Route`/`initial_state`; `test_lab_copy.py` sửa lại để không import các type này |
| `errors` | Khai báo append-only; không node nào ghi hay đọc. `state-fields.md` ghi `retry` ghi `TRANSIENT_TOOL_FAILURE` nhưng code không còn | Bỏ | Đã bỏ. Bằng chứng gốc sai một phần: `retry_or_fallback_node` **vẫn đang ghi** `errors: ["TRANSIENT_TOOL_FAILURE"]` lúc review (không phải "code không còn" như state-fields.md cũ ghi), nhưng xác nhận đúng là không node nào đọc lại — bỏ cả write lẫn field |
| `pending_question` | `converse`/`clarify` ghi, không ai đọc; nội dung trùng `response.question` | Bỏ | Đã bỏ |
| `final_answer` | `clarify`/`finalize` ghi, không ai đọc | Bỏ | **Giữ — bằng chứng sai.** `finalize_node_async` đọc `update['final_answer']` (biến cục bộ từ `finalize_node`) để ghi vào `archive.record_turn(...)["answer"]`, dùng cho lịch sử hội thoại Postgres của user đăng nhập; `test_itinerary_runtime.py:381` cũng assert giá trị này. Grep gốc chỉ tìm `state.get('final_answer')` nên bỏ sót cách đọc qua biến `update` cùng lời gọi |
| `llm_used` | `intake`/`classify`/`converse` ghi, không ai đọc | Bỏ, hoặc đưa vào `itinerary_metrics` ở route nếu muốn đo tỷ lệ dùng LLM | Đã bỏ (không đưa vào metrics) |

### 3.2. Gộp: vai trò chồng lấn

| Field | Vấn đề | Đề xuất | Quyết định |
|---|---|---|---|
| `route`, `decision`, `evaluation_result` | Ba cờ điều hướng: `route` sau `classify`, `evaluation_result` sau `evaluate`, `decision` ghi ở 5 node, đọc ở 9 chỗ | Gộp thành một cờ `decision`; sửa `routing.py` và test | Đã gộp. Mỗi điểm rẽ nhánh (`route_after_classify/extract/evaluate/retry`) chỉ đọc giá trị do đúng node liền trước vừa ghi nên gộp an toàn — miền giá trị theo từng chặng: sau `classify` là `travel`/`simple`/`error`; sau `extract` là `tool`/`missing_info`/`error`; sau `evaluate` là `compose`/`no_results`/`fallback`/`constraint_clarification`/`needs_retry`/`failed`; sau `retry` là `""`/`fallback`/`error`. `routing.py`, `nodes.py`, `steps/classification.py`, `steps/evaluation.py` và 4 file test đã sửa theo |
| `details`, `candidates` | `details` giữ ProductDetail đầy đủ của mọi sản phẩm tool trả, kể cả sản phẩm bị loại; `candidates` chép lại phần đạt. Trace LangSmith mang cả hai | Xoá `details` khỏi state sau khi `evaluate` dựng `candidates`, hoặc chỉ giữ id | Đã xoá hẳn: `evaluation.evaluate_retrieval` trả thêm `details: {}` sau khi `collect()` tiêu thụ xong, nên state/trace từ `evaluate` trở đi không còn payload ProductDetail nặng |
| `tool_results` | Giữ nguyên payload Search/Recommendation (có `description`, `attributes`) | Giữ cho retry; cân nhắc bỏ `data` sau `evaluate` để trace nhẹ | Giữ nguyên, không đổi — phần "cân nhắc bỏ data" là tuỳ chọn, chưa làm để giữ rủi ro thấp cho luồng retry |

### 3.3. Giữ: có node đọc thật

| Nhóm | Field |
|---|---|
| Đầu vào | `query`, `conversation_id`, `conversation_history`, `intent`, `intent_override`, `constraints`, `previous_selection`, `language`, `request_id` |
| Hỏi lại | `missing_fields`, `start_date_asked` (đã hỏi chi tiết chuyến đi), `clarification_reason`, `refusal`, `interaction_type` |
| Tool | `tool_plan`, `tool_results`, `supported_destinations`, `detail_errors`, `attempt`, `max_attempts` |
| Đầu ra | `candidates`, `sources`, `warnings`, `response`, `http_status`, `validation_issues` (route ghi vào metrics), `started_at`, `latency_ms` (route log) |
| Trace | `events` (SSE `node.completed`, runner golden) |

## 4. Khi đã quyết

- Bỏ/gộp field state: sửa `state.py`, `nodes.py`, `steps/*`, `routing.py`, test backend; cập nhật
  [state-fields.md](state-fields.md) và [langgraph-nodes.md](langgraph-nodes.md) §6.1.
- Cắt `ProductSummary`: sửa `SUMMARY_FIELDS`, `AiFloatingWidget.tsx` nếu bỏ `description`; chạy golden để
  chắc grounding vẫn 100%.
- Backend trả `suggestedValues`/`suggestions`: code theo schema hiện có, không cần sửa contract.
- Mỗi hạng mục một entry `history/`.
