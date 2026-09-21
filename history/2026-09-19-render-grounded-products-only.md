# Chỉ render sản phẩm có thật trong lịch trình

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Phần hiển thị chính của chat chỉ cho người dùng thấy sản phẩm được grounding từ catalog; không render các slot tổng quát có `product=null` như ăn uống, nghỉ ngơi, di chuyển hoặc thời gian tự do.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: lọc slot có product, render card sản phẩm/stay, bỏ ngày không có sản phẩm và chỉ hiện tổng khi backend tính được.

## Quyết định

- Card chỉ dùng dữ liệu API của ProductSummary/ProductDetail: tên, taxonomy, destination, ảnh, giá, ghi chú và URL nguồn nếu có.
- Slot `product=null` và ngày chỉ chứa activity note không xuất hiện trong phần chính; vẫn có trong JSON debug đóng mặc định.
- Warning về snapshot giá/khả dụng nằm trong expander riêng để giữ cảnh báo an toàn mà không lấn át danh sách sản phẩm.

## Kiểm tra

- Streamlit `AppTest` với COMPLETED response: hiện sản phẩm thật, không hiện FREE_TIME/REST và không hiện ngày rỗng.
- Python compile: pass.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Fixture chứng minh sản phẩm có trong catalog mẫu, không chứng minh tồn kho thật tại thời điểm đặt.
