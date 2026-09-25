# Fix lỗi 503 do Timeout khi chạy LLM trong Streamlit

- Ngày: 2026-09-18
- Tác giả: nhatnm / Antigravity Agent
- Nhánh: hiện tại
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Sửa lỗi HTTP 503 (LLM_UNAVAILABLE) khi người dùng chat trên Streamlit app do thời gian chờ mặc định quá ngắn.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: Tăng tham số timeout cho LangGraph.

## Quyết định

- Khai báo hàm `build_graph` mặc định `llm_timeout_seconds` bị `None` và fallback về 2 giây trong `nodes.py`. Khi gọi API OpenAI tốn hơn 2 giây, hàm `classify` sẽ quăng TimeoutError và dẫn đến trạng thái 503 LLM_UNAVAILABLE.
- Quyết định truyền rõ `llm_timeout_seconds=10.0` và `tool_timeout_seconds=10.0` vào hàm `build_graph()` bên trong `streamlit_app.py` để LLM có đủ thời gian phản hồi.

## Kiểm tra

- Đã test LLM API key hoạt động bằng kịch bản test_llm riêng. Chờ người dùng verify lại trên giao diện.

## Còn lại / rủi ro

- Không có.
