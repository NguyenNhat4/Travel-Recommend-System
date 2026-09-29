# Thêm Frontend vào Docker Compose local

- Ngày: 2026-09-28
- Tác giả: Người yêu cầu / Codex
- Nhánh: `khoa/frontend-vercel-to-vm`
- Trạng thái: hoàn thành phần build và chạy Frontend local; chưa xác nhận tích hợp Backend
- Phạm vi: frontend, CI/CD

## Mục tiêu

Cho phép build image Next.js Frontend và chạy Frontend cùng Backend/Redis trong Docker Compose local, giữ nguyên `make web`.

## File thay đổi

- `.dockerignore` — sửa: đưa Frontend vào build context; loại `.env`, thư mục `secrets` và file PEM khỏi context.
- `docker-compose.yml` — sửa: thêm service `frontend`, nối BFF tới `backend:8000` và Redis, publish cổng local 3000.
- `src/frontend/Dockerfile.web` — sửa: build từ repo root để cung cấp `src/shared/mocks`, cấu hình standalone server dùng cổng 3000.
- `README.md` — sửa: thêm lệnh build/chạy Frontend bằng Compose.
- `history/2026-09-28-frontend-compose-build.md` — thêm: ghi nhận quyết định và kiểm tra.

## Quyết định

- Giữ `make web` chạy theo cách hiện tại; người dùng có thể chọn lệnh Compose riêng.
- `docker compose build frontend` build Next.js từ standalone output. Build context là repo root vì TypeScript trong frontend tests tham chiếu fixtures tại `src/shared/mocks`.
- Frontend cùng Docker network với Backend và Redis; BFF gọi `http://backend:8000`, session dùng Redis DB 1.
- Chỉ bind cổng frontend vào loopback host (`127.0.0.1`) trong Compose local.
- Không đổi API, luồng người dùng hoặc nội dung PRD.

## Kiểm tra

- `docker compose config -q` — PASS.
- `docker compose config --services` — PASS; có `frontend`.
- Lần `docker compose build frontend` đầu — FAIL do build context frontend không chứa `src/shared/mocks` cần khi Next.js kiểm tra TypeScript.
- Sau khi chuyển context về repo root và cập nhật Dockerfile: `docker compose build frontend` — PASS; image `travel-recommendation-product-frontend:latest` được tạo.
- Build context đo được khoảng 6.48 MB; `.dockerignore` loại `node_modules`, `.next`, `.env*` và `secrets`.
- Container Frontend publish `127.0.0.1:3000->3000/tcp`; `curl http://127.0.0.1:3000/` — HTTP 200 sau khi recreate container để áp port mapping.
- `git diff --check` — PASS.
- Không chạy test ứng dụng. Backend vẫn ở trạng thái `Created` và Weaviate `unhealthy` khi kiểm tra; chưa xác nhận các chức năng cần API.

## Còn lại / rủi ro

- `make web` vẫn chạy Backend/Next.js trực tiếp trên host theo yêu cầu; Compose là đường chạy Docker riêng.
- Chưa kiểm tra runtime tích hợp Frontend → Backend/Redis.
