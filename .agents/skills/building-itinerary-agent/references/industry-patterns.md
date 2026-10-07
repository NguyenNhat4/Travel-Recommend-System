# Thực hành ngành khi xây agent và chỗ chúng nằm trong repo

Đọc file này khi thêm node, tool, bước LLM hoặc kiểu hiển thị mới. Mỗi mục gồm: thực hành, nguồn, chỗ đã có trong repo,
và câu hỏi cần trả lời trước khi thêm.

## Mục lục

1. Workflow trước agent
2. Thiết kế tool
3. Context engineering
4. Đầu ra có cấu trúc, kiểm và dự phòng
5. Guardrail nhiều tầng
6. Eval
7. Generative UI an toàn
8. Trả kết quả từng phần sớm
9. Tự sở hữu prompt và state

## 1. Workflow trước agent

Dùng giải pháp đơn giản nhất chạy được. Chuỗi bước cố định thì dễ kiểm hơn vòng lặp để LLM tự quyết.
Nguồn: [Anthropic, Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

- **Trong repo:** graph cố định (`agents/graph.py`). LLM chỉ ở `classify`, `extract`, lập tool plan, `clarify`, `converse`
  và `narrate`. `compose` và `finalize` là luật.
- **Trước khi thêm lời gọi LLM:** việc này luật làm được không? Mỗi lời gọi LLM nối tiếp cộng thêm vài giây. Golden
  2026-09-24 đo được p50 6,0 s và p95 11,3 s, trong khi NFR-PERF-02 đặt tổng ≤ 4 s.

## 2. Thiết kế tool

Ít tool, tên rõ, tham số được kiểm, lỗi trả mã đọc được thay vì exception thô.
Nguồn: [Anthropic, Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents).

- **Trong repo:** allowlist và validate ở `agents/tools/itinerary_gateway.py`, hợp đồng tool ở
  `application/itinerary/tool_contracts.py`, lỗi engine map thành `ToolError` ở `engine_tools.py`.
- **Trước khi thêm tool:** tool cũ thêm một tham số có đủ không? Output của tool có khớp response của route tương ứng không?

## 3. Context engineering

Đưa LLM lượng ngữ cảnh nhỏ nhất mà có tín hiệu cao. Tóm tắt thay vì đổ nguyên lịch sử. Ngữ cảnh là dữ liệu không tin cậy.
Nguồn: [Anthropic, Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).

- **Trong repo:** `agents/steps/history.py` `llm_context`: một dòng tóm tắt chuyến đi, tin trợ lý cũ thành ghi chú ngắn,
  lịch sử giới hạn 20 tin và 8.000 ký tự (spec itinerary §6).
- **Trước khi thêm field vào prompt:** đưa dạng đã diễn giải (ngày dd/mm/yyyy, nhãn tiếng Việt), không đổ payload thô.

## 4. Đầu ra có cấu trúc, kiểm và dự phòng

LLM viết chữ và **tham chiếu** dữ kiện; code điền và kiểm dữ kiện; LLM lỗi thì có bản dựng bằng luật.

- **Trong repo:** `narration.py`.
  - LLM nhắc sản phẩm bằng `[Tên](product:id)` và ghi giá bằng `[[price:id]]`.
  - Backend thay tên canonical, chặn id lạ và số tiền tự viết.
  - `fallback_message` dựng cùng bố cục bằng luật.
- **Trước khi cho LLM viết dữ kiện mới** (giờ, khoảng cách, điểm đánh giá): cho LLM placeholder, để code điền từ dữ liệu thật.

## 5. Guardrail nhiều tầng

Luật rẻ chạy trước, phân loại bằng LLM sau, rồi kiểm đầu ra; giới hạn tần suất ở biên.
Nguồn: [OpenAI, A practical guide to building agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf).

- **Trong repo:**
  - tầng 1 bằng luật ở `agents/steps/guardrails.py` (NFR-SEC-04);
  - `classify` từ chối ngoài phạm vi;
  - `finalize` kiểm OpenAPI và grounding;
  - rate limit ở route.
- **Trước khi thêm chặn mới:** chặn bằng luật được không, trước khi trả tiền cho một lời gọi LLM?

## 6. Eval

Bắt đầu từ lỗi thật. Grader bằng code rẻ và lặp lại được. Đo độ ổn định (pass^k). Tách bộ năng lực khỏi bộ hồi quy, và
đọc transcript chứ không chỉ nhìn số.
Nguồn: [Anthropic, Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

- **Trong repo:** golden dataset và runner (`src/evaluation/agent/golden.py`), `--repeat`, `--trace-project`;
  quy trình ở [eval-loop.md](eval-loop.md).
- **Trước khi kết luận "đã sửa":** case fail trên code cũ, và pass trên code mới chưa? (Case chập chờn thì đo thêm bằng `--repeat`.)

## 7. Generative UI an toàn

Agent chỉ yêu cầu component từ một danh mục đã duyệt, kèm dữ liệu. Client render bằng component của mình, không chạy
HTML hay code do model sinh.
Nguồn: [A2UI](https://a2ui.org/) ([Google Developers Blog](https://developers.googleblog.com/introducing-a2ui-an-open-project-for-agent-driven-interfaces/)).

- **Trong repo:**
  - LLM nhắc `productId`; widget render `ProductCard` và thẻ lịch trình từ `product` của response.
  - `hop-dong-tich-hop-frontend.md` §9.5: tên, ảnh, giá không bao giờ lấy từ `note` hay `title`.
- **Trước khi thêm kiểu hiển thị:** dữ liệu đến từ field nào của response? Thiếu field thì sửa contract hoặc backend,
  không suy từ chữ của LLM (ví dụ: chọn ảnh theo từ khoá trong ghi chú là sai).

## 8. Trả kết quả từng phần sớm

Stream trạng thái hoặc kết quả trung gian để người dùng không chờ trắng.
Nguồn: [LangGraph, Streaming](https://docs.langchain.com/oss/python/langgraph/streaming).

- **Trong repo:** SSE `node.completed` chỉ mang tiến trình. Kết quả có ở `run.completed`.
- **Trước khi stream thêm:** chỉ stream phần đã qua kiểm grounding, ví dụ lịch trình sau `compose`. Không stream token LLM
  chưa được backend kiểm. Sự kiện mới phải vào `AssistantStreamEvent` trong contract trước.

## 9. Tự sở hữu prompt và state

Prompt là code của mình, có version và test. State là dữ liệu có kiểu; node đọc state và trả phần thay đổi.
Nguồn: [12-Factor Agents](https://github.com/humanlayer/12-factor-agents).

- **Trong repo:** prompt ở `agents/steps/prompts.py` (có thể đẩy lên LangSmith Prompt Hub), `AgentState` typed
  (`agents/state.py`, `docs/spec/agent/state-fields.md`).
- **Trước khi thêm field state:** ghi node nào ghi và node nào đọc vào `state-fields.md`.
