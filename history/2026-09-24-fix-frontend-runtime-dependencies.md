# Khôi phục dependency runtime frontend

- Ngày: 2026-09-24
- Tác giả: Người yêu cầu / Codex
- Nhánh: `main` trong checkout frontend
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Khắc phục lỗi CI TypeScript không tìm thấy `leaflet` và `qrcode` khi cài dependency bằng `npm ci`.

## File thay đổi

- `src/frontend/package.json` — thêm `leaflet`, `qrcode` và type package tương ứng.
- `src/frontend/package-lock.json` — cập nhật lockfile để CI cài được đúng dependency.
- `history/2026-09-24-fix-frontend-runtime-dependencies.md` — thêm: ghi nguyên nhân và kết quả kiểm tra.

## Quyết định

- Giữ `leaflet` và `qrcode` là runtime dependencies vì component import và sử dụng chúng khi chạy trình duyệt.
- Đặt `@types/leaflet` và `@types/qrcode` trong devDependencies vì chỉ phục vụ TypeScript compiler.
- Không cài package ngoài lockfile trong workflow; môi trường CI phải tái lập từ manifest và lockfile.

## Kiểm tra

- `npm install --package-lock-only --ignore-scripts` — PASS.
- `npm ci` — PASS: 569 package, 0 vulnerability.
- `npm run typecheck` — PASS.
- `npm run build` — PASS.
- `npm run test` — PASS: 11 test files, 59 tests.
- `npm run lint` — PASS, 0 error và 7 warning hook dependency có sẵn.
- `npm run test:e2e` — 12 pass, 1 skipped, 1 fail ở test header assistant do không tìm thấy `#aiAssistantBtn`; lỗi này không liên quan dependency.

## Còn lại / rủi ro

- Cần xử lý riêng test E2E `header assistant drawer streams a backend result` trước khi workflow frontend đạt xanh toàn bộ.
