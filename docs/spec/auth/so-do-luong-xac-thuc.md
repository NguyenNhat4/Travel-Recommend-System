# Sơ đồ luồng xác thực (Auth) — Sequence & Activity

- Ngày: 2026-09-23
- Phục vụ: FR-USR-01, FR-USR-03, NFR-SEC-01, NFR-SEC-02 (`docs/prd/requirements.md` §1.6, §2.3)
- Nguồn: `docs/spec/hop-dong-tich-hop-auth.md` (gọi tắt **spec auth**). Tài liệu này chỉ **vẽ lại** spec đó cho dễ đọc; khi có chỗ khác nhau thì spec auth và OpenAPI (`src/shared/contracts/paths/auth.yaml`) thắng.
- Kế hoạch triển khai: `docs/plan/2026-09-23-auth-p0.md`

> **Lưu ý trạng thái.** Cơ chế BFF (Next.js) + Redis đã được chốt vào PRD ngày 2026-09-23 (`docs/prd/update-archive/2026-09-23-auth-hybrid-session.md`). **Mục 7 (2FA/OTP) ngoài phạm vi** — giữ lại chỉ để tham khảo. Khách chưa đăng nhập không sinh sự kiện CDP; không có bước gộp lịch sử ẩn danh.

## Mục lục

