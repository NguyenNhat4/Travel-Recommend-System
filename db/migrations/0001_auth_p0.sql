-- 0001_auth_p0 — bảng bền của auth hybrid (docs/hop-dong-tich-hop-auth.md §16.2)
--
-- Áp phần schema auth lên database ĐÃ CÓ DỮ LIỆU. Nội dung phải khớp db/init/01_vota.sql;
-- khác biệt duy nhất là ở đây mọi lệnh đều idempotent để chạy lại được.
--
-- Redis giữ phần phù du (session, bộ đếm rate limit, OAuth state) — mất thì người dùng chỉ phải
-- đăng nhập lại. Hai bảng dưới giữ phần BỀN: thu hồi được kể cả khi Redis trống, và còn bằng chứng
-- khi điều tra.
--
-- KHÔNG viết BEGIN/COMMIT ở đây: run.py đã bọc mỗi file trong một transaction.

-- app.users — cột xác minh email (auth §11.1). NULL = chưa xác minh; chặn checkout, KHÔNG chặn đăng nhập.
ALTER TABLE app.users ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;

COMMENT ON COLUMN app.users.password_hash IS
    'Argon2id, chuỗi PHC tự mô tả thuật toán (auth §8.1). bcrypt của user seed vẫn kiểm được và được rehash ngay khi đăng nhập (auth §8.2).';

-- app.refresh_tokens — chuỗi rotation một-lần-dùng (auth §10.4).
--   Token bị dùng lại sau khi đã xoay = dấu hiệu bị đánh cắp → thu hồi cả family, không chỉ một dòng.
CREATE TABLE IF NOT EXISTS app.refresh_tokens (
    token_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES app.users (user_id) ON DELETE CASCADE,
    family_id      uuid NOT NULL,
    token_hash     text NOT NULL UNIQUE,
    session_id     text NOT NULL,
    issued_at      timestamptz NOT NULL DEFAULT now(),
    expires_at     timestamptz NOT NULL,
    rotated_at     timestamptz,
    revoked_at     timestamptz,
    revoked_reason text CHECK (revoked_reason IN ('logout','rotation','reuse_detected','password_change','mfa_change','admin')),
    CONSTRAINT refresh_tokens_window CHECK (expires_at > issued_at)
);
CREATE INDEX IF NOT EXISTS refresh_tokens_user_idx   ON app.refresh_tokens (user_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS refresh_tokens_family_idx ON app.refresh_tokens (family_id);

-- app.login_attempts — bằng chứng bền để điều tra; rate limit thời gian thực vẫn chạy trên Redis (auth §9).
--   Không lưu email thô: email_hash = sha256(lower(email)). user_id NULL = email không tồn tại.
CREATE TABLE IF NOT EXISTS app.login_attempts (
    attempt_id      bigserial PRIMARY KEY,
    email_hash      text NOT NULL,
    user_id         uuid REFERENCES app.users (user_id) ON DELETE SET NULL,
    ip_prefix       text NOT NULL,
    user_agent_hash text,
    succeeded       boolean NOT NULL,
    failure_reason  text CHECK (failure_reason IN ('bad_password','unknown_email','locked','mfa_failed','captcha_failed')),
    attempted_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT login_attempts_reason CHECK (succeeded = (failure_reason IS NULL))
);
CREATE INDEX IF NOT EXISTS login_attempts_email_idx ON app.login_attempts (email_hash, attempted_at DESC);
CREATE INDEX IF NOT EXISTS login_attempts_ip_idx    ON app.login_attempts (ip_prefix, attempted_at DESC);

-- Quyền: GRANT ... ON ALL TABLES trong db/init/01_vota.sql chỉ áp cho bảng đã tồn tại lúc nó chạy,
-- nên bảng thêm qua migration phải được cấp quyền tường minh. Bỏ dòng này thì backend gặp
-- "permission denied for table refresh_tokens" ngay lần đăng nhập đầu tiên.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vota_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON app.refresh_tokens, app.login_attempts TO vota_app;
        GRANT USAGE, SELECT ON SEQUENCE app.login_attempts_attempt_id_seq TO vota_app;
    END IF;
END $$;

