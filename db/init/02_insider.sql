\connect insider
-- =====================================================================
--  Insider clone · database RIÊNG `insider` · PostgreSQL 16
--  Bản 20/09/2026 · đi kèm DATABASE_SCHEMA.md
--  Không có bảng nhật ký request: service ghi access log JSON lines ra file (logs/insider_requests.jsonl) — đủ để chứng minh luật 403 / 1.000 user / 5 MB.
--
--  Service mock của Insider (handbook §3): 4 endpoint + các luật "cắn" trong production.
--  Bảng theo đúng tên handbook §6: insider_profiles · insider_events · channel_events · identifiers.
--  Cố ý chỉ giữ TẬP CON của CDP và có TTL — lịch sử dài hạn nằm ở CDP, không ở đây.
--  Không có bảng nào của V-OTA / CDP trong database này.
-- =====================================================================

-- partners — xác thực header: X-PARTNER-NAME phải lowercase, X-REQUEST-TOKEN phải có; sai → 403
CREATE TABLE partners (
    partner_name   text PRIMARY KEY CHECK (partner_name = lower(partner_name)),
    request_token  text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- insider_profiles — bản sao của Insider, keyed theo profile nội bộ; attributes nhận qua POST /user/v1/upsert
CREATE TABLE insider_profiles (
    profile_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_name  text NOT NULL REFERENCES partners (partner_name),
    attributes    jsonb NOT NULL DEFAULT '{}',   -- custom attributes; array attribute APPEND mặc định, ghi đè khi not_append: true;
                                                -- "" hoặc null KHÔNG xoá attribute — lưu đúng giá trị rỗng
    gdpr_optin    boolean NOT NULL DEFAULT true, -- false = không nhận gì qua bất kỳ kênh nào (suppressed)
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX insider_profiles_attributes_gin ON insider_profiles USING gin (attributes jsonb_path_ops);

-- identifiers — map cdp_user_id / email / phone / uuid về một profile, CÓ LỊCH SỬ
--   PATCH /user/v1/identity: đóng dòng cũ (valid_to = now()), mở dòng mới cùng type; old/new phải cùng type (API kiểm tra).
CREATE TABLE identifiers (
    identifier_id  bigserial PRIMARY KEY,
    profile_id     uuid NOT NULL REFERENCES insider_profiles (profile_id) ON DELETE CASCADE,
    id_type        text NOT NULL CHECK (id_type IN ('cdp_user_id','email','phone','uuid')),
    id_value       text NOT NULL,
    valid_from     timestamptz NOT NULL DEFAULT now(),
    valid_to       timestamptz,                  -- NULL = đang hiệu lực
    CONSTRAINT identifiers_range CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE UNIQUE INDEX identifiers_current_uq ON identifiers (id_type, id_value) WHERE valid_to IS NULL;   -- một giá trị chỉ trỏ tới một profile tại một thời điểm
CREATE INDEX identifiers_profile_idx ON identifiers (profile_id, id_type) WHERE valid_to IS NULL;

-- insider_events — event nhận qua Upsert. TTL: purchase 730 ngày, custom event 90 ngày. Quá hạn = biến mất.
CREATE TABLE insider_events (
    event_id      bigserial PRIMARY KEY,
    profile_id    uuid NOT NULL REFERENCES insider_profiles (profile_id) ON DELETE CASCADE,
    event_name    text NOT NULL,                 -- 'purchase' · 'add_to_cart' · 'product_view' · custom…
    event_params  jsonb NOT NULL DEFAULT '{}',   -- product_id, taxonomy, unit_price, quantity, event_group_id…
    event_time    timestamptz NOT NULL,
    received_at   timestamptz NOT NULL DEFAULT now(),
    ttl_days      smallint GENERATED ALWAYS AS (CASE WHEN event_name = 'purchase' THEN 730 ELSE 90 END) STORED
);
CREATE INDEX insider_events_profile_idx ON insider_events (profile_id, event_time DESC);
CREATE INDEX insider_events_time_idx    ON insider_events (event_time);
-- Đọc luôn qua view này để luật TTL không bao giờ bị quên (event quá hạn coi như không tồn tại):
CREATE VIEW live_events AS
SELECT *, event_time + ttl_days * interval '1 day' AS expires_at
FROM   insider_events
WHERE  event_time + ttl_days * interval '1 day' > now();

-- channel_events — engagement theo kênh: SEED sẵn (email open/click/bounce/unsubscribe, push, sms); trả về qua POST /raw/v1/export
CREATE TABLE channel_events (
    channel_event_id  bigserial PRIMARY KEY,
    profile_id        uuid NOT NULL REFERENCES insider_profiles (profile_id) ON DELETE CASCADE,
    channel           text NOT NULL CHECK (channel IN ('email','push','sms')),
    event_type        text NOT NULL CHECK (event_type IN ('sent','delivered','open','click','bounce','unsubscribe')),
    campaign_id       text,
    event_time        timestamptz NOT NULL,
    metadata          jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX channel_events_time_idx    ON channel_events (event_time);
CREATE INDEX channel_events_profile_idx ON channel_events (profile_id, event_time DESC);
