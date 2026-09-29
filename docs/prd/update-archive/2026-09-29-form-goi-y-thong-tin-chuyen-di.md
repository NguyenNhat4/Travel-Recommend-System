# Form gợi ý thông tin chuyến đi khi người dùng không chốt được yêu cầu

- Ngày: 2026-09-29
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-09-29
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01), `docs/prd/architecture.md` §3 (sơ đồ, cạnh `CheckClarification --> AskUser`), `docs/prd/user-flow.md` §4.2 (wireframe màn trợ lý)
- Mã FR/NFR: FR-AGT-01, FR-AGT-03, FR-AGT-05

> Thay thế bản nháp trước cùng ngày (`2026-09-29-so-ngay-mac-dinh-khi-nguoi-dung-khong-chot.md`, chỉ xử lý `days` bằng mặc định
> ngầm). Người dùng đổi hướng: dùng **form gợi ý hiện ngay trong khung chat**, áp dụng cho **mọi trường bắt buộc**.

## Lý do

Hiện `destination` và `days` là bắt buộc trước khi truy xuất: thiếu thì trả `NEEDS_CLARIFICATION` và hỏi lại **không giới hạn số lần**
(`src/backend/app/agents/steps/classification.py:157`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.3). Người dùng trả lời
"bao nhiêu ngày cũng được" thì LLM không trích được con số, lượt sau lại hỏi đúng câu cũ — hội thoại kẹt vòng (ảnh chụp widget: ba
lượt liên tiếp cùng một câu hỏi).

Hỏi lại bằng câu chữ không giải được vấn đề gốc: người dùng **không biết phải trả lời gì**. Giải pháp người dùng chọn là đưa cho họ
một **form đã điền sẵn giá trị gợi ý** để tinh chỉnh, thay vì bắt họ tự nghĩ ra câu trả lời.

## Quyết định người dùng đã đưa ra

| Câu hỏi | Chọn |
|---|---|
| Khi nào hiện form? | Sau **một** lượt người dùng trả lời mà vẫn không rõ. Lượt hỏi đầu vẫn là câu hỏi bình thường. |
| Form gồm field nào? | **Mọi trường bắt buộc** của chuyến đi, không chỉ `days`. |
| Giá trị trong form | Điền sẵn giá trị gợi ý, người dùng sửa được. |
| Dẫn nhập | Một câu thân thiện kiểu *"Mình gợi ý như sau, bạn tinh chỉnh theo nhu cầu nhé"* (được viết dài hơn cho tự nhiên). |
| Giới hạn | Số ngày không quá 7; ngày bắt đầu không được trước hôm nay. |
| Danh sách điểm đến | Chỉ **5–10 điểm đến**, không đổ toàn bộ catalog. |
| Sau khi bấm xác nhận | Dựng một **prompt hoàn chỉnh** từ giá trị trong form và **đặt sẵn vào ô nhập tin nhắn** — không tự gửi, để người dùng đọc lại, sửa rồi mới gửi. |
| Mặc định số ngày | 1 ngày (người dùng chốt ở lượt trao đổi trước; nay là giá trị điền sẵn, sửa được ngay trên form). |

## Nội dung đề xuất

### 1. `docs/prd/requirements.md` §3, AC-AGT-01, cột "Hành vi kỳ vọng"

Hiện tại:

> Trợ lý hỏi gộp một câu, một lần, những gì còn thiếu trong ngày đi, số người và ngân sách (không tự đoán ngày). Người dùng trả lời
> đủ, trả lời một phần hoặc nói chưa chốt; khi đó trợ lý xuất ra lịch trình 3 ngày có cấu trúc; các địa điểm nghỉ ngơi và hoạt động
> đều là thẻ sản phẩm thật kèm giá rõ ràng và nút bấm xem chi tiết. Câu đầu đã đủ ngày đi, số người và ngân sách thì xuất lịch ngay.

Thay bằng (giữ nguyên phần cũ, thêm đoạn in đậm):

> Trợ lý hỏi gộp một câu, một lần, những gì còn thiếu trong ngày đi, số người và ngân sách (không tự đoán ngày). Người dùng trả lời
> đủ, trả lời một phần hoặc nói chưa chốt; khi đó trợ lý xuất ra lịch trình 3 ngày có cấu trúc; các địa điểm nghỉ ngơi và hoạt động
> đều là thẻ sản phẩm thật kèm giá rõ ràng và nút bấm xem chi tiết. Câu đầu đã đủ ngày đi, số người và ngân sách thì xuất lịch ngay.
> **Người dùng đã được hỏi một lượt mà câu trả lời vẫn không cho biết điểm đến hoặc số ngày thì trợ lý không hỏi lại bằng câu chữ
> nữa: nó hiển thị ngay trong khung chat một form thông tin chuyến đi đã điền sẵn giá trị gợi ý (điểm đến, số ngày, ngày khởi hành,
> số người, ngân sách) kèm một câu mời tinh chỉnh; ô điểm đến chỉ liệt kê vài điểm đến tiêu biểu của catalog. Form chặn giá trị không
> hợp lệ: số ngày trong khoảng 1–7, ngày khởi hành không trước ngày hôm nay. Người dùng bấm xác nhận thì câu yêu cầu hoàn chỉnh được
> đặt sẵn vào ô nhập tin nhắn để họ sửa hoặc gửi ngay; gửi đi thì trợ lý coi đó là một yêu cầu đầy đủ và lập lịch, không hỏi thêm.**

