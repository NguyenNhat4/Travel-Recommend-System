# Không render DeltaGenerator trong chat

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Sửa UI chat in ra biểu diễn và tài liệu rất dài của object Streamlit `DeltaGenerator` sau mỗi message dạng text.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: thay biểu thức ternary đứng riêng bằng khối `if/else` chỉ gọi hàm render.

## Quyết định

- Không để giá trị trả về của lệnh `st.markdown` thành biểu thức cuối mà Streamlit magic có thể tự render.

## Kiểm tra

- Không còn ternary render message trong source: pass.
- Streamlit `AppTest`: pass, không có exception và không có markdown chứa `DeltaGenerator`.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Không có.
