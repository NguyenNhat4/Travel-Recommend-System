# README gốc là hướng dẫn setup duy nhất

- Ngày: 2026-09-24
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu `README.md` ở gốc là file hướng dẫn setup duy nhất, viết dễ hiểu và có đủ lệnh để dựng môi trường nhanh.

## File thay đổi

- `README.md` — sửa: viết lại thành các mục cần cài, setup lần đầu theo từng bước, biến môi trường cần điền, bảng lệnh chạy, việc thường ngày, bảng lỗi hay gặp và bảng cổng service.
- `src/backend/README.md` — sửa: bỏ mục "Chạy trong Docker Compose" / "Chạy trực tiếp trên máy", trỏ về README gốc; giữ phần chi tiết kết nối container.
- `src/frontend/README.md` — sửa: mục "Run Locally" trỏ về README gốc.
- `src/data_collection/README.md` — sửa: mục "Dựng database demo từ snapshot" trỏ về README gốc, giữ thông tin snapshot.

## Quyết định

- Chuẩn hoá venv ở `.venv` gốc repo: `make web` và `make chat` chỉ tìm `.venv`, nên README cũ (dùng `src/backend/.venv`) làm hai lệnh này báo lỗi.
- Bỏ ghi chú cũ "backend chưa đọc vector từ Weaviate, tự embed bằng sentence-transformers": `main.py` → `build_recsys()` đã nạp index từ Weaviate và `requirements.txt` không còn `torch`.
- Số sản phẩm snapshot ghi 11.387 theo ngưỡng `db/verify.sql`; README cũ ghi cả 11.387 lẫn 10.320.
- Thêm bước sinh `AUTH_SERVICE_TOKEN` ghi vào cả `.env` và `src/frontend/.env.local`: thiếu hoặc lệch thì web không đăng nhập được.
- Không sửa `Makefile` (đang có thay đổi dở của entry `2026-09-24-makefile-toi-gian-va-make-update.md`).

## Kiểm tra

- Chỉ sửa tài liệu; không chạy lại setup từ đầu. Đã đối chiếu từng lệnh với `Makefile`, `docker-compose.yml`, `.env.example`, `src/frontend/.env.example`, `src/frontend/package.json`.

## Còn lại / rủi ro

- Chưa chạy thử trọn quy trình setup trên máy sạch.
- `make update` không cài `src/data_collection/requirements.txt` (playwright...); seed không cần, chỉ job crawl cần — hướng dẫn crawl vẫn nằm trong README của data_collection.
