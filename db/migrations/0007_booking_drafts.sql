-- 0007_booking_drafts — đơn nháp của "Đặt ngay"; giỏ hàng không còn chứa khách sạn và vé máy bay (FR-BKG-01)
--
-- Áp lên database ĐÃ CÓ DỮ LIỆU. Nội dung phải khớp db/init/01_vota.sql; khác biệt duy nhất là mọi lệnh
-- ở đây đều idempotent. Spec: docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §11.
--
-- KHÔNG viết BEGIN/COMMIT ở đây: run.py đã bọc mỗi file trong một transaction.

CREATE TABLE IF NOT EXISTS app.booking_drafts (
    draft_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cdp_user_id  text NOT NULL REFERENCES cdp.profiles (cdp_user_id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS booking_drafts_user_idx    ON app.booking_drafts (cdp_user_id);
CREATE INDEX IF NOT EXISTS booking_drafts_expires_idx ON app.booking_drafts (expires_at);

CREATE TABLE IF NOT EXISTS app.booking_draft_items (
    draft_item_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id             uuid NOT NULL REFERENCES app.booking_drafts (draft_id) ON DELETE CASCADE,
    product_id           uuid NOT NULL REFERENCES cdp.products (product_id),
    quantity             integer NOT NULL CHECK (quantity > 0),
    using_date           date NOT NULL,
    using_date_to        date,
    unit_price_snapshot  numeric(14,2) NOT NULL,
    added_at             timestamptz NOT NULL DEFAULT now(),
    adults               integer NOT NULL DEFAULT 1,
    children             integer NOT NULL DEFAULT 0,
    child_unit_price_snapshot numeric(14,2),
    CONSTRAINT booking_draft_items_dates CHECK (using_date_to IS NULL OR using_date_to > using_date),
    CONSTRAINT booking_draft_items_adults_min CHECK (adults >= 1),
    CONSTRAINT booking_draft_items_children_min CHECK (children >= 0),
    CONSTRAINT booking_draft_items_party_size CHECK (adults + children <= 9),
    CONSTRAINT booking_draft_items_uq UNIQUE (draft_id, product_id, using_date)
);

-- initdb cấp quyền bằng "ALL TABLES IN SCHEMA app" tại thời điểm chạy; bảng tạo sau phải cấp riêng.
GRANT SELECT, INSERT, UPDATE, DELETE ON app.booking_drafts, app.booking_draft_items TO vota_app;

-- Giỏ không được chứa khách sạn và vé máy bay nữa (R-DIR-04): dọn các mục thêm trước khi có luật này.
-- Chạy lại không xoá gì thêm vì Backend đã từ chối thêm hai loại này vào giỏ.
DELETE FROM app.cart_items ci
 USING cdp.products p
 WHERE p.product_id = ci.product_id AND p.taxonomy IN ('hotel', 'flight');
