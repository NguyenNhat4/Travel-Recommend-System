# Tạo workflow CI frontend

- Ngày: 2026-09-24
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev`
- Trạng thái: hoàn thành
- Phạm vi: frontend, CI/CD

## Mục tiêu

Tạo quality gate riêng cho frontend để các thay đổi Next.js được lint, kiểm tra type, kiểm tra contract, chạy test, build và E2E trước khi Vercel triển khai.

## File thay đổi

- `.github/workflows/frontend-ci.yml` — thêm: workflow chạy trên pull request, push `dev`/`main` và manual dispatch; tách quality checks, Playwright E2E và deploy Vercel.
- `src/frontend/src/types/api.gen.ts` — sinh lại từ `src/shared/contracts/openapi.yaml` để đồng bộ endpoint auth/session, search compatibility, error codes và agent status.
- `history/2026-09-24-frontend-ci-workflow.md` — thêm: ghi quyết định và kết quả kiểm tra.

## Quyết định

- GitHub Actions deploy frontend bằng Vercel CLI sau quality và E2E; token chỉ đọc từ GitHub Environment secrets.
- Dùng Node.js 22, khớp với `src/frontend/Dockerfile.web`.
- PR chỉ chạy CI/E2E; push `dev` deploy Preview; `main` deploy Production.
- Dùng `vercel pull` → `vercel build` → `vercel deploy --prebuilt` để build trong CI và gửi build output lên Vercel.
- Chạy contract validator, tái sinh `api.gen.ts` và từ chối thay đổi chưa được commit của file sinh.
- Chạy E2E với Chromium; test live assistant vẫn skip nếu không bật `RUN_ASSISTANT_LIVE_E2E=1`.
- Không đưa `BACKEND_BASE_URL` vào CI vì các bài E2E hiện tại dùng BFF/mocked stream và không yêu cầu backend staging.

## Kiểm tra

- `python3` parse workflow YAML — PASS.
- Generated API types — PASS sau khi chạy `npm run generate:api-types`; file khớp lại với `src/shared/contracts/openapi.yaml`.
- `npm run lint` — PASS, 0 error và 7 warning hook dependency có sẵn.
- `npm run typecheck` — FAIL do thiếu module `leaflet` và `qrcode` trong dependency hiện tại.
- `npm run test` — PASS: 11 test files, 59 tests.
- `npm run build` — FAIL do thiếu `leaflet` trong dependency hiện tại.
- `npm run test:e2e` — chưa chạy vì production build đã fail với blocker trên.
- Contract validator — PASS: 77 schemas, 50 grounded products, 53 fixtures; CDP clone 12 schemas và 7 fixtures.
- `git diff --check` — PASS cho các file workflow và history.
- `actionlint` — chưa cài trong môi trường local.
- Kiểm tra YAML sau khi thêm job deploy — PASS; xác nhận đủ `vercel pull`, `vercel build` và `vercel deploy --prebuilt`, job deploy không chạy trên pull request.

## Còn lại / rủi ro

- Chưa chạy GitHub Actions thật trong task này.
- Cần tạo GitHub Environments `preview` và `production`, rồi thêm `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.
- Vercel Project cần đặt Root Directory là `src/frontend`, Build Command là `npm run build:web`, và cấu hình `BACKEND_BASE_URL` riêng cho Preview/Production.
