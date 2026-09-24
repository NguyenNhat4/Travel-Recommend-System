# Review field của Itinerary Agent: giữ, bỏ, gộp

Phục vụ FR-AGT-01..05 và NFR-PERF-02 (thời gian phản hồi trợ lý) trong `docs/prd/requirements.md`.
Tài liệu review, **chưa có quyết định**: cột "Quyết định" để người review điền. Chưa sửa code nào theo
tài liệu này.

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
| `message` | → `state.query`, mọi prompt LLM | Giữ | |
| `conversationId` | → `state.conversation_id`, khoá store đa lượt | Giữ | |
| `intentOverride` | → `state.intent_override`, `classify` ghi đè intent (chip UI) | Giữ | |
| `context.language` | → `state.language`, prompt và câu cố định | Giữ | |

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

- `attributes.beachfront`, `attributes.oceanView`, `attributes.pool`, `attributes.ticketed`.
- `description` ở một chỗ: `AiFloatingWidget.tsx` dò chữ "biệt thự", "hồ bơi".

Backend (xếp lịch, lọc) đọc thêm `attributes.durationMinutes`, `parentProductId`, `starRating`, nhưng đọc
từ `candidates`/`details` trong state, **không** đọc từ response.

| Field của `ProductSummary` trong lịch | Đề xuất | Quyết định |
|---|---|---|
| `productId`, `name`, `taxonomy`, `destination`, `unitPrice`, `currency`, `priceUnit`, `available` | Giữ (bắt buộc trong contract) | |
| `availableFrom`, `availableTo`, `imageUrl`, `rating`, `reviewCount` | Giữ (nhỏ, FE hiển thị) | |
| `attributes` | Cắt còn các khoá FE đọc (`beachfront`, `oceanView`, `pool`, `ticketed`). Muốn FE hiện thời lượng hoặc số sao thì giữ thêm `durationMinutes`, `starRating` (FE hiện chưa đọc) | |
| `description` | Bỏ, hoặc cắt còn ~200 ký tự. Nếu bỏ thì `AiFloatingWidget` chuyển sang dùng cờ `attributes` | |

Cắt hai field này không ảnh hưởng grounding: `steps/validation.py` (bước `finalize`) và
`src/evaluation/agent/grounding.py` không đọc `attributes` hay `description`.

### 2.2. Contract có, backend không bao giờ trả, FE vẫn đọc

| Field | FE đọc ở | Hệ quả hiện tại | Đề xuất | Quyết định |
|---|---|---|---|---|
| `suggestedValues` (NEEDS_CLARIFICATION) | `AiFloatingWidget.tsx`, `AssistantResultPanel.tsx` | FE rơi về giá trị cứng "Nha Trang"/3 ngày | Trả: điểm đến lấy từ `supported_destinations`, số ngày 1–7 | |
| `suggestions` (NO_RESULTS) | `AssistantResultPanel.tsx` | FE hiện câu mặc định | Trả hoặc FE bỏ đọc | |
| `slotId` | `AssistantResultPanel.tsx` (làm React key, có fallback) | Không lỗi | Giữ optional, không làm gì | |
| `startTime`, `endTime` | FE hiển thị nếu có | Luôn trống | Giữ optional; trả khi Data có giờ mở cửa (handbook §11 Tuần 4) | |
| `itinerary.title`, `days[].title` | FE có fallback | Luôn trống | Giữ optional | |
| `metadata` (`personalised`, `searchRequestIds`, `generatedAt`, `requestId`) | FE đọc `generatedAt` một chỗ | Không bao giờ có | Giữ optional; trả nếu FE cần hiện "cập nhật lúc" | |

### 2.3. Backend trả, FE không dùng

| Field | Đề xuất | Quyết định |
|---|---|---|
| `intent.pace` | Giữ (contract). Backend không dùng `pace` để xếp lịch (`MAX_ACTIVITIES_PER_DAY` cố định) | |
| `warnings[].productId` của `PRODUCT_DROPPED_*` | Giữ; FE hiện chưa đọc warnings từng sản phẩm. Cân nhắc gộp nhiều warning `PRODUCT_DROPPED_*` giống nhau thành một | |

### 2.4. Giữ nguyên

`status`, `conversationId`, `intent`, `itinerary.stay` (`nights`, `note`, `source`, `because`),
`itinerary.days[].slots[]` (`time`, `activityType`, `note`, `source`, `because`), `bookableCount`,
`estimatedTotal`, `currency`, `budgetStatus`, `priceAsOf`, `warnings`, `question`, `missingFields`,
`knownIntent`, `message`, `searchResults` (FALLBACK). Đều có FE đọc hoặc là field bắt buộc của contract.

## 3. AgentState

### 3.1. Bỏ: không ai đọc

| Field | Bằng chứng | Đề xuất | Quyết định |
|---|---|---|---|
| `thread_id`, `scenario_id`, `messages` | Chỉ `initial_state()` của `Scenario` ghi; luồng API không dùng | Bỏ, cùng `Scenario`, `Route`, `initial_state` (chỉ còn `tests/unit/agents/test_lab_copy.py` dùng) | |
| `errors` | Khai báo append-only; không node nào ghi hay đọc. `state-fields.md` ghi `retry` ghi `TRANSIENT_TOOL_FAILURE` nhưng code không còn | Bỏ | |
| `pending_question` | `converse`/`clarify` ghi, không ai đọc; nội dung trùng `response.question` | Bỏ | |
| `final_answer` | `clarify`/`finalize` ghi, không ai đọc | Bỏ | |
| `llm_used` | `intake`/`classify`/`converse` ghi, không ai đọc | Bỏ, hoặc đưa vào `itinerary_metrics` ở route nếu muốn đo tỷ lệ dùng LLM | |

### 3.2. Gộp: vai trò chồng lấn

| Field | Vấn đề | Đề xuất | Quyết định |
|---|---|---|---|
| `route`, `decision`, `evaluation_result` | Ba cờ điều hướng: `route` sau `classify`, `evaluation_result` sau `evaluate`, `decision` ghi ở 5 node, đọc ở 9 chỗ | Gộp thành một cờ `decision`; sửa `routing.py` và test | |
| `details`, `candidates` | `details` giữ ProductDetail đầy đủ của mọi sản phẩm tool trả, kể cả sản phẩm bị loại; `candidates` chép lại phần đạt. Trace LangSmith mang cả hai | Xoá `details` khỏi state sau khi `evaluate` dựng `candidates`, hoặc chỉ giữ id | |
| `tool_results` | Giữ nguyên payload Search/Recommendation (có `description`, `attributes`) | Giữ cho retry; cân nhắc bỏ `data` sau `evaluate` để trace nhẹ | |

### 3.3. Giữ: có node đọc thật

| Nhóm | Field |
|---|---|
| Đầu vào | `query`, `conversation_id`, `conversation_history`, `intent`, `intent_override`, `constraints`, `previous_selection`, `language`, `request_id` |
| Hỏi lại | `missing_fields`, `clarification_reason`, `refusal`, `interaction_type` |
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
