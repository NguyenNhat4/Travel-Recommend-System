-- =====================================================================
--  V-OTA · Database schema · PostgreSQL 16 + pgvector
--  Bản 20/09/2026 · đi kèm DATABASE_SCHEMA.md (nguồn DDL duy nhất của hệ thống V-OTA)
--
--  Database `vota`, ba schema:
--    cdp      : mirror CDP thật, field-for-field (handbook §6) — products · profiles · events.
--               CdpClient (role cdp_reader) chỉ được đọc schema này. Không thêm cột.
--    catalog  : dựng lại được từ cdp.products bất kỳ lúc nào — product_meta, combo_items, product_vectors.
--    app      : trạng thái của V-OTA, phải backup — users, carts, bookings, conversations, itineraries, logs.
--               Job batch (seed, embed, parse, eval, insider_activation) KHÔNG ghi nhật ký vào DB — kết quả ra file / report.
--  Insider clone là database RIÊNG (insider_schema.sql) — service khác, storage khác.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS cdp;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS app;

-- =====================================================================
--  SCHEMA cdp — mirror CDP thật
-- =====================================================================

-- cdp.products — CDP catalog, đúng 13 trường (chi tiết: PRODUCT_SCHEMA.md)
CREATE TABLE cdp.products (
    product_id      uuid PRIMARY KEY,               -- productId  (UUIDv5 sinh từ sourceRef)
    name            text NOT NULL,                  -- name
    taxonomy        text NOT NULL                   -- taxonomy
                    CHECK (taxonomy IN ('hotel','flight','attraction','combo','golf')),
    destination     text NOT NULL,                  -- destination (nhãn du lịch, không phải tỉnh)
    description     text NOT NULL,                  -- description (văn bản để embedding)
    attributes      jsonb NOT NULL DEFAULT '{}',    -- attributes (lossless; khoá thay đổi theo taxonomy — SCHEMA.md §3)
    unit_price      numeric(14,2),                  -- unitPrice  (NULL = điểm công cộng không bán vé)
    currency        char(3) NOT NULL DEFAULT 'VND', -- currency
    available       boolean NOT NULL,               -- available  (nguồn có trả giá lúc crawl, KHÔNG phải còn chỗ)
    available_from  date,                           -- availableFrom
    available_to    date,                           -- availableTo
    image_url       text,                           -- imageUrl
    source_ref      text NOT NULL UNIQUE,           -- sourceRef  '<nguồn>:<loại>:<id>'
    CONSTRAINT products_available_range CHECK (available_from IS NULL OR available_to IS NULL OR available_from <= available_to),
    CONSTRAINT products_id_taxonomy_uq UNIQUE (product_id, taxonomy)   -- khoá phụ cho FK "đúng loại"
);
CREATE INDEX products_taxonomy_idx    ON cdp.products (taxonomy);
CREATE INDEX products_destination_idx ON cdp.products (destination, taxonomy);
CREATE INDEX products_available_idx   ON cdp.products (available) WHERE available;
CREATE INDEX products_attributes_gin  ON cdp.products USING gin (attributes jsonb_path_ops);
CREATE INDEX products_level_idx       ON cdp.products ((attributes->>'level'));
CREATE INDEX products_parent_idx      ON cdp.products ((attributes->>'parentProductId'));
CREATE INDEX products_province_idx    ON cdp.products ((attributes->>'province'));
CREATE INDEX products_star_idx        ON cdp.products (((attributes->>'starRating')::numeric)) WHERE taxonomy = 'hotel';

