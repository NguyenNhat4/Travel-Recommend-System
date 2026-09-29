# Vòng ReAct có chặn ở node `tool`: lập lại tool plan sau khi quan sát kết quả

- Ngày: 2026-09-29
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (sơ đồ trợ lý, mục "Ngữ cảnh cho LLM"), `docs/prd/requirements.md` §2.1 (NFR-PERF-02)
- Mã FR/NFR: FR-AGT-02, FR-AGT-04, NFR-PERF-02, NFR-REL-01

## Lý do

Hiện `tool` hỏi LLM **một lần** để phát ra toàn bộ lời gọi Search/Recommendation, chạy song song, rồi **không bao giờ cho LLM biết kết quả trả về là gì**. Vòng `evaluate → retry → tool` đang có chỉ là retry tầng vận chuyển: nó cố tình dùng lại `tool_plan` cũ nên không có suy luận mới.

Hệ quả: khi lượt truy xuất đầu để lại khoảng trống — ví dụ người dùng yêu cầu có chỗ ở (`require_hotel`) nhưng vòng 1 không ra khách sạn nào hợp lệ — trợ lý đi thẳng `fallback` hoặc quay ra hỏi lại người dùng, dù chỉ cần một lời gọi Search thứ hai với tham số khác là lấp được. Người dùng phải trả lời thêm một lượt cho việc mà hệ thống tự làm được.

Đề xuất cho phép **đúng một** lần lập lại tool plan sau khi đã quan sát kết quả vòng đầu, có chặn cứng và có deadline.

Hai điểm lệch PRD phải chốt trước khi sửa code:

1. §3 đang liệt kê **danh sách đóng** các điểm gọi LLM. Lập lại tool plan là điểm thứ sáu, chưa có trong danh sách đó.
2. NFR-PERF-02 đặt tổng thời gian ≤ 4.0s. Với trần này, sau `classify` + `extract` + lập plan + gọi tool thì deadline gần như luôn hết trước khi kịp lặp, nên tính năng sẽ không bao giờ chạy. Đồng thời đây đã là **mâu thuẫn tồn đọng**: `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` ghi p95 toàn luồng **dưới 5 giây** ở ba chỗ (dòng 410, 451, 519) và bảng ngân sách §7.2 cũng cộng ra hơn 4 giây. Đề xuất gỡ luôn mâu thuẫn này theo hướng PRD lấy mốc 5.0s.

## Nội dung đề xuất

### 1. `docs/prd/requirements.md` §2.1, NFR-PERF-02

Hiện tại:

> - **NFR-PERF-02 (AI Assistant Response Time):**
>   - Thời gian bắt đầu xuất luồng văn bản (First token latency) của Trợ lý AI phải $\le 1.0\text{ s}$.
>   - Tổng thời gian hoàn tất một phản hồi lịch trình phức tạp phải $\le 4.0\text{ s}$.

Thay bằng:

> - **NFR-PERF-02 (AI Assistant Response Time):**
>   - Thời gian bắt đầu xuất luồng văn bản (First token latency) của Trợ lý AI phải $\le 1.0\text{ s}$.
>   - Tổng thời gian hoàn tất một phản hồi lịch trình phức tạp phải $\le 5.0\text{ s}$ (p95), khớp với bảng ngân sách thời gian ở `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §7.2. Mốc này đã bao gồm phần dự phòng cho một lần lập lại tool plan; hết ngân sách thì trợ lý dừng lặp và trả lời bằng dữ liệu đang có, không vượt trần.

First token latency **không đổi**: vòng lặp nằm ở giai đoạn truy xuất, trước khi soạn câu trả lời.

### 2. `docs/prd/architecture.md` §3, mục "Ngữ cảnh cho LLM"

Hiện tại:

> - **Ngữ cảnh cho LLM:** mọi lượt gọi LLM (phân luồng, trích intent, chọn điểm đến, lập tool plan, viết câu trả lời) nhận cùng ngữ cảnh hội thoại: …

Thay bằng:

> - **Ngữ cảnh cho LLM:** mọi lượt gọi LLM (phân luồng, trích intent, chọn điểm đến, lập tool plan, **lập lại tool plan sau khi quan sát kết quả truy xuất**, viết câu trả lời) nhận cùng ngữ cảnh hội thoại: …

### 3. `docs/prd/architecture.md` §3, thêm một mục vào "Tiêu chuẩn Grounding"

Thêm:

> - **Lập lại tool plan có chặn:** khi lượt truy xuất đầu còn khoảng trống (không có sản phẩm xếp được lịch, hoặc thiếu loại sản phẩm mà người dùng yêu cầu), trợ lý được gọi LLM lập thêm lời gọi tool **tối đa một lần** cho mỗi lượt chat. Ba ràng buộc bắt buộc:
>   - **Luật tất định quyết định dừng.** LLM chỉ *đề nghị* lời gọi mới; việc lặp hay đi tiếp do luật ở bước kiểm kết quả quyết định, dựa trên số candidate đã có so với yêu cầu. LLM không được tự tuyên bố "đã đủ dữ liệu".
>   - **Quan sát không chứa dữ liệu sản phẩm.** Thông tin trả lại cho LLM giữa hai vòng chỉ gồm số liệu do hệ thống tính: số kết quả trả về, số candidate giữ lại, số bị loại theo từng lý do, loại sản phẩm còn thiếu, ràng buộc chưa thoả, thời gian đã dùng. **Không** có `productId`, `title`, `price`, `imageUrl`, `description`, và không có chuỗi văn bản nào do hệ thống ngoài sinh ra. LLM vì vậy vẫn chưa từng thấy dữ liệu sản phẩm, nên nguyên tắc grounding 100% ở trên không đổi.
>   - **Deadline thắng.** Hết ngân sách NFR-PERF-02 thì dừng lặp ngay và dựng lịch từ candidate đang có.

### 4. `docs/prd/architecture.md` §3, sơ đồ

Thêm một cạnh quay lại vào `stateDiagram-v2`, sau dòng `ValidateAvailability --> Rerank`:

```
    ValidateAvailability --> SearchCandidates: Thiếu dữ liệu và còn deadline → lập lại tool plan (tối đa 1 lần)
