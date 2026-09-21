# Auth P0 — bước 3: port, domain, application, infrastructure trong src/backend

- Ngày: 2026-09-21
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: dang dở
- Phạm vi: backend

## Mục tiêu

Bước 3 của kế hoạch auth P0 (`docs/hop-dong-tich-hop-auth.md`). Người yêu cầu chốt phạm vi: **chỉ làm
trong `src/backend`, không đụng phần khác** — nên entry này không chạm `src/frontend`, `src/cdp_clone`
hay `src/data_collection`.

Trước đó `src/backend/app/application/auth/` và `domain/auth/` chỉ có một dòng docstring rỗng.

## File thay đổi

- `src/backend/requirements.txt` — sửa: thêm `argon2-cffi`, `bcrypt`, `PyJWT[crypto]`, `redis`.
- `src/backend/app/domain/auth/identifiers.py` — thêm: cấp phát `cdp_user_id` dải `VPW`, tách khỏi dải seed `VP\d{7}`.
- `src/backend/app/domain/auth/password.py` — thêm: chính sách mật khẩu theo NIST SP 800-63B.
- `src/backend/app/domain/auth/session.py` — thêm: máy trạng thái phiên 3 trạng thái, bảng chuyển §3.8.
- `src/backend/app/application/auth/principal.py` — thêm: `AuthPrincipal`, `AuthenticatedUser`.
- `src/backend/app/application/auth/errors.py` — thêm: lỗi auth, mã khớp bảng §17.
- `src/backend/app/application/auth/use_cases.py` — thêm: `RegisterUser` (hai pha có bù trừ), `AuthenticateUser`.
- `src/backend/app/application/ports/auth.py` — thêm: `PasswordHasher`, `UserRepository`, `RefreshTokenStore`, `TokenIssuer`, `LoginAttemptLog`, `RateLimiter`.
- `src/backend/app/application/ports/cdp_client.py` — sửa: **thêm `ensure_profile` vào port `CdpClient`**.
- `src/backend/app/infrastructure/auth/__init__.py` — thêm.
- `src/backend/app/infrastructure/auth/argon2_hasher.py` — thêm: Argon2id + đường kiểm bcrypt + `dummy_verify`.
- `src/backend/app/infrastructure/auth/jwt_issuer.py` — thêm: RS256, kiểm đủ 10 điểm §10.3, JWKS.
- `src/backend/app/infrastructure/auth/postgres_user_repository.py` — thêm: `app.users` qua role `vota_app`.
- `src/backend/app/infrastructure/auth/postgres_login_attempts.py` — thêm: `app.login_attempts`, băm email, rút IP về /24.
- `src/backend/app/infrastructure/clients/local_cdp_client.py` — sửa: hiện thực `ensure_profile` (`ON CONFLICT DO NOTHING`).
- `src/backend/app/core/config.py` — sửa: biến optional để trống trong `.env` coi là `None` (lỗi có sẵn, xem dưới).
- `.env.example` — sửa: cắt khối lặp cuối file và bỏ `DATABASE_URL=sqlite…` chọi với DSN Postgres (lỗi có sẵn, xem dưới).
- `history/2026-09-21-auth-p0-backend-domain-application.md` — thêm: entry này.

## Quyết định

- **`ensure_profile` thêm vào port `CdpClient`, không tạo port riêng.** Tạo hồ sơ là thao tác trên `cdp.profiles`,
  đúng trách nhiệm của port đó. Use case `RegisterUser` chỉ nhận một `ProfileCreator` hẹp để không kéo cả port CDP
  vào. **Vẫn chờ reviewer Data/Integration** (`ARCHITECTURE.md` §11, spec §22.2 mục A).
- **Không xoá hồ sơ mồ côi khi pha ④ hỏng.** `cdp_writer` chỉ có `INSERT`/`UPDATE` trên `cdp.profiles`, không có
  `DELETE`. Nới quyền chỉ để dọn rác là đánh đổi sai; hồ sơ rỗng không event thì vô hại. Ghi `auth.orphan_profile`.
- **Phân biệt hai ràng buộc UNIQUE lúc INSERT `app.users`** bằng `exc.diag.constraint_name`: trùng email là lỗi
  người dùng (409), trùng `cdp_user_id` là va chạm ID nội bộ → sinh lại, tối đa 3 lần.
