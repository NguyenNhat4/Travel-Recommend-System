# Logging có cấu trúc cho frontend (Next.js)

- Ngày: 2026-10-06
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/logging-frontend
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Triển khai logging JSON một dòng cho phần server của Next.js (BFF) theo `docs/spec/logging-schema.md` và `docs/plan/2026-10-06-logging-he-thong.md`: `ts` giờ Hà Nội, `severity`, `service`, `event`, `request_id`, che dữ liệu nhạy cảm. Không đụng server Express `src/frontend/server/` và `Dockerfile.api`. Người dùng cho phép bỏ qua bước PRD cho việc này.

## File thay đổi

- `src/frontend/package.json`, `package-lock.json` — sửa: thêm dependency `pino`.
- `src/frontend/src/lib/logger.ts` — thêm: logger pino (`ts` +07:00, `ts_utc`, `severity`, `service=frontend`, `LOG_LEVEL`), `redact()`/`redactString()`, `serializeError()`, `hashId()`, `routeOf()`.
- `src/frontend/src/instrumentation.ts` — thêm: `app.startup`, `app.shutdown` (SIGTERM/SIGINT), `render.error` qua `onRequestError` (route, digest, stack).
- `src/frontend/src/services/server/proxy.ts` — sửa: `bff.proxy`, `bff.proxy.upstream_error`, `bff.csrf.rejected`, `bff.guest.issue/merge`, `bff.stream.open/close` (bọc body SSE chỉ đếm byte/thời gian); thay `console.*`.
- `src/frontend/src/services/server/bffSession.ts` — sửa: bỏ `logAuth`, dùng `bff.session.load/refresh/destroy/rotate`; sid được băm; `requestIdOf` chỉ nhận id hợp lệ `[A-Za-z0-9._-]{1,64}`.
- `src/frontend/src/services/server/authRoutes.ts` — sửa: `bff.auth.login/register/logout`, `bff.csrf.rejected`; không log email.
- `src/frontend/src/services/server/sessionStore.ts` — sửa: `console.*` thành `bff.session.store`.
- `src/frontend/src/app/health/live/route.ts`, `ready/route.ts` — sửa: `bff.health` ở DEBUG (WARNING khi backend không với tới).
- `src/frontend/tests/unit/logger.test.ts` — thêm: schema, ts +07:00, severity, LOG_LEVEL, redact.
- `src/frontend/tests/api/proxy-logging.test.ts` — thêm: proxy không log cookie/authorization/sid/csrf/query, chuyển tiếp `X-Request-ID`, csrf, upstream_error.
- `src/frontend/tests/api/bff-auth.test.ts` — sửa: test abort/502 đếm dòng `bff.proxy.upstream_error` trên stdout thay vì spy `console.error`.
- `history/2026-10-06-logging-frontend.md` — thêm: entry này.

## Quyết định

- Chỉ log metadata ở frontend, không log body request/response (auth, mật khẩu, thanh toán); body đã do backend log theo mục 3 schema. `LOG_BODIES` chưa dùng ở frontend.
- Không log query string (có thể chứa email/từ khoá), `route` là mẫu đã bỏ id. `user_id_hash`/`sid_hash`/`guest_hash` là SHA-256 cắt 12 ký tự.
- Logger bọc pino bằng API `log.info(event, fields)`: mọi trường đi qua `redact()` trước khi vào pino; pino `redact` là lớp thứ hai. Mặc định ghi qua `process.stdout.write` để test chặn được.
- `app/error.tsx` là client component nên không dùng được pino; `render.error` ghi ở server qua `onRequestError` với cùng `digest` mà trình duyệt hiển thị. Log phía trình duyệt ngoài phạm vi theo schema.
- Thêm `bff.session.rotate` (đổi sid khi đăng nhập/đổi mật khẩu) và `bff.session.store`, `bff.health` ngoài danh sách trong schema; nên bổ sung vào schema nếu giữ.
- Sự kiện proxy có mức theo status: >=500 ERROR, >=400 WARNING, còn lại INFO.

## Kiểm tra

- `npx vitest run` (src/frontend): 616 passed, 1 failed (`tests/unit/floatingWidgetOpening.test.tsx`). Lỗi này có sẵn, không do thay đổi này: repo track cả `WidgetProgress.tsx` lẫn `widgetProgress.ts`, trên macOS (không phân biệt hoa thường) import `./WidgetProgress` trỏ nhầm sang file `.ts`.
- `npm run lint`: 0 error, 2 warning có sẵn (`ItineraryMap.tsx`).
- `npx tsc --noEmit`: chỉ còn lỗi casing `WidgetProgress` có sẵn nói trên; không có lỗi mới.

## Còn lại / rủi ro

- Chưa chạy trên Docker/standalone build thật: cần kiểm `pino` được trace vào `.next/standalone` và `app.startup` xuất hiện trong `docker logs`.
- `LOG_BODIES` chưa có hiệu lực ở frontend.
- Chưa có metric/Ops Agent parse (thuộc nhánh monitoring).
- Cần xử lý trùng tên `WidgetProgress.tsx`/`widgetProgress.ts` riêng.
