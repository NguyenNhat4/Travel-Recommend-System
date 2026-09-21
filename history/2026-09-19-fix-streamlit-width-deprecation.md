# Sửa cảnh báo width của Streamlit

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Loại bỏ cảnh báo `use_container_width` đã deprecated khi chạy UI demo trên Streamlit hiện hành.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: thay `use_container_width=True` bằng `width="stretch"` cho button, graph và dataframe.

## Quyết định

- Dùng API `width="stretch"` theo hướng dẫn runtime; không thay đổi layout hoặc hành vi của UI.

## Kiểm tra

- Tìm kiếm `use_container_width` trong UI: không còn kết quả.
- Streamlit `AppTest`: pass, không có exception.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Không có.
