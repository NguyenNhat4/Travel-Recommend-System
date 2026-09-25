# Chuẩn hóa URL itinerary rỗng

- Ngày: 2026-09-21
- Tác giả: người yêu cầu / Codex
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Khắc phục lỗi Pydantic khiến Backend trong Docker không khởi động khi `ITINERARY_SERVICE_BASE_URL` được truyền thành chuỗi rỗng.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: chuyển URL itinerary rỗng hoặc chỉ có khoảng trắng thành `None` trước khi áp dụng validation URL.
- `history/2026-09-21-itinerary-url-empty-config.md` — thêm: ghi lại nguyên nhân và kiểm tra.

## Quyết định

- Giữ trường URL là tùy chọn: giá trị không có nội dung được chuẩn hóa về `None`; URL có nội dung vẫn phải bắt đầu bằng `http://` hoặc `https://`.
- Khi `ITINERARY_DATA_MODE=http`, kiểm tra runtime hiện có tiếp tục yêu cầu URL được cấu hình. Chế độ fixture không còn bị chặn bởi biến rỗng.
- Không đổi Compose hay OpenAPI; Compose có thể tiếp tục truyền giá trị rỗng theo mặc định.

## Kiểm tra

- `python3 -c 'import ast, pathlib; ast.parse(pathlib.Path("src/backend/app/core/config.py").read_text())'` — PASS.
- `docker compose config -q` — PASS.
- `docker compose build backend` — PASS; image `travel-recommendation-product-backend:latest` được build lại.
- `git diff --check` — PASS.
- Test tự động và khởi chạy endpoint — chưa thực hiện.

## Còn lại / rủi ro

- Chưa chạy container để xác nhận HTTP health endpoint thực tế.
