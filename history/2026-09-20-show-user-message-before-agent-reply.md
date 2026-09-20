# Hiện tin nhắn người dùng trước khi agent trả lời

- Ngày: 2026-09-20
- Tác giả: người dùng / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Trong Streamlit demo, tin nhắn người dùng chỉ hiện sau khi agent trả lời xong vì code append vào `session_state`, chặn suốt lúc stream SSE rồi mới `st.rerun()`. Cần hiện câu hỏi ngay khi gửi, phần trả lời của agent hiện sau.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: tách `run_agent()` (gọi SSE, cập nhật panel graph, trả body); `st.chat_input` đọc trước khi dựng cột; cột graph dựng trước cột chat để có placeholder; khi có prompt thì vẽ tin nhắn user ngay, rồi bubble assistant với spinner "Agent đang xử lý..." và render response khi có kết quả; bỏ `st.rerun()`.
- `history/2026-09-20-show-user-message-before-agent-reply.md` — thêm: entry này.

## Quyết định

- Render trực tiếp trong lượt chạy hiện tại thay vì rerun: tin nhắn user đã gửi tới trình duyệt trước khi bắt đầu gọi API.
- Cột graph khai báo trước cột chat trong code nhưng bố cục giữ nguyên (chat trái, graph phải), vì thứ tự cột theo `st.columns`, không theo thứ tự chạy.
- Lỗi gọi API vẫn thành một message `FALLBACK` như trước, và `conversation_id_of` giữ nguyên.
- Không đổi backend, contract hay mock; không chạy `validate_contract.py`.

## Kiểm tra

- Streamlit `AppTest` với `httpx.stream` giả: hai lượt chat chạy không exception, thứ tự message `assistant, user, assistant, user, assistant`, `conversationId` được giữ qua lượt 2.
- `git diff --check`: pass.

## Còn lại / rủi ro

- AppTest không đo được thứ tự hiển thị theo thời gian thực trong trình duyệt; cần xem trực tiếp với backend và LLM thật.
- `git status` có sẵn thay đổi `docs/agent/rubric.md` (đã xóa) từ trước, không thuộc thay đổi này.
