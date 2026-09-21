# Giữ cố định panel LangGraph khi cuộn chat

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Giữ sơ đồ và trace LangGraph trong viewport khi lịch sử chat dài và người dùng cuộn trang.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: bọc execution panel trong container có key và áp dụng sticky responsive.

## Quyết định

- Panel sticky trên desktop với chiều cao tối đa theo viewport và thanh cuộn riêng khi cần.
- Tắt sticky dưới 768px để cột graph không che nội dung trên màn hình nhỏ.

## Kiểm tra

- Streamlit `AppTest`: pass, không có exception.
- Kiểm tra source có container `execution_panel` và CSS sticky/responsive: pass.
- `git diff --check`: pass.

## Còn lại / rủi ro

- AppTest chỉ kiểm tra render tree; cần quan sát trực tiếp trong browser để xác nhận cảm giác cuộn ở kích thước màn hình demo.
