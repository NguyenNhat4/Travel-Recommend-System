# AgentState: từng trường, node nào dùng để làm gì

Phục vụ FR-AGT-01 (hội thoại đa lượt), FR-AGT-02 (tool calling), FR-AGT-03 (lịch trình có cấu trúc), FR-AGT-04 (grounding 100%) ở `docs/prd/requirements.md` §1.4 — tài liệu này chỉ mô tả lại field-level cách mười node hiện thực các FR đó qua `AgentState`, không thêm hành vi mới.

Bảng ở [langgraph-nodes.md](langgraph-nodes.md) mục 6.1 tổ chức theo **node** (mỗi node đọc/ghi field nào). Bảng dưới đây tổ chức theo **field** (mỗi field được node nào ghi, node nào đọc, để làm gì) — dùng khi cần tra một field cụ thể thay vì đọc lại toàn bộ một node.

Nguồn field: `src/backend/app/agents/state.py` (định nghĩa `AgentState`). Nguồn hành vi: `src/backend/app/agents/nodes.py` (hàm node), `src/backend/app/agents/steps/` (luật chi tiết của từng bước) và `src/backend/app/agents/routing.py`, khớp tại thời điểm viết — `git blame`/`git log -p` mới là nguồn xác thực khi code đã đổi.

| Trường | Node ghi | Node đọc | Dùng để làm gì |
|---|---|---|---|
| `query` | `intake` (strip) | `classify`, `tool`, `converse`, `clarify` | Message gốc của người dùng — đầu vào prompt LLM và fallback `query` cho `search_products` |
| `conversation_id` | `intake` (tạo mới nếu chưa có) | `tool` (thông báo lỗi), `compose`, `clarify`, `converse`, `finalize` | ID hội thoại trả về client, khóa lưu/khôi phục context multi-turn |
| `conversation_history` | `intake` (khởi tạo/khôi phục), `finalize` (nối lượt user/assistant đã chốt) | `classify`, `tool` (lập plan), `converse`, `clarify`, `finalize` | Lịch sử chat gần nhất để hiểu tham chiếu đa lượt. Chỉ nhận role `user`/`assistant`, tối đa 20 message, 1.000 ký tự/message và 8.000 ký tự tổng; mọi node nhận field này qua state nhưng node tất định không dùng nó làm nguồn dữ liệu sản phẩm |
| `intent` | `intake` (khởi tạo/khôi phục), `classify` (merge patch+override), `tool` (chuẩn hóa destination) | `classify`, `tool`, `evaluate`, `compose`, `converse`, `clarify`, `finalize` | Trục dữ liệu chính: destination, days, budget, party... |
| `intent_override` | *(set từ API request, ngoài graph)* | `classify` | Chip edit của UI, ghi đè patch LLM trích xuất |
| `constraints` | `intake` (khởi tạo), `classify` (merge), `tool` (chuẩn hóa) | `classify`, `tool`, `evaluate`, `compose`, `finalize` | Ràng buộc thêm: `require_hotel`, `specific_hotel/activity`, `exclude_taxonomies`, `exclude_products` (loại đúng productId đã cho xem trước đó khi user xin đổi mà không nêu tên thay thế — FR-AGT-05), giá hotel... |
| `previous_selection` | `intake` (khôi phục từ store), `finalize` (lưu snapshot itinerary vừa `COMPLETED`) | `classify` (đưa vào prompt LLM để khớp câu nói mơ hồ ra đúng productId), `classify` (`_classify_result` dùng làm whitelist validate `exclude_products`, chặn LLM bịa id) | Danh sách gọn `{productId, name, taxonomy}` các sản phẩm đã cho user xem ở lượt trước, phục vụ loại trừ chính xác khi đổi món mà không nêu tên |
| `missing_fields` | `classify` | `converse`, `clarify` | Field còn thiếu (destination/days) để hỏi lại |
| `clarification_reason` | `classify` | `converse`, `clarify` | Lý do cần hỏi thêm: `conflict`/`unverified`/`None` |
| `refusal` | `classify` | `converse`, `clarify` (qua `_conversational_update`) | Đánh dấu yêu cầu ngoài phạm vi/side-effect → trả `VALIDATION_ERROR` 400 |
| `interaction_type` | `intake` (init rỗng), `classify` (domain) | `converse`, `clarify` | Loại tương tác (travel/conversation/out_of_domain/side_effect), làm ngữ cảnh cho prompt hội thoại |
| `route` | `classify` | `route_after_classify` | Điều hướng cạnh ngay sau `classify` |
| `decision` | `intake` (async, lỗi 404), `classify`, `tool` (lỗi), `evaluate`, `retry` | `classify` (bỏ qua LLM nếu đã lỗi), `evaluate` (short-circuit nếu `tool` đã lỗi), `compose` (`_retrieval_outcome`), `route_after_evaluate`, `route_after_retry` | Cờ quyết định nghiệp vụ chính: `compose`/`no_results`/`fallback`/`constraint_clarification`/`error` |
| `evaluation_result` | `evaluate` | `route_after_evaluate` | Kết quả đánh giá tool retrieval: `success`/`needs_retry`/`failed` |
| `http_status` | `intake` (200), mọi `_failure()`, `finalize` | `finalize`, `finalize_node_async` (check resumable) | Mã HTTP trả về cuối |
| `response` | `intake` (init {}), mọi node soạn câu trả lời, `finalize` (có thể ghi đè) | `dead_letter` (bỏ qua nếu đã có lỗi), `finalize` | Payload trả lời cuối cùng theo OpenAPI |
| `validation_issues` | `finalize` | *(không node nào đọc lại — terminal)* | Ghi lỗi schema/grounding phát hiện ở `finalize` để audit |
| `final_answer` | `clarify` (tạm), `finalize` (ghi đè, chốt) | *(không đọc lại trong graph)* | Text ngắn hiển thị cho client/demo |
| `pending_question` | `converse`, `clarify` | *(không đọc lại trong graph)* | Câu hỏi đang chờ, phục vụ tầng ngoài graph (log/store) |
| `llm_used` | `intake` (False), `classify`, `converse`/`clarify` (khi LLM thành công) | *(không đọc lại trong graph)* | Cờ audit/telemetry: lượt này có gọi LLM thành công không |
| `details` | `intake` (init {}), `tool` (từ `hydrate`) | `evaluate` (`collect()`) | Chi tiết sản phẩm (ProductDetail) để dựng `candidates` |
| `detail_errors` | `intake` (init {}), `tool` | `evaluate`, `dead_letter` | Lỗi riêng khi lấy chi tiết sản phẩm |
| `supported_destinations` | `intake` (init `None`), `tool` | `tool` (cache tránh gọi lại `list_destinations`) | Danh sách điểm đến catalog hỗ trợ, để khớp/báo `UNSUPPORTED_DESTINATION` |
| `candidates` | `intake` (init {}), `evaluate` (`collect()`) | `compose`, `retry` (fallback check), `finalize`, `route_after_retry` | Sản phẩm đã qua grounding, nguồn dựng lịch trình/`FALLBACK` |
| `sources` | `intake` (init {}), `evaluate` | `compose`, `finalize` | Nguồn gốc (tool nào trả) của từng candidate, dùng cho `validate_plan` |
| `warnings` | `intake` (init []), `evaluate`, `compose` (append thêm) | `compose` (đọc warnings cũ từ evaluate) | Cảnh báo phi lỗi kèm response (sản phẩm bị loại, giá snapshot...) |
| `tool_plan` | `tool` | `tool` (đọc lại khi vào từ `retry`, tránh lập kế hoạch lại) | Danh sách lời gọi tool đã lập (tên + args) |
| `tool_results` | `intake` (init []), `tool` | `tool` (khớp `tool_call_id` cũ khi retry), `evaluate`, `dead_letter` | Kết quả thực thi từng tool call (data hoặc error) |
| `errors` (append-only) | `retry` (`TRANSIENT_TOOL_FAILURE`) | *(không đọc lại)* | Audit trail lỗi tạm thời tích lũy qua các lần retry |
| `events` (append-only) | **mọi node** | *(không đọc lại trong graph, chỉ tầng SSE/trace ngoài dùng)* | Trace từng bước cho Streamlit/debug |
| `messages` | chỉ `initial_state()` (harness Scenario) | *(không dùng trong `nodes.py`)* | Field append-only cũ của bộ đánh giá kịch bản, không phải lịch sử chat của luồng API; lịch sử thật nằm ở `conversation_history` |
| `attempt` | `intake` (0), `retry` (+1) | `retry`, `route_after_retry` | Đếm số lần đã retry tool |
| `max_attempts` | `intake` (clamp 1..2) | `retry`, `route_after_retry` | Giới hạn số lần retry tối đa |
| `request_id` | *(set từ API layer, ngoài graph)* | mọi log lỗi + `_failure()` ở `classify`/`tool`/`converse`/`clarify`/`dead_letter`, `finalize` | Nối log/trace theo request |
| `started_at` | `intake` | `finalize` | Mốc thời gian bắt đầu để tính `latency_ms` |
| `latency_ms` | `finalize` | *(không đọc lại trong graph)* | Độ trễ tổng của lượt, trả về/log |
| `language` | `intake` (mặc định "vi", khôi phục từ store), `finalize_node_async` (lưu lại) | `classify`, `converse`, `clarify`, mọi `_message()` fallback | Ngôn ngữ trả lời, ảnh hưởng prompt LLM và câu cố định |
| `thread_id`, `scenario_id` | chỉ `initial_state()` (harness Scenario) | *(không dùng trong `nodes.py`)* | Phục vụ bộ đánh giá kịch bản, không phải luồng API |
