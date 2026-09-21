# Tài liệu Itinerary Agent

Tài liệu về agent lập lịch trình (LangGraph trong `src/backend/app/agents`) và bộ đánh giá qua Streamlit (`src/evaluation/agent`).

| File | Nội dung |
|---|---|
| [langgraph-nodes.md](langgraph-nodes.md) | Đọc bảng trace, chín node, các luồng thực thi |
| [response-and-errors.md](response-and-errors.md) | `status` so với `error.code`, luồng sau `UNSUPPORTED_DESTINATION` |
| [evaluation-plan.md](evaluation-plan.md) | Bộ 12 case chạy tay qua Streamlit, cách chấm, mẫu biên bản, giới hạn đã biết |

## Chạy demo

Chạy từ repo root bằng môi trường có dependencies Backend và Streamlit:

```bash
.venv/bin/python -m pip install -r src/backend/requirements.txt -r src/evaluation/requirements.txt
.venv/bin/uvicorn src.backend.app.main:app --reload --port 8000
ASSISTANT_API_BASE_URL=http://127.0.0.1:8000/api/v1 .venv/bin/python -m streamlit run src/evaluation/agent/streamlit_app.py --server.port 8502
```

Cấu hình provider/key/model trong `.env` theo Backend README. UI chat chỉ gọi FastAPI và nhận trace LangGraph an toàn bằng SSE; không import graph trong process Streamlit. FastAPI chạy graph thật qua `get_llm`; ở development, `ITINERARY_DATA_MODE=fixture` dùng 50 sản phẩm trong fixture chung. Nút gửi có thể phát sinh request/chi phí LLM; không hiển thị hoặc lưu key/JWT.

Demo yêu cầu `destination` và `days`. Nếu thiếu, backend trả `NEEDS_CLARIFICATION`, lưu phần intent đã biết theo `conversationId` và chưa gọi tool. `context.language` hỗ trợ `vi`/`en`; khi vắng mặt backend mặc định tiếng Việt và lưu lựa chọn theo conversation.

Timeout LLM của graph lấy từ `ITINERARY_LLM_TIMEOUT_SECONDS`, áp dụng cho cả `classify`, chọn điểm đến trong `tool` và `answer`; timeout tool lấy từ `ITINERARY_TOOL_TIMEOUT_SECONDS`. `.env.example` đặt 30 giây và 1 giây để model thật có thời gian phản hồi khi demo. Đây là cấu hình đánh giá offline và **vượt** ngân sách của spec §7.2 (classify 2 giây, composition 3 giây, toàn request mục tiêu 5 giây), nên không dùng số đo ở chế độ này làm bằng chứng đạt SLA. Lưu ý `ITINERARY_LLM_MODEL` trong `.env.example` không được `Settings` đọc; model thực tế là `MODEL_NAME`.
