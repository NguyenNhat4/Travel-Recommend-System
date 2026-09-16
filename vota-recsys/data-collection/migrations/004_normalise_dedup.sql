-- 004_normalise_dedup.sql — CRAWL LAYER support tables.
--
-- NOT part of the CDP contract. Nothing here mirrors anything upstream; these
-- tables exist because `normalize`, `dedup` and `load` are separate,
-- independently re-runnable commands (spec section 2) and therefore need a
-- durable handoff between them. 001/002 are the spec's authoritative files and
-- are never edited; everything additive lives here and in 005.
--
-- When a future team swaps in the production CdpClient, these tables are
-- dropped. `products`, `product_sources`, `profiles`, `events`, `users`,
-- `bookings` are not.

-- =============================================================================
-- products_normalised — output of `normalize`, input to `dedup` and `load`
-- =============================================================================
-- One row per (source, source_ref) at the current normaliser/parser version.
-- This is also the single home for the spec section 5.3 dedup fields:
-- name_normalized, latitude/longitude, address, phone, star_rating, brand.
-- They are NOT added to `products` - section 5.3 calls them dedup support, and
-- section 4.2 is a field-for-field mirror.
CREATE TABLE products_normalised (
    id                  BIGSERIAL PRIMARY KEY,
    source              TEXT        NOT NULL,
    source_ref          TEXT        NOT NULL,
    staging_id          BIGINT      REFERENCES products_staging(id),
    parser_version      TEXT        NOT NULL,
    normaliser_version  TEXT        NOT NULL,

    -- grain: a vinpearl hotel page emits one 'property' row (the merge parent,
    -- not a sellable product) plus N 'room' rows that point at it. Without this
    -- distinction every hotel would also appear as a priceless product and
    -- duplicate against its own rooms.
    page_kind           TEXT        NOT NULL DEFAULT 'product',  -- product|property|room
    parent_source_ref   TEXT,

    -- projected onto products.* by load.py
    name                TEXT,
    taxonomy            TEXT,
    destination         TEXT        NOT NULL DEFAULT 'unknown',
    description         TEXT,
    attributes          JSONB       NOT NULL DEFAULT '{}',
    unit_price          NUMERIC(14,2),
    currency            CHAR(3)     NOT NULL DEFAULT 'VND',
    available           BOOLEAN     NOT NULL DEFAULT true,
    available_from      DATE,
    available_to        DATE,
    image_url           TEXT,
    images              JSONB       NOT NULL DEFAULT '[]',
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    quality_score       REAL,

    -- section 5.3 dedup support
    name_normalized     TEXT,
    address             TEXT,
    phone               TEXT,
    star_rating         REAL,
    brand               TEXT,

    -- provenance / debugging
    destination_raw     TEXT,
    dest_match_method   TEXT,        -- exact|alias|geo|none
    price_raw           TEXT,
    fx_rate_used        NUMERIC(14,6),
    quote_ctx           TEXT,        -- bare context name ('base') or NULL
    normalised_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (source, source_ref, normaliser_version)
);
CREATE INDEX products_normalised_dest_tax_idx  ON products_normalised (destination, taxonomy);
CREATE INDEX products_normalised_parent_idx    ON products_normalised (parent_source_ref);
CREATE INDEX products_normalised_page_kind_idx ON products_normalised (page_kind);

-- Rows normalize refused to emit, with the reason. A product that silently
-- disappears between staging and products is the hardest bug in this pipeline;
-- this table is how `report` explains the gap.
CREATE TABLE normalise_rejects (
    id                  BIGSERIAL PRIMARY KEY,
    source              TEXT        NOT NULL,
    source_ref          TEXT,
    staging_id          BIGINT,
    normaliser_version  TEXT        NOT NULL,
    reason              TEXT        NOT NULL,   -- no_name|no_taxonomy|no_destination|...
    detail              TEXT,
    payload_excerpt     JSONB       NOT NULL DEFAULT '{}',
    rejected_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX normalise_rejects_reason_idx ON normalise_rejects (reason);

-- =============================================================================
-- dedup (spec section 7)
-- =============================================================================
-- Candidate pairs with their score. Partitioned by dedup_version so two
-- thresholds can be compared without destroying the previous result.
CREATE TABLE dedup_pairs (
    dedup_version   TEXT        NOT NULL,
    a_source        TEXT        NOT NULL,
    a_ref           TEXT        NOT NULL,
    b_source        TEXT        NOT NULL,
    b_ref           TEXT        NOT NULL,
    destination     TEXT        NOT NULL,
    name_similarity REAL,
    distance_m      DOUBLE PRECISION,
    star_delta      REAL,
    brand_match     BOOLEAN,
    address_match   BOOLEAN,
    phone_match     BOOLEAN,
    match_score     REAL        NOT NULL,
    decision        TEXT        NOT NULL,   -- merge|review|reject
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dedup_version, a_source, a_ref, b_source, b_ref)
);
CREATE INDEX dedup_pairs_decision_idx ON dedup_pairs (dedup_version, decision);

