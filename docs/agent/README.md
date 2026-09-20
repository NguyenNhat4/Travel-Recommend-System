# Tài liệu Itinerary Agent

Tài liệu về agent lập lịch trình (LangGraph trong `src/backend/app/agents`) và bộ đánh giá qua Streamlit (`src/evaluation/agent`).

| File | Nội dung |
|---|---|
| [langgraph-nodes.md](langgraph-nodes.md) | Đọc bảng trace, chín node, các luồng thực thi |
| [response-and-errors.md](response-and-errors.md) | `status` so với `error.code`, luồng sau `UNSUPPORTED_DESTINATION` |
| [evaluation-suite.md](evaluation-suite.md) | Chạy case/batch, cách chấm, fixture còn thiếu, kiểm tra local |
| [fixture-generation.md](fixture-generation.md) | Sinh fixture và expected bằng LLM |
| [rubric.md](rubric.md) | Rubric chấm nhanh agent |

## Chạy demo

Chạy từ repo root bằng môi trường có dependencies Backend và Streamlit:

```bash
.venv/bin/python -m pip install -r src/backend/requirements.txt -r src/evaluation/requirements.txt
.venv/bin/uvicorn src.backend.app.main:app --reload --port 8000
ASSISTANT_API_BASE_URL=http://127.0.0.1:8000/api/v1 .venv/bin/python -m streamlit run src/evaluation/agent/streamlit_app.py --server.port 8502
```

Cấu hình provider/key/model trong `.env` theo Backend README. UI chat chỉ gọi FastAPI và nhận trace LangGraph an toàn bằng SSE; không import graph trong process Streamlit. FastAPI chạy graph thật qua `get_llm`; ở development, `ITINERARY_DATA_MODE=fixture` dùng 50 sản phẩm trong fixture chung. Nút gửi có thể phát sinh request/chi phí LLM; không hiển thị hoặc lưu key/JWT.

Demo yêu cầu `destination` và `days`. Nếu thiếu, backend trả `NEEDS_CLARIFICATION`, lưu phần intent đã biết theo `conversationId` và chưa gọi tool. `context.language` hỗ trợ `vi`/`en`; khi vắng mặt backend mặc định tiếng Việt và lưu lựa chọn theo conversation.

Runner từng case/batch và custom chat chờ tối đa 30 giây cho mỗi lời gọi LLM (classify, planner, composition), để model thật có thời gian phản hồi. Timeout tool vẫn là 1 giây. Đây là cấu hình đánh giá offline; API giữ giới hạn classify/planner 2 giây và composition 3 giây. Không dùng kết quả này làm bằng chứng đạt SLA 5 giây của API.
