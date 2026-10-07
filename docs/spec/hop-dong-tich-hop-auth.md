# Hợp đồng tích hợp Auth

> **Trạng thái:** bản chốt đầu tiên, ngày 2026-09-21. Tài liệu này **thay thế** handbook §8 và `hop-dong-tich-hop-backend.md` §3 về cơ chế xác thực, theo quyết định của chủ dự án (§1.4). Các phần khác của hai tài liệu đó giữ nguyên.
>
> **Cơ chế:** hybrid — **session cookie cho web app** (BFF tại Next.js) + **JWT cho service nội bộ**. Trình duyệt không bao giờ giữ token.
>
> **Phạm vi sau khi chốt PRD (2026-09-23, `docs/prd/update-archive/2026-09-23-auth-hybrid-session.md`):** chỉ **P0** thuộc phạm vi. Cơ chế hybrid (BFF + Redis) đã vào PRD. **P1/P2 — xác minh email, đặt lại mật khẩu, 2FA/TOTP, WebAuthn, OAuth (§11, §12, §13 và các dòng P1/P2 ở §21) — ngoài phạm vi**, giữ lại chỉ để tham khảo; không triển khai khi chưa có đề xuất PRD mới. Ghép lịch sử ẩn danh vẫn ngoài phạm vi (§3.7, FR-CDP-02 hoãn): chỉ tracking khi người dùng đã đăng nhập.
>
> Ưu tiên khi mâu thuẫn: `AGENTS.md` §2. Tài liệu này đứng cùng hạng với các `hop-dong-tich-hop-*.md` khác và **dưới** OpenAPI.

## Mục lục

