# Đưa cơ chế auth hybrid (BFF + Redis) và phạm vi auth P1/P2 vào PRD

- Ngày: 2026-09-23
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng (phần A, phần C phương án C1) · từ chối (phần B)
- Chốt bởi / ngày: mihhquan, 2026-09-23
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §1, §4, §6.2 · `docs/prd/deployment-plan.md` §1, §2, §3.1 · `docs/prd/data-model.md` §1, §2.2 · `docs/prd/requirements.md` §1.6, §1.7 · `docs/prd/test-plan.md` §3
- Mã FR/NFR: FR-USR-01, FR-USR-03, NFR-SEC-01 (phần A); mới — cần cấp mã (phần B); FR-CDP-02 (phần C)

Đề xuất chia ba phần độc lập để chốt riêng. Phần A chặn auth P0; phần B và C không chặn P0.

## Lý do

`docs/spec/hop-dong-tich-hop-auth.md` (chốt 2026-09-21, trước khi có PRD) chọn cơ chế hybrid: trình duyệt chỉ giữ cookie phiên, Next.js route handler (BFF) giữ token trong Redis, FastAPI phát JWT RS256. Contract nhóm `/auth/session*`, bảng `app.refresh_tokens`/`app.login_attempts` và service `redis` trong `docker-compose.yml` đã có trong repo. PRD viết sau (2026-09-22) nhưng không ghi các điểm này, nên phần còn lại của auth P0 (BFF, session store, rate limit) sẽ làm code lệch PRD nếu không chốt.

Lý do kỹ thuật chính: FR-USR-03 cho phép "Session token / Cookie / JWT" nhưng không nói token nằm ở đâu. Để token trong `sessionStorage` (cách cũ của `hop-dong-tich-hop-frontend.md` §7.1) thì chỉ cần một lỗi XSS là mất token, trái NFR-SEC-01. Cookie `HttpOnly` cắt ở BFF tránh được điều đó.

## Nội dung đề xuất

### Phần A — cơ chế hybrid (chặn P0)

1. `architecture.md` §1, sơ đồ: hiện `UI --> Router` (trình duyệt gọi thẳng FastAPI) → thay bằng `UI --> BFF[Next.js route handler: cookie phiên, CSRF] --> Router`, thêm node `Redis (session, rate limit)` nối với BFF và FastAPI. Schema `app` ghi `Users, Bookings, Refresh tokens, Login attempts` thay cho `Sessions`: phiên nằm ở Redis, Postgres chỉ giữ phần bền.
2. `architecture.md` §4, thêm dòng: **Session store & rate limit — Redis 7**, `maxmemory-policy noeviction`. Mất dữ liệu thì người dùng chỉ phải đăng nhập lại; refresh token vẫn thu hồi được nhờ bản bền trong `app.refresh_tokens`.
3. `architecture.md` §6.2, thay câu "token không được log hoặc đưa vào URL" → "Trình duyệt không bao giờ giữ JWT: không `localStorage`/`sessionStorage`/URL/body. Route handler BFF trong `src/frontend/src/app/api/` giữ cookie phiên `vota_sid` (HttpOnly), kiểm CSRF, gắn `Authorization` khi proxy sang FastAPI. BFF không ký token."
4. `deployment-plan.md` §2, thêm các biến: `JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH` (bí mật, không commit, không vào image), `JWT_ISSUER`, `JWT_AUDIENCE`, `AUTH_SERVICE_TOKEN` (≥ 32 ký tự, BFF và FastAPI dùng chung), `AUTH_REDIS_URL` / `SESSION_REDIS_URL`, `TRUSTED_PROXIES`, `CAPTCHA_PROVIDER`/`CAPTCHA_SECRET`. Bỏ `JWT_SECRET`/`JWT_ALGORITHM=HS256` (xem "Thay đổi source").
5. `deployment-plan.md` §1 và §3.1: thêm Redis cho từng môi trường (local: `docker compose up -d redis`; staging/prod: chốt managed hay self-host — spec §22.2 mục E).
6. `data-model.md` §1 và §2.2: thêm `refresh_tokens`, `login_attempts` và cột `users.email_verified_at` vào sơ đồ `app`, đúng như `db/vota_schema.sql` hiện có.

### Phần B — mở rộng phạm vi auth P1/P2 (không chặn P0)

