# Timeout khi LLM lập tool plan phải được retry, không bị coi là plan sai cấu trúc

- Ngày: 2026-09-23
- Tác giả: người dùng (báo lỗi qua log) / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Người dùng dán log một request `POST /assistant/itineraries/stream` trả `httpStatus=503 status=ERROR`
với `retryCount=0`, sequence node `intake → classify → tool → evaluate → dead_letter → finalize`
(bỏ qua `retry`). So với các request thành công liền kề (cùng conversation), request lỗi chỉ gọi
được `GET /destinations`, không có dòng "200 OK" nào cho `/search` hay `/recommendations`, trong khi
`tool` node vẫn mất ~1967ms — dấu hiệu của một lượt gọi LLM lập kế hoạch tool bị chậm/lỗi, không
phải lỗi kết nối tới Search/Recommendation (đã xác nhận tầng httpx client ở
`infrastructure/clients/itinerary_http_clients.py` đã phân loại đúng lỗi kết nối/timeout là
`retryable=True`).

Đọc `tool_node` (`src/backend/app/agents/nodes.py`) thấy khối try/except dựng tool plan
(gọi LLM qua `bind_tools(...).ainvoke(...)`) chỉ có `except ToolError` và `except Exception` —
thiếu nhánh `except TimeoutError` riêng như các chỗ khác trong cùng file (chọn điểm đến, thực thi
tool). Khi lệnh gọi LLM lập plan timeout, exception rơi vào `except Exception` chung, bị gắn cứng
`ToolError("INVALID_TOOL_PLAN")` với `retryable=False` mặc định. `evaluate_node` thấy lỗi
"permanent" (không retryable) và không có candidate nào → `evaluation_result="failed"` →
`route_after_evaluate` đi thẳng `dead_letter` thay vì `retry`, dù bản chất là LLM chậm tạm thời,
lẽ ra phải được thử lại (graph có ngân sách `max_attempts=2`).

## File thay đổi

- `src/backend/app/agents/nodes.py` — sửa: thêm nhánh `except TimeoutError` riêng trong khối dựng
  tool plan của `tool_node` (trước dòng gọi `_validated_plan`), trả lỗi `INVALID_TOOL_PLAN` với
  `retryable=True` thay vì mặc định `False`; thêm `logger.exception(...)` ở nhánh `except Exception`
  còn lại để lần sau có traceback thật thay vì phải suy đoán từ log INFO.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: thêm tham số `plan_delay` cho
  `ScriptedLlm` (chỉ trễ ở lượt gọi planner đầu tiên) và test
  `test_llm_plan_timeout_is_retried_instead_of_treated_as_a_permanent_invalid_plan` xác nhận
  request timeout ở bước lập plan đi qua `retry` (gọi lại planner lần 2) rồi hoàn thành, thay vì
  rơi thẳng `dead_letter`.

## Quyết định

- Không sửa `except Exception` ở `tool_node` (dòng thực thi từng tool call, không phải dòng lập
  plan) hay ở `ItineraryToolGateway.execute()` (`src/backend/app/agents/tools/itinerary_gateway.py`)
  vì đọc kỹ thấy lỗi kết nối/timeout HTTP thật sự đã được `_request()`
  (`infrastructure/clients/itinerary_http_clients.py:45-50`) phân loại đúng `retryable=True` trước
  khi tới các nhánh đó; hai nhánh `except Exception` này chỉ còn bắt lỗi validate schema response
  hoặc lỗi lập trình thật sự — giữ `retryable=False` mặc định ở đó là đúng, sửa sẽ che lấp bug thật.
- Không đổi `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.6 vì thay đổi này chỉ sửa đúng ý
  đồ đã ghi ("Search bị lỗi thì Agent trả `SEARCH_UNAVAILABLE` retryable") — không lệch PRD, không
  cần đề xuất trong `docs/prd/update/`.
- Giữ nguyên message/`code` trả về client là `INVALID_TOOL_PLAN` (qua `dead_letter_node` map thành
  `LLM_UNAVAILABLE` khi thật sự hết lượt retry) để không đổi hợp đồng response hiện có; chỉ đổi cờ
  `retryable` nội bộ để `evaluate_node` cho phép `retry` thay vì đi thẳng `dead_letter`.
- Không đụng tới `src/backend/app/core/config.py` (đã có thay đổi uncommitted từ trước nâng default
  `itinerary_tool_timeout_seconds`/`itinerary_llm_timeout_seconds`/`itinerary_request_timeout_seconds`
  từ 1s/2s/5s lên 10s) — thay đổi đó không phải của task này, không thuộc phạm vi entry này.

## Kiểm tra

- `python3 -m pytest src/backend/tests/unit/agents/test_itinerary_runtime.py -q` → 42 passed.
- `python3 -m pytest src/backend/tests/unit -q` → 160 passed (toàn bộ unit test backend, không có
  test nào bị phá vỡ bởi thay đổi).
- Chưa chạy `validate_contract.py` vì không đổi contract/mock.

## Còn lại / rủi ro

- Chưa xác nhận 100% đây là nguyên nhân chính xác của request lỗi cụ thể trong log người dùng gửi
  (thiếu log DEBUG/traceback tại thời điểm xảy ra) — kết luận dựa trên đối chiếu pattern log (chỉ
  `/destinations` được gọi, không có `/search`/`/recommendations`, thời lượng `tool` node phù hợp
  với một lượt gọi LLM) và đọc code đường đi lỗi duy nhất khớp pattern đó.
- Nếu nguyên nhân thật sự khác (ví dụ sự cố hạ tầng LLM provider kéo dài), retry nội bộ
  (`max_attempts=2`) vẫn có thể không đủ; đó là giới hạn thiết kế sẵn có, không thuộc phạm vi sửa
  này.
