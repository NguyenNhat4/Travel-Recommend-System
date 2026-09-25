# Triển khai auth P0: FastAPI RS256 + BFF Next.js (cookie phiên, CSRF, Redis)

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành (còn việc chờ người khác, xem cuối)
- Phạm vi: contract | backend | frontend | docs

## Mục tiêu

Người dùng yêu cầu "hoàn thành chức năng auth". Làm theo `docs/plan/2026-09-23-auth-p0.md` (bước 1, 3, 5, 6, 7) và `docs/spec/hop-dong-tich-hop-auth.md` P0. Phục vụ FR-USR-01, FR-USR-03, NFR-SEC-01, NFR-SEC-02, FR-REC-01 (gỡ IDOR ở `/recommendations`). Không lệch PRD: cơ chế hybrid BFF + Redis đã vào PRD qua `docs/prd/update-archive/2026-09-23-auth-hybrid-session.md`; P1/P2 (xác minh email, reset mật khẩu, 2FA, OAuth, CAPTCHA thật) không làm.

## File thay đổi

Contract / mock
- `src/shared/contracts/paths/auth.yaml` — sửa: thêm `GET /.well-known/jwks.json` (server `/`).
- `src/shared/contracts/paths/recommendations.yaml` — sửa: thêm `GET /internal/recommendations` (`serviceToken`, 404 khi production).
- `src/shared/contracts/schemas/auth.yaml` — sửa: thêm `JwksResponse`.
- `src/shared/contracts/openapi.yaml` — sửa: khai báo hai path và schema trên.
- `src/shared/mocks/auth/getJwks.200-default.json` — thêm: fixture JWKS.
- `src/shared/mocks/index.json` — sửa: đăng ký fixture JWKS.

Backend
- `src/backend/app/domain/auth/privacy.py` — thêm: `hash_email`, `ip_prefix`, `short_sid` (chuyển từ infrastructure để application/api dùng chung).
- `src/backend/app/domain/auth/rate_limits.py` — thêm: ngưỡng §9.1 phần P0.
- `src/backend/app/domain/auth/session.py` — sửa: thêm `new_session_id()`.
- `src/backend/app/application/auth/errors.py` — sửa: thêm `TokenInvalid`, `TokenExpired`, `Unauthenticated`.
- `src/backend/app/application/auth/principal.py` — sửa: thêm `token_id` (jti).
- `src/backend/app/application/auth/use_cases.py` — sửa: `RegisterUser` (rate limit theo IP), `AuthenticateUser` (thêm trục `login:ipwide`, log §15.1), thêm `RotateSession`, `RevokeSession`, `ChangePassword`, `GetCurrentUser`, `ListDemoAccounts`; `with_session` tách v1 khỏi nhóm BFF.
- `src/backend/app/application/ports/auth.py` — sửa: `find_by_id`, `list_personas`, `RotatedRefreshToken`, `RefreshTokenStore.rotate(token)`, `revoke_all_for_user(except_session_id)`, `TokenVerifier`, `RevokedTokens`, `RateLimiter.hit`.
- `src/backend/app/infrastructure/auth/jwt_issuer.py` — sửa: kiểm `alg`/`kid`/`typ` từ header, `sub`/`cdp_user_id` không rỗng, ném lỗi của application, trả `token_id`.
- `src/backend/app/infrastructure/auth/keys.py` — thêm: nạp cặp khoá RS256; dev thiếu file thì sinh khoá tạm, production từ chối.
- `src/backend/app/infrastructure/auth/postgres_refresh_tokens.py` — thêm: `RefreshTokenStore` trên `app.refresh_tokens`.
- `src/backend/app/infrastructure/auth/rate_limiter.py` — thêm: `RedisRateLimiter` (sorted set, cửa sổ trượt, lockout) và `InMemoryRateLimiter`.
- `src/backend/app/infrastructure/auth/revoked_tokens.py` — thêm: `jwt:revoked:{jti}` (§10.3 điểm 9).
- `src/backend/app/infrastructure/auth/postgres_user_repository.py` — sửa: `find_by_id`, `list_personas`.
- `src/backend/app/infrastructure/auth/postgres_login_attempts.py` — sửa: dùng helper ở domain.
- `src/backend/app/api/deps.py` — sửa: `optional_principal`, `current_principal`, `require_service_token`, `require_internal_api`, `client_ip` (TRUSTED_PROXIES).
- `src/backend/app/api/errors.py` — sửa: handler `AuthError` → Error Envelope, `Retry-After`, `WWW-Authenticate`.
- `src/backend/app/api/v1/schemas/auth.py` — thêm: DTO theo `schemas/auth.yaml`.
- `src/backend/app/api/v1/routes/auth.py` — thêm: 4 route v1, 3 route chỉ BFF, `PUT /auth/password`, JWKS.
- `src/backend/app/api/v1/routes/recommendations.py` — sửa: danh tính qua `optional_principal`; thêm `/internal/recommendations`.
- `src/backend/app/api/v1/router.py` — sửa: gắn router auth và `root_router` (ngoài `/api/v1`).
- `src/backend/app/core/config.py` — sửa: bỏ `jwt_secret`/`jwt_algorithm`, thêm biến §19.
- `src/backend/app/core/security.py` — xoá: đường HS256.
- `src/backend/app/main.py` — sửa: `build_auth()` trong composition root, Redis client theo `AUTH_REDIS_URL`.
- `src/backend/README.md` — sửa: endpoint và hướng dẫn chạy auth.

