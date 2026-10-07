# Đo latency_ms thật cho từng node của Itinerary Agent

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: fix/agent-node-latency
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Trong LangGraph Studio, `events[*].latency_ms` của mọi node luôn là 0. Nguyên nhân: `LabEvent.latency_ms` mặc định 0 và `make_event`/`event` không bao giờ truyền giá trị. Cần đo thời gian chạy thật của từng node để biết node nào chậm (NFR-PERF-02).

## File thay đổi

- `src/backend/app/agents/graph.py` — sửa: thêm `timed()` bọc mọi node (sync và async), ghi `latency_ms` (ms, tối thiểu 1) vào các event node trả về; event đã tự có `latency_ms` thì giữ nguyên.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: test mọi event có `latency_ms >= 1`, node `tool` với client chậm 50 ms đo được `>= 50`.
- `docs/spec/agent/langgraph-nodes.md` — sửa: §4 mô tả `durationMs` của SSE nay là thời gian chạy của chính node.

## Quyết định

- Đo ở một chỗ (`build_graph`) thay vì sửa 12 node: node giữ nguyên, node mới tự được đo.
- Đo wall-clock bằng `perf_counter`, gồm cả thời gian chờ LLM/tool — đó là thứ cần nhìn khi tìm node chậm.
- Route SSE (`api/v1/routes/assistant.py`) vốn đã ưu tiên `latency_ms` hơn thời gian quan sát, nên `durationMs` tự chuyển sang số đo thật, không phải sửa route và contract (`durationMs` vẫn là integer ms).
- Không lệch PRD: `latency_ms` đã có trong `LabEvent`, PRD không quy định cách đo theo node.

## Kiểm tra

- `pytest src/backend/tests/architecture src/backend/tests/unit/agents src/backend/tests/contract/test_assistant_contract.py`: 367 passed.
- Tên node trong trace giữ nguyên (`test_every_node_is_named_for_the_trace` pass; `tool` vẫn là `tool`).

## Còn lại / rủi ro

- `durationMs` trên SSE nay không còn gồm overhead cập nhật state giữa các node; tổng các `durationMs` có thể nhỏ hơn `latency_ms` của cả lượt một chút.
