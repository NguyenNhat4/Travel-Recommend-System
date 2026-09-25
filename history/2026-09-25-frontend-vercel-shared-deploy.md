# Cho phép mọi branch deploy frontend bằng credential chung của GitHub Actions

- Ngày: 2026-09-25
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev`
- Trạng thái: hoàn thành phần workflow và kiểm tra local; chưa chạy GitHub Actions thật
- Phạm vi: frontend, CI/CD

## Mục tiêu

Cho phép mọi thành viên có quyền push hoặc chạy `workflow_dispatch` trên GitHub deploy frontend qua cùng credential của GitHub Actions, không yêu cầu thêm member/team trên Vercel Free.

## File thay đổi

- `.github/workflows/frontend-ci.yml` — sửa: push mọi branch tạo Preview, manual dispatch không còn bị chặn theo branch, production vẫn dành cho `main`/`release-mvp-v1`, pin Vercel CLI và chạy build không tương tác.
- `history/2026-09-25-frontend-vercel-shared-deploy.md` — thêm: ghi quyết định và bằng chứng kiểm tra.

## Quyết định

- Giữ `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` ở GitHub Actions secrets; người chạy workflow không cần là member Vercel.
- Giữ `--project` và `--scope` để token chung luôn deploy đúng project/team hiện tại; không sửa member/team Vercel.
- Push mọi branch và manual dispatch ngoài `main`/`release-mvp-v1` dùng Preview. `main` và `release-mvp-v1` tiếp tục dùng Production.
- Pin Vercel CLI `59.26.0` thay cho `latest` để tránh thay đổi hành vi giữa các lần chạy; thêm `--yes` cho `vercel build` để không chờ prompt trên runner.
- Không dùng `--no-wait`: workflow phải chờ deployment kết thúc để không báo xanh khi Vercel còn đang build hoặc thất bại.

## Kiểm tra

- PyYAML parse `.github/workflows/frontend-ci.yml` — PASS; jobs `quality`, `e2e`, `deploy` nhận diện đúng.
- Static workflow assertions — PASS: push không còn branch filter, manual dispatch không còn guard từ chối branch, production/preview expression còn nguyên.
- `git diff --check` — PASS.
- `vercel build --help` và `vercel deploy --help` — PASS; CLI hỗ trợ các cờ `--yes`, `--prebuilt`, `--prod`, `--project`, `--scope`.
- Chưa chạy deploy thật; không đọc hoặc in giá trị secret.

## Còn lại / rủi ro

- GitHub repository/environment phải có đủ `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`; workflow không thể tự cấp quyền cho token.
- Cần một lần chạy GitHub Actions thật để xác nhận token hiện tại và thời gian build Vercel; ảnh log trước đó mới chứng minh upload tới bước `Building`, chưa chứng minh deployment hoàn tất.
