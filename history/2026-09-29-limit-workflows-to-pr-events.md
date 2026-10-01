# Giới hạn workflow theo PR và chạy thủ công

- Ngày: 2026-09-29
- Tác giả: Người yêu cầu / Codex
- Nhánh: `khoa/workflow-pr-push-triggers`
- Trạng thái: hoàn thành phần cấu hình; chưa chạy GitHub Actions thật
- Phạm vi: DevOps, CI/CD

## Mục tiêu

Kích hoạt workflow khi tạo/cập nhật/mở lại PR, khi PR được merge vào target branch, khi push trực tiếp vào target branch, hoặc khi người dùng chạy thủ công.

## File thay đổi

- `.github/workflows/backend-ci-cd.yml` — trigger theo PR `opened`/`synchronize`/`reopened`/`closed`, push target branch và `workflow_dispatch`; publish/deploy theo push, merge thành công hoặc dispatch trên target branch.
- `.github/workflows/frontend-ci-cd.yml` — cùng trigger; build/publish/deploy theo push, merge thành công hoặc dispatch trên target branch.
- `.github/workflows/crawler-ci-cd.yml` — cùng trigger; publish/deploy theo push, merge thành công hoặc dispatch trên target branch.
- `.github/workflows/monitoring-terraform-staging.yml` — cùng trigger; apply staging theo push, merge thành công hoặc dispatch trên target branch.
- `history/2026-09-29-limit-workflows-to-pr-events.md` — ghi nhận thay đổi và kiểm tra.

## Quyết định

- Target branch giữ nguyên: `main`, `release-mvp-v1`, `release-mvp-v2`, `release-mvp-v3`.
- PR kích hoạt ở `opened`, `synchronize`, `reopened` và `closed`; PR đóng nhưng không merge tạo event workflow nhưng tất cả job đều skip vì `merged` không đúng.
- Push trực tiếp chỉ kích hoạt workflow trên bốn target branch và theo path filter của từng workflow. Publish/deploy/apply staging chạy theo push target branch, PR merge hoặc dispatch từ target branch.
- `workflow_dispatch` được bật; chỉ các target branch được chạy job.
- Các chỉnh sửa khác đã có sẵn trong worktree ở một số workflow và script deploy được giữ nguyên, không thuộc phạm vi trigger này.

## Kiểm tra

- Kiểm tra diff và `git status` — xác nhận trigger được đổi trong đúng 4 workflow; các chỉnh sửa sẵn có vẫn được giữ.
- PyYAML compose trên 4 workflow — PASS.
- `git diff --check` — PASS.
- GitHub Actions — chưa chạy.

## Còn lại / rủi ro

- PR merge event được GitHub biểu diễn bằng `pull_request: closed`; job gate `github.event.pull_request.merged == true` phân biệt merge với đóng thường.
- Chưa xác nhận runtime GitHub Actions, OIDC/WIF, secrets hoặc staging apply/deploy.
