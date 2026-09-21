# Tài liệu Itinerary Agent

Tài liệu về agent lập lịch trình (LangGraph trong `src/backend/app/agents`) và bộ đánh giá qua Streamlit (`src/evaluation/agent`).

| File | Nội dung |
|---|---|
| [langgraph-nodes.md](langgraph-nodes.md) | Vì sao graph chia thành mười node, vì sao mọi nhánh qua `finalize`, cách đọc bảng trace |
| [response-and-errors.md](response-and-errors.md) | `status` so với `error.code`, luồng sau `UNSUPPORTED_DESTINATION` |
| [evaluation-plan.md](evaluation-plan.md) | Bộ 12 case chạy tay qua Streamlit, cách chấm, mẫu biên bản, giới hạn đã biết |

## Chạy demo

Chạy từ repo root bằng môi trường có dependencies Backend và Streamlit:

```bash
.venv/bin/python -m pip install -r src/backend/requirements.txt -r src/evaluation/requirements.txt
.venv/bin/uvicorn src.backend.app.main:app --reload --port 8000
ASSISTANT_API_BASE_URL=http://127.0.0.1:8000/api/v1 .venv/bin/python -m streamlit run src/evaluation/agent/streamlit_app.py --server.port 8502
```

Cấu hình provider/key/model trong `.env` theo Backend README. UI chat chỉ gọi FastAPI và nhận trace LangGraph an toàn bằng SSE; không import graph trong process Streamlit. FastAPI dựng **một** client LLM dùng chung trong `lifespan` (`infrastructure/llm/build_chat_model`) và tiêm vào graph qua `app.state.itinerary_llm`; provider chọn theo key có mặt, thứ tự Gemini → OpenAI → Anthropic. `ITINERARY_USE_LLM=false` thì không client nào được dựng: app vẫn khởi động không cần API key, `/assistant/status` trả `llmMode=disabled` và mọi request itinerary trả 503 `LLM_UNAVAILABLE`. Ở development, `ITINERARY_DATA_MODE=fixture` dùng 50 sản phẩm trong fixture chung. Nút gửi có thể phát sinh request/chi phí LLM; không hiển thị hoặc lưu key/JWT.

Demo yêu cầu `destination` và `days`. Nếu thiếu, backend trả `NEEDS_CLARIFICATION`, lưu phần intent đã biết theo `conversationId` và chưa gọi tool. `context.language` hỗ trợ `vi`/`en`; khi vắng mặt backend mặc định tiếng Việt và lưu lựa chọn theo conversation.

Timeout LLM của graph lấy từ `ITINERARY_LLM_TIMEOUT_SECONDS`, áp dụng cho cả `classify`, chọn điểm đến trong `tool`, `clarify` và `converse`; timeout tool lấy từ `ITINERARY_TOOL_TIMEOUT_SECONDS`. `.env.example` đặt 30 giây và 1 giây để model thật có thời gian phản hồi khi demo. Đây là cấu hình đánh giá offline và **vượt** ngân sách của spec §7.2 (classify 2 giây, composition 3 giây, toàn request mục tiêu 5 giây), nên không dùng số đo ở chế độ này làm bằng chứng đạt SLA. `ITINERARY_LLM_MODEL` và `ITINERARY_USE_LLM` nay **được** `Settings` đọc; bỏ trống `ITINERARY_LLM_MODEL` thì OpenAI dùng `MODEL_NAME`, các provider khác dùng mặc định của mình. Nhiệt độ của agent lấy từ `ITINERARY_LLM_TEMPERATURE` (mặc định 0), không dùng chung `LLM_TEMPERATURE`.

## Đọc input/output từng node bằng LangSmith

Bảng trace trong Streamlit chỉ cho biết node nào đã chạy và mất bao lâu; nó **không** hiển thị state, prompt hay payload nội bộ. Muốn xem input/output thật của từng node thì bật LangSmith trong `.env` (`LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY`) rồi chạy demo như thường. Lưu ý: bật là gửi prompt và dữ liệu người dùng lên `LANGSMITH_ENDPOINT`, chỉ dùng ở môi trường dev cá nhân.

Mỗi lượt sinh ra một trace **đặt tên theo chính câu bạn gõ**, nên tìm lại đúng lượt vừa chạy trong danh sách là được ngay:

```text
đi Nha Trang 2 ngày            ← trace gốc, metadata: request_id, conversation_id, transport, run_id
  intake → intake_node
  classify → classify_node     ← run con là lời gọi LLM thật
  tool
  evaluate → evaluate_node
  compose → compose_node
  finalize → finalize_node
```

Cách đọc:

- **Mở run ở tầng ngoài** (`classify`, `compose`...) để xem input/output của node. `input` là toàn bộ state tại thời điểm đó; `output` chỉ là **phần node đó thay đổi**, nên nhìn output là biết ngay node vừa làm gì.
- **Run con cùng tên hàm** (`classify_node`) là lớp bọc sync/async, nội dung trùng với run cha. Dưới nó mới là lời gọi model thật khi node có dùng LLM.
- `route_after_classify` và `route_after_evaluate` là hàm chọn nhánh, không phải node; bỏ qua khi đọc.
- **Lọc theo `request_id`** để nối trace với log backend — mọi dòng log của lượt đó đều ghi `requestId=`. Metadata này có ở mọi run con, nên lọc được tới từng node.

`transport` trong metadata cho biết lượt đó đi đường nào: `sse` là Streamlit, `json` là gọi thẳng `POST /assistant/itineraries`.
