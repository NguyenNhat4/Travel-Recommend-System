# Spec auth hybrid: session cookie ở BFF + JWT nội bộ

- Ngày: 2026-09-21
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành (spec); triển khai chưa bắt đầu
- Phạm vi: docs

## Mục tiêu

Viết hợp đồng tích hợp cho phần xác thực. Chủ dự án đã chốt cơ chế **hybrid**: session cookie cho web app (BFF tại Next.js) + JWT cho service nội bộ, và yêu cầu viết kỹ phần logic mapping. Repo trước đó chỉ có 4 endpoint auth JWT-bearer trong contract, còn `src/backend/app/application/auth/` và `domain/auth/` chỉ có docstring rỗng — chưa có bất kỳ quyết định nào về phiên, mật khẩu, rate limit hay CSRF.

## File thay đổi

- `docs/hop-dong-tich-hop-auth.md` — thêm: hợp đồng auth đầy đủ, 23 mục, trọng tâm là §3 Logic mapping (sáu định danh, chuỗi ánh xạ, hai pha đăng ký, bảng chuyển trạng thái phiên, bảng quyết định resolve danh tính).
- `AGENTS.md` — sửa: thêm một dòng vào bảng §1.2 để agent sau phải đọc spec auth khi chạm phần đăng nhập/phiên/JWT.
- `history/2026-09-21-spec-auth-hybrid.md` — thêm: entry này.

Không sửa file nào trong `src/` hoặc `db/`. Delta OpenAPI và DDL được **đặc tả** trong spec (§16.2, §18) nhưng chưa áp dụng.

## Quyết định

Bốn quyết định do chủ dự án chọn trong phiên:

- **Cookie phiên cắt ở BFF Next.js.** Route handler giữ cookie, đổi ra JWT khi gọi FastAPI; trình duyệt không bao giờ thấy token. BFF **không** ký JWT — private key chỉ ở FastAPI, BFF là người giữ token chứ không phải người phát hành.
- **Không lên v2.** Bốn endpoint `/auth/register|login|me|demo-accounts` giữ nguyên cho client nội bộ/test; thêm nhóm mới `/auth/session/*` dùng cookie. `AuthResponse.accessToken` vẫn required nên không phá tương thích (`AGENTS.md` §3).
- **Redis cho phiên, Postgres cho phần bền.** Session, rate limit, OAuth state, khoá refresh → Redis. `refresh_tokens`, `login_attempts`, `email_verifications`, `mfa_credentials`, `mfa_recovery_codes`, `oauth_identities` → schema `app`.
- **Spec đầy đủ, chia pha P0/P1/P2.** P0 là phần bắt buộc cho MVP v01; P1 thêm xác minh email + TOTP + reset password; P2 thêm OAuth/PKCE + WebAuthn.

Các quyết định kỹ thuật rút ra từ ràng buộc có sẵn của repo:

- **`cdp_user_id` là danh tính cốt lõi, không phải `user_id`.** Toàn bộ `app.carts`, `app.bookings`, `cdp.events` và engine recommendation khoá theo nó (`docs/DATABASE_SCHEMA.md` §4). Auth không sinh danh tính, nó chứng minh quyền dùng một `cdp_user_id` đã có.
- **Đăng ký phải là hai pha có bù trừ.** `app.users.cdp_user_id` là `NOT NULL REFERENCES cdp.profiles`, mà role `vota_app` không có quyền ghi `cdp.profiles` (chỉ `cdp_writer` có) và `AGENTS.md` §6.2 cấm gói hai connection vào một transaction. Thứ tự bị ép cứng: `CdpClient.ensure_profile` trước, `INSERT app.users` sau. Profile mồ côi khi pha 2 hỏng thì **không xoá** — `cdp_writer` không có `DELETE` trên `profiles`, và nới quyền chỉ để dọn rác là đánh đổi sai; ghi log `auth.orphan_profile` thay thế.
- **Cần thêm `CdpClient.ensure_profile`.** Port hiện tại không có đường tạo profile. Đây là thay đổi port, cần reviewer Data/Integration (`ARCHITECTURE.md` §11) — ghi ở §22.2 mục A.
- **Tách dải `cdp_user_id`.** Seed giữ `VP\d{7}` (VP0000001–VP0002000); Backend cấp `VPW` + 12 ký tự base32 từ `secrets`. Vừa tránh va chạm khi chạy lại seed, vừa không cho đoán ID hàng xóm.
- **Gỡ query param `cdp_user_id` khỏi `/recommendations`.** Nó là IDOR với ID tuần tự đoán được. Đóng `TODO` ở `src/backend/app/api/v1/routes/recommendations.py:8` (việc dang dở ghi trong `2026-09-21-gop-recsys-vao-backend-postgres.md`). Nhu cầu demo/eval chuyển sang `/internal/*` có `X-Service-Token`.
- **`SameSite=Lax` chứ không `Strict`.** `Strict` phá OAuth callback (P2) và deep link `/login?redirect=`. Bù bằng double-submit CSRF + kiểm `Origin`; không endpoint nào đổi state qua `GET`.
- **Argon2id, giữ đường bcrypt cho 54 user seed.** Seed dùng một hash BCrypt cost 10 dùng chung (`seed_histories.py:40`); verify-rồi-rehash khi đăng nhập để không phải re-seed hay bắt đổi mật khẩu.
- **`ipPrefix` lệch không huỷ phiên**, chỉ log và bắt xác thực lại cho hành động nhạy cảm. Người dùng di động đổi IP liên tục; huỷ theo IP là làm hỏng sản phẩm. `uaHash` lệch thì huỷ.
- **Token hỏng không im lặng thành khách vãng lai** — giữ nguyên `hop-dong-tich-hop-backend.md` §6.5 và `hop-dong-tich-hop-frontend.md` §7.5.

