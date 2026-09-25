# Render sản phẩm trong fallback của Agent

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Khi Agent không dựng được lịch trình đã kiểm tra nhưng đã retrieval được sản phẩm thật, UI phải hiển thị `searchResults` trong response `FALLBACK` thay vì chỉ hiện câu cảnh báo.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: gom và render card sản phẩm fallback, loại trùng theo `productId`.

## Quyết định

- Chỉ render item thực sự có `productId` trong `searchResults` do API trả về.
- Không suy diễn lịch trình hoặc tạo activity mới từ các ứng viên fallback.
- Giữ message cảnh báo của backend ở trên danh sách để người dùng hiểu đây là ứng viên tham khảo, chưa phải lịch trình hoàn chỉnh.

## Kiểm tra

- Streamlit `AppTest` với FALLBACK response: hiện message, số lượng và tên sản phẩm; item trùng chỉ xuất hiện một lần.
- Python compile: pass.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Log cho thấy nguyên nhân fallback hiện tại là composition chọn `product_id` không hợp lệ; UI đã suy giảm đúng, còn chất lượng composition cần xử lý riêng.