PRD hiện chỉ có đăng ký/đăng nhập email-mật khẩu và persona switcher (FR-USR-01). Spec §21 thêm:

- **FR-USR-04 (mới)** — Xác minh email và đặt lại mật khẩu qua link một lần dùng; chặn checkout khi email chưa xác minh (P1).
- **FR-USR-05 (mới)** — 2FA TOTP + recovery code; CAPTCHA sau nhiều lần đăng nhập sai (P1). WebAuthn (P2).
- **FR-USR-06 (mới)** — Đăng nhập OAuth/OIDC (Google), PKCE bắt buộc (P2).

Thêm ba dòng trên vào `requirements.md` §1.6 và AC tương ứng vào §3 (lấy từ spec §21 "Nghiệm thu P1/P2"). Nếu từ chối phần này, spec §11–§13 được đánh dấu "ngoài phạm vi MVP".

### Phần C — ghép lịch sử ẩn danh: PRD và spec đang mâu thuẫn

- PRD `requirements.md` FR-CDP-02 và `test-plan.md` §3 bước 4 yêu cầu gộp hành vi ẩn danh vào profile khi đăng nhập; bước 1 còn yêu cầu `cdp.events` có `anonymous_id`.
- Spec auth §3.7 và `hop-dong-tich-hop-cdp.md` §1.6 để việc này ngoài phạm vi, vì `cdp.events.cdp_user_id` là `NOT NULL REFERENCES cdp.profiles`. Làm FR-CDP-02 cần đổi DDL `cdp.events` và có quyết định của reviewer CDP.

Cần người dùng chọn một trong hai:

- **C1 — Hoãn FR-CDP-02 khỏi MVP.** Ghi "(sau MVP)" vào FR-CDP-02; sửa `test-plan.md` §3 bước 1 (không sinh event cho khách ẩn danh) và bước 4 (bỏ cột "Gộp dữ liệu hành vi ẩn danh"). Auth P0 không đổi.
- **C2 — Giữ FR-CDP-02.** Mở spec riêng cho identity stitching (bảng `app.anonymous_links` hoặc cột `anonymous_id` trong `cdp.events`, sự kiện `identify`) và sửa spec auth §3.7. Việc này là một workstream CDP riêng, không nằm trong kế hoạch auth.

Agent đề xuất C1, vì C2 phải đổi DDL của schema `cdp` (hiện `cdp.events.cdp_user_id` bắt buộc) và cần reviewer CDP duyệt.

## Thay đổi source sau khi chốt

- Phần A: `docs/plan/2026-09-23-auth-p0.md` bước 3b, 5b, 6 được mở khoá. Gỡ `JWT_SECRET`/`JWT_ALGORITHM` khỏi `.env.example` và `src/backend/app/core/config.py`, xoá `src/backend/app/core/security.py` (HS256) và thay bằng dependency RS256. Sửa `README.md` (lệnh chạy Redis).
- Phần B: cấp mã FR, sau đó viết `docs/plan/<ngày>-auth-p1.md`; migration `0003_auth_p1.sql` (`email_verifications`, `mfa_credentials`, `mfa_recovery_codes`).
- Phần C (C1): sửa `test-plan.md` §3; không đổi source. (C2): spec CDP mới, không thuộc kế hoạch auth.

## Kết quả chốt (2026-09-23)

- **Phần A — đã chốt, đã áp dụng** vào `architecture.md` §1, §4, §6.2; `deployment-plan.md` §1, §2, §3.1; `data-model.md` §1, §2.2. Riêng mục A.4 "bỏ `JWT_SECRET`/`JWT_ALGORITHM`" là thay đổi source, làm ở bước 3a của `docs/plan/2026-09-23-auth-p0.md` (PRD chưa từng ghi hai biến này nên không cần sửa PRD).
- **Phần B — từ chối.** P1/P2 ngoài phạm vi; không cấp FR-USR-04..06. Spec auth §11–§13 được đánh dấu ngoài phạm vi.
- **Phần C — chốt C1.** Người chốt: "lịch sử ẩn danh nằm ngoài phạm vi hiện tại, chỉ cần tracking khi người dùng đăng nhập". Đã sửa `requirements.md` FR-CDP-02 và `test-plan.md` §3 bước 1–4.