Test backend
- `src/backend/tests/fakes/auth.py`, `src/backend/tests/fakes/auth_app.py` — thêm: bản giả in-memory và gắn vào `app.state`.
- `src/backend/tests/unit/domain/test_auth_domain.py` — thêm: cdp_user_id, chính sách mật khẩu, 12 dòng §3.8, privacy, ngưỡng.
- `src/backend/tests/unit/application/test_auth_use_cases.py` — thêm: đăng ký hai pha, lockout lần 6, rehash bcrypt, rotation/reuse, đổi mật khẩu, demo.
- `src/backend/tests/unit/infrastructure/test_auth_infrastructure.py` — thêm: 13 kiểu token hỏng (alg none, RS256→HS256, kid lạ…), JWKS, khoá, Argon2/bcrypt, rate limiter.
- `src/backend/tests/contract/test_auth_contract.py` — thêm: mọi response khớp schema + status khai báo; IDOR; service token; jti thu hồi.
- `src/backend/tests/integration/test_auth_postgres.py`, `test_auth_redis.py` — thêm: chạy trên Postgres/Redis local.
- `src/backend/tests/unit/api/test_security.py` — xoá: test đường HS256 đã gỡ (thay bằng test ở trên).
- `src/backend/tests/unit/agents/test_recsys_agent_integration.py` — sửa: gọi route với `principal=None`.

Frontend
- `src/frontend/src/services/server/sessionStore.ts`, `bffSession.ts`, `authRoutes.ts`, `proxy.ts` — thêm: session store Redis/in-memory, cookie, CSRF ba lớp, xoay sid, refresh có khoá, route auth, proxy.
- `src/frontend/src/app/api/auth/{session,login,register,logout,refresh}/route.ts` — thêm: re-export route BFF.
- `src/frontend/src/app/api/[...path]/route.ts` — sửa: dùng proxy mới (xoá cookie/authorization của client, gắn Bearer, giữ `x-request-id` hai chiều).
- `src/frontend/src/services/http.ts` — thêm: `apiFetch` (same-origin, `X-CSRF-Token`, retry một lần khi `CSRF_FAILED`/`SESSION_EXPIRED`).
- `src/frontend/src/services/auth.ts` — thêm: client của `/api/auth/*`.
- `src/frontend/src/services/{recsys,search,shareService,assistantStream}.ts` — sửa: qua `apiFetch`; bỏ query `cdp_user_id` và tham số `authorizationToken`.
- `src/frontend/src/context/TravelContext.tsx` — sửa: danh tính từ `GET /api/auth/session`, `signIn`/`signUp`/`switchPersona` gọi BFF, xoá state client khi đổi tài khoản, modal khi phiên hết hạn.
- `src/frontend/src/components/auth/LoginView.tsx`, `common/LoginModal.tsx`, `common/DemoAccountSwitcher.tsx`, `common/Header.tsx`, `home/HomeView.tsx` — sửa: nối luồng thật, hiển thị lỗi theo `code`.
- `src/frontend/src/data/personas.ts` — sửa: `PERSONA_LOGIN` (email seed + cdp_user_id).
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract.
- `src/frontend/package.json`, `package-lock.json` — sửa: thêm `redis@5`.
- `src/frontend/.env.example`, `src/frontend/README.md` — sửa: biến BFF.
- `src/frontend/tests/api/bff-auth.test.ts` — thêm: §20.4; `tests/api/proxy-stream.test.ts`, `tests/unit/{assistantStream,recsysService,searchService}.test.ts` — sửa theo CSRF/không token.

Cấu hình / docs
- `.env.example` — sửa: gỡ `JWT_SECRET`/`JWT_ALGORITHM`, ghi chú `AUTH_REDIS_URL`, `AUTH_SERVICE_TOKEN`.
- `docker-compose.yml` — sửa: backend phụ thuộc Redis, biến auth, mount `./secrets` read-only.
- `Makefile` — sửa: target `jwt-keys`.
- `docs/spec/hop-dong-tich-hop-auth.md` — sửa: đường dẫn cũ, §22.3 ghi chú hiện thực.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: §3 trỏ sang spec auth, Argon2id, §8.2 trỏ bảng mã lỗi auth.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §4.7 và §7 theo BFF.
- `docs/plan/2026-09-23-auth-p0.md` — sửa: mục Tiến độ.