- **`dummy_verify()` khi email không tồn tại.** Không có nó, thời gian phản hồi thành oracle liệt kê tài khoản.
- **Allowlist `alg` cứng `{RS256, ES256}`, truyền tường minh vào `jwt.decode`.** Không bao giờ đọc `alg` từ header
  token để chọn hàm kiểm.
- **Token thiếu `cdp_user_id` bị từ chối** dù chữ ký hợp lệ: không có danh tính nghiệp vụ thì không truy vấn được
  gì của người dùng, và đó là dấu hiệu token của phiên `pending_mfa` bị dùng sai chỗ.
- **`ip_prefix()` trả `'unknown'` thay vì ném lỗi** với giá trị không parse được: ghi nhật ký đăng nhập không được
  phép làm hỏng chính lần đăng nhập đó.
- **Máy trạng thái phiên không có nhánh mặc định.** Cặp (state, event) không khai báo thì ném `InvalidTransition`;
  im lặng cho qua ở tầng này nghĩa là một phiên nửa-đăng-nhập có thể mang danh tính.

## Hai lỗi có sẵn phát hiện khi chạy test, đã sửa

Cả hai không do thay đổi lần này; lộ ra vì đây là lần đầu chạy backend với một `.env` thật.

1. **Backend không khởi động nổi khi có `.env`.** `config.py` khai
   `itinerary_service_base_url: str | None = Field(default=None, pattern=r"^https?://")`, mà `.env.example` để
   biến này **trống**. Biến trống trong `.env` đến pydantic là chuỗi rỗng `""`, không phải `None`, nên `""` không
   khớp `^https?://` và `Settings()` ném `ValidationError`. Ai làm đúng hướng dẫn "copy `.env.example` sang `.env`"
   đều vấp: `pytest` dừng ở collection với 2 ERROR, `uvicorn` không lên. Sửa bằng `field_validator(mode="before")`
   coi chuỗi rỗng là `None`, chỉ áp cho hai trường thực sự Optional (`itinerary_service_base_url`,
   `itinerary_data_mode`) — trường `str` thường như `cdp_service_token` vẫn coi `""` là hợp lệ.

2. **`.env.example` có 17 khóa trùng; backend âm thầm dùng SQLite thay vì PostgreSQL.** File là ba phiên bản nối
   vào nhau: dòng 143–166 là bản sao **y hệt** dòng 1–24 (đã đối chiếu bằng `diff`), và `DATABASE_URL` xuất hiện
   **ba lần** — `sqlite:///./data/app.db` (dòng 22), DSN Postgres (dòng 41), rồi lại `sqlite` (dòng 164).
   Đã kiểm bằng thực nghiệm: **pydantic-settings lấy dòng CUỐI** khi khóa trùng, nên `sqlite` thắng và toàn bộ
   cấu hình Postgres — gồm cả schema vừa migrate — bị bỏ qua mà không có cảnh báo nào.
   Sửa: cắt khối lặp cuối file, bỏ dòng `DATABASE_URL=sqlite…` ở khối đầu, thêm ghi chú giải thích vì sao không
   được khai lại. Sau khi sửa: **0 khóa trùng**, `database_url` phân giải ra `postgresql://vota_app_login@…/vota`.

   **`.env` của người dùng vẫn còn cả ba dòng đó** — file local, không sửa hộ. Cần `cp .env.example .env` (rồi
   điền lại secret) hoặc tự xoá hai dòng `DATABASE_URL=sqlite…`, nếu không backend vẫn chạy trên SQLite.

## Kiểm tra

Chạy thật bằng `src/backend/.venv` trên PostgreSQL Docker (`localhost:5432`), hai role tách biệt.

- **Ranh giới role — nền tảng của thiết kế hai pha, đã xác nhận bằng lệnh thật:**
  - `vota_app` INSERT `cdp.profiles` → `permission denied for table profiles`;
  - `vota_app` SELECT `cdp.profiles` → permission denied (nên `cdp_user_id` **phải** nằm cùng hàng `app.users`);
  - `cdp_writer` SELECT `app.users` → permission denied.
- **Đăng ký end-to-end:** tạo `cdp.profiles` trước, `app.users` sau; `cdp_user_id = VPW8Z32XKPEEXKA` (đúng dải
  `VPW`, không đụng dải seed). Hồ sơ CDP có `lifecycle_stage='new'`, `lifetime_order_count=0`,
  `purchased_verticals=[]` → đúng điều kiện `coldStart: true` của spec.