-- cdp.profiles — CDP Profile Store (handbook §6). Tên cột opt-in cần người biết CDP xác nhận (handbook §17.3).
CREATE TABLE cdp.profiles (
    cdp_user_id              text PRIMARY KEY,      -- 'VP0092381'
    lifecycle_stage          text NOT NULL DEFAULT 'new'
                             CHECK (lifecycle_stage IN ('new','active','dormant','churned')),
    days_since_last_booking  integer CHECK (days_since_last_booking >= 0),   -- NULL = chưa từng đặt
    lifetime_order_count     integer NOT NULL DEFAULT 0 CHECK (lifetime_order_count >= 0),
    vinclub_tier             text CHECK (vinclub_tier IN ('Member','Gold','Platinum','Diamond')),
    purchased_verticals      text[] NOT NULL DEFAULT '{}',                    -- taxonomy đã từng mua
    home_city                text,
    last_destination         text,
    email_optin              boolean NOT NULL DEFAULT true,                   -- "opt-in states" — tên cột chờ xác nhận
    sms_optin                boolean NOT NULL DEFAULT true,
    push_optin               boolean NOT NULL DEFAULT true,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX profiles_stage_idx ON cdp.profiles (lifecycle_stage);

-- cdp.events — CDP Event Store (handbook §6 UserEvent). KHÔNG FK sang products: CDP thật không có,
-- và "event trỏ tới sản phẩm đã xoá" là cạnh lộn xộn phải mô phỏng được.
CREATE TABLE cdp.events (
    event_id        bigserial PRIMARY KEY,
    cdp_user_id     text NOT NULL REFERENCES cdp.profiles (cdp_user_id),       -- cdpUserId
    event_name      text NOT NULL                                              -- eventName
                    CHECK (event_name IN ('purchase','add_to_cart','product_view','search')),
    "timestamp"     timestamptz NOT NULL,                                      -- timestamp
    product_id      uuid,                                                      -- productId (NULL với search)
    taxonomy        text CHECK (taxonomy IN ('hotel','flight','attraction','combo','golf')),  -- taxonomy
    event_group_id  text,                                                      -- eventGroupId — một chuyến
    quantity        integer CHECK (quantity > 0),                              -- quantity
    unit_price      numeric(14,2),                                             -- unitPrice
    using_date      date,                                                      -- usingDate
    CONSTRAINT events_product_required CHECK (event_name = 'search' OR product_id IS NOT NULL)
);
CREATE INDEX events_user_time_idx  ON cdp.events (cdp_user_id, "timestamp" DESC);
CREATE INDEX events_group_idx      ON cdp.events (event_group_id);
CREATE INDEX events_product_idx    ON cdp.events (product_id);
CREATE INDEX events_name_time_idx  ON cdp.events (event_name, "timestamp" DESC);

-- =====================================================================
--  SCHEMA catalog — dựng lại được từ cdp.products
-- =====================================================================

-- catalog.product_meta — VIEW 1:1, nơi duy nhất định nghĩa variant / is_bookable / is_search_unit / is_recommendable.
--   Quy tắc điền cdp.products.available_from/to (một nghĩa cho mọi loại): ngày sớm nhất và muộn nhất khách được chọn usingDate.
--   Lịch kín/trống 30 ngày (đọc-only, do crawler/mock điền) ở attributes.availability {from, days, calendar "1/0"...}.
CREATE VIEW catalog.product_meta AS
SELECT
    p.product_id,
    p.taxonomy,
    CASE p.taxonomy
        WHEN 'hotel'  THEN 'hotel_'  || COALESCE(p.attributes->>'level', 'property')
        WHEN 'flight' THEN CASE WHEN p.attributes->>'level' = 'route' THEN 'flight_route' ELSE 'flight' END
        ELSE p.taxonomy
    END                                                        AS variant,
    (COALESCE(p.attributes->>'level', '') NOT IN ('property', 'route')
     AND COALESCE((p.attributes->>'ticketed')::boolean, true)
     AND p.unit_price IS NOT NULL)                              AS is_bookable,
    (COALESCE(p.attributes->>'level', '') NOT IN ('room', 'flight')) AS is_search_unit,
    -- được gợi ý: search unit và (tự đặt được, hoặc có ít nhất một con đặt được).
    -- 243 property không có hạng phòng → false: vẫn search ra, chỉ hiển thị, không vào /recommendations (availability precision ≥ 95%).
    (COALESCE(p.attributes->>'level', '') NOT IN ('room', 'flight')
     AND (
        (COALESCE(p.attributes->>'level', '') NOT IN ('property', 'route')
         AND COALESCE((p.attributes->>'ticketed')::boolean, true) AND p.unit_price IS NOT NULL)
        OR EXISTS (SELECT 1 FROM cdp.products c
                   WHERE c.attributes->>'parentProductId' = p.product_id::text
                     AND c.available AND c.unit_price IS NOT NULL)
     ))                                                         AS is_recommendable,
    NULLIF(p.attributes->>'parentProductId', '')::uuid          AS parent_product_id,
    (p.attributes->>'latitude')::double precision               AS latitude,
    (p.attributes->>'longitude')::double precision              AS longitude,
    p.attributes->>'locationPrecision'                          AS location_precision,
    p.attributes->>'province'                                   AS province,
    p.attributes->>'city'                                       AS city,
    p.attributes->>'brand'                                      AS brand,
    (p.attributes->>'starRating')::numeric                      AS star_rating,
    (p.attributes->>'reviewScore')::numeric                     AS review_score,
    (p.attributes->>'reviewCount')::integer                     AS review_count,
    (p.attributes->>'descriptionSource') IS NOT NULL            AS description_is_derived
FROM cdp.products p;

CREATE VIEW catalog.product_parents AS
SELECT product_id, parent_product_id FROM catalog.product_meta WHERE parent_product_id IS NOT NULL;

-- catalog.combo_items — thành phần combo, parse từ description (nguồn đã chốt 18/09)
CREATE TABLE catalog.combo_items (
    combo_product_id  uuid NOT NULL,
    combo_taxonomy    text GENERATED ALWAYS AS ('combo') STORED,     -- FK ép combo_product_id phải là combo
    position          smallint NOT NULL,
    label             text NOT NULL,                                 -- nhãn hiển thị, lấy từ đoạn text đã parse
    item_kind         text NOT NULL
                      CHECK (item_kind IN ('hotel','flight','attraction','golf','meal','transfer','other')),
    item_product_id   uuid REFERENCES cdp.products (product_id),     -- NULL khi chưa map được sang sản phẩm
    quantity          numeric(6,2) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit              text NOT NULL DEFAULT 'suất'
                      CHECK (unit IN ('đêm','vé','khách','suất','lượt')),
    is_optional       boolean NOT NULL DEFAULT false,
    source            text NOT NULL DEFAULT 'description_parse'      -- parse tự động · sửa tay · API (sau này)
                      CHECK (source IN ('description_parse','manual','api')),
    confidence        numeric(3,2) CHECK (confidence BETWEEN 0 AND 1), -- độ tin của bước map sang product
    evidence          text,                                          -- đoạn description đã khớp, để soát tay
    PRIMARY KEY (combo_product_id, position),
    CONSTRAINT combo_items_combo_fk FOREIGN KEY (combo_product_id, combo_taxonomy)
        REFERENCES cdp.products (product_id, taxonomy) ON DELETE CASCADE,
    CONSTRAINT combo_items_kind_fk  FOREIGN KEY (item_product_id, item_kind)
        REFERENCES cdp.products (product_id, taxonomy),
    CONSTRAINT combo_items_not_self CHECK (item_product_id IS DISTINCT FROM combo_product_id)
);
CREATE INDEX combo_items_item_idx ON catalog.combo_items (item_product_id) WHERE item_product_id IS NOT NULL;
CREATE INDEX combo_items_review_idx ON catalog.combo_items (confidence) WHERE item_product_id IS NULL OR confidence < 0.8;

-- catalog.product_vectors — chỉ search unit; D chốt Tuần 2
CREATE TABLE catalog.product_vectors (
    product_id     uuid PRIMARY KEY REFERENCES cdp.products (product_id) ON DELETE CASCADE,
    embedding      vector(768) NOT NULL,
    model_version  text NOT NULL,
    embed_text     text NOT NULL,
    text_hash      text NOT NULL,
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX product_vectors_hnsw ON catalog.product_vectors USING hnsw (embedding vector_cosine_ops);

CREATE VIEW catalog.search_rows AS
SELECT p.product_id, p.name, p.taxonomy, m.variant, m.is_bookable, m.is_search_unit, m.is_recommendable,
       p.destination, p.unit_price, p.currency, p.available, p.available_from, p.available_to, p.image_url,
       m.latitude, m.longitude, m.province, m.star_rating, m.review_score, m.review_count
FROM   cdp.products p JOIN catalog.product_meta m USING (product_id);

-- =====================================================================
--  SCHEMA app — trạng thái của V-OTA (BE · FE · agent)
-- =====================================================================

-- app.users — demo only (handbook §6, §8): email + BCrypt, mỗi user ↔ một cdp_user_id
CREATE TABLE app.users (
    user_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email          text NOT NULL UNIQUE,
    password_hash  text NOT NULL,                                     -- BCrypt
    display_name   text NOT NULL,
    cdp_user_id    text NOT NULL UNIQUE REFERENCES cdp.profiles (cdp_user_id),
    persona        text CHECK (persona IN ('P1_frequent','P2_first_time','P3_dormant','P4_no_history')),  -- tài khoản seed cho demo
    created_at     timestamptz NOT NULL DEFAULT now(),
    last_login_at  timestamptz
);

-- app.carts / app.cart_items — giỏ phía server, một giỏ đang mở / user (UX spec D6)
CREATE TABLE app.carts (
    cart_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cdp_user_id  text NOT NULL UNIQUE REFERENCES cdp.profiles (cdp_user_id),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app.cart_items (
    cart_item_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cart_id              uuid NOT NULL REFERENCES app.carts (cart_id) ON DELETE CASCADE,
    product_id           uuid NOT NULL REFERENCES cdp.products (product_id),
    quantity             integer NOT NULL CHECK (quantity > 0),
    using_date           date NOT NULL,                                -- ngày sử dụng / nhận phòng (UserEvent.usingDate)
    using_date_to        date,                                         -- trả phòng (hotel); NULL với vé, chuyến
    unit_price_snapshot  numeric(14,2) NOT NULL,                       -- giá lúc thêm; checkout so lại với products
    added_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT cart_items_dates CHECK (using_date_to IS NULL OR using_date_to > using_date),
    CONSTRAINT cart_items_uq UNIQUE (cart_id, product_id, using_date)
);

-- app.bookings / app.booking_items — demo only (handbook §6, §10). Một checkout = một booking = một event_group_id.
--   CDP KHÔNG có bảng booking: với CDP, một lần đặt chỗ chỉ là các event 'purchase' cùng event_group_id.
--   Bảng này giữ phần CDP không giữ (mã tham chiếu, liên hệ, snapshot dòng hàng) cho Web hiển thị.
--   Nối sang cdp.events bằng event_group_id (trường CDP thật có) — KHÔNG FK tới events.event_id (id nội bộ của clone,
--   CDP production không có). Chiều phụ thuộc: app → cdp; cdp không bao giờ trỏ về app.
CREATE TABLE app.bookings (
    booking_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_code   text NOT NULL UNIQUE,                             -- 'VOTA-20261015-8K3F'
    cdp_user_id      text NOT NULL REFERENCES cdp.profiles (cdp_user_id),
    event_group_id   text NOT NULL UNIQUE,                             -- = eventGroupId của các event purchase ghi ra
    status           text NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed','cancelled')),
    contact_name     text NOT NULL,
    contact_email    text NOT NULL,
    contact_phone    text NOT NULL,
    special_request  text,
    total_amount     numeric(14,2) NOT NULL CHECK (total_amount >= 0),
    currency         char(3) NOT NULL DEFAULT 'VND',
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX bookings_user_idx ON app.bookings (cdp_user_id, created_at DESC);

CREATE TABLE app.booking_items (
    booking_item_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id       uuid NOT NULL REFERENCES app.bookings (booking_id) ON DELETE CASCADE,
    product_id       uuid NOT NULL REFERENCES cdp.products (product_id),   -- RESTRICT: không xoá sản phẩm đã có booking
    taxonomy         text NOT NULL,                                        -- copy lúc đặt (products có thể đổi)
    product_name     text NOT NULL,                                        -- snapshot tên
    unit_price       numeric(14,2) NOT NULL,
    quantity         integer NOT NULL CHECK (quantity > 0),
    using_date       date NOT NULL,
    using_date_to    date,
    guest_names      text[],                                               -- tên khách nhận phòng / hành khách
    line_total       numeric(14,2) GENERATED ALWAYS AS (unit_price * quantity) STORED,
    -- event purchase tương ứng: cdp.events WHERE event_group_id = bookings.event_group_id
    --                                          AND product_id = booking_items.product_id AND using_date = booking_items.using_date
    CONSTRAINT booking_items_dates CHECK (using_date_to IS NULL OR using_date_to > using_date),
    CONSTRAINT booking_items_uq UNIQUE (booking_id, product_id, using_date)   -- khớp 1:1 với event purchase
);
CREATE INDEX booking_items_booking_idx ON app.booking_items (booking_id);

-- app.conversations / conversation_messages / itineraries — trợ lý lịch trình (handbook §9, ARCHITECTURE §8)
CREATE TABLE app.conversations (
    conversation_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cdp_user_id      text REFERENCES cdp.profiles (cdp_user_id),           -- NULL = khách vãng lai
    intent           jsonb NOT NULL DEFAULT '{}',                          -- {destination, days, party, interests, startDate} đã chuẩn hoá
    status           text NOT NULL DEFAULT 'open' CHECK (status IN ('open','planned','expired')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    last_message_at  timestamptz NOT NULL DEFAULT now(),
    expires_at       timestamptz NOT NULL DEFAULT now() + interval '24 hours'   -- TTL 24h
);
CREATE INDEX conversations_user_idx    ON app.conversations (cdp_user_id, created_at DESC);
CREATE INDEX conversations_expires_idx ON app.conversations (expires_at);

CREATE TABLE app.conversation_messages (
    message_id       bigserial PRIMARY KEY,
    conversation_id  uuid NOT NULL REFERENCES app.conversations (conversation_id) ON DELETE CASCADE,
    role             text NOT NULL CHECK (role IN ('user','assistant','system')),
    content          text NOT NULL,
    payload          jsonb,                                                -- thẻ hỏi lại, thẻ tóm tắt kế hoạch, chip gợi ý
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX conversation_messages_conv_idx ON app.conversation_messages (conversation_id, message_id);

CREATE TABLE app.itineraries (
    itinerary_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  uuid NOT NULL REFERENCES app.conversations (conversation_id) ON DELETE CASCADE,
    message_id       bigint REFERENCES app.conversation_messages (message_id),
    intent           jsonb NOT NULL,                                        -- ý định dùng để tạo bản này
    plan             jsonb NOT NULL,                                        -- ItineraryResponse (UX spec §6.4): stay, days[], slots[]
    product_ids      uuid[] NOT NULL DEFAULT '{}',                          -- mọi productId trong plan — kiểm tra grounding
    total_amount     numeric(14,2),
    model_version    text NOT NULL,                                         -- LLM + embedding đã dùng
    fallback         boolean NOT NULL DEFAULT false,                        -- true = LLM lỗi, chỉ có searchResults
    latency_ms       integer,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX itineraries_conv_idx ON app.itineraries (conversation_id, created_at DESC);

-- app.recommendation_logs — mỗi lần gọi /recommendations (debug `because`, eval, batch đẩy Insider Tuần 5)
CREATE TABLE app.recommendation_logs (
    log_id           bigserial PRIMARY KEY,
    cdp_user_id      text NOT NULL REFERENCES cdp.profiles (cdp_user_id),
    generated_at     timestamptz NOT NULL DEFAULT now(),
    trigger          text NOT NULL CHECK (trigger IN ('home','detail','cart','confirmation','chat','batch')),
    model_version    text NOT NULL,
    strategy         text NOT NULL,                                         -- cross_vertical · popular · dormant · …
    next_vertical    text,
    destination      text,
    k                smallint NOT NULL,
    recommendations  jsonb NOT NULL,                                        -- [{rank, productId, score, because[]}]
    diagnostics      jsonb NOT NULL,                                        -- {eventsUsed, coldStart, excludedVerticals, latencyMs}
    latency_ms       integer
);
CREATE INDEX recommendation_logs_user_idx ON app.recommendation_logs (cdp_user_id, generated_at DESC);

-- app.search_logs — câu truy vấn thật (UserEvent 'search' của CDP không có chỗ cho query text).
--   Không nối bằng id với cdp.events; khi cần, ghép theo (cdp_user_id, created_at) — event 'search' ghi cùng thời điểm.
CREATE TABLE app.search_logs (
    search_id           bigserial PRIMARY KEY,
    cdp_user_id         text REFERENCES cdp.profiles (cdp_user_id),        -- NULL = khách vãng lai
    session_id          text,
    query               text NOT NULL,
    filters             jsonb,                                              -- {taxonomy, destination, priceMin, priceMax, stars}
    result_product_ids  uuid[] NOT NULL DEFAULT '{}',
    result_count        integer NOT NULL,
    model_version       text NOT NULL,
    latency_ms          integer,
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX search_logs_user_idx ON app.search_logs (cdp_user_id, created_at DESC);

-- =====================================================================
--  Quyền — ranh giới "CdpClient là cửa duy nhất vào CDP" (handbook §6) ép bằng role, không bằng database riêng.
--    cdp_reader : đọc cdp.* — dùng cho job/eval chỉ đọc.
--    cdp_writer : LocalCdpClient của backend dùng MỘT connection riêng (CDP_DATABASE_URL) với role này:
--                 đọc cdp.*, ghi events (INSERT; DELETE chỉ để bù trừ theo event_group_id khi commit booking lỗi),
--                 cập nhật profiles. KHÔNG có USAGE trên catalog/app → không JOIN được sang bảng riêng của V-OTA.
--    vota_app   : backend/agent qua DATABASE_URL — toàn quyền catalog + app; trên cdp CHỈ SELECT cdp.products
--                 (catalog.* dựng từ nó, FK của booking_items/cart_items trỏ tới nó). Không ghi cdp.*, không đọc events/profiles.
--    Loader/seed chạy bằng superuser (postgres) — ngoài các role này.
--  Lên production: HttpCdpClient thay LocalCdpClient; cdp.products vẫn là bảng local do job sync ghi qua CdpClient;
--  cdp.events/profiles không còn dùng — code ngoài CdpClient chưa bao giờ chạm chúng nên không phải sửa.
-- =====================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cdp_reader') THEN CREATE ROLE cdp_reader NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cdp_writer') THEN CREATE ROLE cdp_writer NOLOGIN IN ROLE cdp_reader; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vota_app')   THEN CREATE ROLE vota_app   NOLOGIN; END IF;
END $$;
GRANT USAGE  ON SCHEMA cdp TO cdp_reader, vota_app;
GRANT SELECT ON ALL TABLES IN SCHEMA cdp TO cdp_reader;
GRANT INSERT, DELETE ON cdp.events   TO cdp_writer;
GRANT INSERT, UPDATE ON cdp.profiles TO cdp_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA cdp TO cdp_writer;
GRANT SELECT ON cdp.products TO vota_app;
GRANT USAGE  ON SCHEMA catalog, app TO vota_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA catalog, app TO vota_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO vota_app;
-- cdp_reader/cdp_writer KHÔNG có USAGE trên catalog/app; vota_app KHÔNG có quyền gì trên cdp.events/cdp.profiles.
-- Login role cho .env (tạo ngoài file này, ví dụ db/init/03_roles_dev.sql):
--   CREATE ROLE vota_app_login LOGIN PASSWORD '…' IN ROLE vota_app;  CREATE ROLE cdp_client_login LOGIN PASSWORD '…' IN ROLE cdp_writer;