## Quyết định

- **Không thêm path ngoài contract.** Đăng ký qua BFF = `POST /auth/register` (v1) rồi `POST /auth/session`. Đã viết thử `/auth/session/register` rồi gỡ trước khi xong.
- **`session_id` do backend sinh** vì `SessionRequest`/`RefreshRequest` không mang sid của BFF; cookie `vota_sid` xoay độc lập. Refresh giữ nguyên `expires_at` của family (không vượt 12 giờ). Ghi ở spec auth §22.3.
- **`api` không import `infrastructure`**: lỗi token là của application (`TokenInvalid`/`TokenExpired`), dependency gọi qua port `TokenVerifier`/`RevokedTokens`. `tests/architecture` xanh.
- **Không có Redis/khoá thì dev vẫn chạy** (rate limiter + session store in-memory, khoá RS256 tạm), production từ chối khởi động.
- **Proxy BFF**: cookie còn mà phiên chết → `401 SESSION_EXPIRED` (không âm thầm thành khách); chỉ tin `Origin` trong `ALLOWED_ORIGINS`; đổi mật khẩu thành công thì huỷ phiên khác và xoay sid (§3.8 J).
- **Client chỉ chặn mật khẩu < 8 ký tự**; chữ/số chỉ là gợi ý (spec §8.3).
- Persona: dùng `app.users.persona` của DDL (`P1_frequent`…), đúng AGENTS.md §6.4.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (78 schemas, 54 fixtures).
- `RUN_POSTGRES_INTEGRATION=1 RUN_REDIS_INTEGRATION=1 python -m pytest -q src/backend/tests`: 269 passed (lần chạy cuối, gồm integration Postgres + Redis thật).
- Bao phủ (coverage, test auth): `domain/auth` 100%, `application/auth` 96–100%, `api/deps.py` 92%.
- `npx vitest run` (src/frontend): 11 file, 65 passed. `npx tsc --noEmit`: chỉ còn 2 lỗi có sẵn (`leaflet`, `qrcode` không có trong package.json). `npx eslint` các file sửa: sạch.
- Chạy tay §20.5 trên uvicorn + `next dev` (bản sao ở scratchpad vì :3000 đang có dev server của người dùng) + Postgres + Redis local — 8/8 đạt:
  1. Cookie JS đọc được chỉ có `vota_csrf`; `vota_sid` HttpOnly.
  2. `vota_sid=s_hacked` → `401 SESSION_EXPIRED`, không 500.
  3. `Authorization: Bearer forged…` từ browser bị BFF xoá; recs vẫn của VP0000001 theo phiên.
  4. POST từ `https://evil.example` không CSRF → `403 CSRF_FAILED`.
  5. `GET /api/v1/recommendations?cdp_user_id=VP0000001` không đăng nhập → `cdpUserId: null`, `popular`.
  6. 6 lần sai mật khẩu: `401×5`, lần 6 `429`, `Retry-After: 900`.
  7. Email không tồn tại vs tồn tại (cùng Argon2id): ~44 ms vs ~45 ms. Với user còn hash bcrypt cũ lệch ~33 ms (< 50 ms), hết khi seed lại.
  8. Trộm refresh token: kẻ trộm dùng token cũ → 401, nạn nhân refresh tiếp → 401, log `auth.refresh_reuse`.
- Nghiệm thu: 4 persona đăng nhập qua BFF, recs khác nhau: P1 `cross_vertical`, P2 `cold_start_content`, P3 `dormant`, P4 `popular`.
- Đã xoá bộ đếm `rl:*`/`lockout:*` do bài kiểm tra tạo trong Redis db 1 local.

## Còn lại / rủi ro

- `CdpClient.ensure_profile` vẫn chờ reviewer Data/Integration (plan câu hỏi 2) trước khi merge `POST /auth/register`.
- DB local của người làm còn hash bcrypt (seed trước 2026-09-23); integration test đã nâng 4 persona lên Argon2id. Chạy `make demo-db` để seed lại.
- Trang UI trả 500 khi chạy dev vì `leaflet`, `qrcode` không có trong `src/frontend/package.json` (lỗi có sẵn, ngoài phạm vi). Chưa kiểm luồng đăng nhập trên trình duyệt; mới kiểm ở mức route BFF + curl.
- Muốn đăng nhập từ web phải đặt `AUTH_SERVICE_TOKEN` giống nhau ở `.env` (backend) và `src/frontend/.env.local`, và `SESSION_REDIS_URL`.
- Nhánh khác còn dùng `JWT_SECRET`/HS256 sẽ gãy khi merge (đã gỡ `core/security.py`).
- Redis staging (managed hay tự host) chưa chốt.
