# Sinh lại `api.gen.ts` trên dev: bỏ khối auth bị lặp

- Ngày: 2026-09-25
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/dev-api-gen-ts (tách từ `origin/dev` tại `f3f7795`)
- Trạng thái: hoàn thành
- Phạm vi: frontend (chỉ file sinh tự động)

## Mục tiêu

Frontend CI fail ở bước "Check generated OpenAPI types are committed" với mọi PR vào `dev` có chạm `src/frontend/**` hoặc `src/shared/contracts/**` (gặp ở PR `feat/hybrid-search`). Nguyên nhân: `src/frontend/src/types/api.gen.ts` trên `dev` lệch `openapi.yaml` 122 dòng — khối path `/auth/session`, `/auth/session/token`, `/auth/session/revoke`, `/auth/session/mfa/verify`, `/auth/password` và khối schema `SessionState`, `SessionRequest`, `SessionResponse`, `RefreshRequest`, `RevokeRequest`, `MfaVerifyRequest`, `PasswordChangeRequest` xuất hiện hai lần. Khối lặp vào `dev` qua merge `8e5e69b` (Merge branch 'dev' into release-mvp-v1); contract không đổi, chỉ file sinh bị gộp sai. `dev` đứng riêng cũng fail đúng 122 dòng này.

## File thay đổi

- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại bằng `npm run generate:api-types` (openapi-typescript 7.13.0, đúng bản trong `package-lock.json`); chỉ xoá 122 dòng lặp, không đổi dòng nào khác.

## Quyết định

- Không sửa tay: file này sinh tự động và CI so nó với `openapi.yaml` (`docs/spec/hop-dong-tich-hop-frontend.md` dòng 65, 81). Contract giữ nguyên.
- Sửa ở nhánh riêng tách từ `dev` thay vì trong `feat/hybrid-search`, để nhánh search không mang phần vá của `dev` (người dùng chọn).

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (83 schemas, 62 fixtures; CDP clone 12 schemas, 7 fixtures).
- Sinh lại lần hai rồi so với bản đã sửa: không lệch (bước `git diff --exit-code` của CI sẽ pass).
- `npm run lint`: 0 lỗi, 4 warning có sẵn (`react-hooks/exhaustive-deps`).
- `npm run typecheck`: pass.
- `npm run test`: 17 file, 111/111 test pass.
- `npm run build`: `next build` và `build:api` pass; hai lệnh `cp` của `build:web` chạy lại bằng bash vì `cmd` trên Windows không có `cp` (CI chạy Linux nên không ảnh hưởng).

## Còn lại / rủi ro

- Merge nhánh này vào `dev` trước; PR `feat/hybrid-search` → `dev` sẽ hết lỗi ở bước này mà không cần sửa gì thêm.
- Khi merge chéo giữa `dev` và `release-mvp-v1` về sau, không gộp tay `api.gen.ts`: lấy một phía rồi chạy lại `npm run generate:api-types`.