### 2. `docs/prd/architecture.md` §3, sơ đồ

Hiện tại:

```
    CheckClarification --> AskUser: Thiếu điểm đến/số ngày, hoặc chưa hỏi ngày đi–số người–ngân sách
```

Thay bằng hai cạnh:

```
    CheckClarification --> AskUser: Lượt đầu thiếu thông tin → hỏi bằng câu chữ
    AskUser --> SuggestForm: Đã hỏi một lượt mà vẫn thiếu → gợi ý form đã điền sẵn
    SuggestForm --> [*]: Chờ người dùng xác nhận form
```

(`SuggestForm` là một nhánh trả về của `clarify`, **không phải node mới**; graph giữ đúng 11 node.)

### 3. `docs/prd/user-flow.md` §4.2

Thêm dưới wireframe màn `/assistant` một dòng mô tả: khi trợ lý đã hỏi một lượt mà vẫn thiếu thông tin, khung chat hiển thị form gợi ý
(điểm đến, số ngày, ngày đi, số người, ngân sách) kèm nút **Xác nhận**; form xuất hiện trong cả màn `/assistant` lẫn widget nổi.

### 4. Quy tắc hành vi đi kèm (ghi ở spec, không ở PRD)

- Đếm theo hội thoại: `clarification_rounds` = số lượt trợ lý đã hỏi vì thiếu `destination`/`days`. 0 → hỏi bằng câu chữ (=1);
  ≥ 1 mà vẫn thiếu → trả `NEEDS_CLARIFICATION` kèm **form**, không tăng tiếp và không hỏi lại bằng câu chữ nữa.
- Giá trị điền sẵn: `destination` = điểm đến đầu tiên trong `supported_destinations` (lấy từ catalog, không do LLM bịa);
  `days` = 1; `startDate` = hôm nay theo giờ Việt Nam (`vietnam_today()`); `party` = 2 người lớn, 0 trẻ em; `budget` = để trống
  (không giới hạn). Giá trị người dùng đã nói ở các lượt trước luôn thắng giá trị gợi ý.
- Giới hạn: `days` 1–7 (đã có trong contract); `startDate` ≥ hôm nay theo giờ Việt Nam — **ràng buộc mới**, hiện không tồn tại ở cả
  contract lẫn backend (ngày quá khứ đang được chấp nhận). Backend kiểm lại khi nhận lượt xác nhận, không tin mỗi FE.
- Câu dẫn nhập do **LLM** viết (prompt bắt buộc: mời tinh chỉnh, không bịa số liệu); câu cố định vi/en dự phòng khi LLM lỗi.
- Ô điểm đến chỉ liệt kê **8 điểm đến** nhiều sản phẩm nhất (sắp theo `productCount` của `GET /destinations`), không đổ hết catalog.
  Người dùng muốn nơi khác thì gõ thẳng vào ô nhập.
- Bấm xác nhận → FE dựng **một câu yêu cầu đầy đủ** từ form (theo đúng cách `tripStarterMessage()` đang làm ở
  `src/frontend/src/components/assistant/AssistantTripStarter.tsx:40`) và **đặt câu đó vào ô nhập tin nhắn, không tự gửi**. Người dùng
  đọc lại, sửa thêm nếu muốn, rồi bấm gửi như một lượt chat bình thường. Không dùng `intentOverride`, vì `intentOverride` là chip sửa
  từng field và đang bị loại khỏi luật hỏi chi tiết (`classification.py:174`).
- Form chỉ hiện một lần cho mỗi hội thoại; người dùng bỏ qua và gõ tay thì luồng chạy như bình thường.

### 5. Thay đổi contract (phải làm trước code, `AGENTS.md` mục 3)

Thêm **field tuỳ chọn** vào `ItineraryNeedsClarification` (`src/shared/contracts/schemas/itinerary-agent.yaml:417`) — tương thích ngược,
không đổi/gỡ field nào, nên vẫn là v1:

```yaml
      clarificationForm:
        type: object
        description: Form gợi ý hiển thị trong khung chat khi hỏi bằng câu chữ một lượt vẫn chưa đủ thông tin.
        required: [fields, defaults]
        properties:
          fields:
            type: array
            minItems: 1
            items: { type: string, enum: [destination, days, startDate, party, budget] }
          defaults: { $ref: ../openapi.yaml#/components/schemas/TripIntent }
          startDateMin: { type: string, format: date }
```

