# Chuẩn hóa ignore cho frontend

- Ngày: 2026-09-17
- Tác giả: người yêu cầu / agent
- Nhánh: ghi nhận theo trạng thái Git hiện tại
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Ignore các file và thư mục sinh ra phổ biến trong quá trình phát triển frontend, đồng thời loại metadata `.DS_Store` khỏi repository.

## File thay đổi

- `.gitignore` — thêm rule cấp repository cho `.DS_Store`.
- `src/frontend/.gitignore` — bổ sung rule cho build output, test/tooling output, dependency, environment và log.

## Quyết định

- Giữ `.env.example` được phép track để làm mẫu cấu hình.
- Đặt `.DS_Store` ở `.gitignore` cấp repository để áp dụng cả root, `src/` và `src/frontend/`.

## Kiểm tra

- `git check-ignore -v .DS_Store src/.DS_Store src/frontend/.DS_Store src/frontend/node_modules src/frontend/.next src/frontend/.env.local src/frontend/.env.example src/frontend/tsconfig.tsbuildinfo` — pass; các mục runtime/build bị ignore, `.env.example` được giữ lại.
- `git diff --check` — pass.

## Còn lại / rủi ro

- Không có.
