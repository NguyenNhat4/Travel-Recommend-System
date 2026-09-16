-- 003_pgvector.sql — DEFERRED. DO NOT RUN IN WEEK 1.
--
-- Spec section 4.3: "chạy sau khi chốt model ở Week 2" and
-- "**Dimension nằm trong schema.** Đổi model sau = re-index toàn bộ.
--  Không chạy migration này trong Week 1."
--
-- The vector dimension below is a placeholder that encodes an unmade decision:
-- 768 = intfloat/multilingual-e5-base, 384 = paraphrase-multilingual-MiniLM-L12.
-- Applying this file now freezes that choice before Week 2 has benchmarked it.
--
-- The migration runner keeps this file in DEFERRED and refuses to apply it
-- without --force-deferred. tests/test_migrations.py asserts that after a full
-- `cli migrate` on a fresh container, `SELECT 1 FROM pg_extension WHERE
-- extname='vector'` returns no rows.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE product_vectors (
    product_id      UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
    model_version   TEXT NOT NULL,
    embedding       vector(768),   -- 768 = multilingual-e5-base; 384 nếu chọn MiniLM-L12
    indexed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
