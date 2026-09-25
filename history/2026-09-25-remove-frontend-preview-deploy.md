# Bỏ deploy Preview của frontend

- Ngày: 2026-09-25
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev`
- Trạng thái: hoàn thành phần workflow và kiểm tra local; chưa chạy GitHub Actions thật
- Phạm vi: frontend, CI/CD

## Mục tiêu

Không tạo deployment Preview trên Vercel. Frontend chỉ deploy Production từ `main` hoặc `release-mvp-v1`.

## File thay đổi

- `.github/workflows/frontend-ci.yml` — sửa: job deploy chỉ chạy trên hai branch production; bỏ toàn bộ nhánh lệnh Preview.
- `history/2026-09-25-remove-frontend-preview-deploy.md` — thêm: ghi quyết định và bằng chứng kiểm tra.

## Quyết định

- Các branch khác vẫn chạy quality và E2E khi push, nhưng job deploy bị skip.
- `workflow_dispatch` từ branch khác cũng không deploy; chỉ `main` và `release-mvp-v1` dùng environment `production`.
- Giữ nguyên credential và project/team Vercel; không thay đổi member Vercel.

## Kiểm tra

- PyYAML parse workflow — PASS.
- Static assertions xác nhận không còn nhánh Preview, job deploy chỉ có điều kiện production — PASS.
- Bash syntax cho các block `run` — PASS.
- `git diff --check` — PASS.
- Chưa chạy GitHub Actions thật; không đọc hoặc in secret.

## Còn lại / rủi ro

- Cần một lần chạy từ `main` hoặc `release-mvp-v1` để xác nhận token và build Production trên GitHub Actions.
