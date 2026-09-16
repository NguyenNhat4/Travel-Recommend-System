-- 002_cdp_clone.sql — CDP clone (spec section 4.2)
--
-- This mirrors V-OTA's CDP FIELD FOR FIELD. Reproduced verbatim from spec
-- section 4.2. The only deviation is explicit index names (see 001 for why).
--
-- DO NOT ADD ANYTHING HERE. Not a column, not a constraint, not a trigger.
-- Spec section 4.2 and section 13: "Chỗ nào không chắc thì hỏi, đừng tự đặt —
-- field không tồn tại ở upstream là cái bẫy cho người tích hợp sau này."
-- In particular there is deliberately NO UNIQUE on products.source_ref: load
-- idempotency is achieved through product_sources (source, source_ref) and a
-- deterministic product_id instead (see load.py).
--
-- Open questions about these fields live in
-- ../../docs/decisions/cdp-schema-questions.md. Every crawl-layer support
-- table this pipeline needs is in 004/005, never here.

CREATE TABLE products (
    product_id      UUID PRIMARY KEY,
    name            TEXT        NOT NULL,
    taxonomy        TEXT        NOT NULL CHECK (taxonomy IN
                    ('hotel','flight','combo','attraction','golf')),
    destination     TEXT        NOT NULL,
    description     TEXT,
    attributes      JSONB       NOT NULL DEFAULT '{}',
    unit_price      NUMERIC(14,2),
    currency        CHAR(3)     NOT NULL DEFAULT 'VND',
    available       BOOLEAN     NOT NULL DEFAULT true,
    available_from  DATE,
    available_to    DATE,
    image_url       TEXT,
    source_ref      TEXT        NOT NULL,
    -- cột hỗ trợ, không thuộc contract CDP:
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    images          JSONB       NOT NULL DEFAULT '[]',
    quality_score   REAL,                       -- section 7
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX products_taxonomy_destination_idx ON products (taxonomy, destination);
CREATE INDEX products_attributes_gin_idx       ON products USING gin (attributes);
CREATE INDEX products_name_trgm_idx            ON products USING gin (name gin_trgm_ops);

-- mapping dedup: nhiều bản ghi nguồn → 1 product
CREATE TABLE product_sources (
    product_id      UUID        REFERENCES products(product_id) ON DELETE CASCADE,
    source          TEXT        NOT NULL,
    source_ref      TEXT        NOT NULL,
    is_primary      BOOLEAN     NOT NULL DEFAULT false,
    match_score     REAL,
    PRIMARY KEY (source, source_ref)
);

CREATE TABLE profiles (
    cdp_user_id                 TEXT PRIMARY KEY,
    lifecycle_stage             TEXT,     -- new|active|dormant|churned
    days_since_last_booking     INT,
    lifetime_order_count        INT NOT NULL DEFAULT 0,
    vinclub_tier                TEXT,
    purchased_verticals         TEXT[],
    home_city                   TEXT,
    last_destination            TEXT,
    gdpr_optin                  BOOLEAN NOT NULL DEFAULT true,
    email_optin                 BOOLEAN NOT NULL DEFAULT true,
    sms_optin                   BOOLEAN NOT NULL DEFAULT true,
    push_optin                  BOOLEAN NOT NULL DEFAULT true,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE events (
    id              BIGSERIAL PRIMARY KEY,
    cdp_user_id     TEXT        NOT NULL REFERENCES profiles(cdp_user_id),
    event_name      TEXT        NOT NULL,  -- purchase|add_to_cart|product_view|search
    timestamp       TIMESTAMPTZ NOT NULL,
    product_id      UUID,                  -- cố tình KHÔNG có FK: phải có event trỏ vào product đã xoá
    taxonomy        TEXT,
    event_group_id  TEXT,                  -- gom 1 trip — Week 3 cần cột này
    quantity        INT,
    unit_price      NUMERIC(14,2),
    using_date      DATE,
    payload         JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX events_user_timestamp_idx  ON events (cdp_user_id, timestamp DESC);
CREATE INDEX events_event_group_id_idx  ON events (event_group_id);

-- demo only
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    cdp_user_id     TEXT NOT NULL REFERENCES profiles(cdp_user_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bookings (
    id              BIGSERIAL PRIMARY KEY,
    cdp_user_id     TEXT NOT NULL,
    event_group_id  TEXT NOT NULL,
    product_id      UUID NOT NULL,
    quantity        INT  NOT NULL DEFAULT 1,
    unit_price      NUMERIC(14,2),
    using_date      DATE,
    reference_no    TEXT UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
