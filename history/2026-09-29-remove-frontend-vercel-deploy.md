# Bỏ deploy Frontend lên Vercel khỏi workflow

- Ngày: 2026-09-29
- Tác giả: Người yêu cầu / Codex
- Nhánh: `khoa/remove-deploy-frontend-vercel`
- Trạng thái: hoàn thành
- Phạm vi: frontend, CI/CD

## Mục tiêu

Ngừng job deploy Frontend lên Vercel trong GitHub Actions; giữ quality checks, E2E và đường deploy Frontend lên Backend VM.

## File thay đổi

- `.github/workflows/frontend-ci-cd.yml` — xóa job `deploy` dùng Vercel và biến `VERCEL_CLI_VERSION`.
- `history/2026-09-29-remove-frontend-vercel-deploy.md` — ghi nhận thay đổi và kiểm tra.

## Quyết định

- Không xóa cấu hình Vercel khác ngoài workflow job; Frontend VM là đường deploy của workflow này.
- Job `build_vm`, `publish_vm` và `deploy_vm` vẫn giữ điều kiện chạy trên `release-mvp-v1`; PR checks vẫn chạy trên `release-mvp-v2`.

## Kiểm tra

- PyYAML parse workflow — PASS.
- `git diff --check` — PASS.
- GitHub Actions — chưa chạy.

## Còn lại / rủi ro

- Cần mở PR branch này vào nhánh release phù hợp và xác nhận các secrets Vercel không còn được workflow tham chiếu.
