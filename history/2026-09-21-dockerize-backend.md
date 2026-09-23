# Đưa Backend vào Docker Compose

- Ngày: 2026-09-21
- Tác giả: người yêu cầu / Codex
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Đóng gói FastAPI Backend vào Docker để chạy cùng PostgreSQL qua Docker Compose và cập nhật Makefile, đồng thời giữ lệnh chạy Uvicorn trực tiếp cho phát triển.

## File thay đổi

- `.dockerignore` — thêm: loại dependency, cache và workstream không cần khỏi build context.
- `Dockerfile.backend` — thêm: image Python 3.11, cài PyTorch CPU, chạy Backend bằng user không phải root.
- `docker-compose.yml` — sửa: thêm Backend, healthcheck, DSN nội bộ Compose và volume cache.
- `Makefile` — sửa: `backend` chạy Compose; thêm `backend-build`, `backend-logs`, `backend-stop`, `backend-local`.
- `README.md` — sửa: hướng dẫn khởi chạy Backend bằng Docker và chạy local với reload.
- `src/backend/README.md` — sửa: hướng dẫn môi trường Compose, DSN theo hostname `postgres`, cache và quy trình seed.
- `history/2026-09-21-dockerize-backend.md` — thêm: ghi nhận quyết định và kiểm tra của task.

## Quyết định

- Backend đợi PostgreSQL healthy; Compose vẫn dùng hai DSN và hai role giới hạn riêng, không cấp quyền seed cho ứng dụng.
- Mặc định itinerary dùng fixture. Nếu chuyển sang HTTP, phải cấu hình `BACKEND_ITINERARY_SERVICE_BASE_URL` thay vì âm thầm trỏ URL về chính Backend.
- Cache embedding và Hugging Face được giữ trong named volume. `backend-stop` chỉ dừng Backend, không dừng PostgreSQL hay xóa dữ liệu.
- `backend-local` giữ luồng reload trên máy. Backend không tự seed hoặc reset database khi khởi động; dùng `make demo-db` khi cần catalog demo.
- Không đổi API/OpenAPI. Image cài PyTorch CPU để tránh tải các wheel CUDA không cần cho container này.

## Kiểm tra

- `docker compose config -q && docker compose config --services` — PASS; có `postgres` và `backend`.
- `make -n backend backend-build backend-logs backend-stop backend-local` — PASS; các target sinh đúng lệnh dự kiến.
- `docker compose build backend` — PASS; image `travel-recommendation-product-backend:latest` được tạo, dependency dùng `torch 2.14.0+cpu`.
- `git diff --check` — PASS.
- Test tự động — chưa chạy; không có thay đổi logic ứng dụng và task không yêu cầu chạy test.
- Chưa khởi chạy service hoặc kiểm tra endpoint HTTP thực tế.

## Còn lại / rủi ro

- `make backend` khởi động Backend cùng PostgreSQL nhưng không nạp catalog; chạy `make demo-db` trước khi dùng search/recommendation với dữ liệu demo.
- Lần chạy đầu có thể cần tải model embedding; các volume cache giữ dữ liệu giữa những lần chạy.
