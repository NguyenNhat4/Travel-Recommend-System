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
- Job build/publish/deploy của Backend và Frontend chạy khi push hoặc dispatch từ `main`, `release-mvp-v1`, `release-mvp-v2` hoặc `release-mvp-v3`.

## Kiểm tra

- PyYAML parse workflow — PASS.
- `git diff --check` — PASS.
- Đã kiểm tra các điều kiện deploy chứa đủ bốn nhánh mục tiêu — PASS.
- GitHub Actions — chưa chạy.

## Còn lại / rủi ro

- Cần mở PR branch này vào nhánh release phù hợp và xác nhận các secrets Vercel không còn được workflow tham chiếu.
