-- 0003_booking_payments — giữ chỗ và thanh toán Stripe cho booking (FR-BKG-05..07)
--
-- Áp lên database ĐÃ CÓ DỮ LIỆU. Nội dung phải khớp db/init/01_vota.sql; khác biệt duy nhất là mọi lệnh
-- ở đây đều idempotent. Đơn cũ (mọi dòng đang là 'confirmed') giữ nguyên trạng thái.
--
-- KHÔNG viết BEGIN/COMMIT ở đây: run.py đã bọc mỗi file trong một transaction.

ALTER TABLE app.bookings ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE app.bookings ADD COLUMN IF NOT EXISTS hold_expires_at timestamptz;
ALTER TABLE app.bookings ADD COLUMN IF NOT EXISTS confirmed_at timestamptz;
ALTER TABLE app.bookings ADD COLUMN IF NOT EXISTS cancelled_at timestamptz;
ALTER TABLE app.bookings ADD COLUMN IF NOT EXISTS cancel_reason text;
ALTER TABLE app.bookings ADD COLUMN IF NOT EXISTS purchase_events_cancelled_at timestamptz;

-- Trạng thái đơn: thêm pending_payment, payment_failed, expired; mặc định mới là pending_payment.
ALTER TABLE app.bookings DROP CONSTRAINT IF EXISTS bookings_status_check;
ALTER TABLE app.bookings ADD CONSTRAINT bookings_status_check
    CHECK (status IN ('pending_payment','confirmed','payment_failed','expired','cancelled'));
ALTER TABLE app.bookings ALTER COLUMN status SET DEFAULT 'pending_payment';

-- Đơn cũ đã confirmed: điền confirmed_at để hiển thị nhất quán
UPDATE app.bookings SET confirmed_at = created_at WHERE status = 'confirmed' AND confirmed_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS bookings_one_pending_per_user ON app.bookings (cdp_user_id) WHERE status = 'pending_payment';
CREATE INDEX IF NOT EXISTS bookings_hold_idx ON app.bookings (hold_expires_at) WHERE status = 'pending_payment';

CREATE TABLE IF NOT EXISTS app.payments (
    payment_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id           uuid NOT NULL UNIQUE REFERENCES app.bookings (booking_id) ON DELETE CASCADE,
    provider             text NOT NULL CHECK (provider IN ('stripe','fake','seed')),
    checkout_session_id  text UNIQUE,
    payment_intent_id    text UNIQUE,
    checkout_url         text,
    amount               bigint NOT NULL CHECK (amount >= 0),
    currency             char(3) NOT NULL DEFAULT 'VND',
    status               text NOT NULL DEFAULT 'open'
                         CHECK (status IN ('open','succeeded','failed','expired','refund_pending','refunded','refund_failed')),
    failed_attempts      integer NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    last_failure_code    text,
    refund_id            text,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS payments_status_idx ON app.payments (status, updated_at);

-- Đơn cũ đã confirmed nhận một dòng thanh toán 'seed' để cặp trạng thái đơn/thanh toán luôn hợp lệ
INSERT INTO app.payments (booking_id, provider, amount, currency, status, created_at, updated_at)
SELECT b.booking_id, 'seed', b.total_amount::bigint, b.currency, 'succeeded', b.created_at, b.created_at
  FROM app.bookings b
 WHERE b.status = 'confirmed'
   AND NOT EXISTS (SELECT 1 FROM app.payments p WHERE p.booking_id = b.booking_id);

-- Quyền: GRANT ... ON ALL TABLES trong db/init/01_vota.sql chỉ áp cho bảng đã tồn tại lúc nó chạy.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vota_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON app.payments TO vota_app;
    END IF;
END $$;
