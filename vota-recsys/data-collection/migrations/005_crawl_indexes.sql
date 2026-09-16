-- 005_crawl_indexes.sql — additive crawl-layer indexes and operational state.
-- Runs after 004. Nothing here touches 001/002 shapes.

-- =============================================================================
-- NULL quote_ctx duplicate targets
-- =============================================================================
-- spec section 4.1 has UNIQUE (source, url_hash, quote_ctx), and Postgres
-- treats NULLs as distinct by default. So every re-run of `discover` inserts a
-- duplicate row for every date-independent page (attractions, golf, combos) -
-- which then gets fetched again at 0.5 rps and inflates the product count.
--
-- Postgres 16 (the pinned image) has NULLS NOT DISTINCT, which fixes it with an
-- additive index and leaves the section 4.1 DDL untouched. This also gives
-- `ON CONFLICT (source, url_hash, quote_ctx)` the NULL-safe behaviour discover
-- needs.
CREATE UNIQUE INDEX IF NOT EXISTS crawl_targets_uniq_nulls_not_distinct
    ON crawl_targets (source, url_hash, quote_ctx) NULLS NOT DISTINCT;

-- Fast lookup of the page that produced a staging row, for `save-fixture` and
-- for report provenance.
CREATE INDEX IF NOT EXISTS products_staging_raw_page_idx
    ON products_staging (raw_page_id);
CREATE INDEX IF NOT EXISTS products_staging_source_version_idx
    ON products_staging (source, parser_version);

-- Orphan detection for `adopt-orphans`.
CREATE INDEX IF NOT EXISTS raw_pages_content_sha_idx
    ON raw_pages (content_sha256);
CREATE INDEX IF NOT EXISTS raw_pages_target_idx
    ON raw_pages (target_id);

-- =============================================================================
-- pg_trgm index for dedup (spec section 7)
-- =============================================================================
-- The similarity threshold is checked with similarity(), but only the `%`
-- operator (and `<->`) can use a trgm GIN index. dedup.py therefore uses `%`
-- to generate candidates and similarity() to score them.
CREATE INDEX IF NOT EXISTS products_normalised_name_trgm_idx
    ON products_normalised USING gin (name_normalized gin_trgm_ops);

-- =============================================================================
-- source_state — the blocked-source latch (spec sections 1, 9, 13)
-- =============================================================================
-- "Đụng anti-bot rồi cố vượt → Dừng, chuyển fallback."
--
-- A config comment is not enforcement: `fetch --retry-failed`, a cron, or a
-- shell wrapper will happily re-request a site that just served a CAPTCHA, and
-- that is mechanically indistinguishable from probing anti-bot. This table is
-- the durable latch. It is written in the same transaction that records the
-- hard stop, checked by every discover/fetch preflight, and cleared ONLY by
-- `cli unblock --source X --reason "<human sign-off>"` - never by a timer.
CREATE TABLE IF NOT EXISTS source_state (
    source          TEXT PRIMARY KEY,
    blocked_at      TIMESTAMPTZ,
    reason          JSONB       NOT NULL DEFAULT '{}',
    cleared_by      TEXT,
    cleared_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- description review ledger (spec sections 7, 13)
-- =============================================================================
-- "Trước khi tuyên bố Week 1 xong: đọc tay 20 mô tả ngẫu nhiên."
-- `sample-descriptions --mark` records that it happened, and `report --strict`
-- reads it back. Without a ledger this requirement is an intention, not a gate.
CREATE TABLE IF NOT EXISTS description_reviews (
    id              BIGSERIAL PRIMARY KEY,
    reviewed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_by     TEXT,
    product_ids     JSONB       NOT NULL DEFAULT '[]',
    sample_size     INT         NOT NULL,
    verdict         TEXT,                       -- ok|generic|truncated|mixed
    notes           TEXT,
    products_max_updated_at TIMESTAMPTZ         -- freshness anchor for the gate
);
