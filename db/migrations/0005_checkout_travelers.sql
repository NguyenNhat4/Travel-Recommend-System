-- 0005_checkout_travelers — đoàn khách người lớn/trẻ em, giá theo loại khách, line_total do Backend ghi (FR-BKG-08)
--
-- Áp lên database ĐÃ CÓ DỮ LIỆU. Nội dung phải khớp db/init/01_vota.sql; khác biệt duy nhất là mọi lệnh ở đây đều
-- idempotent. Spec: docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §9.
-- KHÔNG viết BEGIN/COMMIT ở đây: run.py đã bọc mỗi file trong một transaction.

-- 1. Giỏ hàng: số người lớn, số trẻ em và snapshot giá vé trẻ em của mỗi mục.
--    Dòng cũ (client cũ không gửi guests) nhận mặc định R-CRT-05: khách sạn và dịch vụ tính theo người mỗi phòng/vé một
--    người lớn; combo 1 người lớn. Số phòng/vé quá 9 (trước đây cho tới 99) bị kéo về 9 theo giới hạn đoàn 9 khách.
ALTER TABLE app.cart_items ADD COLUMN IF NOT EXISTS adults integer;
ALTER TABLE app.cart_items ADD COLUMN IF NOT EXISTS children integer NOT NULL DEFAULT 0;
ALTER TABLE app.cart_items ADD COLUMN IF NOT EXISTS child_unit_price_snapshot numeric(14,2);

UPDATE app.cart_items ci
   SET adults = CASE WHEN p.taxonomy = 'combo' THEN 1 ELSE LEAST(GREATEST(ci.quantity, 1), 9) END,
       quantity = CASE WHEN p.taxonomy = 'combo' THEN ci.quantity ELSE LEAST(ci.quantity, 9) END
  FROM cdp.products p
 WHERE p.product_id = ci.product_id AND ci.adults IS NULL;

ALTER TABLE app.cart_items ALTER COLUMN adults SET NOT NULL;
ALTER TABLE app.cart_items ALTER COLUMN adults SET DEFAULT 1;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cart_items_adults_min'
                   AND conrelid = 'app.cart_items'::regclass) THEN
        ALTER TABLE app.cart_items ADD CONSTRAINT cart_items_adults_min CHECK (adults >= 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cart_items_children_min'
                   AND conrelid = 'app.cart_items'::regclass) THEN
        ALTER TABLE app.cart_items ADD CONSTRAINT cart_items_children_min CHECK (children >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cart_items_party_size'
                   AND conrelid = 'app.cart_items'::regclass) THEN
        ALTER TABLE app.cart_items ADD CONSTRAINT cart_items_party_size CHECK (adults + children <= 9);
    END IF;
END $$;

-- 2. Đoàn khách của đơn. Ngày sinh chỉ lưu ở đây (không API, không CDP, Insider, Stripe).
CREATE TABLE IF NOT EXISTS app.booking_travelers (
    traveler_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id     uuid NOT NULL REFERENCES app.bookings (booking_id) ON DELETE CASCADE,
    traveler_ref   text NOT NULL,
    position       integer NOT NULL CHECK (position BETWEEN 1 AND 9),
    traveler_type  text NOT NULL CHECK (traveler_type IN ('adult','child')),
    surname        text NOT NULL,
    given_names    text NOT NULL,
    full_name      text NOT NULL,
    birth_date     date,
    CONSTRAINT booking_travelers_ref_uq UNIQUE (booking_id, traveler_ref),
    CONSTRAINT booking_travelers_position_uq UNIQUE (booking_id, position),
    CONSTRAINT booking_travelers_child_birth CHECK (traveler_type = 'adult' OR birth_date IS NOT NULL)
);

-- 3. Dòng đơn: metadata (dòng giá, hành khách, phân phòng) và line_total do Backend ghi.
--    Cột sinh `unit_price * quantity` sai với khách sạn nhiều đêm và với giá trẻ em. DROP EXPRESSION giữ nguyên giá trị
--    hiện có của từng dòng; IF EXISTS để chạy lại không lỗi khi cột đã là cột thường.
ALTER TABLE app.booking_items ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}';
ALTER TABLE app.booking_items ALTER COLUMN line_total DROP EXPRESSION IF EXISTS;
ALTER TABLE app.booking_items ALTER COLUMN line_total SET NOT NULL;

-- Đơn khách sạn nhiều đêm do Backend tạo trước đây (provider khác 'seed', chưa có dòng giá): cột sinh cũ bỏ qua số đêm nên
-- line_total lệch total_amount. Tính lại cho khớp; booking seed giữ nguyên vì total_amount của seed không nhân số đêm.
UPDATE app.booking_items bi
   SET line_total = bi.unit_price * bi.quantity * GREATEST(1, bi.using_date_to - bi.using_date)
  FROM app.payments p
 WHERE p.booking_id = bi.booking_id AND p.provider <> 'seed'
   AND bi.taxonomy = 'hotel' AND bi.using_date_to IS NOT NULL AND bi.metadata = '{}'::jsonb;

-- Quyền: GRANT ... ON ALL TABLES trong db/init/01_vota.sql chỉ áp cho bảng đã tồn tại lúc nó chạy.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vota_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON app.booking_travelers TO vota_app;
    END IF;
END $$;
