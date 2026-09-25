# Sửa BFF không tạo sid: thiếu dependency leaflet/qrcode và thiếu cấu hình auth local

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Agent review báo "BFF không tạo sid" sau khi triển khai auth P0 (`history/2026-09-23-trien-khai-auth-p0.md`). Điều tra và sửa để luồng phiên BFF (`docs/spec/hop-dong-tich-hop-auth.md` §3.3, §3.8 dòng A và C) chạy được trên máy dev.

## File thay đổi

- `src/frontend/package.json` — sửa: thêm `leaflet`, `qrcode` (dependencies) và `@types/leaflet`, `@types/qrcode` (devDependencies).
- `src/frontend/package-lock.json` — sửa: lockfile tương ứng (npm 11); vài package con của `qrcode` chuyển từ `dev` sang dependency thường.

Ngoài git (đã bị ignore, không commit): `.env` gốc (đặt `AUTH_SERVICE_TOKEN`), `src/frontend/.env.local` (thêm `AUTH_SERVICE_TOKEN`, `SESSION_REDIS_URL`, `ALLOWED_ORIGINS`), `secrets/jwt-{private,public}.pem` (sinh bằng `make jwt-keys`).

## Quyết định

- Nguyên nhân gốc không nằm ở code auth. `ItineraryMap.tsx` và `ShareItineraryModal.tsx` import `leaflet`/`qrcode`, nhưng hai package này chưa từng được khai báo trong `package.json` ở bất kỳ nhánh nào. Turbopack gặp lỗi biên dịch nên trả 500 cho mọi route, kể cả `GET /api/auth/session`, vì vậy không có `Set-Cookie: vota_sid`. Sửa bằng cách khai báo dependency, không đụng tới component.
- Nguyên nhân thứ hai: `AUTH_SERVICE_TOKEN` rỗng ở cả backend lẫn BFF, và `src/frontend/.env.local` thiếu biến auth (Next chỉ đọc env trong `src/frontend/`). Backend từ chối `X-Service-Token` ngắn hơn 32 ký tự (`401 INVALID_TOKEN`), nên login không bao giờ phát được sid đã đăng nhập. Đã đặt cùng một token ở cả hai phía theo §19 của spec.
- Không đổi thiết kế `session_id` phía backend (spec §22.3). Việc claim `sid` của JWT khác cookie `vota_sid` (lệch spec §3.1) vẫn để chờ người dùng quyết định, vì muốn sửa phải đổi contract `SessionRequest`.

## Kiểm tra

- Tái hiện lỗi trước khi sửa: `GET /api/auth/session` → 500 `Module not found: Can't resolve 'leaflet'`; `POST /api/v1/auth/session` với token rỗng → `401 INVALID_TOKEN`.
- Sau khi sửa, chạy curl trên Next dev (:3000) + FastAPI (:8000) + Redis + Postgres local:
  - `GET /api/auth/session` → 200, có `vota_sid` (HttpOnly) và `vota_csrf`.
  - `POST /api/auth/login` với P1 → 200 `authenticated`; sid đã xoay, sid cũ bị xoá khỏi Redis.
  - `GET /api/auth/session` lần hai → vẫn `authenticated`.
  - `/api/v1/recommendations` qua proxy: P1 → `cross_vertical`, khách → `popular`.
  - `GET /` → 200.
- JWKS backend khớp `secrets/jwt-public.pem` (không phải khoá tạm của dev).
- `vitest run`: 65/65 pass (trong đó `tests/api/bff-auth.test.ts` 17/17). `tsc --noEmit`: không lỗi.

## Còn lại / rủi ro

- Máy khác clone về phải tự làm lại phần env: sinh token, đặt vào `.env` và `src/frontend/.env.local`, rồi chạy `make jwt-keys`.
- Chờ quyết định: có cho BFF truyền `sid` sang backend để claim `sid` của JWT trùng `vota_sid` (spec §3.1) hay giữ như §22.3.
- Tuỳ chọn: BFF đang chuyển nguyên `401 INVALID_TOKEN` (lỗi cấu hình service token) về màn đăng nhập với thông báo "Phiên đăng nhập không hợp lệ", dễ gây hiểu nhầm; nên đổi thành 502.
