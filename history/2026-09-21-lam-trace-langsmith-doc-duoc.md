# Làm trace LangSmith đọc được: đặt tên run và gắn request_id

- Ngày: 2026-09-21
- Tác giả: nhatutc2@gmail.com / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, docs

## Mục tiêu

Người dùng test qua Streamlit (gọi API, không import graph) và cần LangSmith để đọc input/output của từng node. Mở dashboard lên thì không đọc được.

Dựng trace thật ở local bằng một `BaseTracer` tự viết (không gửi lên LangSmith) để xem đúng cái dashboard hiện. Kết quả: **input/output từng node vốn đã đúng và đủ dùng** — `input` là toàn bộ state, `output` là đúng phần node đó thay đổi. Các node ở tầng ngoài cũng đã có tên đúng.

Vấn đề thật chỉ là **không tìm được trace của lượt vừa chạy**: mọi trace đều tên `LangGraph` và không mang `request_id` nào.

## File thay đổi

- `src/backend/app/api/v1/routes/assistant.py` — thêm `_trace_config()`; truyền `config` vào cả `ainvoke` (đường JSON) và `astream` (đường SSE mà Streamlit dùng).
- `src/backend/app/agents/graph.py` — thêm `name=` cho ba `RunnableLambda` dựng từ `partial` (`classify`, `converse`, `clarify`); sửa docstring đầu file còn ghi "nine-node" (sót từ commit 7a81fba).
- `src/backend/tests/unit/test_backend_wiring.py` — thêm `TraceConfigTests` (3 test).
- `src/backend/tests/unit/agents/test_lab_copy.py` — thêm `test_every_node_is_named_for_the_trace`.
- `docs/agent/README.md` — thêm mục "Đọc input/output từng node bằng LangSmith".

## Quyết định

- **`run_name` lấy từ chính câu người dùng gõ** (rút gọn 60 ký tự, gộp khoảng trắng). Đây là cách tìm lại lượt vừa chạy nhanh nhất khi test tay qua Streamlit: nhìn danh sách trace là thấy đúng câu mình vừa hỏi. **Không lộ thêm dữ liệu** — câu hỏi vốn đã nằm trong input của graph mà trace ghi lại. Message rỗng thì dùng `"itinerary turn"`.
- **`metadata` gồm `request_id`, `conversation_id`, `transport`, và `run_id` (chỉ đường SSE).** Đã đo: metadata đặt ở chỗ gọi **lan xuống mọi run con**, nên lọc được tới từng node. `request_id` là thứ nối trace với log backend — mọi dòng log đã ghi `requestId=`.
- **Đặt `name=` cho `RunnableLambda` thay vì bỏ `partial`.** `functools.partial` không có `__name__` nên LangChain fallback về tên class; đã kiểm riêng: `RunnableLambda(partial(f))` → `"RunnableLambda"`, thêm `name=` → `"classify_node"`. Bỏ `partial` sẽ phải đổi cách tiêm `llm`, không đáng.
- **Không sửa tầng lồng đôi** (`evaluate` → `evaluate_node`) và không bỏ run của `route_after_*`. Tầng đôi là hệ quả của việc truyền một Runnable vào `add_node` (hàm thường thì chỉ một tầng — xem node `tool`), và bản `afunc` tồn tại có lý do: `run_local` giữ node thuần khỏi bị đẩy sang worker thread. Ghi cách bỏ qua chúng vào tài liệu thay vì đổi cấu trúc.
- **Không đụng cơ chế bật/tắt tracing.** `_forward_langsmith_env` đã đúng (opt-in, 4 biến, ở composition root) và có test khoá.
- **Không cần `config` cho checkpointer**: đường API gọi `runtime.graph()` không truyền checkpointer, nên không có config sẵn để phải merge.

## Kiểm tra

- `python -m pytest -q src/backend/tests`: **147 passed, 2 skipped** (trước: 143 + 4 test mới).
- Dựng trace local sau khi sửa, xác nhận cây:
  `đi Nha Trang 2 ngày [request_id=req-abc123]` → `intake`/`classify → classify_node`/`tool`/`evaluate`/`compose`/`finalize`, `request_id` có mặt ở mọi node.
- Kiểm tên node qua `build_graph().nodes`: cả 10 node đều có tên thật, không node nào còn là `RunnableLambda`.
- **Kiểm rò rỉ JWT:** chạy graph với token giả xuyên suốt, đếm run chứa token — **0/14**. Token do `ItineraryToolGateway` giữ, không nằm trong state nên không vào trace. Đúng AGENTS.md §3.
- `validate_contract.py`: **không chạy** — không đổi contract hay mock.
- **Chưa xác nhận trên dashboard LangSmith thật.** Mọi kết luận ở trên đo bằng tracer local; chưa gửi một trace thật nào lên `api.smith.langchain.com`.

## Còn lại / rủi ro

- **Chưa chạy thật với LLM và LangSmith thật.** Tracer local không phát callback cho model (fake `ScriptedLlm`), nên chưa thấy tầng run của model nằm dưới `classify`/`converse`/`clarify`. Suy luận rằng nó nest đúng dựa trên contextvars, chưa phải quan sát.
- Streamlit hiện chỉ hiện `requestId` **khi lỗi** (`streamlit_app.py:94`). Hiện luôn cho mọi lượt sẽ giúp dò trace nhanh hơn, nhưng chưa làm vì đổi UI demo — cần người dùng quyết.
- Phát hiện ngoài phạm vi, **chưa xử lý**: không chỗ nào gọi graph theo đường đồng bộ (API, CLI, test đều `ainvoke`/`astream`). Nghĩa là bản sync của năm node gọi LLM chưa từng chạy qua graph, chỉ còn được test gọi trực tiếp. Gỡ hay giữ cần đánh giá riêng về độ phủ test.
- Các việc còn lại từ entry trước vẫn chưa làm: smoke test `clarify` với key thật; `InMemoryConversationStore` phình không giới hạn; ngân sách timeout không cộng lại được.
