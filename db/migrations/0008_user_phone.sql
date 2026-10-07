-- 0008_user_phone — số điện thoại trong hồ sơ người dùng (FR-USR-04)
--
-- Áp lên database ĐÃ CÓ DỮ LIỆU. Nội dung phải khớp db/init/01_vota.sql; khác biệt duy nhất là mọi lệnh
-- ở đây đều idempotent. PRD `docs/prd/data-model.md` đã có cột `phone` ở APP_USERS; DDL chỉ đuổi kịp.
-- Số điện thoại chỉ nằm ở app.users: không gửi sang CDP, Insider hay Stripe.
--
-- KHÔNG viết BEGIN/COMMIT ở đây: run.py đã bọc mỗi file trong một transaction.

ALTER TABLE app.users ADD COLUMN IF NOT EXISTS phone text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'users_phone_format' AND conrelid = 'app.users'::regclass
    ) THEN
        ALTER TABLE app.users
            ADD CONSTRAINT users_phone_format CHECK (phone IS NULL OR phone ~ '^0[0-9]{9}$');
    END IF;
END $$;
