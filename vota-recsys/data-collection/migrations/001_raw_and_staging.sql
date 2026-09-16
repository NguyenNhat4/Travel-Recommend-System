-- 001_raw_and_staging.sql — crawl layer (spec section 4.1)
--
-- This file reproduces spec section 4.1 field for field. The ONLY deviations
-- are listed here, and none of them change a column, a type or a constraint:
--   * indexes are given explicit names (the spec writes `CREATE INDEX ON t (...)`
--     and lets Postgres auto-name them). Named indexes are referenced by
--     005_crawl_indexes.sql and make `\d crawl_targets` readable at 6pm.
--   * `IF NOT EXISTS` on the extension only, exactly as the spec has it.
--
-- Do not add columns or constraints here. If something is missing, it goes in
-- 004/005 as an additive crawl-layer migration.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE crawl_runs (
    id              UUID PRIMARY KEY,
    source          TEXT        NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'running',  -- running|done|failed
    stats           JSONB       NOT NULL DEFAULT '{}'
);

-- hàng đợi resumable: discover ghi vào đây, fetch tiêu thụ
CREATE TABLE crawl_targets (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT        NOT NULL,
    url             TEXT        NOT NULL,
    url_hash        TEXT        NOT NULL,
    page_type       TEXT        NOT NULL,       -- list|detail|price|room
    quote_ctx       TEXT,                       -- NULL với trang không phụ thuộc ngày
    status          TEXT        NOT NULL DEFAULT 'pending', -- pending|fetched|parsed|failed|skipped
    attempts        INT         NOT NULL DEFAULT 0,
    last_error      TEXT,
    priority        INT         NOT NULL DEFAULT 100,
    discovered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, url_hash, quote_ctx)
);
CREATE INDEX crawl_targets_source_status_priority_idx
    ON crawl_targets (source, status, priority);

CREATE TABLE raw_pages (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID        REFERENCES crawl_runs(id),
    target_id       BIGINT      REFERENCES crawl_targets(id),
    source          TEXT        NOT NULL,
    url             TEXT        NOT NULL,
    http_status     INT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_path    TEXT        NOT NULL,       -- data/raw/... (.html.gz | .json.gz)
    content_sha256  TEXT        NOT NULL,
    content_type    TEXT,
    quote_ctx       TEXT,
    meta            JSONB       NOT NULL DEFAULT '{}'
);
CREATE INDEX raw_pages_source_fetched_at_idx ON raw_pages (source, fetched_at);

-- 1 row / (source, source_ref) — output của parse, chưa normalize
CREATE TABLE products_staging (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT        NOT NULL,
    source_ref      TEXT        NOT NULL,       -- 'vinpearl:VPNT-DLX-OCV'
    raw_page_id     BIGINT      REFERENCES raw_pages(id),
    parser_version  TEXT        NOT NULL,
    payload         JSONB       NOT NULL,       -- field thô, tên field giữ như nguồn
    parsed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_ref, parser_version)
);