1. [Các thành phần tham gia](#1-các-thành-phần-tham-gia)
2. [Cách đọc sơ đồ](#2-cách-đọc-sơ-đồ)
3. [Đăng nhập](#3-đăng-nhập)
4. [Đăng ký tài khoản](#4-đăng-ký-tài-khoản)
5. [Gọi API khi đã đăng nhập](#5-gọi-api-khi-đã-đăng-nhập)
6. [Làm mới token và phát hiện token bị đánh cắp](#6-làm-mới-token-và-phát-hiện-token-bị-đánh-cắp)
7. [Xác minh OTP 2 lớp (ngoài phạm vi)](#7-xác-minh-otp-2-lớp-ngoài-phạm-vi)
8. [Đăng xuất](#8-đăng-xuất)
9. [Vòng đời phiên đăng nhập](#9-vòng-đời-phiên-đăng-nhập)
10. [Bảng lỗi và cách hiển thị](#10-bảng-lỗi-và-cách-hiển-thị)

---

## 1. Các thành phần tham gia

```mermaid
flowchart LR
    U["👤 Người dùng"]
    W["🖥️ Web<br/>React component"]
    B["🔀 BFF<br/>Next.js route handler"]
    R[("⚡ Redis<br/>phiên, bộ đếm")]
    F["⚙️ Backend<br/>FastAPI"]
    P[("🗄️ Postgres app.*<br/>users, refresh_tokens,<br/>login_attempts")]
    C[("🗄️ Postgres cdp.profiles<br/>qua CdpClient")]

    U --> W
    W -- "cookie vota_sid<br/>+ X-CSRF-Token" --> B
    B <--> R
    B -- "Bearer JWT<br/>+ X-Service-Token" --> F
    F <--> R
    F -- "DATABASE_URL<br/>role vota_app" --> P
    F -- "CDP_DATABASE_URL<br/>role cdp_writer" --> C
```

| Thành phần | Làm gì | Không bao giờ làm |
|---|---|---|
| **Người dùng** | Nhập email, mật khẩu, mã OTP | — |
| **Web** (React) | Hiện form, hiện lỗi theo `code` | Giữ token, gọi thẳng FastAPI, tự quyết định quyền |
| **BFF** (Next.js) | Giữ cookie phiên, kiểm CSRF, cất token trong Redis, gắn `Authorization` khi chuyển tiếp | Tự ký JWT, giữ khoá ký |
| **Redis** | Lưu phiên (`session:{sid}`), bộ đếm rate limit, khoá refresh | Lưu dữ liệu cần giữ lâu dài |
| **Backend** (FastAPI) | Kiểm mật khẩu, phát JWT, xoay refresh token, rate limit, **mọi quyết định quyền** | Tin `cdp_user_id` do client gửi |
| **Postgres `app`** | Tài khoản, refresh token (bản băm), nhật ký đăng nhập | — |
| **Postgres `cdp`** | Hồ sơ khách hàng `cdp.profiles` — chỉ ghi được qua `CdpClient` | Biết gì về mật khẩu hay phiên |

**Không có swimlane Admin hay Payment Service.** Spec auth §1.3 để phân quyền theo vai trò (admin) ngoài phạm vi, và thanh toán thật nằm ngoài phạm vi dự án (`docs/prd/project-brief.md` §4.2).

**Điểm quan trọng nhất:** trình duyệt chỉ giữ một cookie "con trỏ" (`vota_sid`), không bao giờ giữ JWT. Token nằm trong Redis phía BFF. Nhờ vậy, kể cả khi trang web bị chèn mã độc (XSS), kẻ tấn công vẫn không đọc được token.

---

## 2. Cách đọc sơ đồ

**Sequence diagram** trả lời câu hỏi *"ai gửi gì cho ai, theo thứ tự nào"*. Đọc từ trên xuống; mũi tên liền là lời gọi, mũi tên nét đứt là phản hồi. Khối `alt/else` là rẽ nhánh, `opt` là bước tuỳ chọn, `loop` là lặp.

**Activity diagram** trả lời câu hỏi *"hệ thống quyết định thế nào ở mỗi bước"*. Ký hiệu dùng chung cho mọi sơ đồ activity trong tài liệu:

```mermaid
flowchart LR
    S(("Bắt đầu")) --> A["Hành động"] --> D{"Điều kiện?"}
    D -- "Có" --> DB[("Dữ liệu đọc/ghi")]
    D -- "Không" --> X["Đường lỗi"]:::err
    DB --> E((("Kết thúc")))
    classDef err fill:#fde2e2,stroke:#c0392b,color:#7b1d1d
```

| Ký hiệu | Ý nghĩa |
|---|---|
| Hình tròn `Bắt đầu` / tròn kép `Kết thúc` | Điểm bắt đầu và kết thúc |
| Hình chữ nhật | Hành động cụ thể |
| Hình thoi | Điều kiện rẽ nhánh |
| Hình trụ | Dữ liệu được tạo, đọc hoặc thay đổi (nối bằng nét đứt) |
| Ô **đỏ** | Đường lỗi: lỗi mạng, dữ liệu sai, hết hạn, không đủ quyền |
| Khung có tiêu đề | Swimlane: ai thực hiện bước đó |
| Mũi tên quay ngược lên | Vòng lặp |

---

## 3. Đăng nhập

### 3.1. Sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as Người dùng
    participant W as Web
    participant B as BFF (Next.js)
    participant R as Redis
    participant F as Backend (FastAPI)
    participant P as Postgres app

    U->>W: Nhập email + mật khẩu, bấm Đăng nhập
    W->>B: POST /api/auth/login, kèm cookie vota_sid và X-CSRF-Token
    B->>R: GET session:{sid} (phiên khách)
    alt CSRF hoặc Origin sai
        B-->>W: 403 CSRF_FAILED
        W-->>U: Tải lại trang rồi thử lại
    else CSRF hợp lệ
        B->>F: POST /api/v1/auth/session, kèm X-Service-Token
        F->>R: Đọc bộ đếm rl:login:email, rl:login:ip
        alt Đang bị khoá
            F-->>B: 429 TOO_MANY_ATTEMPTS, Retry-After 900
            B-->>W: 429
            W-->>U: Đếm ngược 15 phút, khoá nút gửi
        else Còn lượt thử
            F->>P: SELECT app.users WHERE email = lower(email)
            F->>F: Kiểm mật khẩu Argon2id hoặc bcrypt<br/>(email không tồn tại vẫn chạy một lần với hash giả)
            alt Sai email hoặc mật khẩu
                F->>R: Tăng bộ đếm sai
                F->>P: INSERT login_attempts (succeeded = false)
                F-->>B: 401 INVALID_CREDENTIALS (có thể kèm captchaRequired)
                B-->>W: 401
                W-->>U: Email hoặc mật khẩu không đúng
            else Đúng
                opt Hash cũ là bcrypt (user seed)
                    F->>P: UPDATE password_hash sang Argon2id
                end
                F->>P: UPDATE last_login_at, INSERT login_attempts (ok), INSERT refresh_tokens (bản băm)
                F->>R: Xoá bộ đếm sai
                F-->>B: 200 state, accessToken 10 phút, refreshToken 12 giờ, user
                B->>R: DEL session cũ, SET session mới (hết hạn sau 30 phút không hoạt động)
                B-->>W: 200 state + Set-Cookie vota_sid (HttpOnly), vota_csrf
                W-->>U: Vào trang chủ đã cá nhân hoá
            end
        end
    end
```

**Giải thích dễ hiểu:**

- Ở bước 2, Web chỉ gửi email và mật khẩu cho BFF. Web **không** nhận lại token nào.
- Sai email hay sai mật khẩu đều trả **cùng một lỗi, cùng thông điệp và mất cùng khoảng thời gian**. Nếu hai trường hợp khác nhau, kẻ xấu sẽ dò được email nào đã đăng ký.
- Khi đăng nhập thành công, phiên khách cũ bị xoá và một `sid` mới được phát (chống *session fixation*: kẻ xấu cài sẵn một `sid` cho nạn nhân rồi chờ nạn nhân đăng nhập bằng chính `sid` đó).
- 54 tài khoản seed dùng mật khẩu băm kiểu cũ (bcrypt). Lần đăng nhập đầu, hệ thống tự băm lại bằng Argon2id; người dùng không thấy gì khác.

### 3.2. Activity

```mermaid
flowchart TB
    subgraph LU["👤 Người dùng"]
        S(("Bắt đầu"))
        U1["Nhập email + mật khẩu"]
        U2["Nhập lại, giải CAPTCHA nếu được yêu cầu"]
        EOK((("Kết thúc:<br/>đã đăng nhập")))
        ELOCK((("Kết thúc:<br/>chờ hết khoá 15 phút")))
    end

    subgraph LB["🔀 Web + BFF"]
        B1{"CSRF + Origin<br/>hợp lệ?"}
        B2["Gọi POST /auth/session"]
        B3{"Gọi được Backend?"}
        B4["Xoay sid, lưu token vào phiên,<br/>Set-Cookie"]
        BX1["403 CSRF_FAILED<br/>tải lại trang"]:::err
        BX2["502 lỗi mạng<br/>hiện nút Thử lại"]:::err
    end

    subgraph LF["⚙️ Backend"]
        F1{"Email hoặc IP<br/>đang bị khoá?"}
        F2{"Đã tới ngưỡng CAPTCHA<br/>3/5 email hoặc 10/20 IP?"}
        F3{"captchaToken<br/>có và hợp lệ?"}
        F4["Tra user theo email,<br/>kiểm mật khẩu"]
        F5{"Mật khẩu đúng?"}
        F6["Tăng bộ đếm sai,<br/>ghi nhật ký thất bại"]
        F7{"Đủ 5 lần sai<br/>trong 15 phút?"}
        F8{"Hash là bcrypt cũ?"}
        F9["Băm lại bằng Argon2id"]
        F10["Phát JWT 10 phút<br/>+ refresh token 12 giờ"]
        F11{"User đã bật 2FA?<br/>(P1)"}
        FX1["429 TOO_MANY_ATTEMPTS<br/>Retry-After 900"]:::err
        FX2["400 CAPTCHA_REQUIRED<br/>hoặc CAPTCHA_FAILED"]:::err
        FX3["401 INVALID_CREDENTIALS"]:::err
        FMFA["Trả state = pending_mfa<br/>→ sang mục 7"]
    end

    subgraph LD["🗄️ Dữ liệu"]
        D1[("Redis rl:login:*<br/>lockout:*")]
        D2[("app.users")]
        D3[("app.login_attempts")]
        D4[("app.refresh_tokens")]
        D5[("Redis session:{sid}")]
    end

    S --> U1 --> B1
    B1 -- "Không" --> BX1
    B1 -- "Có" --> B2 --> B3
    B3 -- "Không" --> BX2
    B3 -- "Có" --> F1
    F1 -- "Có" --> FX1 --> ELOCK
    F1 -- "Không" --> F2
    F2 -- "Chưa" --> F4
    F2 -- "Rồi" --> F3
    F3 -- "Không" --> FX2 --> U2
    F3 -- "Có" --> F4
    F4 --> F5
    F5 -- "Sai" --> F6 --> F7
    F7 -- "Chưa" --> FX3 --> U2
    F7 -- "Đủ" --> FX1
    U2 -- "lặp lại" --> B1
    F5 -- "Đúng" --> F8
    F8 -- "Có" --> F9 --> F11
    F8 -- "Không" --> F11
    F11 -- "Có" --> FMFA
    F11 -- "Không" --> F10 --> B4 --> EOK

    F1 -.-> D1
    F6 -.-> D1
    F6 -.-> D3
    F4 -.-> D2
    F9 -.-> D2
    F10 -.-> D4
    F10 -.-> D3
    B4 -.-> D5

    classDef err fill:#fde2e2,stroke:#c0392b,color:#7b1d1d
```

**Vòng lặp:** người dùng được thử lại nhiều lần. Từ lần sai thứ 3 (theo email) phải giải CAPTCHA; tới lần sai thứ 5 trong 15 phút thì tài khoản bị **khoá tạm 15 phút**, không khoá vĩnh viễn. Khoá vĩnh viễn sẽ biến tính năng bảo vệ thành công cụ để kẻ xấu cố tình khoá tài khoản của người khác.

**Vì sao đếm cả theo email và theo IP:** chỉ đếm theo IP thì kẻ tấn công đổi proxy là thử tiếp được; chỉ đếm theo email thì kẻ tấn công thử một mật khẩu phổ biến trên 2.000 email khác nhau mà không chạm ngưỡng.

---

## 4. Đăng ký tài khoản

Đăng ký khó hơn đăng nhập vì phải ghi vào **hai nơi có quyền khác nhau**: hồ sơ khách hàng `cdp.profiles` (chỉ role `cdp_writer` ghi được) và tài khoản `app.users` (role `vota_app`). Hai kết nối này **không được** gói chung một transaction (`AGENTS.md` §6.2), nên hệ thống làm theo hai pha: tạo hồ sơ CDP trước, tạo tài khoản sau.

### 4.1. Sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as Người dùng
    participant W as Web
    participant B as BFF
    participant F as Backend
    participant P as Postgres app
    participant C as CdpClient (cdp_writer)

    U->>W: Nhập email, mật khẩu, họ tên
    W->>B: POST /api/auth/register + X-CSRF-Token
    B->>F: POST /api/v1/auth/register
    F->>F: Kiểm chính sách mật khẩu (8–128 ký tự, không nằm trong danh sách phổ biến, không giống email/tên)
    alt Mật khẩu yếu
        F-->>W: 400 WEAK_PASSWORD {reasons}
    else Hợp lệ
        F->>P: Email đã tồn tại?
        alt Đã tồn tại
            F-->>W: 409 EMAIL_ALREADY_EXISTS
        else Chưa
            F->>F: Sinh cdp_user_id = VPW + 12 ký tự ngẫu nhiên
            F->>C: ensure_profile(cdp_user_id) — pha 1
            alt CDP không phản hồi
                C-->>F: CdpUnavailableError
                F-->>W: 503 CDP_UNAVAILABLE (retryable)
                W-->>U: Có lỗi, bấm Thử lại
            else Tạo hồ sơ xong
                loop Tối đa 3 lần nếu trùng cdp_user_id
                    F->>P: INSERT app.users (password_hash Argon2id, cdp_user_id) — pha 2
                end
                alt INSERT thất bại
                    F->>F: Log auth.orphan_profile (giữ hồ sơ CDP, không xoá)
                    F-->>W: 409 EMAIL_ALREADY_EXISTS hoặc 500
                else Thành công
                    F-->>B: Phát phiên như đăng nhập (mục 3)
                    B-->>W: 200 + Set-Cookie
                    W-->>U: Đăng nhập luôn, trang chủ hiện gợi ý phổ biến (tài khoản mới chưa có lịch sử)
                end
            end
        end
    end
```

### 4.2. Activity

```mermaid
flowchart TB
    subgraph LU["👤 Người dùng"]
        S(("Bắt đầu"))
        U1["Nhập email, mật khẩu, họ tên"]
        U2["Sửa thông tin hoặc bấm Thử lại"]
        EOK((("Kết thúc:<br/>tài khoản mới, đã đăng nhập")))
    end

    subgraph LF["⚙️ Backend"]
        F1{"Dữ liệu hợp lệ<br/>và mật khẩu đủ mạnh?"}
        F2{"Email đã có?"}
        F3["Sinh cdp_user_id VPW…"]
        F4["Pha 1: ensure_profile"]
        F5{"CDP phản hồi?"}
        F6["Pha 2: INSERT app.users"]
        F7{"Kết quả INSERT?"}
        F8{"Đã thử 3 lần?"}
        F9["Log auth.orphan_profile"]
        F10["Phát phiên, Set-Cookie"]
        FX1["400 VALIDATION_ERROR<br/>hoặc WEAK_PASSWORD"]:::err
        FX2["409 EMAIL_ALREADY_EXISTS"]:::err
        FX3["503 CDP_UNAVAILABLE"]:::err
        FX4["500 INTERNAL_ERROR"]:::err
    end

    subgraph LD["🗄️ Dữ liệu"]
        D1[("cdp.profiles")]
        D2[("app.users")]
    end

    S --> U1 --> F1
    F1 -- "Không" --> FX1 --> U2
    F1 -- "Có" --> F2
    F2 -- "Có" --> FX2 --> U2
    F2 -- "Không" --> F3 --> F4 --> F5
    F5 -- "Không" --> FX3 --> U2
    F5 -- "Có" --> F6 --> F7
    F7 -- "Thành công" --> F10 --> EOK
    F7 -- "Trùng cdp_user_id" --> F8
    F8 -- "Chưa" --> F3
    F8 -- "Rồi" --> F9 --> FX4
    F7 -- "Trùng email<br/>(người khác vừa đăng ký)" --> F9
    F9 --> FX2
    FX4 --> U2
    U2 -- "lặp lại" --> F1

    F2 -.-> D2
    F4 -.-> D1
    F6 -.-> D2

    classDef err fill:#fde2e2,stroke:#c0392b,color:#7b1d1d
```

**Giải thích dễ hiểu:**

- **Vì sao CDP đi trước:** cột `app.users.cdp_user_id` bắt buộc trỏ tới một hồ sơ có thật, nên phải có hồ sơ rồi mới tạo được tài khoản.
- **Nếu pha 2 hỏng, hồ sơ CDP bị bỏ lại ("mồ côi")** và hệ thống **cố ý không xoá**. Role `cdp_writer` không có quyền xoá hồ sơ; cấp thêm quyền xoá chỉ để dọn rác thì rủi ro hơn lợi. Hồ sơ rỗng không có sự kiện nào nên không ảnh hưởng gợi ý hay số liệu. Hệ thống ghi log `auth.orphan_profile` để job dọn dẹp xử lý sau.
- **Mã `VPW…` ngẫu nhiên, không tuần tự:** mã tuần tự cho phép đoán mã của người khác. Dải `VP0000001–VP0002000` dành riêng cho dữ liệu seed.
- Tài khoản mới chưa có lịch sử, nên trang chủ hiện gợi ý **phổ biến** (`coldStart: true`).

---

## 5. Gọi API khi đã đăng nhập

Ví dụ: người dùng mở trang chủ (gợi ý cá nhân hoá) hoặc thêm sản phẩm vào giỏ. Mọi request đều đi qua BFF; BFF gắn token rồi chuyển sang Backend.

### 5.1. Sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as Người dùng
    participant W as Web
    participant B as BFF
    participant R as Redis
    participant F as Backend
    participant P as Postgres app

    U->>W: Bấm Thêm vào giỏ
    W->>B: POST /api/v1/cart/items + cookie + X-CSRF-Token
    B->>R: GET session:{sid}
    alt Không có phiên, quá 30 phút không hoạt động, hoặc quá 12 giờ
        B-->>W: 401 SESSION_EXPIRED
        W-->>U: Hộp thoại "Phiên đã hết hạn", điền sẵn email
    else User-Agent khác lúc đăng nhập
        B->>R: DEL session (nghi phiên bị đánh cắp)
        B-->>W: 401 SESSION_EXPIRED
    else Phiên hợp lệ
        B->>B: Kiểm CSRF + Origin (request ghi)
        opt Access token còn 60 giây hoặc ít hơn
            B->>F: Làm mới token (mục 6)
        end
        B->>B: Xoá cookie và Authorization do trình duyệt gửi, gắn Bearer từ phiên
        B->>F: POST /api/v1/cart/items, Authorization Bearer, X-Request-ID
        F->>F: Kiểm JWT đủ 10 điểm (alg, kid, chữ ký, iss, aud, exp, nbf, sub, cdp_user_id, jti)
        alt Token hỏng
            F-->>B: 401 INVALID_TOKEN
        else Token hết hạn
            F-->>B: 401 TOKEN_EXPIRED
        else Hợp lệ
            F->>P: Ghi giỏ WHERE cdp_user_id = principal.cdp_user_id
            F-->>B: 201 + X-Request-ID
        end
        B->>R: Gia hạn phiên thêm 30 phút
        B-->>W: Phản hồi + X-Request-ID
    end
```

### 5.2. Activity — Backend quyết định danh tính và quyền

```mermaid
flowchart TB
    subgraph LB["🔀 BFF"]
        S(("Bắt đầu:<br/>nhận request"))
        B1{"Có phiên hợp lệ?<br/>idle 30 phút, tối đa 12 giờ"}
        B2{"User-Agent khớp<br/>lúc đăng nhập?"}
        B3{"Request ghi?<br/>POST/PUT/PATCH/DELETE"}
        B4{"CSRF + Origin đúng?"}
        B5{"state của phiên"}
        B6["Không gắn Authorization<br/>(khách vãng lai)"]
        B7["Gắn Bearer token,<br/>chuyển tiếp"]
        BX1["401 SESSION_EXPIRED"]:::err
        BX2["403 CSRF_FAILED"]:::err
        BX3["403 MFA_REQUIRED"]:::err
    end

    subgraph LF["⚙️ Backend"]
        F1{"Có Bearer?"}
        F2{"Chữ ký và claim<br/>hợp lệ?"}
        F3{"Còn hạn?"}
        F4["principal = user đã xác thực"]
        F5["principal = None<br/>(khách)"]
        F6{"Endpoint cần<br/>đăng nhập?"}
        F7["Truy vấn lọc theo<br/>principal.cdp_user_id"]
        F8{"Tìm thấy bản ghi<br/>của chính user?"}
        F9["Trả kết quả chung,<br/>ví dụ gợi ý phổ biến"]
        FX1["401 INVALID_TOKEN<br/>(không hạ thành khách)"]:::err
        FX2["401 TOKEN_EXPIRED"]:::err
        FX3["401 UNAUTHENTICATED"]:::err
        FX4["404 NOT_FOUND<br/>(không trả 403)"]:::err
        EOK((("Kết thúc:<br/>trả dữ liệu")))
    end

    subgraph LD["🗄️ Dữ liệu"]
        D1[("Redis session:{sid}")]
        D2[("app.carts, app.bookings,<br/>recommend(cdp_user_id)")]
    end

    S --> B1
    B1 -- "Không có phiên" --> B6
    B1 -- "Hết hạn" --> BX1
    B1 -- "Có" --> B2
    B2 -- "Không" --> BX1
    B2 -- "Có" --> B3
    B3 -- "Có" --> B4
    B3 -- "Không" --> B5
    B4 -- "Sai" --> BX2
    B4 -- "Đúng" --> B5
    B5 -- "anonymous" --> B6
    B5 -- "pending_mfa" --> BX3
    B5 -- "authenticated" --> B7
    B6 --> F1
    B7 --> F1
    F1 -- "Không" --> F5 --> F6
    F1 -- "Có" --> F2
    F2 -- "Không" --> FX1
    F2 -- "Có" --> F3
    F3 -- "Không" --> FX2
    F3 -- "Có" --> F4 --> F7 --> F8
    F6 -- "Có, ví dụ giỏ hàng" --> FX3
    F6 -- "Không, ví dụ gợi ý" --> F9 --> EOK
    F8 -- "Có" --> EOK
    F8 -- "Không" --> FX4

    B1 -.-> D1
    F7 -.-> D2

    classDef err fill:#fde2e2,stroke:#c0392b,color:#7b1d1d
```

**Giải thích dễ hiểu:**

- **Danh tính chỉ lấy từ phiên đã xác thực**, không bao giờ từ tham số trên URL hay trong body. Trước đây `/recommendations?cdp_user_id=VP0000001` cho phép bất kỳ ai xem gợi ý của người khác; đường này đã bị bỏ.
- **Token hỏng thì báo lỗi, không lặng lẽ coi là khách.** Nếu hạ ngầm thành khách, người dùng sẽ thấy trang chủ không cá nhân hoá mà không hiểu vì sao, và lỗi xác thực sẽ không bao giờ lộ ra trong demo.
- **Đơn của người khác trả `404` chứ không `403`.** Trả `403` là ngầm xác nhận "mã đơn này có tồn tại".
- **Frontend chỉ lo trải nghiệm.** Ẩn nút "Thêm vào giỏ" khi chưa đăng nhập chỉ để giao diện gọn; Backend vẫn tự kiểm lại mọi thứ.

---

## 6. Làm mới token và phát hiện token bị đánh cắp

Access token chỉ sống 10 phút. BFF tự đổi refresh token lấy cặp token mới, người dùng không thấy gì. Mỗi refresh token **chỉ dùng được một lần**.

### 6.1. Sequence — hai tab cùng làm mới, và trường hợp token bị đánh cắp

```mermaid
sequenceDiagram
    autonumber
    participant T1 as BFF (tab 1)
    participant T2 as BFF (tab 2)
    participant R as Redis
    participant F as Backend
    participant P as Postgres app
    actor K as Kẻ tấn công

    T1->>R: SET lock:refresh:{sid} NX PX 5000
    R-->>T1: OK (giữ khoá)
    T2->>R: SET lock:refresh:{sid} NX PX 5000
    R-->>T2: Đã có khoá
    T1->>F: POST /auth/session/token {refreshToken RT1}
    F->>P: RT1 còn hiệu lực và thuộc đúng sid?
    F->>P: Đánh dấu RT1 rotated, INSERT RT2 (cùng family_id)
    F-->>T1: accessToken mới + RT2
    T1->>R: Ghi token mới vào session, DEL khoá
    loop Chờ tối đa 2 giây
        T2->>R: Đọc lại session
    end
    R-->>T2: Đã có token mới, dùng luôn

    Note over K,F: Giả sử RT1 đã bị đánh cắp trước đó
    K->>F: POST /auth/session/token {RT1}
    F->>P: RT1 đã rotated → dùng lại!
    F->>P: Thu hồi cả family (RT1, RT2…), revoked_reason = reuse_detected
    F->>F: Log auth.refresh_reuse mức ERROR, cảnh báo ngay
    F-->>K: 401 INVALID_TOKEN
    Note over T1,F: Lần làm mới sau của người dùng thật cũng bị 401,<br/>phiên bị huỷ, người dùng đăng nhập lại
```

### 6.2. Activity

```mermaid
flowchart TB
    subgraph LB["🔀 BFF"]
        S(("Bắt đầu:<br/>token còn ≤ 60 giây"))
        B1{"Lấy được khoá<br/>lock:refresh:{sid}?"}
        B2["Chờ, đọc lại phiên"]
        B3{"Đã có token mới?"}
        B4{"Chờ quá 2 giây?"}
        B5["Gửi refresh token"]
        B6["Ghi token mới vào phiên,<br/>nhả khoá"]
        BX1["Huỷ phiên,<br/>401 SESSION_EXPIRED"]:::err
        EOK((("Kết thúc:<br/>tiếp tục request")))
    end

    subgraph LF["⚙️ Backend"]
        F1{"Token tồn tại, chưa hết hạn,<br/>chưa bị thu hồi?"}
        F2{"Đúng sid<br/>đã gắn?"}
        F3{"Đã rotated?"}
        F4["Đánh dấu rotated,<br/>phát cặp mới cùng family"]
        F5["Thu hồi cả family,<br/>log auth.refresh_reuse"]:::err
        FX1["401 INVALID_TOKEN"]:::err
    end

    subgraph LD["🗄️ Dữ liệu"]
        D1[("Redis lock:refresh:{sid}")]
        D2[("app.refresh_tokens<br/>token_hash, family_id,<br/>rotated_at, revoked_at")]
        D3[("Redis session:{sid}")]
    end

    S --> B1
    B1 -- "Có" --> B5 --> F1
    B1 -- "Không" --> B2 --> B3
    B3 -- "Có" --> EOK
    B3 -- "Chưa" --> B4
    B4 -- "Chưa" --> B2
    B4 -- "Rồi" --> BX1
    F1 -- "Không" --> FX1
    F1 -- "Có" --> F2
    F2 -- "Không" --> FX1
    F2 -- "Có" --> F3
    F3 -- "Có" --> F5 --> FX1
    F3 -- "Không" --> F4 --> B6 --> EOK
    FX1 --> BX1

    B1 -.-> D1
    F1 -.-> D2
    F4 -.-> D2
    F5 -.-> D2
    B6 -.-> D3

    classDef err fill:#fde2e2,stroke:#c0392b,color:#7b1d1d
```

**Vì sao cần khoá:** không có khoá, hai tab cùng gửi một refresh token; tab thứ hai sẽ bị coi là "dùng lại token" và tự đăng xuất người dùng.

**Vì sao thu hồi cả chuỗi:** khi một token cũ bị dùng lại, hệ thống không biết bên nào là người thật, bên nào là kẻ trộm. Thu hồi hết là cách an toàn duy nhất; người dùng thật chỉ mất công đăng nhập lại.

---

## 7. Xác minh OTP 2 lớp (ngoài phạm vi)

> **Ngoài phạm vi** theo PRD chốt 2026-09-23. Mục này chỉ mô tả hành vi ở spec auth §12 và §3.8 dòng D–E để tham khảo; không triển khai. Ở phạm vi hiện tại, nhánh "User đã bật 2FA?" trong mục 3.2 luôn là **Không**.

Người dùng đã bật 2FA thì đăng nhập đúng mật khẩu **chưa đủ**: phiên ở trạng thái `pending_mfa`, chưa mang danh tính nghiệp vụ (`cdpUserId = null`) và chỉ được gọi một endpoint duy nhất là xác minh OTP.

### 7.1. Sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as Người dùng
    participant W as Web
    participant B as BFF
    participant F as Backend
    participant R as Redis
    participant P as Postgres app

    Note over U,P: Đã qua bước mật khẩu, phiên đang pending_mfa
    W-->>U: Màn hình nhập mã OTP 6 số
    loop Tối đa 5 lần sai trong 15 phút
        U->>W: Nhập mã OTP (hoặc recovery code)
        W->>B: POST /api/auth/mfa/verify {code}
        B->>F: POST /api/v1/auth/session/mfa/verify
        F->>R: Kiểm bộ đếm rl:mfa:{user_id}
        F->>P: Đọc secret TOTP (giải mã AES-GCM), last_counter
        alt Mã sai hoặc trùng mã đã dùng
            F->>R: Tăng bộ đếm
            F-->>W: 401 MFA_INVALID {attemptsLeft}
            W-->>U: Mã không đúng, còn N lần
        else Mã đúng
            F->>P: Cập nhật last_counter (chống dùng lại cùng mã)
            F-->>B: 200 authenticated + token
            B->>B: Xoay sid lần hai, amr = pwd + otp
            B-->>W: Set-Cookie
            W-->>U: Vào trang chủ
        end
    end
    alt Vượt 5 lần
        F-->>W: 429 TOO_MANY_ATTEMPTS, huỷ phiên pending_mfa
        W-->>U: Quay lại màn đăng nhập
    end
```

### 7.2. Activity

```mermaid
flowchart TB
    subgraph LU["👤 Người dùng"]
        S(("Bắt đầu:<br/>phiên pending_mfa"))
        U1["Nhập mã OTP 6 số<br/>hoặc recovery code"]
        EOK((("Kết thúc:<br/>đăng nhập đủ 2 lớp")))
        EFAIL((("Kết thúc:<br/>đăng nhập lại từ đầu")))
    end

    subgraph LB["🔀 BFF"]
        B1{"Phiên còn<br/>pending_mfa?"}
        B2["Xoay sid lần hai,<br/>state = authenticated"]
        BX1["401 SESSION_EXPIRED"]:::err
    end

    subgraph LF["⚙️ Backend"]
        F1{"Đã sai 5 lần<br/>trong 15 phút?"}
        F2{"Loại mã?"}
        F3{"OTP khớp trong cửa sổ<br/>±30 giây?"}
        F4{"Counter mới hơn<br/>lần dùng trước?"}
        F5{"Recovery code khớp<br/>và chưa dùng?"}
        F6["Tăng bộ đếm sai"]
        F7["Ghi counter hoặc<br/>đánh dấu code đã dùng"]
        FX1["401 MFA_INVALID<br/>attemptsLeft"]:::err
        FX2["429 TOO_MANY_ATTEMPTS<br/>huỷ phiên pending_mfa"]:::err
    end

    subgraph LD["🗄️ Dữ liệu"]
        D1[("Redis rl:mfa:{user_id}")]
        D2[("app.mfa_credentials<br/>secret_enc, last_counter")]
        D3[("app.mfa_recovery_codes")]
    end

    S --> U1 --> B1
    B1 -- "Không" --> BX1 --> EFAIL
    B1 -- "Có" --> F1
    F1 -- "Rồi" --> FX2 --> EFAIL
    F1 -- "Chưa" --> F2
    F2 -- "OTP" --> F3
    F2 -- "Recovery code" --> F5
    F3 -- "Không" --> F6
    F3 -- "Có" --> F4
    F4 -- "Không, mã đã dùng" --> F6
    F4 -- "Có" --> F7
    F5 -- "Không" --> F6
    F5 -- "Có" --> F7
    F6 --> FX1
    FX1 -- "thử lại" --> U1
    F7 --> B2 --> EOK

    F1 -.-> D1
    F6 -.-> D1
    F3 -.-> D2
    F7 -.-> D2
    F5 -.-> D3
    F7 -.-> D3

    classDef err fill:#fde2e2,stroke:#c0392b,color:#7b1d1d
```

**Vòng lặp:** tối đa **5 lần sai trong 15 phút** (spec auth §9.1, khoá `rl:mfa`). Vượt ngưỡng thì phiên `pending_mfa` bị huỷ và người dùng phải nhập lại mật khẩu từ đầu.

**Vì sao lưu `last_counter`:** một mã OTP hợp lệ trong 30 giây. Nếu kẻ xấu nhìn trộm được mã, họ có thể dùng lại ngay trong 30 giây đó. Ghi lại counter đã dùng thì mỗi mã chỉ dùng được một lần.

---

## 8. Đăng xuất

```mermaid
sequenceDiagram
    autonumber
    actor U as Người dùng
    participant W as Web
    participant B as BFF
    participant R as Redis
    participant F as Backend
    participant P as Postgres app

    U->>W: Bấm Đăng xuất
    W->>B: POST /api/auth/logout + X-CSRF-Token
    B->>F: POST /api/v1/auth/session/revoke {refreshToken}
    alt Backend trả lời
        F->>P: UPDATE refresh_tokens SET revoked_at, revoked_reason = logout
        F-->>B: 204
    else Lỗi mạng hoặc Backend lỗi
        F--xB: Không phản hồi
        Note over B: Vẫn tiếp tục đăng xuất phía trình duyệt
    end
    B->>R: DEL session:{sid}
    B-->>W: 204 + xoá cookie vota_sid, vota_csrf
    W->>W: Xoá mọi cache client: dữ liệu đã tải, conversationId, kế hoạch, badge giỏ
    W-->>U: Về trang chủ ở chế độ khách
```

**Điểm cần nhớ:** BFF **luôn** xoá cookie, kể cả khi Backend lỗi. Người dùng bấm đăng xuất mà vẫn còn đăng nhập là lỗi nặng hơn việc một refresh token còn sống thêm ít giờ trong database. Token đó cũng không dùng được nữa, vì bản rõ chỉ nằm trong phiên Redis vừa bị xoá.

---

## 9. Vòng đời phiên đăng nhập

Phiên chỉ có **ba trạng thái**. Mỗi lần mức đặc quyền thay đổi, `sid` được thay mới (ô "xoay sid").

```mermaid
stateDiagram-v2
    [*] --> anonymous: A. Lần đầu vào site<br/>phát sid, anon_id, csrfToken

    anonymous --> authenticated: B. Đăng ký thành công [xoay sid]
    anonymous --> authenticated: C. Đăng nhập, không 2FA [xoay sid]
    anonymous --> pending_mfa: D. Đăng nhập, có 2FA [xoay sid]
    pending_mfa --> authenticated: E. OTP đúng [xoay sid lần hai]

    authenticated --> authenticated: F. Đổi tài khoản demo [xoay sid]
    authenticated --> authenticated: J. Đổi mật khẩu [xoay sid, thu hồi phiên khác]
    authenticated --> authenticated: K. Bật/tắt 2FA [xoay sid]
    authenticated --> authenticated: L. Xác minh email [giữ sid]

    anonymous --> [*]: G/H/I
    pending_mfa --> [*]: G. Đăng xuất / H. User-Agent lệch / I. Hết hạn
    authenticated --> [*]: G. Đăng xuất / H. User-Agent lệch / I. Hết hạn
```

| Trạng thái | Có `cdpUserId`? | Được làm gì |
|---|---|---|
| `anonymous` (khách) | Không | Duyệt, tìm kiếm, chat, xem gợi ý phổ biến. Không có sự kiện nào ghi vào CDP. |
| `pending_mfa` | **Không** | Chỉ gọi được xác minh OTP. Mọi route khác trả `403 MFA_REQUIRED`. |
| `authenticated` | Có | Mọi tính năng, dữ liệu lọc theo `cdpUserId` của chính mình. |

**Hai mốc hết hạn:** không hoạt động **30 phút** thì hết phiên (idle); và dù hoạt động liên tục, phiên cũng hết sau **12 giờ** (absolute). Đổi IP (ví dụ điện thoại chuyển từ Wi-Fi sang 4G) **không** huỷ phiên; hệ thống chỉ ghi log và yêu cầu nhập lại mật khẩu cho hành động nhạy cảm như đổi mật khẩu.

---

## 10. Bảng lỗi và cách hiển thị

| HTTP | Mã | Khi nào | Web hiển thị | Thử lại tự động? |
|---:|---|---|---|---|
| 400 | `VALIDATION_ERROR` | Thiếu trường, sai định dạng email | Lỗi dưới ô nhập | Không |
| 400 | `WEAK_PASSWORD` | Mật khẩu vi phạm chính sách | Lỗi dưới ô mật khẩu, kèm lý do | Không |
| 400 | `CAPTCHA_REQUIRED` / `CAPTCHA_FAILED` | Tới ngưỡng CAPTCHA mà thiếu hoặc sai | Hiện hoặc reset widget CAPTCHA | Không |
| 401 | `INVALID_CREDENTIALS` | Sai email hoặc mật khẩu | "Email hoặc mật khẩu không đúng" | Không |
| 401 | `UNAUTHENTICATED` | Route cần đăng nhập, chưa đăng nhập | Hộp thoại đăng nhập tại chỗ, xong tự làm tiếp hành động | Không |
| 401 | `SESSION_EXPIRED` | Phiên hết hạn hoặc bị huỷ | Hộp thoại "Phiên đã hết hạn", điền sẵn email, gửi lại request **đúng một lần** | Một lần sau khi đăng nhập lại |
| 401 | `INVALID_TOKEN` / `TOKEN_EXPIRED` | Token hỏng hoặc hết hạn (client nội bộ) | BFF xử lý, Web thấy `SESSION_EXPIRED` | Không |
| 401 | `MFA_INVALID` | OTP sai (P1) | Lỗi dưới ô mã, số lần còn lại | Không |
| 403 | `CSRF_FAILED` | Thiếu/sai CSRF hoặc Origin lạ | Tải lại trang rồi thử lại | Không |
| 403 | `MFA_REQUIRED` | Phiên `pending_mfa` gọi route khác | Chuyển sang màn nhập OTP | Không |
| 404 | `BOOKING_NOT_FOUND` | Đơn không có **hoặc không thuộc về bạn** | "Không tìm thấy đơn" | Không |
| 409 | `EMAIL_ALREADY_EXISTS` | Email đã đăng ký | Gợi ý đăng nhập | Không |
| 429 | `TOO_MANY_ATTEMPTS` | Vượt rate limit hoặc đang bị khoá | Đếm ngược theo `retryAfterSeconds`, khoá nút gửi | **Có**, sau thời gian chờ |
| 502 | — | BFF không gọi được Backend (lỗi mạng) | Trạng thái lỗi + nút Thử lại | Người dùng bấm |
| 503 | `CDP_UNAVAILABLE` | Không tạo được hồ sơ CDP khi đăng ký | Trạng thái lỗi + nút Thử lại | **Có** |

Mọi lỗi theo đúng Error Envelope `{ error: { code, message, retryable, requestId, details } }` (`src/shared/contracts/schemas/common.yaml`). Khi báo lỗi cho team, gửi kèm `requestId` để tra log.

**Không bao giờ ghi vào log:** mật khẩu (kể cả mật khẩu sai), JWT, refresh token, `sid` đầy đủ (chỉ 8 ký tự đầu), CSRF token, secret OTP, recovery code, email đầy đủ (dùng bản băm hoặc `m***h@example.com`), IP đầy đủ (chỉ /24).
