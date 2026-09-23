# Auth P0 — bước 1 contract và bước 2 database

- Ngày: 2026-09-21
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: dang dở
- Phạm vi: contract, database, docs

## Mục tiêu

Triển khai P0 của `docs/hop-dong-tich-hop-auth.md`. Entry này ghi **bước 1 (contract)** và **bước 2 (database)**; bước 3–7 (backend port/domain, tài khoản test, API, BFF, test) chưa làm.

## File thay đổi

Contract:

- `src/shared/contracts/schemas/common.yaml` — sửa: thêm 13 giá trị `ErrorCode` của auth; sửa mô tả `retryable` (thống nhất 5 mã) và mô tả `details`.
- `src/shared/contracts/schemas/auth.yaml` — sửa: thêm `SessionState`, `SessionRequest`, `SessionResponse`, `RefreshRequest`, `RevokeRequest`, `MfaVerifyRequest`, `PasswordChangeRequest`.
- `src/shared/contracts/paths/auth.yaml` — sửa: thêm `/auth/session`, `/auth/session/token`, `/auth/session/revoke`, `/auth/session/mfa/verify`, `/auth/password`.
- `src/shared/contracts/openapi.yaml` — sửa: khai báo 5 path và 7 schema mới; thêm securityScheme `serviceToken`.
- `src/shared/mocks/auth/createSession.200-authenticated.json` — thêm.
- `src/shared/mocks/auth/createSession.200-pending-mfa.json` — thêm.
- `src/shared/mocks/auth/createSession.429-too-many-attempts.json` — thêm.
- `src/shared/mocks/index.json` — sửa: đăng ký 3 fixture trên.

Database:

- `db/init/01_vota.sql` — sửa: thêm `app.refresh_tokens`, `app.login_attempts`; thêm cột `app.users.email_verified_at`; đổi comment `password_hash` từ BCrypt sang Argon2id.
- `db/vota_schema.sql` — sửa: y hệt (hai file vẫn byte-identical).
- `docs/DATABASE_SCHEMA.md` — sửa: §4 ERD thêm hai bảng auth + `email_verified_at` + ghi chú Redis/Postgres; §7 thêm hai dòng bảng; §8 sửa thứ tự nạp (Argon2id thay BCrypt); §11 đồng bộ lại toàn bộ khối DDL theo `db/vota_schema.sql`.
- `docker-compose.yml` — sửa: thêm service `redis:7-alpine`, bind `127.0.0.1:6379`, `--requirepass`, `maxmemory-policy noeviction`.
- `.env.example` — sửa: thêm khối cấu hình auth (JWT, Argon2, Redis, CAPTCHA, SMTP, service token, BFF, mật khẩu 4 tài khoản test, OAuth P2).
- `.gitignore` — sửa: thêm `secrets/`.
- `history/2026-09-21-auth-p0-contract-va-database.md` — thêm: entry này.

## Quyết định

- **Contract chỉ thêm, không sửa.** `git diff --numstat`: `openapi.yaml` +31/-0, `paths/auth.yaml` +144/-0, `schemas/auth.yaml` +83/-0. Hai dòng xoá duy nhất ở `common.yaml` là phần mô tả `retryable`/`details`, không đổi hình dạng schema. Bốn endpoint v1 giữ nguyên nên không phải lên v2 (`AGENTS.md` §3).
- **`maxmemory-policy noeviction` cho Redis.** `allkeys-lru` sẽ ngẫu nhiên đá người dùng đang đăng nhập ra khi bộ nhớ đầy.
- **Hai bảng auth đặt trước khối GRANT** trong `01_vota.sql`. `GRANT … ON ALL TABLES IN SCHEMA app` áp tại thời điểm chạy, nên bảng phải tồn tại trước thì `vota_app` mới có quyền; đã kiểm bằng truy vấn thật.
- **`login_attempts` không lưu email thô**, chỉ `sha256(lower(email))`, và `ip_prefix` /24 thay vì IP đầy đủ — theo §15.2 của spec.
- **CHECK `succeeded = (failure_reason IS NULL)`** để không ghi được bản ghi mâu thuẫn (thành công mà vẫn có lý do thất bại).
- **`docs/DATABASE_SCHEMA.md` §11 được sinh lại từ `db/vota_schema.sql`** thay vì sửa tay, để hai bên không lệch nhau.

## Kiểm tra

- `validate_contract.py` → **PASS**: 77 schemas, all local refs, 50 grounded products, 4 itinerary statuses, negative checks, **53 fixtures** (trước đó 50); CDP clone 12 schemas, 7 fixtures, 11 negative checks.
- `bundle_openapi.py` → chạy được, bundle chứa 4 tham chiếu `auth/session`.
- `docker compose config` → **VALID**.
- `diff db/init/01_vota.sql db/vota_schema.sql` → **không khác biệt**.
- §11 của `DATABASE_SCHEMA.md` so với `db/vota_schema.sql` → **khớp byte-for-byte**.
- **DDL chạy thật** trên container `pgvector/pgvector:pg16` tạm (không đụng volume `build-phase_pgdata` của người dùng): initdb sạch, không ERROR/FATAL.
  - `app.refresh_tokens`, `app.login_attempts` tạo đúng cột, index, CHECK, FK.
  - `app.users.email_verified_at` có mặt.
  - `vota_app` có `SELECT,INSERT,UPDATE,DELETE` trên cả hai bảng mới, và `USAGE` trên `login_attempts_attempt_id_seq`.
  - `cdp_reader`/`cdp_writer` có **0** quyền trong schema `app` → ranh giới role còn nguyên.
  - Smoke test ghi thật bằng role `vota_app`: insert user + refresh token + 2 login attempt đều thành công.
  - CHECK `login_attempts_reason` chặn đúng bản ghi mâu thuẫn.
  - Container tạm đã xoá; volume của người dùng không bị đụng.
- Chưa chạy `pytest` hay test frontend: chưa có code auth, và máy hiện không có môi trường Python của backend (không pip/conda). Validator contract chạy bằng venv tạm trong scratchpad.

## Còn lại / rủi ro

- **Bước 3–7 chưa làm**: port `CdpClient.ensure_profile` + domain/application/infrastructure auth, `seed_auth.py` (4 tài khoản test thật), route FastAPI, BFF Next.js, test.
- **`seed_auth.py` chưa có** nên chưa tạo được 4 tài khoản Argon2id; `seed_histories.py` vẫn ghi hash BCrypt dùng chung. Đường verify-rồi-rehash của §8.2 sẽ xử lý số user cũ này.
- **`CdpClient.ensure_profile` vẫn chờ reviewer Data/Integration** (`ARCHITECTURE.md` §11, spec §22.2 mục A).
- **Chạy `db/init/*.sql` cần volume trống.** Máy nào đã có `pgdata` phải `docker compose down -v && make demo-db` thì mới thấy hai bảng mới — nếu không, `app.refresh_tokens` sẽ không tồn tại và auth sẽ lỗi lúc chạy.
- Không có migration tool trong repo; thay đổi schema hiện vẫn theo cách "xoá volume, chạy lại initdb". Với database staging cloud phải chạy tay `psql -f db/init/01_vota.sql` (hoặc chỉ phần DDL mới) vì cloud không chạy initdb.
- Spec và entry `2026-09-21-spec-auth-hybrid.md` đã được người yêu cầu commit ở `5556b3e`; entry này ghi phần triển khai tiếp theo.
- Chưa commit, chưa push.
