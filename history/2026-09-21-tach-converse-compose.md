# Tách `answer` thành `converse` + `compose` và viết lại tài liệu node

- Ngày: 2026-09-21
- Tác giả: nhatutc2@gmail.com / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, docs
- Thay thế: `2026-09-21-tach-clarify-khoi-answer.md` (phần việc còn lại: `answer` vẫn gộp nhánh LLM với nhánh dựng kết quả)

## Mục tiêu

Người dùng cho biết chưa tự giải thích lại được các node của graph, và hỏi thẳng: "finalize làm gì, tại sao nhiều route đều có nó?". Qua trao đổi lộ ra hai nguyên nhân:

1. Node `answer` gộp hai việc không liên quan — trò chuyện (gọi LLM, có timeout) và dựng kết quả (code thuần). Nhìn trace chỉ thấy một chữ `answer` nên không nói gọn được node đó làm gì.
2. `docs/agent/langgraph-nodes.md` viết theo kiểu bảng tra cứu 9 dòng phẳng, trả lời được "node X làm gì" nhưng không trả lời "vì sao graph chia như vậy" — đúng câu người dùng vướng.

## File thay đổi

- `src/backend/app/agents/nodes.py` — sửa: `answer_node`/`answer_node_async` → `converse_node`/`converse_node_async` (chỉ còn nhánh hội thoại); thêm `compose_node` (thuần sync); xoá `_needs_conversational_answer` và `_answer_message`; `_non_compose` → `_retrieval_outcome` và bỏ nhánh `refusal` đã chết; docstring đầu file 9 → 10 node.
- `src/backend/app/agents/routing.py` — sửa: `simple` → `converse`; mặc định của `route_after_evaluate` → `compose`; nhánh fallback của `route_after_retry` → `compose`.
- `src/backend/app/agents/graph.py` — sửa: đăng ký `converse` (có LLM + timeout) và `compose` (qua `run_local`); hai cạnh tới `finalize`; ba mapping conditional.
- `src/backend/app/agents/report.py` — sửa: mục 2 mô tả topology theo tên node mới.
- `src/backend/tests/unit/agents/test_routing.py` — sửa: kỳ vọng ba nhánh.
- `src/backend/tests/unit/agents/test_lab_copy.py` — sửa: `test_nine_node_topology` → `test_ten_node_topology`, tập node 10 phần tử; thêm `compose_node` vào test bất biến state.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: chuỗi node của lời chào → `converse`; thêm assert luồng `COMPLETED` đi qua `compose`.
- `docs/agent/langgraph-nodes.md` — viết lại toàn bộ: bốn giai đoạn, mục riêng giải thích `finalize` là cửa ra duy nhất, sáu ví dụ từ câu người dùng gõ, bảng tra cứu chuyển xuống cuối.
- `docs/agent/README.md` — sửa: dòng mục lục; timeout LLM áp dụng cho `converse`.
- `docs/agent/response-and-errors.md` — sửa: ví dụ luồng `answer` → `compose`.
- `docs/agent/evaluation-plan.md` — sửa: trace kỳ vọng của case 01, ghi rõ case 06/12 đi qua `converse` và case 07 đi qua `clarify`, mục 8 đổi `answer` → `compose`.

## Quyết định

- **Ranh giới tách sạch nên không cần thêm điều kiện nào.** Ba đường vào `answer` vốn đã chia đúng theo hai nhóm việc: route `simple` từ `classify` luôn là hội thoại, còn hai đường từ `evaluate`/`retry` luôn là dựng kết quả. Tách chỉ là đổi đích ba nhánh routing.
- **`compose_node` không có bản async.** Bản `answer_node_async` cũ đã ghi trong comment rằng nhánh này thuần tính toán, không có gì để `await`. Nay đăng ký qua `run_local` như `evaluate`, xoá được một cặp sync/async trùng nhau.
- **Xoá `_needs_conversational_answer`.** Routing đã quyết định node nào chạy; để node tự đoán lại là hai nguồn sự thật cho cùng một quyết định.
- **Bỏ nhánh `refusal` trong `_retrieval_outcome`.** Nhánh này đã chết từ thay đổi trước (`_needs_conversational_answer` luôn bắt `refusal` trước). Sau khi tách, `refusal` thuộc hẳn `converse`.
- **Đổi tên `_non_compose` → `_retrieval_outcome`** vì tên cũ mô tả cái hàm *không* làm.
- **Không phải thay đổi contract.** Đã kiểm trước khi làm: `AssistantStreamEvent.data` là `additionalProperties: true` nên không có enum `nodeId`; `_topology` ở `api/v1/routes/assistant.py` sinh danh sách node từ chính graph; `graph_dot` trong Streamlit vẽ theo topology nhận được. Vì vậy thêm/đổi tên node không cần đụng OpenAPI và không cần sửa Streamlit. Không chạy `validate_contract.py` vì không có file contract hay mock nào thay đổi.
- **Tài liệu viết lại theo ý đồ thiết kế, không chỉ liệt kê.** Phần `finalize` giải thích bằng ẩn dụ cổng an ninh sân bay, kèm mục "nếu không có finalize thì sao" và điểm dễ nhầm là nó có quyền phủ quyết (`ITINERARY_VALIDATION_FAILED`). Bảng tra cứu vẫn giữ nhưng chuyển xuống cuối.
- **Giữ nguyên mọi cảnh báo cũ trong tài liệu**: `completed` của node không phải PASS của evaluation; `durationMs` là latency quan sát tại biên SSE; trace chạy fixture không chứng minh SLA production. Không thêm tuyên bố mới nào về latency.

## Kiểm tra

- `python -m pytest -q src/backend/tests`: **143 passed, 2 skipped** — bằng đúng số trước thay đổi, đúng kỳ vọng của một refactor.
- Kiểm topology thật bằng `build_graph().get_graph()`: 10 node (`clarify`, `classify`, `compose`, `converse`, `dead_letter`, `evaluate`, `finalize`, `intake`, `retry`, `tool`), và đúng 4 cạnh vào `finalize` (`clarify`, `compose`, `converse`, `dead_letter`).
- `grep` toàn `src/` và `docs/`: không còn tham chiếu `answer_node`, `_non_compose`, `_needs_conversational_answer`, `_answer_message`, và không còn tên node `answer` trong tài liệu.
- `validate_contract.py`: **không chạy** — không thay đổi contract hay mock (lý do ở mục Quyết định).
- **Chưa chạy demo Streamlit với LLM thật.** Chưa xác nhận bằng mắt rằng panel graph hiện 10 node và ba ví dụ (chào hỏi → `converse`, thiếu điểm đến → `clarify`, lịch trình đầy đủ → `compose`) khớp tài liệu.

## Còn lại / rủi ro

- **Chưa smoke test qua Streamlit.** Suy luận rằng panel tự nhận 10 node dựa trên việc đọc code `_topology`/`graph_dot`, chưa phải quan sát thật.
- Bản sync và async của `converse` và `clarify` vẫn lặp code; chỉ `compose` thoát được vì nó thuần.
- Các việc còn lại từ entry trước vẫn chưa làm: chất lượng câu chữ của `clarify` chưa smoke test với key thật; `InMemoryConversationStore` vẫn phình không giới hạn; ngân sách timeout vẫn không cộng lại được.
- `interests`, `party`, `pace` vẫn không ảnh hưởng tới việc `compose` chọn sản phẩm nào — hạn chế đã ghi ở `2026-09-21-deterministic-itinerary-composition.md`, không thuộc phạm vi thay đổi này.