1. [Phạm vi và quyết định nền](#1-phạm-vi-và-quyết-định-nền)
2. [Kiến trúc hybrid](#2-kiến-trúc-hybrid)
3. [**Logic mapping**](#3-logic-mapping) ← phần dài nhất, đọc kỹ
4. [Bề mặt BFF (Next.js)](#4-bề-mặt-bff-nextjs)
5. [Bề mặt Backend (FastAPI)](#5-bề-mặt-backend-fastapi)
6. [Cookie](#6-cookie)
7. [CSRF](#7-csrf)
8. [Mật khẩu](#8-mật-khẩu)
9. [Rate limiting, lockout, CAPTCHA](#9-rate-limiting-lockout-captcha)
10. [JWT](#10-jwt)
11. [Xác minh email (P1)](#11-xác-minh-email-p1)
12. [2FA (P1/P2)](#12-2fa-p1p2)
13. [OAuth / OIDC (P2)](#13-oauth--oidc-p2)
14. [Authorization phía server](#14-authorization-phía-server)
15. [Logging và monitoring](#15-logging-và-monitoring)
16. [Mô hình dữ liệu](#16-mô-hình-dữ-liệu)
17. [Mã lỗi](#17-mã-lỗi)
18. [Delta OpenAPI](#18-delta-openapi)
19. [Cấu hình](#19-cấu-hình)
20. [Kiểm thử](#20-kiểm-thử)
21. [Phân pha và nghiệm thu](#21-phân-pha-và-nghiệm-thu)
22. [Mâu thuẫn đã xử lý và phần còn mở](#22-mâu-thuẫn-đã-xử-lý-và-phần-còn-mở)
23. [Definition of Done (P0)](#23-definition-of-done-p0)

---

## 1. Phạm vi và quyết định nền

### 1.1. Ai chịu trách nhiệm gì

| Thành phần | Chịu trách nhiệm | **Không** được làm |
|---|---|---|
| **Web (React component)** | Form, trạng thái UI, hiển thị lỗi theo `code` | Không đọc/ghi token, không gọi FastAPI trực tiếp, không quyết định quyền |
| **BFF (Next.js route handler)** | Phát/kiểm cookie phiên, giữ token trong session store, gắn `Authorization` khi proxy, CSRF, chống XSS-token | Không tự ký JWT, không giữ private key, không tự quyết định quyền nghiệp vụ |
| **Backend (FastAPI)** | Băm/kiểm mật khẩu, phát JWT, xoay refresh token, rate limit, lockout, 2FA, OAuth, **mọi quyết định authorization** | Không tin bất kỳ trường danh tính nào do client gửi trong body/query |
| **CDP clone** | System of record của `cdp.profiles` | Không biết gì về mật khẩu, session hay token |
| **Insider clone** | `identifiers` (email/phone/cdp_user_id → profile) | Không tham gia đăng nhập |

### 1.2. Nguyên tắc bất biến

1. **Trình duyệt không bao giờ nhận JWT.** Không `localStorage`, không `sessionStorage`, không URL, không body. Thay thế điều 1 và 2 của `hop-dong-tich-hop-frontend.md` §7.
2. **Danh tính chỉ đến từ phiên đã xác thực phía server.** `cdp_user_id`, `user_id`, `email` không bao giờ đọc từ query param hoặc body. Đây là điều kiện đóng `TODO` ở `src/backend/app/api/v1/routes/recommendations.py:8`.
3. **Mọi quyết định quyền nằm ở FastAPI.** BFF chỉ chuyển tiếp; frontend chỉ là UX.
4. **Hai connection không gói chung một transaction** (`AGENTS.md` §6.2). Đăng ký chạm cả `cdp.profiles` và `app.users` → hai pha có bù trừ, xem §3.6.
5. **TLS bắt buộc** ở mọi môi trường không phải `localhost`. Cookie luôn `Secure` khi `APP_ENV != development`.
6. **Không log secret.** Giữ nguyên `hop-dong-tich-hop-backend.md` §8.6, bổ sung ở §15.

### 1.3. Ngoài phạm vi

- Phân quyền theo vai trò (RBAC/ABAC). Hệ thống chỉ có một loại người dùng. Nếu cần admin, mở spec mới.
- SSO doanh nghiệp, SCIM, quản lý tổ chức.
- Ghép lịch sử duyệt web ẩn danh vào tài khoản sau khi đăng nhập — vẫn **ngoài phạm vi** theo `hop-dong-tich-hop-cdp.md` §1.6. Xem §3.7 để biết chính xác ranh giới.
- Thanh toán, PCI.

### 1.4. Quan hệ với tài liệu đã có

| Tài liệu | Mục | Trạng thái sau tài liệu này |
|---|---|---|
| handbook `recsys-internship-handbook-v3-vi.md` §8 | "Đừng xây: OAuth provider, xác minh email, luồng đặt lại mật khẩu" | **Bị thay thế.** Chủ dự án chốt đưa các mục này vào, chia pha ở §21. Handbook vẫn đúng ở điểm: auth tồn tại để demo cá nhân hóa, và JWT hạn ngắn. |
| handbook §8 | "băm bằng BCrypt" | **Bị thay thế** bằng Argon2id (§8). BCrypt giữ đường xác minh cho 54 user seed. |
| `hop-dong-tich-hop-backend.md` §3.1–§3.5 | Register/login/me, JWT claims | **Giữ nguyên, vẫn hợp lệ** cho client nội bộ (§3.4 demo-accounts đã gỡ ngày 2026-09-24). Web chuyển sang nhóm endpoint session mới (§5). |
| `hop-dong-tich-hop-backend.md` §8.2 | Bảng mã lỗi | **Mở rộng** ở §17, không sửa mã cũ. |
| `hop-dong-tich-hop-frontend.md` §7.1, §7.2, §7.8 | Token trong `sessionStorage`, gửi `Authorization` từ browser, không refresh | **Bị thay thế** bởi §4 và §6. Các điều 3–7 của §7 giữ nguyên tinh thần, diễn đạt lại ở §4.5. |
| `hop-dong-tich-hop-cdp.md` §1.6 | Ghép lịch sử ẩn danh ngoài phạm vi | **Giữ nguyên.** Xem §3.7. |
| `docs/product.md` §4.7.5 | "Hết phiên (JWT hạn ngắn)" | Hành vi UI giữ nguyên; nguyên nhân đổi từ "JWT hết hạn" sang "phiên hết hạn" (§3.8). |
| `db/init/01_vota.sql`, `db/vota_schema.sql` | `password_hash -- BCrypt` | Comment phải sửa thành `-- Argon2id (PHC string); bcrypt hợp lệ cho user seed`, cùng `docs/DATABASE_SCHEMA.md` §4 và §11 (`AGENTS.md` §6). |

---

## 2. Kiến trúc hybrid

```text
┌─────────────┐
│  Trình duyệt │  Cookie: vota_sid (HttpOnly, Secure, SameSite=Lax, Path=/)
│             │          vota_csrf (readable, SameSite=Lax)   ← double-submit
└──────┬──────┘
       │ fetch('/api/...', { credentials: 'same-origin', headers: { 'X-CSRF-Token': … } })
       ▼
┌──────────────────────────────────────────────────────────────┐
│ BFF — Next.js route handler (src/frontend/src/app/api/…)      │
│  1. đọc vota_sid → Redis: session:{sid}                       │
│  2. kiểm CSRF + Origin                                        │
│  3. lấy access_token trong session; sắp hết hạn → refresh     │
│  4. proxy sang FastAPI kèm Authorization: Bearer …            │
│     và X-Request-ID                                           │
│  KHÔNG có private key. KHÔNG tự ký token.                     │
└──────┬───────────────────────────────────────────────────────┘
       │ HTTPS nội bộ
       ▼
┌──────────────────────────────────────────────────────────────┐
│ Backend — FastAPI                                             │
│  • /api/v1/auth/session/*  ← chỉ BFF gọi (X-Service-Token)     │
│  • /api/v1/auth/*          ← contract v1 cũ, client nội bộ     │
│  • mọi endpoint khác: bearerAuth → AuthPrincipal               │
│  • giữ private key ký RS256, công bố JWKS                      │
└──────┬─────────────────────────┬─────────────────────────────┘
       │ DATABASE_URL            │ CdpClient (CDP_DATABASE_URL)
       ▼                         ▼
   app.users, app.*          cdp.profiles, cdp.events
```

**Vì sao BFF không tự ký JWT:** private key chỉ tồn tại ở FastAPI. Next.js là tiến trình hướng ra internet và deploy độc lập; đưa khóa ký vào đó nhân đôi bề mặt tấn công và tạo hai nguồn phát hành phải thu hồi riêng. BFF **nhận** token từ FastAPI lúc đăng nhập, cất trong session store, và **xin token mới** bằng refresh token. Nó là người giữ token, không phải người phát hành.

**Vì sao vẫn cần JWT khi đã có session:** Agent (`src/backend/app/agents`), job, CLI, test và các service nội bộ sau này (Insider push, embed job) gọi API không qua trình duyệt. Chúng không có cookie. JWT là dạng danh tính duy nhất mà cả hai đường dùng chung, nên FastAPI chỉ phải hiện thực **một** resolver danh tính (§3.5).

---

## 3. Logic mapping

Đây là phần dễ làm sai nhất, vì hệ thống có **sáu** định danh khác nhau cho cùng một con người, mỗi cái do một thành phần sở hữu, với vòng đời khác nhau. Mục này định nghĩa từng cái, quy tắc chuyển đổi giữa chúng, và điều gì xảy ra ở mọi chuyển trạng thái.

### 3.1. Sáu định danh

| # | Định danh | Ví dụ | Ai sinh | Ở đâu | Vòng đời | Ai được thấy |
|---|---|---|---|---|---|---|
| ① | `sid` — session id | `s_01JB3Y…` (128-bit, base32url) | BFF | Cookie `vota_sid` + key Redis `session:{sid}` | Xoay mỗi lần đổi mức đặc quyền; tối đa 12 giờ | Trình duyệt (opaque) + BFF |
| ② | `anon_id` — khách vãng lai | `a_01JB3Y…` | BFF | Trong bản ghi session | Bằng vòng đời session khách | BFF |
| ③ | `user_id` — khóa chính tài khoản | `uuid` | Postgres (`gen_random_uuid()`) | `app.users.user_id` | Vĩnh viễn | Backend, BFF, JWT `sub` |
| ④ | `cdp_user_id` — **danh tính nghiệp vụ** | `VP0000001`, `VPW7K3F9QZ2M` | Seed (user demo) hoặc Backend (user đăng ký) | `cdp.profiles.cdp_user_id`, gương ở `app.users.cdp_user_id` | Vĩnh viễn | Backend, CDP, JWT claim `cdp_user_id` |
| ⑤ | `oauth_subject` — `(provider, sub)` (P2) | `("google", "1179…")` | Nhà cung cấp OIDC | `app.oauth_identities` | Vĩnh viễn | Backend |
| ⑥ | `identifier` của Insider | `("email", "minh.anh@…")` | Job đẩy sang Insider | `insider.identifiers` | Có `valid_from`/`valid_to` | Insider clone |

**Định danh cốt lõi là ④ `cdp_user_id`, không phải ③ `user_id`.** Toàn bộ `app.carts`, `app.bookings`, `app.conversations`, `cdp.events` và engine recommendation khoá theo `cdp_user_id` (`docs/spec/DATABASE_SCHEMA.md` §4). `app.users` chỉ là *credential + persona*. Hệ quả thực tế: **auth không sinh ra danh tính, nó chỉ chứng minh quyền dùng một `cdp_user_id` đã có.**

### 3.2. Chuỗi ánh xạ đầy đủ

```text
Cookie vota_sid
   │  ① BFF: Redis GET session:{sid}
   ▼
Bản ghi session  { user_id?, cdp_user_id?, anon_id?, access_token, refresh_token, amr, … }
   │  ② BFF: gắn Authorization: Bearer <access_token>
   ▼
JWT  { sub: user_id, cdp_user_id, email, sid, amr, iss, aud, exp }
   │  ③ FastAPI: kiểm chữ ký + claim → AuthPrincipal
   ▼
AuthPrincipal(user_id, cdp_user_id, email, session_id, amr, email_verified)
   │  ④ use case đọc principal.cdp_user_id
   ▼
app.carts.cdp_user_id · app.bookings.cdp_user_id · cdp.events.cdp_user_id · recommend(cdp_user_id)
```

Bốn mũi tên, bốn chỗ có thể hỏng. Mỗi chỗ có quy tắc riêng ở §3.3–§3.6.

### 3.3. ① Cookie → bản ghi session (BFF sở hữu)

Redis, key `session:{sid}`, giá trị JSON, `EXPIRE` đặt bằng **idle timeout**:

```json
{
  "v": 1,
  "state": "authenticated",
  "userId": "4f0e…",
  "cdpUserId": "VP0000001",
  "anonId": null,
  "email": "minh.anh@example.com",
  "emailVerified": true,
  "amr": ["pwd", "otp"],
  "accessToken": "eyJhbGciOiJSUzI1NiIs…",
  "accessTokenExp": 1789000000,
  "refreshToken": "rt_01JB…",
  "refreshTokenExp": 1789600000,
  "csrfToken": "c_9f2…",
  "createdAt": 1788996400,
  "lastSeenAt": 1788996400,
  "absoluteExp": 1789039600,
  "uaHash": "sha256:3f1c…",
  "ipPrefix": "203.0.113.0/24"
}
```

| Trường | Quy tắc |
|---|---|
| `state` | `anonymous` \| `pending_mfa` \| `authenticated`. Ba trạng thái, không có trạng thái thứ tư. |
| `userId`, `cdpUserId`, `email` | `null` khi `state = anonymous`. Với `pending_mfa`, `userId` đã biết nhưng **`cdpUserId` vẫn `null`** — chưa xác thực xong thì chưa được mang danh tính nghiệp vụ. |
| `amr` | Authentication methods references: `pwd`, `otp`, `webauthn`, `oauth`. Dùng cho step-up ở §14. |
| `accessToken` | JWT hạn 10 phút. Chỉ tồn tại trong Redis và trên dây BFF→FastAPI. |
| `refreshToken` | Token đục hạn 12 giờ, **một lần dùng** (§10.4). |
| `absoluteExp` | `createdAt + 12h`. Không gia hạn được bằng hoạt động. |
| `uaHash` | SHA-256 của `User-Agent`. Lệch → huỷ phiên (§3.8, trường hợp H). |
| `ipPrefix` | /24 (IPv4) hoặc /48 (IPv6). Lệch → **không huỷ**, chỉ ghi log `session.ip_changed` và bắt xác thực lại cho hành động nhạy cảm (§14.3). Người dùng di động đổi IP liên tục; huỷ phiên theo IP là làm hỏng sản phẩm, không phải làm chặt bảo mật. |

**Idle timeout** 30 phút: mỗi request hợp lệ đặt lại `EXPIRE` và `lastSeenAt`. **Absolute timeout** 12 giờ: kiểm `absoluteExp` trong code, không dựa vào TTL của Redis.

**Redis mất dữ liệu** (restart, eviction): mọi phiên biến mất → người dùng thấy như đăng xuất. Chấp nhận được và là lý do refresh token cũng nằm trong session chứ không chỉ ở Redis — xem §16.2, bảng `app.refresh_tokens` giữ bản bền để thu hồi được kể cả khi Redis trống.

### 3.4. ② Session → JWT (BFF xin, FastAPI phát)

BFF **không ký**. Nó gọi `POST /api/v1/auth/session/token` kèm `X-Service-Token` và refresh token, nhận cặp mới.

```text
Mỗi request proxy:
  exp - now > 60s  ──▶ dùng access token đang có
  exp - now ≤ 60s  ──▶ refresh trước (§10.4), ghi token mới vào session, rồi mới proxy
  refresh 401      ──▶ huỷ phiên, trả 401 SESSION_EXPIRED cho Web
```

Refresh đồng thời (nhiều tab): BFF lấy khoá Redis `lock:refresh:{sid}` (`SET NX PX 5000`). Bên thua khoá chờ tối đa 2 giây rồi đọc lại session. Không có khoá thì rotation một-lần-dùng sẽ khiến tab thứ hai tự đá mình ra.

Với `state = anonymous`, BFF **không gắn `Authorization`**. Request đi tới FastAPI không có token, và mọi API đọc phải chấp nhận (giữ nguyên `hop-dong-tich-hop-backend.md` §3.5, điều 2).

### 3.5. ③ JWT → `AuthPrincipal` (FastAPI sở hữu)

Một resolver duy nhất, dùng chung cho request từ BFF và từ service nội bộ:

```python
# src/backend/app/application/auth/principal.py  (application layer, không import FastAPI)
@dataclass(frozen=True)
class AuthPrincipal:
    user_id: str
    cdp_user_id: str          # không bao giờ None — principal tồn tại nghĩa là đã xác thực
    email: str
    session_id: str | None    # sid khi đến từ BFF; None khi là service nội bộ
    amr: tuple[str, ...]
    email_verified: bool
```

```python
# src/backend/app/application/auth/bearer.py  (application layer, không import FastAPI) — resolver duy nhất
def bearer_token(authorization: str | None) -> str | None     # không có header → None; không phải Bearer/rỗng → TokenInvalid
async def verified_principal(token, verifier, revoked) -> AuthPrincipal              # chữ ký/claim rồi jti thu hồi (§10.3 điểm 9)
async def principal_from_header(authorization, verifier, revoked) -> AuthPrincipal | None
```

```python
# src/backend/app/api/deps.py  (chỉ HTTP; theo docs/prd/architecture.md §2) — bọc các hàm trên
async def current_principal(...) -> AuthPrincipal          # 401 nếu thiếu/hỏng
async def optional_principal(...) -> AuthPrincipal | None  # None cho khách vãng lai
```

Tool `get_recommendations` của Itinerary Agent ở `ITINERARY_DATA_MODE=inprocess` (`application/itinerary/engine_tools.py`) dùng cùng `principal_from_header`, và chỉ xác minh khi tool thật sự được gọi. Token hỏng, hết hạn hoặc bị thu hồi thì tool lỗi 401, không hạ thành khách (§3.11 dòng 2). Header vắng hoặc chuỗi rỗng thì là khách, giống mode `http` (adapter HTTP bỏ header rỗng). Kho thu hồi lỗi thì tool trả `SEARCH_UNAVAILABLE` 503 retryable. Token chỉ nằm trong phạm vi request, không vào graph state, log hay trace (`hop-dong-tich-hop-itinerary-assistant.md` §2.4).

Quy tắc dùng, không có ngoại lệ:

| Nhóm endpoint | Dependency | Thiếu danh tính thì |
|---|---|---|
| `/products`, `/products/{id}`, `/destinations`, `/search`, `/recommendations`, `/popular`, `/assistant/*` | `optional_principal` | Trả kết quả không cá nhân hóa (`strategy: popular`) |
| `/bookings`, `/bookings/{ref}`, `/events` | `current_principal` | `401 UNAUTHENTICATED` |
| `/cart/*`, `/booking-drafts/*` | `cart_owner`: Bearer hợp lệ → người dùng; không có Bearer nhưng có `X-Service-Token` hợp lệ **và** `X-Guest-Id` đúng dạng → khách (§3.7a) | `401 UNAUTHENTICATED` |
| `/guest-bookings/merge` | `X-Service-Token` **và** `current_principal` | `401` |
| `/auth/session/*` | `X-Service-Token` | `401 INVALID_TOKEN` |

**Đóng `TODO` hiện tại.** `recommendations.py` phải đổi:

```python
# TRƯỚC — danh tính do client tự khai, ai cũng đọc được gợi ý của người khác
def recommendations(request: Request, k: int = 5, cdp_user_id: str | None = None):
    return request.app.state.recommend(cdp_user_id, k=k)

# SAU — danh tính từ phiên đã xác thực
def recommendations(request: Request, k: int = 5,
                    principal: AuthPrincipal | None = Depends(optional_principal)):
    return request.app.state.recommend(principal.cdp_user_id if principal else None, k=k)
```

Query param `cdp_user_id` **bị gỡ khỏi `/recommendations`**. Nó là IDOR: catalog seed có 2.000 profile và ID tuần tự `VP0000001`… nên đoán được. Cần gọi theo `cdp_user_id` tuỳ ý cho demo/eval thì dùng `GET /api/v1/internal/recommendations?cdp_user_id=…` với `X-Service-Token`, tắt khi `APP_ENV=production` (§14.4).

### 3.6. ④ `user_id` ↔ `cdp_user_id` — ánh xạ khó nhất

#### 3.6.1. Ràng buộc từ database

```sql
-- db/init/01_vota.sql
cdp_user_id text NOT NULL UNIQUE REFERENCES cdp.profiles (cdp_user_id)

GRANT SELECT ON cdp.products TO vota_app;           -- vota_app CHỈ đọc được products
GRANT INSERT, UPDATE ON cdp.profiles TO cdp_writer; -- chỉ cdp_writer ghi được profiles
```

Ba hệ quả bắt buộc phải tôn trọng:

1. **Quan hệ là 1–1 và bất biến.** `UNIQUE` hai chiều. Không có tài khoản dùng chung profile, không có người dùng đổi `cdp_user_id`. Đổi `cdp_user_id` = mất toàn bộ lịch sử, giỏ, booking — không có luồng nào trong sản phẩm được phép làm việc đó.
2. **Role của Backend (`vota_app`) không tạo được `cdp.profiles`.** Nó cũng không `SELECT` được bảng đó. Nên đăng ký **bắt buộc** đi qua `CdpClient` bằng connection `CDP_DATABASE_URL`.
3. **Hai connection, không transaction chung** (`AGENTS.md` §6.2). Phải là hai pha có bù trừ, đúng khuôn mẫu checkout đã chốt.

> `CdpClient` (`application/ports/cdp_client.py`) **hiện chưa có** phương thức tạo profile. Phải thêm `ensure_profile(cdp_user_id, *, home_city=None) -> None` (idempotent: đã có thì không lỗi), hiện thực ở `LocalCdpClient` bằng `INSERT … ON CONFLICT (cdp_user_id) DO NOTHING`. Đây là thay đổi port, cần reviewer Data/Integration (`architecture-repo.md` §11).

#### 3.6.2. Cấp phát `cdp_user_id` mới

| Dải | Dạng | Ai cấp | Ghi chú |
|---|---|---|---|
| `VP` + 7 chữ số | `VP0000001`–`VP0002000` | **chỉ job seed** | `src/data_collection/seed/seed_histories.py`. Backend **không được** cấp trong dải này. |
| `VPW` + 12 ký tự Crockford base32 | `VPW7K3F9QZ2M4XHB` | Backend, lúc đăng ký | `VPW` = "V-OTA Profile, Web-registered" |

Sinh từ `secrets.token_bytes(10)`, không phải từ bộ đếm. Lý do: ID tuần tự cho phép đếm số người dùng và đoán ID hàng xóm; một bảng đếm dùng chung cũng cần khoá giữa hai connection mà ta vừa quyết định không dùng chung transaction. Va chạm ở 80 bit là không đáng lo, và `ON CONFLICT DO NOTHING` + kiểm tra lại vẫn bắt được.

Tách dải cũng giữ cho `make demo-db-reset` chạy lại seed mà không bao giờ đè lên profile của người dùng thật.

#### 3.6.3. Đăng ký — hai pha có bù trừ

Thứ tự bị ép cứng: `app.users.cdp_user_id` là `NOT NULL`, nên không thể tạo user trước rồi gán profile sau. **CDP luôn đi trước.**

```text
① SELECT 1 FROM app.users WHERE email = lower(:email)         -- kiểm sớm, tiết kiệm một profile rác
   có → 409 EMAIL_ALREADY_EXISTS

② cdp_user_id := "VPW" + base32(secrets.token_bytes(10))

③ await cdp_client.ensure_profile(cdp_user_id)                -- CDP_DATABASE_URL, cdp_writer
   CdpUnavailableError → 503 CDP_UNAVAILABLE, retryable: true, KHÔNG tạo user

④ INSERT INTO app.users (…, cdp_user_id) VALUES (…)           -- DATABASE_URL, vota_app, một transaction
   unique violation trên email → 409 EMAIL_ALREADY_EXISTS   (thua cuộc đua với ①)
   unique violation trên cdp_user_id → quay lại ②, tối đa 3 lần

⑤ Thành công → phát phiên (§3.8 trường hợp B)
```

**Bù trừ khi ④ hỏng:** dòng `cdp.profiles` ở ③ trở thành mồ côi. Ta **cố ý không xoá nó**:

- `cdp_writer` chỉ có `INSERT, UPDATE` trên `cdp.profiles`, **không có `DELETE`**. Xoá được thì phải nới quyền, mà nới quyền để dọn rác là đánh đổi sai.
- Một profile rỗng không có event thì vô hại: nó không xuất hiện trong popular, không ảnh hưởng recall, không lộ dữ liệu.
- Ghi log `auth.orphan_profile` kèm `cdp_user_id` để job dọn theo lịch xử lý sau nếu cần.

Điểm này khác checkout (ở đó `cancel_purchases` xoá được vì `cdp_writer` có `DELETE` trên `cdp.events`). Khác biệt là cố ý và bắt nguồn từ bảng GRANT, không phải sơ suất.

**Tài khoản mới:** 0 event → `/recommendations` trả `coldStart: true`, `strategy: "popular"`, `because: []`. Giữ nguyên `hop-dong-tich-hop-backend.md` §3.1.

#### 3.6.4. Đăng nhập — tra ngược

```sql
SELECT user_id, email, password_hash, display_name, cdp_user_id, persona
FROM app.users WHERE email = lower(:email);
```

`cdp_user_id` **đi cùng hàng user**, không phải một lượt truy vấn sang CDP. Backend không cần và không được `SELECT cdp.profiles` bằng `vota_app` (không có quyền). Gương `app.users.cdp_user_id` tồn tại chính vì lý do này.

Sai email và sai mật khẩu trả **cùng một** `401 INVALID_CREDENTIALS`, cùng thông điệp, và — quan trọng — **cùng độ trễ**: email không tồn tại vẫn chạy một lần `argon2.verify` với hash giả cố định, nếu không thì thời gian phản hồi thành oracle liệt kê tài khoản.

### 3.7. Khách vãng lai và ranh giới CDP

| Việc | Trong phạm vi? | Vì sao |
|---|---|---|
| Phiên khách có `anon_id`, giữ được giỏ tạm ở client | Có | Cần cho CSRF và rate limit theo phiên |
| Ghi `cdp.events` cho khách chưa đăng nhập | **Không** | `cdp.events.cdp_user_id` là `NOT NULL REFERENCES cdp.profiles`. Tạo profile cho mỗi khách vãng lai sẽ bơm rác vào system of record và làm lệch mọi chỉ số Evaluation. |
| Ghép lịch sử ẩn danh vào tài khoản khi đăng nhập | **Không** | `hop-dong-tich-hop-cdp.md` §1.6 đặt ngoài phạm vi. |

Vì vậy `anon_id` **chưa bao giờ** được ghi xuống database. Nó chỉ sống trong bản ghi session, phục vụ CSRF và rate limit. Code hiện tại đã đúng hướng: `BehaviourTracker.track_search` no-op khi `cdp_user_id is None` (`application/tracking/behaviour.py:62`).

Nếu sau này muốn mở phần ghép: nó cần một bảng `app.anonymous_links(anon_id, cdp_user_id, linked_at)` và một quyết định của CDP về sự kiện `identify`. Đừng tự thêm; mở spec và hỏi reviewer CDP (`AGENTS.md` §6).

### 3.7a. Giỏ và đơn nháp của khách chưa đăng nhập (thêm 2026-10-01)

> Thêm theo đề xuất đã chốt `docs/prd/update-archive/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md` (FR-BKG-01, FR-USR-03). Bộ luật: `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md` §8, §9. **Cần chủ auth rà lại** phần cookie và header dưới đây.

Khách chưa đăng nhập thêm giỏ, Đặt ngay và điền thông tin thanh toán được; chỉ tạo đơn cần đăng nhập. Việc này **không** đổi ranh giới của §3.7: khách vẫn không sinh event CDP, không có profile, và không có định danh nào của khách được ghi xuống PostgreSQL.

| Điểm | Quy định |
|---|---|
| Định danh | `guestId` = `g_` + 22 ký tự base64url (128 bit ngẫu nhiên), do **BFF** phát. Tách khỏi `anon_id`: phiên khách hết sau 30 phút không hoạt động, còn giỏ của khách phải sống 3 ngày |
| Cookie | `vota_guest`: HttpOnly, `SameSite=Lax`, `Secure` như `vota_sid`, `Path=/`, `Max-Age` 3 ngày. Chỉ chứa `guestId`, không chứa dữ liệu. BFF phát khi khách chưa đăng nhập gọi lần đầu vào `/cart*` hoặc `/booking-drafts*` |
| Chuyển tiếp | BFF xoá `x-guest-id` do trình duyệt gửi, rồi tự gắn `X-Service-Token` + `X-Guest-Id` cho request của khách tới hai nhóm route trên. Trình duyệt không đọc được và không tự đặt được mã khách |
| Backend tin gì | `X-Guest-Id` chỉ có nghĩa khi `X-Service-Token` hợp lệ (so sánh hằng thời gian). Có Bearer thì Bearer thắng, mã khách bị bỏ qua |
| Lưu ở đâu | Redis: `guest:cart:{guestId}`, `guest:draft:{draftId}`, `guest:drafts:{guestId}`, TTL `GUEST_BOOKING_TTL_DAYS` (3 ngày). `guestId` **không bao giờ** được ghi vào PostgreSQL, log nghiệp vụ hay CDP |
| Gộp khi đăng nhập | Request đầu tiên tới `/cart*`, `/booking-drafts*`, `/bookings*` của phiên đã đăng nhập mà còn cookie `vota_guest`: BFF gọi `POST /api/v1/guest-bookings/merge` (`X-Service-Token` + Bearer) rồi xoá cookie. Backend chép mục chưa có vào giỏ tài khoản, bỏ mục trùng, chuyển đơn nháp còn hạn, xoá dữ liệu Redis của khách. Gọi lại không gây trùng |
| Không mở ra ngoài | BFF trả `404` cho mọi request từ trình duyệt tới `/api/v1/guest-bookings/*` |

Quyền sở hữu: đơn nháp của khách chỉ đọc được bằng đúng `guestId` đã tạo nó; đơn nháp của tài khoản chỉ đọc được bằng `cdp_user_id` của tài khoản đó. Sai chủ thì `404 BOOKING_DRAFT_NOT_FOUND`, không lộ sự tồn tại.

### 3.8. Bảng chuyển trạng thái phiên

Mỗi dòng là một chuyển trạng thái. Cột "Xoay sid" là biện pháp chống **session fixation**: bất cứ khi nào mức đặc quyền đổi, sid cũ bị `DEL` và sid mới được phát.

| # | Sự kiện | state trước → sau | Xoay `sid` | `cdpUserId` | Việc kèm theo |
|---|---|---|---|---|---|
| A | Lần đầu vào site | — → `anonymous` | phát mới | `null` | Sinh `anon_id`, `csrfToken` |
| B | Đăng ký thành công | `anonymous` → `authenticated` | **Có** | gán từ §3.6.3 | Gửi mail xác minh (P1); không chặn đăng nhập |
| C | Đăng nhập, không 2FA | `anonymous` → `authenticated` | **Có** | gán từ `app.users` | `UPDATE app.users SET last_login_at = now()`; xoá bộ đếm lockout |
| D | Đăng nhập, có 2FA | `anonymous` → `pending_mfa` | **Có** | **vẫn `null`** | Phiên này **chỉ** gọi được `/auth/session/mfa/verify`; mọi route khác trả `403 MFA_REQUIRED` |
| E | Nhập đúng OTP | `pending_mfa` → `authenticated` | **Có** (lần hai) | gán | `amr += ["otp"]` |
| F | Đăng nhập tài khoản khác khi đang đăng nhập | `authenticated` → `authenticated` | **Có** | đổi sang user mới | Là đăng xuất + đăng nhập; Web xoá **mọi** cache client (`hop-dong-tich-hop-frontend.md` §7.7) |
| G | Đăng xuất | bất kỳ → — | `DEL` | — | Thu hồi refresh token, xoá cookie, `revoked_reason='logout'` |
| H | `uaHash` lệch | bất kỳ → — | `DEL` | — | Log `session.ua_mismatch` mức WARN |
| I | Quá idle 30′ / absolute 12h | bất kỳ → — | `DEL` | — | Web hiện modal "Phiên đăng nhập đã hết hạn" (`product.md` §4.7.5) |
| J | Đổi mật khẩu | `authenticated` → `authenticated` | **Có** | giữ | Thu hồi **mọi** phiên khác của user; phiên hiện tại sống tiếp với sid mới |
| K | Bật/tắt 2FA | `authenticated` → `authenticated` | **Có** | giữ | Như J |
| L | Xác minh email xong | `authenticated` → `authenticated` | Không | giữ | `emailVerified = true` trong session và trong JWT lần refresh kế |

Chỉ dòng L không xoay sid, vì nó không đổi mức đặc quyền theo hướng có thể bị lợi dụng.

### 3.9. OAuth subject → user (P2)

```text
Callback (code, state, iss)
  │ state khớp Redis oauth:state:{state} và chưa dùng? → DEL ngay (một lần dùng)
  │ PKCE: gửi code_verifier tương ứng
  ▼
ID token đã kiểm (iss, aud, nonce, exp, chữ ký qua JWKS của provider)
  │
  ├─ (provider, sub) có trong app.oauth_identities? ──▶ user_id đó. Xong.
  │
  ├─ Không, nhưng email trùng app.users.email:
  │     email_verified của provider = true  ──▶ liên kết vào user đó, ghi audit
  │     email_verified = false              ──▶ 409 OAUTH_EMAIL_UNVERIFIED, KHÔNG liên kết
  │
  └─ Không trùng gì ──▶ tạo user mới, chạy đúng §3.6.3 từ bước ② (password_hash = NULL)
```

Nhánh giữa là chỗ chiếm tài khoản (account takeover) kinh điển: provider nào cho phép đặt email tuỳ ý mà không xác minh thì `email` của nó không phải bằng chứng danh tính. Chỉ liên kết khi provider khẳng định `email_verified: true`.

`password_hash` cho phép `NULL` sau P2 → cần đổi DDL (`ALTER TABLE app.users ALTER COLUMN password_hash DROP NOT NULL`) và bổ sung `CHECK (password_hash IS NOT NULL OR EXISTS …)` ở tầng ứng dụng, không ở database. Ghi vào cùng commit với doc (`AGENTS.md` §6).

### 3.10. Insider identifiers

Insider giữ ánh xạ riêng: `identifiers(id_type, id_value) → profile_id`, `valid_to IS NULL` là bản đang hiệu lực, có `UNIQUE INDEX identifiers_current_uq`.

Auth chạm vào đây đúng **một** trường hợp: **người dùng đổi email**. Khi đó job đẩy Insider phải đóng bản ghi cũ (`valid_to = now()`) rồi mở bản mới, chứ không `UPDATE` tại chỗ — unique index chỉ áp cho bản đang hiệu lực nên `UPDATE` sẽ va chạm nếu email mới từng thuộc về ai khác.

Auth **không** gọi Insider trực tiếp. Nó phát sự kiện miền `EmailChanged(cdp_user_id, old, new)`; job đẩy Insider tiêu thụ. Backend không có connection tới database `insider` (`architecture-repo.md` §9).

### 3.11. Bảng quyết định — một request đến thì resolve thế nào

FastAPI, theo thứ tự, dừng ở dòng khớp đầu tiên:

| # | Có `Authorization: Bearer` | Có `X-Service-Token` hợp lệ | Kết quả |
|---|---|---|---|
| 1 | không | không | `principal = None` → khách vãng lai |
| 2 | có, chữ ký/claim hỏng | — | `401 INVALID_TOKEN` (**không** hạ xuống khách vãng lai) |
| 3 | có, `exp` đã qua | — | `401 TOKEN_EXPIRED` |
| 4 | có, hợp lệ, `state=pending_mfa` (`amr` thiếu yếu tố thứ hai mà user đã bật) | — | `403 MFA_REQUIRED` |
| 5 | có, hợp lệ | — | `principal` đầy đủ |
| 6 | không | có | Ngữ cảnh service; chỉ vào được `/auth/session/*` và `/internal/*`. Kèm `X-Guest-Id` đúng dạng thì thêm `/cart/*` và `/booking-drafts/*` với danh tính khách (§3.7a) |
| 7 | có **và** có | — | Ưu tiên Bearer; `X-Service-Token` chỉ mở thêm `/internal/*` và `/guest-bookings/merge` |

Dòng 2 là chủ ý và giữ nguyên `hop-dong-tich-hop-backend.md` §6.5 + `hop-dong-tich-hop-frontend.md` §7.5: **token hỏng không bao giờ im lặng thành khách vãng lai.** Nếu hạ ngầm, người dùng sẽ thấy gợi ý của người lạ mà không hiểu vì sao, và bug xác thực sẽ không bao giờ lộ ra trong demo.

---

## 4. Bề mặt BFF (Next.js)

Đặt tại `src/frontend/src/app/api/auth/`. Các route này **không** proxy — BFF tự xử lý rồi mới gọi FastAPI.

| Route | Method | Body | Trả | Ghi chú |
|---|---|---|---|---|
| `/api/auth/session` | `GET` | — | `{ state, user? , csrfToken }` | Thay `GET /auth/me` cho Web. Khôi phục phiên sau reload. Không bao giờ 401 — khách trả `{ state: "anonymous" }` |
| `/api/auth/login` | `POST` | `{ email, password }` | `{ state }` + `Set-Cookie` | `state` = `authenticated` hoặc `pending_mfa` |
| `/api/auth/register` | `POST` | `{ email, password, fullName }` | như trên | |
| `/api/auth/mfa/verify` | `POST` | `{ code }` | `{ state }` | Chỉ chấp nhận khi `state = pending_mfa` |
| `/api/auth/logout` | `POST` | — | `204` | Xoá cookie kể cả khi backend lỗi |
| `/api/auth/refresh` | `POST` | — | `204` | Chủ động; bình thường refresh tự động khi proxy |

Mọi route khác giữ nguyên proxy catch-all hiện có (`src/frontend/src/app/api/[...path]/route.ts`), bổ sung ba việc: đọc session, kiểm CSRF, gắn `Authorization`.

### 4.1. Sửa proxy hiện có

`route.ts` hiện `new Headers(request.headers)` rồi chỉ xoá `host` và `content-length` — tức là **chuyển tiếp nguyên cookie của người dùng sang FastAPI**. Phải sửa:

```ts
headers.delete('cookie');          // FastAPI không bao giờ thấy cookie của trình duyệt
headers.delete('authorization');   // client không được tự đặt
if (session?.accessToken) headers.set('authorization', `Bearer ${session.accessToken}`);
```

Proxy cũng xoá `x-guest-id` và `x-service-token` do trình duyệt gửi; hai header này chỉ BFF tự gắn cho khách chưa đăng nhập ở `/cart*` và `/booking-drafts*` (§3.7a).

Và phải chuyển tiếp thêm `x-request-id` (hiện response chỉ giữ lại `content-type`, `cache-control`, `location` — mất `X-Request-ID`, phá `hop-dong-tich-hop-backend.md` §8.4).

### 4.2. Quy tắc phía component

Thay điều 1–2 và 8 của `hop-dong-tich-hop-frontend.md` §7:

1. Không component nào chạm token. Không `sessionStorage`, không `localStorage`.
2. `fetch` luôn `credentials: 'same-origin'`; method ghi kèm `X-CSRF-Token` đọc từ cookie `vota_csrf`.
3. Reload → `GET /api/auth/session`. `state = anonymous` → chế độ khách, **không** mở modal.
4. Nhận `401 SESSION_EXPIRED` giữa phiên → modal "Phiên đăng nhập đã hết hạn", điền sẵn email, đăng nhập lại rồi **gửi lại đúng request đã hỏng một lần** (giữ nguyên §7.4 cũ).
5. Khách bấm hành động ghi → modal đăng nhập tại chỗ, xong thì tự thực hiện hành động đang chờ (giữ nguyên §7.6 cũ).
6. Đổi tài khoản hoặc đăng xuất → xoá **mọi** cache client: query cache, `conversationId`, state kế hoạch, badge giỏ (giữ nguyên §7.7 cũ).
7. Không còn "chủ động mở modal khi `expiresIn` < 60s" — BFF tự refresh, Web không biết hạn token.

---

## 5. Bề mặt Backend (FastAPI)

**Nhóm v1 cũ giữ nguyên, không sửa một dòng nào.** (Từ contract 1.18.0 (gộp từ nhánh hồ sơ và đơn hàng; số 1.15.0 và 1.16.0 từng được hai nhánh dùng cho thay đổi khác nhau): `AuthUser` thêm trường `phone` — chỉ thêm, nullable — và có thêm `PATCH /auth/me` sửa họ tên, số điện thoại; BFF ghi họ tên, số điện thoại mới vào phiên sau khi Backend trả 200.) `POST /auth/register`, `POST /auth/login`, `GET /auth/me` tiếp tục trả `AuthResponse` có `accessToken` cho client nội bộ, Agent, CLI và contract test. Đây là điều kiện để không phải lên v2 (`AGENTS.md` §3).

Nhóm mới, **chỉ BFF gọi**, bắt buộc `X-Service-Token`:

| Endpoint | Method | Mục đích |
|---|---|---|
| `/api/v1/auth/session` | `POST` | Xác thực credential, trả `{ accessToken, refreshToken, expiresIn, state, user }` |
| `/api/v1/auth/session/token` | `POST` | Đổi refresh token lấy cặp mới (rotation) |
| `/api/v1/auth/session/revoke` | `POST` | Thu hồi refresh token (logout) |
| `/api/v1/auth/session/mfa/verify` | `POST` | Xác minh OTP, nâng `pending_mfa` → `authenticated` |
| `/api/v1/auth/password` | `PUT` | Đổi mật khẩu (yêu cầu mật khẩu cũ) |
| `/api/v1/auth/password/reset` | `POST` | Yêu cầu link đặt lại (P1) |
| `/api/v1/auth/password/reset/confirm` | `POST` | Đặt lại bằng token (P1) |
| `/api/v1/auth/email/verify` | `POST` | Xác minh email bằng token (P1) |
| `/api/v1/auth/email/verify/resend` | `POST` | Gửi lại (P1) |
| `/api/v1/auth/mfa/totp` | `POST` / `DELETE` | Bật / tắt TOTP (P1) |
| `/api/v1/auth/oauth/{provider}/authorize` | `GET` | Sinh URL + `state` + PKCE (P2) |
| `/api/v1/auth/oauth/{provider}/callback` | `POST` | Đổi code lấy token, ánh xạ theo §3.9 (P2) |
| `/.well-known/jwks.json` | `GET` | Public key để service nội bộ tự kiểm token |

Tách `/auth/session` khỏi `/auth/login` vì hai bên trả khác nhau: `/auth/login` (v1) không có refresh token và không biết `state`. Gộp lại sẽ phải đổi `AuthResponse` — đúng thứ ta tránh.

---

## 6. Cookie

| Cookie | Nội dung | HttpOnly | Secure | SameSite | Path | Max-Age |
|---|---|---|---|---|---|---|
| `vota_sid` | session id đục | **Có** | Có¹ | `Lax` | `/` | phiên (không đặt) |
| `vota_csrf` | CSRF token | **Không**² | Có¹ | `Lax` | `/` | phiên |
| `vota_guest` | mã khách của giỏ và đơn nháp (§3.7a) | **Có** | Có¹ | `Lax` | `/` | 3 ngày; xoá sau khi gộp vào tài khoản |

¹ `Secure` bật trừ khi `APP_ENV=development` trên `localhost`. Ở staging/production, TLS bắt buộc và thêm `Strict-Transport-Security: max-age=31536000; includeSubDomains`.

² Cố ý đọc được: mô hình double-submit cần JavaScript đọc giá trị để đặt vào header. Token này **không phải** bí mật xác thực — biết nó mà không có `vota_sid` thì vô dụng.

**Vì sao `Lax` chứ không `Strict`:** `Strict` làm hỏng hai luồng đã có trong sản phẩm — OAuth callback quay về từ domain provider (P2), và deep link `/login?redirect=…` bấm từ email hoặc từ trang khác thì phiên không được gửi kèm, người dùng thấy mình bị đăng xuất. `Lax` + double-submit CSRF + kiểm `Origin` (§7) cho cùng mức bảo vệ mà không hỏng sản phẩm. Không có endpoint nào đổi state qua `GET`, nên lỗ hổng duy nhất của `Lax` (top-level GET) không áp dụng.

Cookie session **không chứa dữ liệu**, chỉ là con trỏ. Không dùng cookie đã ký chứa payload: không thu hồi được, và mọi lỗi giải mã thành lỗ hổng.

---

## 7. CSRF

Ba lớp, phải qua cả ba:

1. **`SameSite=Lax`** — chặn phần lớn cross-site POST ngay ở trình duyệt.
2. **Double-submit token** — mọi `POST`/`PUT`/`PATCH`/`DELETE` qua BFF phải có header `X-CSRF-Token` khớp `session.csrfToken` trong Redis. So sánh bằng hàm hằng thời gian. Lệch → `403 CSRF_FAILED`. Token xoay cùng lúc với `sid` (§3.8).
3. **Kiểm `Origin`** — `Origin` (hoặc `Referer` khi thiếu) phải thuộc allowlist. Không có cả hai trên request ghi → từ chối.

`GET`, `HEAD`, `OPTIONS` không kiểm CSRF và **không được** đổi state.

Endpoint FastAPI **không** kiểm CSRF: chúng xác thực bằng Bearer + `X-Service-Token`, không bằng cookie, nên không có bề mặt CSRF. Đây là lợi ích trực tiếp của việc BFF cắt cookie ở §4.1.

---

## 8. Mật khẩu

### 8.1. Băm

**Argon2id**, tham số tối thiểu (OWASP 2024):

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| `memory_cost` | 19 MiB (19456 KiB) | |
| `time_cost` | 2 | |
| `parallelism` | 1 | |
| `hash_len` | 32 byte | |
| `salt_len` | 16 byte | thư viện tự sinh, ngẫu nhiên mật mã |

Thư viện `argon2-cffi>=23.1`. Lưu ở dạng chuỗi PHC (`$argon2id$v=19$m=19456,t=2,p=1$…`) trong `app.users.password_hash` — tự mô tả thuật toán nên **không cần thêm cột** `password_algo`.

Tuyệt đối không MD5, SHA-1, SHA-256 trần, hay bất kỳ hàm băm nhanh nào. Không "pepper" tự chế bằng cách nối chuỗi.

### 8.2. Di trú từ BCrypt

**Cập nhật 2026-09-23:** seed đã băm **Argon2id ngay từ đầu** (`seed_histories.demo_password_hash`, đúng tham số §8.1, salt tất định theo `user_id`), nên database seed mới không còn hash BCrypt và không cần bước rehash. Đường bcrypt dưới đây giữ lại **chỉ** cho database đã seed trước ngày này mà chưa seed lại; gỡ khi mọi môi trường đã seed lại, ở một entry history riêng.

Trước đó, 54 user seed dùng chung một hash BCrypt cost 10. Không re-seed và không bắt họ đổi mật khẩu:

```text
verify(plain, stored):
  stored bắt đầu bằng "$argon2"  → argon2.verify
  stored bắt đầu bằng "$2a$/$2b$/$2y$" → bcrypt.checkpw
                                          đúng → UPDATE password_hash = argon2.hash(plain)
                                          (rehash trong request đăng nhập, người dùng không thấy gì)
  khác → từ chối, log auth.unknown_hash_format
```

Sau khi mọi tài khoản đã đăng nhập ít nhất một lần, đường bcrypt chỉ còn là code chết — gỡ ở một entry history riêng, không gỡ sớm.

Cần cả `argon2-cffi` và `bcrypt>=4.1` trong `src/backend/requirements.txt`.

### 8.3. Chính sách mật khẩu

| Quy tắc | Giá trị |
|---|---|
| Độ dài tối thiểu | 8 (giữ nguyên `RegisterRequest.minLength` trong contract v1) |
| Độ dài tối đa | 128 — chặn DoS bằng chuỗi dài vì Argon2 tốn bộ nhớ |
| Chuẩn hoá | Unicode NFKC trước khi băm |
| Danh sách chặn | Top 10.000 mật khẩu phổ biến + `email`, phần trước `@`, `fullName` |
| Bắt buộc ký tự đặc biệt / hoa / số | **Không** |

Không ép thành phần ký tự là cố ý, theo NIST SP 800-63B: nó đẩy người dùng tới `Matkhau@123` và không tăng entropy thật. UI hiện tại (`LoginView.tsx:17-19`) đang kiểm chữ + số phía client — giữ làm gợi ý hiển thị thì được, nhưng **server không được từ chối vì lý do đó**, và mọi kiểm tra phải lặp lại ở server (§14.1).

Không có thời hạn mật khẩu. Ép đổi định kỳ làm mật khẩu yếu đi.

---

## 9. Rate limiting, lockout, CAPTCHA

### 9.1. Ngưỡng

Cửa sổ trượt trong Redis, key hết hạn theo TTL.

| Bảo vệ | Key | Ngưỡng | Cửa sổ | Vượt thì |
|---|---|---|---|---|
| Login theo email | `rl:login:email:{sha256(email)}` | 5 lần sai | 15 phút | `429 TOO_MANY_ATTEMPTS`, khoá 15 phút |
| Login theo IP | `rl:login:ip:{ip}` | 20 lần sai | 15 phút | `429`, khoá 15 phút |
| Login toàn cục theo IP (chống credential stuffing) | `rl:login:ipwide:{ip}` | 100 lần thử | 1 giờ | `429` |
| Đăng ký theo IP | `rl:register:ip:{ip}` | 5 | 1 giờ | `429` |
| Gửi lại mail xác minh | `rl:verify:{user_id}` | 3 | 1 giờ | `429` |
| Yêu cầu đặt lại mật khẩu | `rl:reset:{sha256(email)}` | 3 | 1 giờ | `429` (response vẫn như thành công, §11.2) |
| Xác minh OTP | `rl:mfa:{user_id}` | 5 | 15 phút | `429`, huỷ phiên `pending_mfa` |

Băm email trong key để Redis không chứa PII ở dạng đọc được.

Đếm **cả hai** trục email và IP là cố ý: chỉ theo IP thì kẻ tấn công xoay proxy vẫn thử thoải mái một tài khoản; chỉ theo email thì kẻ tấn công spray một mật khẩu qua 2.000 email mà không chạm ngưỡng nào.

### 9.2. Lockout

Khoá **tạm thời theo thời gian**, không khoá vĩnh viễn: khoá vĩnh viễn biến rate limit thành công cụ DoS nhắm vào người dùng thật. Đăng nhập đúng trong lúc chưa khoá thì xoá sạch bộ đếm.

Response khi khoá:

```json
{ "error": { "code": "TOO_MANY_ATTEMPTS", "message": "Quá nhiều lần thử. Vui lòng thử lại sau 15 phút.",
             "retryable": true, "requestId": "…", "details": { "retryAfterSeconds": 900 } } }
```

kèm header `Retry-After: 900`. Đây là lỗi **duy nhất** của auth có `retryable: true`.

**Không tiết lộ tài khoản có tồn tại hay không** qua thông điệp khoá. Email không tồn tại vẫn tăng bộ đếm IP và trả cùng dạng lỗi.

### 9.3. CAPTCHA

Kích hoạt khi bộ đếm email đạt **3/5** hoặc bộ đếm IP đạt **10/20** — tức trước khi khoá, để người dùng thật gõ nhầm hai lần vẫn có đường đi tiếp.

- Backend trả `401 INVALID_CREDENTIALS` kèm `details.captchaRequired: true`.
- Lần thử kế phải có `captchaToken`; thiếu → `400 CAPTCHA_REQUIRED`.
- Xác minh **phía server**, gọi API nhà cung cấp. Secret chỉ ở FastAPI.
- `APP_ENV=development`/`test`: provider `noop` luôn pass, để test tự động không phụ thuộc mạng.

### 9.4. Rate limit áp ở đâu

Ở **FastAPI**, không ở BFF. BFF chỉ là một client; ai gọi thẳng FastAPI trong mạng nội bộ vẫn phải bị giới hạn. BFF có thể thêm một lớp thô phía trước, không thay thế.

IP thật lấy từ `X-Forwarded-For` **chỉ khi** request đến từ proxy trong danh sách tin cậy (`TRUSTED_PROXIES`); nếu không, dùng địa chỉ peer. Tin `X-Forwarded-For` vô điều kiện = rate limit bỏ qua được bằng một header.

---

## 10. JWT

### 10.1. Claims

```json
{
  "iss": "https://api.vota.local",
  "aud": "vota-api",
  "sub": "4f0e8c2a-…",
  "cdp_user_id": "VP0000001",
  "email": "minh.anh@example.com",
  "email_verified": true,
  "sid": "s_01JB3Y…",
  "amr": ["pwd", "otp"],
  "iat": 1788996400,
  "nbf": 1788996400,
  "exp": 1788997000,
  "jti": "01JB3Y…"
}
```

`cdp_user_id` giữ `snake_case` — ngoại lệ đã chốt ở `hop-dong-tich-hop-backend.md` §3.5, trong body JSON luôn là `cdpUserId`. Claim mới `sid`, `amr`, `email_verified`, `jti`, `nbf` là bổ sung tương thích ngược.

### 10.2. Thuật toán và khoá

| Mục | Quyết định |
|---|---|
| Thuật toán | **RS256** (hoặc ES256). Đối xứng HS256 bị loại: mọi bên kiểm token sẽ cần khoá ký. |
| Khoá riêng | Chỉ FastAPI. File hoặc secret manager, không trong repo, không trong image. |
| Khoá công | `GET /.well-known/jwks.json`, có `kid` |
| Xoay khoá | Hai khoá song song; JWKS trả cả hai suốt thời gian chuyển |
| Hạn access token | **10 phút** |
| Hạn refresh token | **12 giờ**, khớp absolute timeout của phiên |

### 10.3. Kiểm mỗi request — danh sách đầy đủ

Không bỏ dòng nào:

1. Header `alg` nằm trong **allowlist cứng `{RS256, ES256}`**. Mọi giá trị khác, gồm `none`, `HS256`: từ chối. Không đọc `alg` từ token để chọn hàm kiểm — chọn hàm từ cấu hình, chỉ dùng `alg` để xác nhận khớp.
2. `kid` có trong JWKS đang hiệu lực.
3. Chữ ký hợp lệ.
4. `iss` khớp cấu hình chính xác.
5. `aud` chứa `vota-api`.
6. `exp` > now − 60s (dung sai đồng hồ 60 giây, không hơn).
7. `nbf` ≤ now + 60s.
8. `sub` và `cdp_user_id` đều có và không rỗng.
9. `jti` không nằm trong danh sách thu hồi `jwt:revoked:{jti}` (chỉ dùng cho thu hồi khẩn; bình thường hạn 10 phút là đủ).
10. `typ` (nếu có) là `JWT`.

Điểm 1 chặn hai lỗ hổng kinh điển: `alg: none`, và đánh tráo RS256→HS256 để ký bằng chính public key.

Thư viện: `PyJWT>=2.9` với `algorithms=["RS256"]` truyền tường minh mỗi lần gọi `jwt.decode`, `options={"require": ["exp", "iat", "nbf", "sub", "aud", "iss"]}`.

### 10.4. Refresh token

| Thuộc tính | Quyết định |
|---|---|
| Dạng | Chuỗi đục 256-bit, **không phải JWT** |
| Lưu | `app.refresh_tokens`, chỉ lưu SHA-256; bản rõ chỉ tồn tại trong session Redis của BFF |
| Dùng | **Một lần.** Mỗi lần refresh sinh token mới, đánh dấu token cũ `rotated` |
| Phát hiện tái sử dụng | Token đã `rotated` bị dùng lại → **thu hồi cả chuỗi** (`family_id`), huỷ mọi phiên của user, log `auth.refresh_reuse` mức ERROR |
| Ràng buộc | Gắn với `session_id`; refresh bằng token của phiên khác bị từ chối |

Phát hiện tái sử dụng là cách duy nhất biết refresh token đã bị đánh cắp. Không có nó, token bị trộm dùng được đủ 12 giờ mà không ai biết.

---

## 11. Xác minh email (P1)

### 11.1. Đăng ký

1. Tạo tài khoản, `email_verified = false`.
2. Sinh token 256-bit; lưu **SHA-256** vào `app.email_verifications`, TTL 24 giờ, một lần dùng.
3. Gửi `https://<web>/verify-email?token=…`.
4. **Không chặn đăng nhập.** Chưa xác minh vẫn duyệt, tìm kiếm, chat, xem gợi ý.
5. **Chặn** khi chưa xác minh: `POST /bookings` (checkout) và bật 2FA. Lý do: đơn đặt chỗ gửi xác nhận tới email đó.
6. Chưa xác minh → banner cố định kèm nút "Gửi lại".

Chặn ở checkout chứ không ở đăng nhập là có chủ ý: chặn đăng nhập giết demo (người trình bày phải mở hộp thư giữa buổi), còn checkout là chỗ email thật sự có hệ quả.

### 11.2. Đặt lại mật khẩu

Cùng khuôn: token đục, lưu băm, TTL **1 giờ**, một lần dùng, huỷ mọi token cũ khi phát token mới.

`POST /auth/password/reset` **luôn** trả `202` với cùng thông điệp, email có tồn tại hay không. Trả khác nhau là biến endpoint thành máy liệt kê tài khoản.

Đặt lại thành công → thu hồi mọi phiên và mọi refresh token của user (§3.8 dòng J), gửi mail thông báo "mật khẩu vừa đổi".

---

## 12. 2FA (P1/P2)

### 12.1. TOTP (P1)

| Mục | Quyết định |
|---|---|
| Chuẩn | RFC 6238, SHA-1, 6 chữ số, chu kỳ 30 giây |
| Cửa sổ chấp nhận | ±1 chu kỳ |
| Secret | 160-bit, **mã hoá ở tầng ứng dụng** trước khi lưu `app.mfa_credentials` (AES-GCM, khoá trong secret manager) |
| Chống phát lại | Lưu `last_used_counter`; từ chối counter ≤ giá trị đã dùng |
| Recovery code | 10 mã, mỗi mã một lần, lưu **băm Argon2id** như mật khẩu |
| Bật | Yêu cầu mật khẩu hiện tại + một OTP đúng |
| Tắt | Yêu cầu mật khẩu hiện tại + OTP hoặc recovery code |

Secret TOTP mã hoá chứ không chỉ băm, vì server phải đọc lại được để tính mã. Recovery code thì băm, vì chỉ cần so.

### 12.2. WebAuthn (P2)

Tuỳ chọn, mạnh hơn TOTP vì chống được phishing. `user_verification: "preferred"`, attestation `none`, lưu credential id + public key + signature counter ở `app.webauthn_credentials`. Counter lùi → nghi nhân bản, từ chối và cảnh báo.

### 12.3. Phiên và 2FA

Đăng nhập đúng mật khẩu mà user có 2FA → `state = pending_mfa` (§3.8 dòng D). Phiên đó **không có `cdpUserId`** và bị từ chối ở mọi route trừ `/auth/session/mfa/verify`. Không có nửa-đăng-nhập.

---

## 13. OAuth / OIDC (P2)

Chỉ làm **client**, không làm provider.

| Yêu cầu | Quyết định |
|---|---|
| Luồng | Authorization Code + **PKCE bắt buộc** (`code_challenge_method=S256`), kể cả cho confidential client |
| `state` | 256-bit từ `secrets.token_urlsafe`, lưu Redis `oauth:state:{state}` TTL 10 phút, **`DEL` ngay khi dùng**, khớp một lần rồi vô hiệu |
| `nonce` | Bắt buộc, kiểm trong ID token |
| `redirect_uri` | So khớp **chính xác** với allowlist; không wildcard, không so tiền tố |
| Kiểm ID token | Chữ ký qua JWKS của provider, `iss`, `aud`, `nonce`, `exp`, `azp` khi có |
| Ánh xạ tài khoản | Theo đúng §3.9 |
| Token của provider | Access/refresh token của provider **không** lưu nếu không dùng API của họ |

`state` vừa là CSRF cho callback vừa là chỗ mang `redirect` sau đăng nhập. **Không** nhét URL thật vào `state`; lưu nó trong bản ghi Redis và chỉ chấp nhận đường dẫn nội bộ bắt đầu bằng `/` không có `//` (chống open redirect).

PKCE bắt buộc kể cả khi có client secret: nó chặn chiếm mã trên kênh redirect, thứ client secret không bảo vệ được.

---

## 14. Authorization phía server

### 14.1. Frontend chỉ là UX

Mọi thứ frontend kiểm đều phải kiểm lại ở FastAPI, không có ngoại lệ:

| Frontend làm | Server **phải** làm lại |
|---|---|
| Mở modal đăng nhập khi khách bấm Thanh toán | `current_principal` trên `POST /bookings` → `401` |
| Không hiện nút "Thêm vào giỏ" cho khách sạn, vé máy bay | `POST /cart/items` từ chối bằng `422 DIRECT_BOOKING_ONLY` |
| Chỉ gửi mã khách qua BFF | `cart_owner` chỉ nhận `X-Guest-Id` khi `X-Service-Token` hợp lệ; không có thì `401` |
| Kiểm mật khẩu ≥ 8 ký tự (`LoginView.tsx:17-19`) | Validate lại toàn bộ chính sách §8.3 |
| Chỉ hiện đơn của người dùng | `WHERE cdp_user_id = :principal` trong truy vấn |
| Không gửi `cdp_user_id` của người khác | Không đọc `cdp_user_id` từ request, chấm hết |

### 14.2. Quyền sở hữu tài nguyên

Mọi truy vấn chạm dữ liệu người dùng lọc theo `principal.cdp_user_id` **trong mệnh đề `WHERE`**, không kiểm sau khi đã nạp:

```python
# SAI — IDOR: nạp trước, kiểm sau, và đã lộ qua thời gian phản hồi
booking = await repo.get(reference_code)
if booking.cdp_user_id != principal.cdp_user_id: raise Forbidden

# ĐÚNG — không thuộc về mình thì không tồn tại
booking = await repo.get(reference_code, cdp_user_id=principal.cdp_user_id)
if booking is None: raise NotFound("BOOKING_NOT_FOUND")
```

Trả `404 BOOKING_NOT_FOUND` chứ không `403`: `403` xác nhận mã đơn có thật. Khớp đúng mô tả sẵn có ở `hop-dong-tich-hop-backend.md` §8.2 ("Không tìm thấy đơn, **hoặc đơn không thuộc người dùng**").

### 14.3. Step-up

| Hành động | Yêu cầu |
|---|---|
| Đổi mật khẩu, bật/tắt 2FA, đổi email | Nhập lại mật khẩu hiện tại, kể cả khi phiên còn hạn |
| Checkout | `email_verified = true` (P1 trở đi) |
| Sau khi `ipPrefix` đổi | Nhập lại mật khẩu cho nhóm trên |

### 14.4. Endpoint nội bộ

`/api/v1/internal/*` cần `X-Service-Token` (≥ 32 ký tự, so sánh hằng thời gian) và trả `404` khi `APP_ENV=production` trừ khi bật `INTERNAL_API_ENABLED=true` tường minh. Cùng quy tắc với `X-Service-Token` của CDP (`hop-dong-tich-hop-cdp.md` §8.3).

---

## 15. Logging và monitoring

### 15.1. Sự kiện phải ghi

Mọi dòng có `requestId`, `timestamp`, `ipPrefix`, `userAgentHash`, và `userId` khi biết.

| Sự kiện | Mức | Trường thêm |
|---|---|---|
| `auth.login.success` | INFO | `userId`, `amr`, `sid` |
| `auth.login.failure` | INFO | `reason` (`bad_password` \| `unknown_email` \| `locked`), `emailHash` |
| `auth.logout` | INFO | `userId`, `sid` |
| `auth.register.success` | INFO | `userId`, `cdpUserId` |
| `auth.session.rotated` | DEBUG | `oldSid`, `newSid`, `reason` |
| `auth.session.expired` | INFO | `sid`, `reason` (`idle` \| `absolute`) |
| `auth.ratelimit.hit` | WARN | `scope`, `key` (đã băm) |
| `auth.lockout` | WARN | `emailHash`, `durationSeconds` |
| `auth.mfa.failure` | WARN | `userId`, số lần liên tiếp |
| `auth.refresh_reuse` | **ERROR** | `userId`, `familyId` — luôn cảnh báo |
| `auth.orphan_profile` | WARN | `cdpUserId` (§3.6.3) |
| `auth.unknown_hash_format` | ERROR | `userId` |
| `session.ua_mismatch` | WARN | `sid` |
| `session.ip_changed` | INFO | `sid`, `oldPrefix`, `newPrefix` |
| `auth.oauth.link` | INFO | `userId`, `provider`, `linkMode` (`existing` \| `new`) |

### 15.2. Không bao giờ ghi

Mở rộng `hop-dong-tich-hop-backend.md` §8.6: mật khẩu ở bất kỳ dạng nào (kể cả sai), JWT hoặc mảnh JWT, refresh token, session id **đầy đủ** (chỉ ghi 8 ký tự đầu), CSRF token, secret TOTP, recovery code, `code`/`code_verifier` của OAuth, `X-Service-Token`, email đầy đủ (dùng `sha256` hoặc `m***h@example.com`), IP đầy đủ (dùng /24).

### 15.3. Cảnh báo

| Điều kiện | Ngưỡng |
|---|---|
| `auth.refresh_reuse` | **bất kỳ lần nào** |
| Tỷ lệ login thất bại | > 30% trong 5 phút |
| Lockout riêng lẻ | > 20 trong 10 phút (dấu hiệu credential stuffing) |
| `auth.unknown_hash_format` | bất kỳ lần nào |
| `session.ua_mismatch` | > 5 trong 5 phút cho một `userId` |
| Lỗi 5xx của nhóm `/auth/*` | > 1% trong 5 phút |

---

## 16. Mô hình dữ liệu

Chia theo quyết định đã chốt: **Redis giữ phần phù du, Postgres giữ phần bền.** Tiêu chí: mất khi restart thì người dùng chỉ phải đăng nhập lại → Redis. Mất thì dữ liệu bảo mật biến mất hoặc không thu hồi được nữa → Postgres.

### 16.1. Redis

| Key | Kiểu | TTL | Nội dung |
|---|---|---|---|
| `session:{sid}` | string (JSON) | 30 phút, gia hạn | §3.3 |
| `lock:refresh:{sid}` | string | 5 giây | Khoá chống refresh đồng thời (§3.4) |
| `rl:*` | string (counter) | theo §9.1 | Bộ đếm rate limit |
| `lockout:{scope}:{hash}` | string | 15 phút | Dấu khoá |
| `oauth:state:{state}` | string (JSON) | 10 phút | `code_verifier`, `nonce`, `redirect`, `provider` (P2) |
| `jwt:revoked:{jti}` | string | tới `exp` | Thu hồi khẩn (§10.3 điểm 9) |
| `idx:user_sessions:{user_id}` | set | — | Danh sách `sid` để thu hồi hàng loạt (§3.8 dòng J) |
| `guest:cart:{guestId}`, `guest:draft:{draftId}`, `guest:drafts:{guestId}` | string (JSON) / set | 3 ngày (`GUEST_BOOKING_TTL_DAYS`) | Giỏ và đơn nháp của khách chưa đăng nhập (§3.7a). Do **Backend** ghi qua `BOOKING_REDIS_URL`, không phải BFF |

Thêm service `redis:7-alpine` vào `docker-compose.yml`, bind `127.0.0.1` như Postgres, `--requirepass` ngay cả ở local. Cấu hình `maxmemory-policy noeviction` cho database chứa session: `allkeys-lru` sẽ ngẫu nhiên đá người dùng ra khi bộ nhớ đầy.

### 16.2. Postgres — bảng mới trong schema `app`

Toàn bộ vào `db/init/01_vota.sql` **và** `db/vota_schema.sql`, cập nhật `docs/spec/DATABASE_SCHEMA.md` §4 (ERD) và §11 (DDL) trong **cùng commit** (`AGENTS.md` §6).

```sql
-- app.refresh_tokens — chuỗi rotation; giữ bền để thu hồi được kể cả khi Redis trống
CREATE TABLE app.refresh_tokens (
    token_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL REFERENCES app.users (user_id) ON DELETE CASCADE,
    family_id    uuid NOT NULL,                                  -- cả chuỗi rotation; phát hiện tái dùng thì thu hồi theo đây
    token_hash   text NOT NULL UNIQUE,                           -- SHA-256 của token đục, không bao giờ lưu bản rõ
    session_id   text NOT NULL,                                  -- sid ràng buộc; refresh bằng token của phiên khác bị từ chối
    issued_at    timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    rotated_at   timestamptz,                                    -- NULL = còn dùng được
    revoked_at   timestamptz,
    revoked_reason text CHECK (revoked_reason IN
                   ('logout','rotation','reuse_detected','password_change','mfa_change','admin')),
    CONSTRAINT refresh_tokens_window CHECK (expires_at > issued_at)
);
CREATE INDEX refresh_tokens_user_idx   ON app.refresh_tokens (user_id) WHERE revoked_at IS NULL;
CREATE INDEX refresh_tokens_family_idx ON app.refresh_tokens (family_id);

-- app.login_attempts — bằng chứng bền cho điều tra; rate limit thời gian thực vẫn ở Redis
CREATE TABLE app.login_attempts (
    attempt_id   bigserial PRIMARY KEY,
    email_hash   text NOT NULL,                                  -- sha256(lower(email)); không lưu email thô
    user_id      uuid REFERENCES app.users (user_id) ON DELETE SET NULL,  -- NULL = email không tồn tại
    ip_prefix    text NOT NULL,                                  -- /24 hoặc /48
    user_agent_hash text,
    succeeded    boolean NOT NULL,
    failure_reason text CHECK (failure_reason IN
                   ('bad_password','unknown_email','locked','mfa_failed','captcha_failed')),
    attempted_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX login_attempts_email_idx ON app.login_attempts (email_hash, attempted_at DESC);
CREATE INDEX login_attempts_ip_idx    ON app.login_attempts (ip_prefix, attempted_at DESC);

-- app.email_verifications — dùng cho cả xác minh email và đặt lại mật khẩu
CREATE TABLE app.email_verifications (
    verification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL REFERENCES app.users (user_id) ON DELETE CASCADE,
    purpose      text NOT NULL CHECK (purpose IN ('verify_email','reset_password','change_email')),
    token_hash   text NOT NULL UNIQUE,                           -- SHA-256; bản rõ chỉ có trong email
    email        text NOT NULL,                                  -- đích đến; với change_email là email mới
    issued_at    timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    consumed_at  timestamptz,                                    -- một lần dùng
    CONSTRAINT email_verifications_window CHECK (expires_at > issued_at)
);
CREATE INDEX email_verifications_user_idx ON app.email_verifications (user_id, purpose)
    WHERE consumed_at IS NULL;

-- app.mfa_credentials — TOTP (P1) và WebAuthn (P2) trong một bảng
CREATE TABLE app.mfa_credentials (
    credential_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL REFERENCES app.users (user_id) ON DELETE CASCADE,
    kind         text NOT NULL CHECK (kind IN ('totp','webauthn')),
    label        text,                                           -- "iPhone của Minh Anh"
    secret_enc   bytea,                                          -- totp: secret mã hoá AES-GCM (đọc lại được để tính mã)
    public_key   bytea,                                          -- webauthn
    credential_ref text,                                         -- webauthn credential id (base64url)
    sign_count   bigint NOT NULL DEFAULT 0,                      -- webauthn: lùi = nghi nhân bản
    last_counter bigint,                                         -- totp: chống phát lại trong cùng chu kỳ
    confirmed_at timestamptz,                                    -- NULL = đang đăng ký, chưa dùng được
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    CONSTRAINT mfa_totp_shape     CHECK (kind <> 'totp'     OR secret_enc IS NOT NULL),
    CONSTRAINT mfa_webauthn_shape CHECK (kind <> 'webauthn' OR (public_key IS NOT NULL AND credential_ref IS NOT NULL))
);
CREATE UNIQUE INDEX mfa_webauthn_ref_uq ON app.mfa_credentials (credential_ref) WHERE credential_ref IS NOT NULL;
CREATE INDEX mfa_user_idx ON app.mfa_credentials (user_id) WHERE confirmed_at IS NOT NULL;

-- app.mfa_recovery_codes — băm như mật khẩu, mỗi mã một lần
CREATE TABLE app.mfa_recovery_codes (
    code_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL REFERENCES app.users (user_id) ON DELETE CASCADE,
    code_hash    text NOT NULL,                                  -- Argon2id
    created_at   timestamptz NOT NULL DEFAULT now(),
    consumed_at  timestamptz
);
CREATE INDEX mfa_recovery_user_idx ON app.mfa_recovery_codes (user_id) WHERE consumed_at IS NULL;

-- app.oauth_identities — (provider, subject) → user  (P2)
CREATE TABLE app.oauth_identities (
    identity_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL REFERENCES app.users (user_id) ON DELETE CASCADE,
    provider     text NOT NULL CHECK (provider IN ('google','facebook','apple')),
    subject      text NOT NULL,                                  -- claim sub, bất biến theo provider
    email_at_link text NOT NULL,                                 -- email lúc liên kết; audit, không dùng để tra
    linked_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT oauth_identities_uq UNIQUE (provider, subject)
);
CREATE INDEX oauth_identities_user_idx ON app.oauth_identities (user_id);
```

**Không thêm cột nào vào `app.users`** trừ hai cột dưới, cần cho §11 và §3.9:

```sql
ALTER TABLE app.users ADD COLUMN email_verified_at timestamptz;   -- NULL = chưa xác minh
ALTER TABLE app.users ALTER COLUMN password_hash DROP NOT NULL;   -- CHỈ khi P2 bật OAuth
```

Cột `password_hash` đổi comment `-- BCrypt` → `-- Argon2id (PHC string); bcrypt cho user seed, rehash khi đăng nhập`.

### 16.3. Dọn dẹp

Không có bảng nhật ký job (`AGENTS.md` §6.1). Một lệnh CLI `python -m backend.app.cli auth-cleanup` chạy theo lịch, ghi kết quả ra file report:

| Bảng | Xoá |
|---|---|
| `app.refresh_tokens` | `expires_at < now() - 30 ngày` |
| `app.login_attempts` | `attempted_at < now() - 90 ngày` |
| `app.email_verifications` | `expires_at < now() - 7 ngày` |
| `app.mfa_recovery_codes` | `consumed_at < now() - 90 ngày` |

Redis tự hết hạn, không cần dọn.

---

## 17. Mã lỗi

Bổ sung vào `ErrorCode` trong `src/shared/contracts/schemas/common.yaml` và bảng `hop-dong-tich-hop-backend.md` §8.2. **Không sửa mã cũ** — thêm giá trị enum là thay đổi tương thích ngược (`AGENTS.md` §3, `hop-dong-tich-hop-backend.md` §8.7).

| HTTP | Mã | Ý nghĩa | `details` | `retryable` | Web hiển thị |
|---:|---|---|---|---:|---|
| 401 | `UNAUTHENTICATED` | Route cần đăng nhập, không có phiên | — | false | Modal đăng nhập tại chỗ |
| 401 | `SESSION_EXPIRED` | Phiên hết idle/absolute timeout | — | false | Modal "Phiên đăng nhập đã hết hạn", điền sẵn email |
| 403 | `CSRF_FAILED` | Thiếu/sai CSRF token hoặc `Origin` | — | false | Tải lại trang rồi thử lại |
| 403 | `MFA_REQUIRED` | Phiên `pending_mfa` gọi route khác | — | false | Chuyển màn nhập OTP |
| 401 | `MFA_INVALID` | OTP hoặc recovery code sai | `{ attemptsLeft }` | false | Lỗi dưới ô mã |
| 403 | `EMAIL_NOT_VERIFIED` | Checkout khi chưa xác minh email | `{ email }` | false | Banner + nút "Gửi lại" |
| 429 | `TOO_MANY_ATTEMPTS` | Vượt rate limit / đang lockout | `{ retryAfterSeconds }` | **true** | Đếm ngược, khoá nút gửi |
| 400 | `CAPTCHA_REQUIRED` | Cần CAPTCHA mà thiếu `captchaToken` | — | false | Hiện widget CAPTCHA |
| 400 | `CAPTCHA_FAILED` | CAPTCHA không hợp lệ | — | false | Reset widget |
| 400 | `WEAK_PASSWORD` | Vi phạm chính sách §8.3 | `{ reasons: [...] }` | false | Lỗi dưới ô mật khẩu |
| 400 | `INVALID_VERIFICATION_TOKEN` | Token verify/reset sai, hết hạn hoặc đã dùng | `{ purpose }` | false | "Link đã hết hạn" + gửi lại |
| 409 | `OAUTH_EMAIL_UNVERIFIED` | Provider không xác minh email, không liên kết (§3.9) | `{ provider }` | false | "Vui lòng đăng nhập bằng mật khẩu rồi liên kết" |
| 409 | `OAUTH_ALREADY_LINKED` | `(provider, subject)` đã thuộc user khác | `{ provider }` | false | Thông điệp chung |
| 503 | `CDP_UNAVAILABLE` | Không tạo được `cdp.profiles` lúc đăng ký (§3.6.3) | — | **true** | `ErrorState` + Thử lại |

`INVALID_CREDENTIALS`, `INVALID_TOKEN`, `TOKEN_EXPIRED`, `EMAIL_ALREADY_EXISTS`, `VALIDATION_ERROR` giữ nguyên ý nghĩa cũ. `DEMO_ONLY` đã gỡ khỏi enum ngày 2026-09-24.

Hai mã `retryable: true` mới (`TOO_MANY_ATTEMPTS`, `CDP_UNAVAILABLE`) nới danh sách hiện hành. Danh sách đó **đang không khớp nhau giữa hai nguồn**: `hop-dong-tich-hop-backend.md` §8.2 ghi hai mã (`SEARCH_UNAVAILABLE`, `INTERNAL_ERROR`), còn `schemas/common.yaml:163-165` ghi ba (thêm `LLM_UNAVAILABLE`). Sửa cả hai về cùng một danh sách năm mã trong cùng thay đổi: `SEARCH_UNAVAILABLE`, `INTERNAL_ERROR`, `LLM_UNAVAILABLE`, `TOO_MANY_ATTEMPTS`, `CDP_UNAVAILABLE`.

---

## 18. Delta OpenAPI

`AGENTS.md` §3: cập nhật contract **trước**, rồi mới code. Thứ tự file:

1. `src/shared/contracts/schemas/common.yaml` — thêm 13 giá trị `ErrorCode` (§17); sửa mô tả `retryable`.
2. `src/shared/contracts/schemas/auth.yaml` — thêm schema mới, **giữ nguyên** `RegisterRequest`, `LoginRequest`, `AuthUser`, `AuthResponse`.
3. `src/shared/contracts/paths/auth.yaml` — thêm path mới, **giữ nguyên** các path v1 cũ (`/auth/demo-accounts` gỡ sau, ngày 2026-09-24).
4. `src/shared/contracts/openapi.yaml` — khai báo path/schema mới; thêm `serviceToken` vào `securitySchemes`.

```yaml
# openapi.yaml → components.securitySchemes (thêm, không sửa bearerAuth)
    serviceToken:
      type: apiKey
      in: header
      name: X-Service-Token
      description: Chỉ BFF, seed và job nội bộ. Không bao giờ có trong code frontend.
```

```yaml
# schemas/auth.yaml (thêm vào cuối file)
SessionState:
  type: string
  enum: [anonymous, pending_mfa, authenticated]
SessionRequest:
  type: object
  required: [email, password]
  properties:
    email:      { type: string, format: email }
    password:   { type: string }
    captchaToken: { type: string }
SessionResponse:
  type: object
  required: [state]
  properties:
    state:        { $ref: ../openapi.yaml#/components/schemas/SessionState }
    accessToken:  { type: string, description: Chỉ có khi state = authenticated. Không bao giờ tới trình duyệt. }
    refreshToken: { type: string, description: Chuỗi đục, một lần dùng. Chỉ có khi state = authenticated. }
    expiresIn:    { type: integer, description: Giây tới hạn của accessToken }
    user:         { $ref: ../openapi.yaml#/components/schemas/AuthUser }
RefreshRequest:
  type: object
  required: [refreshToken]
  properties:
    refreshToken: { type: string }
MfaVerifyRequest:
  type: object
  required: [code]
  properties:
    code:        { type: string, minLength: 6, maxLength: 10 }
    isRecoveryCode: { type: boolean, default: false }
PasswordChangeRequest:
  type: object
  required: [currentPassword, newPassword]
  properties:
    currentPassword: { type: string }
    newPassword:     { type: string, minLength: 8, maxLength: 128 }
```

Sau khi sửa: `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` từ repo root, và thêm fixture tối thiểu cho `SessionResponse` ở `src/shared/mocks/`.

---

## 19. Cấu hình

Thêm vào `.env.example` và `src/backend/app/core/config.py` (`Settings`). Không giá trị thật nào vào repo.

```env
# --- Auth: Backend (FastAPI) -------------------------------------------------
JWT_PRIVATE_KEY_PATH=./secrets/jwt-private.pem   # RS256; KHÔNG commit, KHÔNG vào image
JWT_PUBLIC_KEY_PATH=./secrets/jwt-public.pem
JWT_ISSUER=https://api.vota.local
JWT_AUDIENCE=vota-api
JWT_ACCESS_TTL_SECONDS=600                       # 10 phút
JWT_CLOCK_SKEW_SECONDS=60

REFRESH_TTL_SECONDS=43200                        # 12 giờ, khớp absolute timeout
SESSION_IDLE_TTL_SECONDS=1800                    # 30 phút
SESSION_ABSOLUTE_TTL_SECONDS=43200

ARGON2_MEMORY_KIB=19456
ARGON2_TIME_COST=2
ARGON2_PARALLELISM=1

AUTH_REDIS_URL=redis://:devpass@localhost:6379/1
TRUSTED_PROXIES=127.0.0.1/32                     # chỉ tin X-Forwarded-For từ đây

CAPTCHA_PROVIDER=noop                            # noop | turnstile | recaptcha
CAPTCHA_SECRET=

SMTP_URL=                                        # P1; trống = ghi mail ra log, dùng cho dev
MAIL_FROM=no-reply@vota.local

INTERNAL_API_ENABLED=false
AUTH_SERVICE_TOKEN=                              # >= 32 ký tự; BFF và FastAPI phải trùng

# --- Auth: BFF (Next.js) -----------------------------------------------------
BACKEND_BASE_URL=http://127.0.0.1:8000
AUTH_SERVICE_TOKEN=                              # cùng giá trị với trên
SESSION_REDIS_URL=redis://:devpass@localhost:6379/1
SESSION_COOKIE_NAME=vota_sid
CSRF_COOKIE_NAME=vota_csrf
ALLOWED_ORIGINS=http://localhost:3000

# --- OAuth (P2) --------------------------------------------------------------
OAUTH_GOOGLE_CLIENT_ID=
OAUTH_GOOGLE_CLIENT_SECRET=
OAUTH_REDIRECT_BASE=http://localhost:3000/auth/callback
```

Sinh khoá dev: `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out secrets/jwt-private.pem && openssl rsa -pubout -in secrets/jwt-private.pem -out secrets/jwt-public.pem`. Thêm `secrets/` vào `.gitignore`.

---

## 20. Kiểm thử

Theo `architecture-repo.md` §10.

### 20.1. Unit (`src/backend/tests/unit/{domain,application,infrastructure}/test_auth_*.py` — đặt theo lớp như `docs/prd/architecture.md` §2)

- Argon2id băm/kiểm; bcrypt cũ kiểm được và **được rehash** sang Argon2id.
- Chính sách mật khẩu: độ dài, danh sách chặn, giống email/tên, NFKC.
- Định dạng `cdp_user_id` mới không rơi vào dải `VP\d{7}`.
- Kiểm JWT: `alg: none` bị từ chối · RS256→HS256 bị từ chối · sai `iss` · sai `aud` · `exp` quá hạn · `nbf` tương lai · `kid` lạ · thiếu claim bắt buộc.
- Cửa sổ trượt rate limit: đúng ngưỡng, hết hạn đúng, hai trục email/IP độc lập.
- Máy trạng thái phiên: cả 12 dòng của §3.8, khẳng định sid có/không xoay.
- Rotation refresh token: xoay bình thường; **tái dùng → thu hồi cả family**.
- TOTP: cửa sổ ±1, từ chối phát lại cùng counter.
- Ánh xạ OAuth (§3.9): cả ba nhánh, gồm `email_verified: false` → `OAUTH_EMAIL_UNVERIFIED`.

### 20.2. Integration (`src/backend/tests/integration/`)

- Đăng ký đi đúng hai pha: tạo `cdp.profiles` **trước** `app.users`.
- `ensure_profile` lỗi → không có hàng nào trong `app.users`.
- `INSERT app.users` lỗi sau khi có profile → profile mồ côi vẫn còn, log `auth.orphan_profile`, không có user.
- `vota_app` **không** `INSERT` được `cdp.profiles` (khẳng định lại ranh giới role — mở rộng `test_local_postgres_adapters.py` đã có).
- Đăng nhập 4 persona seed bằng hash bcrypt hiện có; sau lần đầu, `password_hash` bắt đầu bằng `$argon2id$`.
- Đổi mật khẩu thu hồi mọi phiên khác nhưng giữ phiên hiện tại.
- `WHERE cdp_user_id = :principal`: user A không đọc được booking của user B (`404`, không phải `403`).

### 20.3. Contract (`src/backend/tests/contract/`)

- 4 endpoint v1 cũ **không đổi shape** — chạy cùng fixture như trước khi có tài liệu này.
- Endpoint session mới khớp `SessionResponse`.
- Mọi mã lỗi mới có trong enum `ErrorCode`.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` pass.

### 20.4. Frontend (`src/frontend/tests/`)

- `grep -r "localStorage\|sessionStorage" src/` không có kết quả nào liên quan token.
- Proxy `[...path]/route.ts` **xoá** `cookie` và `authorization` đến từ client, **đặt** `authorization` từ session, **giữ** `x-request-id` hai chiều.
- Request ghi không có `X-CSRF-Token` → `403 CSRF_FAILED`.
- `401 SESSION_EXPIRED` → modal, đăng nhập lại, gửi lại request hỏng **đúng một lần**.
- Đăng nhập tài khoản khác xoá hết cache client.

### 20.5. Kiểm tra bảo mật thủ công trước khi đóng

| Việc | Đạt khi |
|---|---|
| Đăng nhập rồi đọc `document.cookie` | Không thấy `vota_sid` |
| Sửa `sid` trong cookie thành giá trị khác | `401`, không lỗi 500 |
| Gửi `Authorization: Bearer <token của người khác>` từ browser | BFF xoá header, không có tác dụng |
| POST từ origin khác không kèm CSRF | `403` |
| `GET /api/v1/recommendations?cdp_user_id=VP0000001` không đăng nhập | Trả `popular`, **không** trả gợi ý của VP0000001 |
| Thử 6 mật khẩu sai | Lần 6 `429`, có `Retry-After` |
| Email không tồn tại và email có tồn tại | Cùng mã lỗi, cùng thông điệp, độ trễ lệch < 50 ms |
| Trộm refresh token, dùng sau khi nạn nhân đã refresh | Cả chuỗi bị thu hồi, cả hai bên bị đăng xuất |

---

## 21. Phân pha và nghiệm thu

### P0 — bắt buộc cho MVP v01

| Hạng mục | Mục |
|---|---|
| Hybrid session: cookie ở BFF, JWT nội bộ | §2, §4, §5 |
| **Toàn bộ logic mapping**, gồm hai pha đăng ký và bảng chuyển trạng thái | §3 |
| Gỡ query param `cdp_user_id` khỏi `/recommendations` | §3.5 |
| Argon2id + đường bcrypt cho user seed | §8 |
| Cookie flags, xoay sid, idle/absolute timeout | §6, §3.8 |
| CSRF ba lớp | §7 |
| Rate limit + lockout (CAPTCHA có thể `noop` ở P0) | §9 |
| Kiểm JWT đủ 10 điểm, RS256, JWKS | §10.1–§10.3 |
| Refresh token rotation + phát hiện tái dùng | §10.4 |
| Authorization phía server, lọc theo `cdp_user_id` | §14.1, §14.2 |
| Logging + cảnh báo | §15 |
| Bảng `refresh_tokens`, `login_attempts` | §16.2 |

**Nghiệm thu P0:** đăng nhập được cả 4 persona; Home mỗi persona khác nhau; `document.cookie` không có token; §20.5 đạt cả 8 dòng.

### P1 — trước khi mở cho người dùng thật (**ngoài phạm vi**, PRD 2026-09-23)

Xác minh email (§11.1) · đặt lại mật khẩu (§11.2) · TOTP + recovery code (§12.1) · CAPTCHA thật (§9.3) · chặn checkout khi chưa xác minh (§11.1 điểm 5) · bảng `email_verifications`, `mfa_credentials`, `mfa_recovery_codes`.

**Nghiệm thu P1:** đăng ký → nhận mail → xác minh → checkout được; bật TOTP → đăng nhập hai bước; quên mật khẩu → đặt lại → mọi phiên cũ bị đăng xuất.

### P2 — mở rộng (**ngoài phạm vi**, PRD 2026-09-23)

OAuth/OIDC + PKCE (§13) · WebAuthn (§12.2) · bảng `oauth_identities`, `webauthn_credentials` · `password_hash` nullable.

**Nghiệm thu P2:** đăng nhập Google tạo user mới có `cdp_user_id` đúng §3.6.3; `state` dùng lại bị từ chối; provider `email_verified: false` không liên kết được vào tài khoản có sẵn.

---

## 22. Mâu thuẫn đã xử lý và phần còn mở

### 22.1. Đã xử lý

| # | Mâu thuẫn | Xử lý |
|---|---|---|
| 1 | handbook §8 cấm OAuth / xác minh email / đặt lại mật khẩu | Chủ dự án chốt đưa vào, chia pha §21. Ghi ở §1.4. |
| 2 | handbook §8 và DDL ghi BCrypt | Argon2id + đường bcrypt cho seed (§8.2). Phải sửa comment DDL và `docs/DATABASE_SCHEMA.md`. |
| 3 | `hop-dong-tich-hop-frontend.md` §7.1 chốt `sessionStorage` | Bị thay thế bởi §4.2. |
| 4 | `AuthResponse.accessToken` required trong v1 | Không sửa v1; thêm nhóm `/auth/session/*` (§5). Không lên v2. |
| 5 | `§8.2`: `retryable: true` chỉ cho 2 mã | Mở rộng thành 4, sửa cả `schemas/common.yaml` (§17). |
| 6 | `recommendations.py` nhận `cdp_user_id` qua query | Gỡ; chuyển sang `optional_principal` (§3.5). Đóng `TODO` của `history/2026-09-21-gop-recsys-vao-backend-postgres.md`. |
| 7 | Proxy Next chuyển tiếp nguyên cookie và mất `X-Request-ID` | Sửa ở §4.1. |
| 8 | `vota_app` không tạo được `cdp.profiles` | Hai pha có bù trừ; thêm `CdpClient.ensure_profile` (§3.6). |
| 9 | Va chạm `cdp_user_id` giữa seed và đăng ký | Tách dải `VP\d{7}` / `VPW…` (§3.6.2). |

### 22.2. Còn mở — cần người quyết trước khi code phần tương ứng

| # | Câu hỏi | Chặn phần nào | Quy tắc tạm |
|---|---|---|---|
| A | Thêm `CdpClient.ensure_profile` cần reviewer Data/Integration (`architecture-repo.md` §11) | Đăng ký (P0) | Viết port + `LocalCdpClient`, đánh dấu chờ duyệt trong PR |
| B | Nhà cung cấp CAPTCHA (Turnstile / reCAPTCHA / hCaptcha) | §9.3 thật (P1) | `CAPTCHA_PROVIDER=noop`, giao diện đã có chỗ cắm |
| C | Nhà cung cấp email giao vận | §11 (P1) | `SMTP_URL` trống → ghi mail ra log ở dev |
| D | Danh sách OAuth provider và client credentials | §13 (P2) | Chỉ `google` trong enum, thêm sau |
| E | Redis quản lý hay tự host ở staging | §16.1 | `docker compose` local; staging chốt cùng lúc với Postgres cloud |
| F | Tên cột opt-in trong `cdp.profiles` vẫn chờ reviewer CDP (`AGENTS.md` §6.4) | Đồng bộ tuỳ chọn email marketing | Auth không chạm cột opt-in |
| G | Có mở ghép lịch sử ẩn danh không (`hop-dong-tich-hop-cdp.md` §1.6) | §3.7 | Giữ ngoài phạm vi; `anon_id` không xuống database |

---

### 22.3. Ghi chú hiện thực P0 (2026-09-23)

Các điểm spec để ngỏ, đã chốt khi code (không lệch PRD):

- **`session_id` phía backend** (claim `sid`, cột `app.refresh_tokens.session_id`) do FastAPI sinh lúc `POST /auth/session` (`s_` + 128 bit), vì `SessionRequest`/`RefreshRequest` không mang sid của BFF. Cookie `vota_sid` là định danh riêng của BFF và xoay theo §3.8 mà backend không cần biết. Refresh giữ nguyên `session_id` và `expires_at` của family (không kéo dài quá 12 giờ).
- **Đăng ký qua BFF** = `POST /api/v1/auth/register` (v1) rồi `POST /api/v1/auth/session` — không thêm path mới vào contract.
- **Tái sử dụng refresh token** thu hồi mọi refresh token còn sống của user (`reuse_detected`), không chỉ family.
- **Điểm 9 của §10.3** kiểm trong `application/auth/bearer.py` (`verified_principal`) qua port `RevokedTokens` (Redis `jwt:revoked:{jti}`), vì cần I/O. `api/deps.py` (HTTP) và tool itinerary chạy trong tiến trình cùng gọi hàm này (§3.5). Trước 2026-09-28, kiểm tra này nằm ở `api/deps.py`.
- **Không có Redis** (`AUTH_REDIS_URL`/`SESSION_REDIS_URL` trống): rate limiter và session store chạy trong bộ nhớ một tiến trình, chỉ cho development/test; production từ chối khởi động. Thiếu file khoá RS256: development sinh khoá tạm, production từ chối khởi động.
- **Key rate limit**: `rl:{scope}:{sha256(key)}` (sorted set, cửa sổ trượt) và `lockout:{scope}:{sha256(key)}`; key IP cũng băm.
- `/auth/session/mfa/verify` có trong contract nhưng **không mount** (2FA ngoài phạm vi); CAPTCHA chỉ `noop`, backend không trả `details.captchaRequired`.

## 23. Definition of Done (P0)

- [ ] Contract sửa trước code: `schemas/common.yaml`, `schemas/auth.yaml`, `paths/auth.yaml`, `openapi.yaml`; `validate_contract.py` pass.
- [ ] 4 endpoint auth v1 cũ không đổi shape, contract test cũ vẫn pass.
- [ ] `db/init/01_vota.sql` **và** `db/vota_schema.sql` có bảng mới; `docs/DATABASE_SCHEMA.md` §4 + §11 cập nhật cùng commit.
- [ ] Comment `-- BCrypt` đã đổi ở cả hai file .sql và trong doc.
- [ ] `docker-compose.yml` có Redis bind `127.0.0.1`, có mật khẩu.
- [ ] `.env.example` có đủ biến §19; không giá trị thật nào được commit.
- [ ] `src/backend/requirements.txt` có `argon2-cffi`, `bcrypt`, `PyJWT`, `redis`.
- [ ] `recommendations.py` không còn query param `cdp_user_id`; `TODO` đã gỡ.
- [ ] Proxy Next xoá cookie/authorization từ client và giữ `X-Request-ID`.
- [ ] Không chỗ nào trong `src/frontend` lưu token vào `localStorage`/`sessionStorage`.
- [ ] Test §20.1–§20.4 pass; §20.5 chạy tay và ghi kết quả.
- [ ] `hop-dong-tich-hop-frontend.md` §7 và `hop-dong-tich-hop-backend.md` §8.2 cập nhật trỏ sang tài liệu này.
- [ ] Entry `history/` theo `AGENTS.md` §5.