## Mâu thuẫn tài liệu đã xử lý

Ghi đầy đủ ở §1.4 và §22.1 của spec. Bốn cái đáng chú ý:

1. **handbook §8 cấm OAuth / xác minh email / đặt lại mật khẩu.** Chủ dự án chốt đưa vào, chia pha. Spec ghi rõ nó thay thế handbook §8 về cơ chế.
2. **handbook §8 và DDL ghi BCrypt** → Argon2id. Phải sửa comment ở `db/init/01_vota.sql:189`, `db/vota_schema.sql:189` và `docs/DATABASE_SCHEMA.md` khi triển khai.
3. **`hop-dong-tich-hop-frontend.md` §7.1 chốt token trong `sessionStorage`** → bị thay thế; token không bao giờ tới trình duyệt.
4. **`retryable: true` không khớp giữa hai nguồn**: `hop-dong-tich-hop-backend.md` §8.2 liệt kê 2 mã, `schemas/common.yaml:163-165` liệt kê 3. Spec chốt danh sách 5 mã thống nhất cho cả hai.

Ngoài ra phát hiện hai lỗi có sẵn, đã đặc tả cách sửa ở §4.1 nhưng **chưa sửa code**: proxy `src/frontend/src/app/api/[...path]/route.ts` chuyển tiếp nguyên cookie của trình duyệt sang FastAPI, và làm mất header `X-Request-ID` ở đường response (phá `hop-dong-tich-hop-backend.md` §8.4).

## Kiểm tra

- Không chạy `validate_contract.py`: thay đổi lần này chỉ là tài liệu, chưa sửa `openapi.yaml`, `paths/`, `schemas/` hay mock. Delta contract được đặc tả ở §18 và phải chạy validator khi áp dụng.
- Đã đối chiếu mọi tham chiếu chéo trong spec với file thật: `recommendations.py:8` (TODO), `behaviour.py:62` (`track_search` no-op khi `cdp_user_id is None`), `LoginView.tsx:17-19` (kiểm mật khẩu phía client), `seed_histories.py:40` (`DEMO_PASSWORD_HASH` bcrypt), `common.yaml:161-165` (mô tả `retryable`), `db/init/01_vota.sql:186-195` (`app.users`), bảng GRANT ở `01_vota.sql:341-353`.
- Chưa chạy test nào vì chưa có code auth.

## Còn lại / rủi ro

- **Chưa triển khai gì.** Spec là đầu ra duy nhất. Việc kế tiếp theo đúng `AGENTS.md` §3: sửa contract (`schemas/common.yaml`, `schemas/auth.yaml`, `paths/auth.yaml`, `openapi.yaml`) → chạy validator → DDL + doc database → code backend → code BFF.
- **Bảy mục còn mở** ở §22.2: duyệt `CdpClient.ensure_profile` (chặn P0), nhà cung cấp CAPTCHA, nhà cung cấp email, danh sách OAuth provider, Redis ở staging, tên cột opt-in `cdp.profiles` (vốn đã chờ reviewer CDP), và việc có mở ghép lịch sử ẩn danh hay không.
- **Ghép lịch sử ẩn danh vẫn ngoài phạm vi** theo `hop-dong-tich-hop-cdp.md` §1.6. `anon_id` chỉ sống trong bản ghi session, không bao giờ xuống database. Muốn mở thì cần bảng mới và quyết định của reviewer CDP — không tự thêm (`AGENTS.md` §6).
- **P0 là khối lớn so với mốc v01.** `docs/mvp-v01.md` chỉ yêu cầu "đăng ký/đăng nhập/JWT, tài khoản demo" và hạn là hôm nay 21/09. Nếu cần chạy demo trước, phần nhỏ nhất vẫn giữ được tính đúng đắn là: hybrid session + Argon2id + lọc theo `cdp_user_id` phía server + gỡ query param; rate limit và refresh rotation có thể vào ngay sau.
- Chưa commit, chưa push.