-- One cluster = one future product. cluster_key = min(source_ref) over members,
-- produced by a union-find that unions by SMALLER ROOT KEY, so the key is
-- identical on every re-run regardless of the order edges arrive.
--
-- PK is (cluster_key, dedup_version), not cluster_key alone: with cluster_key
-- alone, `DELETE ... WHERE dedup_version = :dv` removes rows another version
-- still owns and the version column becomes decorative.
CREATE TABLE product_clusters (
    cluster_key     TEXT        NOT NULL,
    dedup_version   TEXT        NOT NULL,
    destination     TEXT        NOT NULL,
    taxonomy        TEXT        NOT NULL,
    grain           TEXT        NOT NULL DEFAULT 'product',
    member_count    INT         NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cluster_key, dedup_version)
);

CREATE TABLE product_cluster_members (
    cluster_key     TEXT        NOT NULL,
    dedup_version   TEXT        NOT NULL,
    source          TEXT        NOT NULL,
    source_ref      TEXT        NOT NULL,
    is_primary      BOOLEAN     NOT NULL DEFAULT false,
    match_score     REAL,
    PRIMARY KEY (dedup_version, source, source_ref),
    FOREIGN KEY (cluster_key, dedup_version)
        REFERENCES product_clusters(cluster_key, dedup_version) ON DELETE CASCADE
);
CREATE INDEX pcm_cluster_idx ON product_cluster_members (dedup_version, cluster_key);

-- Manual decisions from reading data/reports/dedup_review.csv. Survives a
-- dedup re-run: applied after scoring, before clustering.
CREATE TABLE dedup_overrides (
    a_source        TEXT        NOT NULL,
    a_ref           TEXT        NOT NULL,
    b_source        TEXT        NOT NULL,
    b_ref           TEXT        NOT NULL,
    decision        TEXT        NOT NULL CHECK (decision IN ('merge','reject')),
    reason          TEXT        NOT NULL,
    decided_by      TEXT,
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (a_source, a_ref, b_source, b_ref)
);

-- =============================================================================
-- load
-- =============================================================================
-- Keeps cluster_key OUT of `products` while still letting load be idempotent.
CREATE TABLE product_load_meta (
    product_id      UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
    cluster_key     TEXT        NOT NULL UNIQUE,
    dedup_version   TEXT        NOT NULL,
    meta            JSONB       NOT NULL DEFAULT '{}',
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Which source won which field, per product. This is what makes README
-- section 12 item 2 ("rule nguồn thắng field khi dedup") a generated table
-- rather than a hand-maintained claim.
CREATE TABLE product_merge_log (
    product_id      UUID        NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    field           TEXT        NOT NULL,
    winning_source  TEXT,
    winning_ref     TEXT,
    strategy        TEXT,
    dedup_version   TEXT        NOT NULL,
    PRIMARY KEY (product_id, field)
);

-- =============================================================================
-- helpers
-- =============================================================================
-- Haversine in metres. Named crawl_* so it is obviously ours and not a CDP
-- object. IMMUTABLE so it can be used in index expressions if ever needed.
CREATE OR REPLACE FUNCTION crawl_distance_m(
    lat1 DOUBLE PRECISION, lon1 DOUBLE PRECISION,
    lat2 DOUBLE PRECISION, lon2 DOUBLE PRECISION
) RETURNS DOUBLE PRECISION AS $$
    SELECT CASE
        WHEN lat1 IS NULL OR lon1 IS NULL OR lat2 IS NULL OR lon2 IS NULL THEN NULL
        ELSE 2 * 6371000 * asin(sqrt(
              power(sin(radians(lat2 - lat1) / 2), 2)
            + cos(radians(lat1)) * cos(radians(lat2))
            * power(sin(radians(lon2 - lon1) / 2), 2)
        ))
    END;
$$ LANGUAGE sql IMMUTABLE;

-- What the Friday demo is allowed to show (spec section 7: quality_score < 0.5
-- is not demo material). The 0.5 lives in config.quality.demo_threshold; this
-- view reads the value that `load` stamped into product_load_meta.meta so the
-- number is not duplicated as a SQL literal.
CREATE OR REPLACE VIEW products_demo AS
SELECT p.*
  FROM products p
  LEFT JOIN product_load_meta m USING (product_id)
 WHERE p.quality_score IS NOT NULL
   AND p.quality_score >= COALESCE((m.meta->>'demo_threshold')::real, 0.5)
   AND p.destination <> 'unknown';
