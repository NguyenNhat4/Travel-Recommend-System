# Ép Vercel CLI chọn đúng project và team

- Ngày: 2026-09-24
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev`
- Trạng thái: hoàn thành
- Phạm vi: frontend, CI/CD

## Mục tiêu

Khắc phục bước `vercel pull` trong frontend workflow bị lỗi `Could not retrieve Project Settings` khi runner không xác định được project link phù hợp.

## File thay đổi

- `.github/workflows/frontend-ci.yml` — truyền tường minh `VERCEL_PROJECT_ID` qua `--project` và `VERCEL_ORG_ID` qua `--scope` cho `pull`, `build` và `deploy`.
- `history/2026-09-24-fix-vercel-project-resolution.md` — thêm: ghi nguyên nhân và kết quả kiểm tra.

## Quyết định

- Giữ `.vercel/` không commit; workflow CI dùng secrets và tham số CLI tường minh.
- Dùng cùng project/team cho cả ba bước để tránh CLI dùng project link hoặc scope mặc định của token.

## Kiểm tra

- `vercel pull --help` — xác nhận CLI hỗ trợ `--project`, `--scope`, `--environment` và `--token`.
- `vercel build --help` và `vercel deploy --help` — xác nhận `--project` và `--scope` được hỗ trợ.
- Parse `.github/workflows/frontend-ci.yml` bằng PyYAML — PASS.
- `git diff --check` — PASS.
- Chưa chạy deploy thật vì token Vercel không được đọc từ workspace.

## Còn lại / rủi ro

- Nếu vẫn lỗi sau khi push, cần kiểm tra `VERCEL_TOKEN` có quyền với team `VERCEL_ORG_ID` và project `VERCEL_PROJECT_ID`; thay đổi workflow không thể cấp quyền cho token.
