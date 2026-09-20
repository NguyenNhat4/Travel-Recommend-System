# Cập nhật giao diện chat cho Streamlit Agent App

- Ngày: 2026-09-18
- Tác giả: nhatnm / Antigravity Agent
- Nhánh: hiện tại
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Chuyển đổi giao diện tĩnh (chạy kịch bản 1 lần qua nút bấm) của Streamlit App sang dạng chat liên tục sử dụng `st.chat_input`, cho phép người dùng trò chuyện tương tác với LangGraph agent.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: Đổi luồng sử dụng `st.button` thành `st.chat_input` và thêm câu chào mặc định.

## Quyết định

- Thay thế nút bấm "Chạy Agent" bằng `st.chat_input`.
- Giữ lại các kịch bản test ở sidebar, khi đổi kịch bản sẽ reset conversation về một tin nhắn chào của AI để mồi input thay vì nhét thẳng input của kịch bản thành message đầu tiên chưa có ai trả lời.
- LangGraph graph đã có sẵn `memory checkpointer` qua thread_id, nên luồng chat mới vẫn giữ nguyên state qua các turn chat.

## Kiểm tra

- Chưa chạy.

## Còn lại / rủi ro

- Không có.