`suggestedValues` giữ nguyên (FE vẫn dùng cho chip điểm đến/số ngày ở màn `/assistant`).

## Ảnh hưởng và rủi ro

- **Widget nổi hiện chưa có UI nào cho `NEEDS_CLARIFICATION`** — nó chỉ in `question` dạng text (`useFloatingWidget.ts:62-88`,
  `WidgetChat.tsx:22-30`), `missingFields`/`suggestedValues` bị bỏ. Đây là phần việc lớn nhất của đề xuất: form phải render được
  trong widget (nơi người dùng gặp lỗi kẹt vòng) chứ không chỉ ở `AssistantResultPanel`.
- **Ràng buộc "ngày đi không trước hôm nay" là hành vi mới** và lệch với spec hiện hành (`hop-dong-tich-hop-itinerary-assistant.md`
  §4.3: "ngày không bị từ chối dù đã qua"). Chỉ áp dụng cho giá trị đến từ form; câu chat tự do giữ nguyên hành vi cũ để không phá
  golden case đang có.
- **Người dùng có thể xác nhận nguyên giá trị gợi ý** và nhận lịch cho điểm đến mình không chủ động chọn. Giảm rủi ro bằng cách để
  `destination` là ô chọn (select) chứ không phải giá trị chốt sẵn vô hình — người dùng nhìn thấy và đổi được trước khi bấm.
- **Grounding không đổi:** form chỉ chứa tham số chuyến đi; `destination` lấy từ catalog qua `list_destinations`, không do LLM sinh.
  NFR-REL-01 và FR-AGT-04 giữ nguyên.
- **Độ trễ không đổi:** không thêm lời gọi LLM nào; lượt xác nhận là một lượt chat bình thường.
- **Tương thích ngược:** client cũ bỏ qua `clarificationForm` và vẫn thấy `question` như cũ.

## Thay đổi source sau khi chốt

**Contract (trước tiên)**
- `src/shared/contracts/schemas/itinerary-agent.yaml` — thêm `clarificationForm`; chạy `validate_contract.py`.
- `src/frontend/src/types/api.gen.ts` — sinh lại.

**Backend**
- `src/backend/app/agents/state.py` — thêm `clarification_rounds` (lưu theo hội thoại, thay vai trò mở rộng của `start_date_asked`).
- `src/backend/app/agents/steps/classification.py` — đếm `clarification_rounds` khi thiếu `destination`/`days`.
- `src/backend/app/agents/steps/conversation.py` — `_question_response` dựng `clarificationForm` (fields còn thiếu + defaults +
  `startDateMin`) từ vòng thứ hai trở đi; `clarification_fallback` có câu dẫn nhập cố định vi/en.
- `src/backend/app/agents/steps/prompts.py`, `messages.py` — câu dẫn nhập mời tinh chỉnh.
- `src/backend/app/agents/nodes.py` — khởi tạo/carry `clarification_rounds` ở `intake`, lưu ở `finalize`.
- `src/backend/app/agents/steps/validation.py` hoặc `classification.py` — chặn `startDate` trước hôm nay khi đến từ form.

**Frontend**
- Component mới `src/frontend/src/components/assistant/TripDetailsForm.tsx` — tái dùng pattern của `AssistantTripStarter.tsx`
  (chip group, `listDestinations()`), thêm ô ngày (`<input type="date" min={startDateMin}>`) và stepper số ngày chặn 1–7
  (mẫu stepper: `HomeView.tsx:1020-1066`), ô ngân sách tuỳ chọn.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx`, `useFloatingWidget.ts` — giữ `response` của từng transcript item và
  render form khi `response.clarificationForm` có mặt.
- `src/frontend/src/components/assistant/AssistantResultPanel.tsx`, `AssistantConversation.tsx` — render form ở màn `/assistant`.
- Hàm dựng câu yêu cầu đầy đủ từ form (cùng file component, theo mẫu `tripStarterMessage`).

**Test / tài liệu**
- Backend: `src/backend/tests/unit/agents/test_classify.py` (hai nấc), `test_itinerary_runtime.py` (hỏi → vẫn thiếu → có
  `clarificationForm`), `tests/contract/test_assistant_contract.py`.
- Frontend: unit test cho `TripDetailsForm` (giới hạn 1–7 ngày, `min` của ô ngày, câu dựng ra), cập nhật
  `tests/unit/assistantResultPanel.test.tsx`, e2e `tests/e2e/widget-opening.spec.ts`.
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — case "hà nội" → hỏi; "bao nhiêu ngày cũng được" → `NEEDS_CLARIFICATION`
  có form, `toolCalled: false`; lượt câu dựng từ form → `COMPLETED`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.3, `docs/spec/hop-dong-tich-hop-frontend.md`,
  `docs/spec/agent/state-fields.md`, `langgraph-nodes.md`, `field-review.md`, `golden-dataset-how-to-add-more-case.md`.
