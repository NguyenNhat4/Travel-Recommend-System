# Fix lỗi list object has no attribute values khi trả về candidates

- Ngày: 2026-09-18
- Tác giả: nhatnm / Antigravity Agent
- Nhánh: hiện tại
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Sửa lỗi Runtime Error: `'list' object has no attribute 'values'` xảy ra ở `evaluate_node` (trong `nodes.py`) khi truy cập `candidates.values()`.

## File thay đổi

- `src/backend/app/application/itinerary/retrieval.py` — sửa: Đổi kiểu trả về của `candidates` trong hàm `collect` từ `list` sang `dict` để tương thích với các bước sau trong LangGraph.

## Quyết định

- Theo logic của `nodes.py`, biến `candidates` luôn được dùng dưới dạng dictionary (truy cập `candidates[pid]` và lặp `candidates.values()`). Tuy nhiên hàm `collect` lúc trước lại return `list(candidates.values())`. Quyết định sửa lại hàm `collect` để trả về dictionary `candidates`.

## Kiểm tra

- Chưa chạy toàn luồng nhưng đã review lại flow gọi `candidates.values()` và `state.get('candidates', {}).get(productId)` thấy đã hoàn toàn khớp kiểu dữ liệu.

## Còn lại / rủi ro

- Không có.
