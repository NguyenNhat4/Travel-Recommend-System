# Neo cột LangGraph theo viewport

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Giữ toàn bộ bảng LangGraph execution cố định trong viewport khi lịch sử hội thoại bên trái dài.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: chuyển sticky từ container con lên đúng cột Streamlit chứa execution panel.

## Quyết định

- Chọn cột bằng `:has(.st-key-execution_panel)` thay vì phụ thuộc thứ tự cột, tránh tác động sidebar hoặc layout khác.
- Dùng `align-self: flex-start` để sticky hoạt động trong horizontal flex layout; panel có scroll riêng khi cao hơn viewport.
- Trên màn hình tối đa 768px, cột trở lại static để không che nội dung chat.

## Kiểm tra

- Streamlit `AppTest`: pass, không có exception.
- Source có selector cột chứa execution panel, sticky desktop và static mobile: pass.
- `git diff --check`: pass.

## Còn lại / rủi ro

- AppTest không mô phỏng scroll trình duyệt; cần reload browser và thử với hội thoại dài để xác nhận hành vi trực quan.