```

## Ảnh hưởng

- **Độ trễ:** thêm tối đa một lượt LLM (~0,8s) và một lượt gọi tool (~1,0s), chỉ khi predicate cho phép. Trần mới 5.0s. Lượt không có khoảng trống chạy đúng như hiện nay, không chậm thêm.
- **Grounding:** không đổi. NFR-REL-01 và FR-AGT-04 giữ nguyên vì LLM không nhận field sản phẩm nào (xem mục 3).
- **Bảo mật:** không mở bề mặt prompt-injection mới — payload quan sát chỉ có số nguyên và mã lý do của chính hệ thống, không mang chuỗi từ upstream. NFR-SEC-01 không đổi.
- **Contract:** **không đổi.** `AssistantStreamEvent` không yêu cầu `nodeId` duy nhất, nên `tool` và `evaluate` xuất hiện hai lần trên SSE là hợp lệ; `sequence` vẫn tăng đơn điệu. Frontend gom `progress` theo khoá `${sequence}-${nodeId}` nên không vỡ, chỉ hiển thị bước "Truy xuất sản phẩm" hai lần.
- **Đo lường:** Tool Calling Accuracy (≥ 95%) và Grounding Rate (100%) ở `docs/prd/test-plan.md` §2.4 giữ ngưỡng cũ; golden runner chấm theo tập node nên node lặp lại không ảnh hưởng.
- **Spec phải sửa theo:** `docs/spec/agent/langgraph-nodes.md` (câu "chỉ cho retry một lần" phải đổi thành mô tả hai loại vòng: retry vận chuyển và lập lại plan), `docs/spec/agent/state-fields.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.1 và §7.2 cùng ba dòng p95.
- **Không** thêm node nào: graph giữ đúng 11 node, chỉ thêm một cạnh `evaluate → tool`.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/state.py` — thêm `tool_iteration`, `max_tool_iterations`, `tool_observations`, `replan_requested`.
- `src/backend/app/agents/steps/evaluation.py` — predicate tất định `_should_replan` (cap + deadline + có khoảng trống thật), dựng payload quan sát, giữ `details` khi lặp.
- `src/backend/app/agents/steps/tool_planning.py` — id lời gọi thành `call-{iteration}-{index}` (bắt buộc: id hiện tại đếm lại từ 0 nên vòng 2 sẽ dùng nhầm kết quả vòng 1 do memo theo `tool_call_id`); `build_plan` phân biệt lập lại plan với retry vận chuyển; plan tích lũy.
- `src/backend/app/agents/steps/prompts.py` — `TOOL_PLAN_PROMPT` mô tả vòng thứ hai và payload quan sát.
- `src/backend/app/agents/routing.py`, `src/backend/app/agents/graph.py` — nhánh `replan` và cạnh `evaluate → tool`.
- `src/backend/app/agents/nodes.py` — khởi tạo field mới ở `intake`, đếm vòng và reset cờ ở `tool`, hằng số ngân sách.
- Test: `src/backend/tests/unit/agents/test_routing.py`, `test_itinerary_runtime.py`, `test_itinerary_tools.py`, `test_lab_copy.py`.
- Tài liệu: các spec nêu ở mục Ảnh hưởng, `src/evaluation/agent/README.md`.