- **Trùng email** → `409 EMAIL_ALREADY_EXISTS`.
- **Đăng nhập** → OK, trả đúng `cdp_user_id`; `last_login_at` được cập nhật.
- **Sai mật khẩu** và **email không tồn tại** → cùng `401 INVALID_CREDENTIALS`, **cùng thông điệp**.
- **Thời gian không rò rỉ:** verify-sai 21 ms vs `dummy_verify` 21 ms.
- **Rehash bcrypt → Argon2id:** user có hash `$2b$10$` đăng nhập xong thì cột đổi thành `$argon2id$`.
- **JWT — 10 đòn tấn công đều bị từ chối**, gồm hai token **tự tay dựng** (PyJWT không cho `encode` chúng):
  `alg:none`, RS256→HS256 ký bằng chính public key. Còn lại: sai issuer, sai audience, hết hạn, `nbf` tương lai,
  thiếu `cdp_user_id`, thiếu `exp`, chữ ký khóa khác, body bị sửa. JWKS sinh đúng khoá RSA.
- **`app.login_attempts`** ghi đúng: `email_hash` dạng `sha256:…`, `ip_prefix` `203.0.113.0/24`, ba dòng với
  `succeeded`/`failure_reason` đúng (`bad_password`, `unknown_email`).
- **Máy trạng thái:** `LOGIN`→authenticated+xoay sid, `LOGIN_NEEDS_MFA`→pending_mfa **không mang danh tính**,
  `LOGOUT`→huỷ; `PENDING_MFA + LOGIN` bị chặn bằng `InvalidTransition`.
- Dữ liệu test đã xoá sạch sau khi kiểm (`users=0 profiles=0 attempts=0`).
- **Bộ test hiện có: `125 passed, 2 skipped`** bằng `src/backend/.venv` (Python 3.14.7), chạy **có** `.env` thật
  trong repo — đúng trường hợp trước khi sửa thì dừng ở collection với 2 ERROR. Thay đổi lần này không phá test nào.
- **Chưa viết test mới cho auth**: các kiểm tra ở trên chạy bằng script tay, chưa nằm trong `src/backend/tests/`.

## Còn lại / rủi ro

- **Chưa có test tự động cho auth.** Toàn bộ kiểm tra auth ở trên là script chạy tay, không nằm trong
  `src/backend/tests/`. Phải chuyển thành unit + integration test theo `ARCHITECTURE.md` §10 trước khi coi bước 3 là xong.
- **`.env` local của người dùng vẫn còn `DATABASE_URL=sqlite…` thắng dòng Postgres.** Không sửa file local hộ;
  người dùng phải tự xử lý, nếu không mọi thứ vừa làm với PostgreSQL sẽ không có tác dụng lúc chạy thật.
- **Chưa hiện thực:** `RefreshTokenStore` (Postgres, rotation + phát hiện tái dùng), `RateLimiter` (Redis),
  `RotateRefreshToken`/`RevokeSession` use case. Kiểm tra ở trên dùng bản giả cho hai port này.
- **Chưa làm bước 5** (route FastAPI, dependency `current_principal`/`optional_principal`, gỡ query param
  `cdp_user_id` khỏi `/recommendations`). `TODO` ở `recommendations.py:8` **vẫn còn**.
- **Ngoài phạm vi lần này** theo yêu cầu "chỉ làm backend": bước 4 (`seed_auth.py` trong `src/data_collection`) và
  bước 6 (BFF trong `src/frontend`). Nghĩa là chưa có 4 tài khoản test thật, và cookie phiên chưa tồn tại —
  hiện mới có đường JWT thuần cho client nội bộ.
- **Không đoán được mật khẩu demo dùng chung của seed** (`DEMO_PASSWORD_HASH` ở `seed_histories.py:40`); đường
  rehash được kiểm bằng hash bcrypt tự tạo. `seed_auth.py` ở bước 4 sẽ đặt mật khẩu tường minh nên vấn đề này biến mất.
- **Venv dùng Python 3.14.7** (máy không có bản thấp hơn). Cài được, `torch 2.14.0+cu130` có CUDA, nhưng repo ghi
  "Python >= 3.10" và chưa ai kiểm repo trên 3.14 — có thể còn lỗi tương thích chưa lộ.
- Chưa commit, chưa push.
