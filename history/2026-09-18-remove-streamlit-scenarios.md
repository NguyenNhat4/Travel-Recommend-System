# Xóa cấu hình kịch bản trong Streamlit App

- Ngày: 2026-09-18
- Tác giả: nhatnm / Antigravity Agent
- Nhánh: hiện tại
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Xóa tính năng chọn kịch bản ở sidebar trong `streamlit_app.py` để giữ giao diện ở mức chat đơn giản nhất.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: Xóa đoạn code UI cấu hình kịch bản (SCENARIOS, st.sidebar.radio) và thay bằng lời chào cơ bản cố định.

## Quyết định

- Bỏ qua mock theo context và cố định sử dụng file json default (`searchProducts.200-default.json`) cho mock search data để luồng chat diễn ra tự nhiên.

## Kiểm tra

- Chưa chạy.

## Còn lại / rủi ro

- Do bỏ cấu hình mock nên các ca test fallback, thiếu thông tin (TH2, TH3) trước đây sẽ không thể chọn mock data từ file empty nữa, Agent sẽ tự handle bằng file default hoặc bằng LLM validation.
