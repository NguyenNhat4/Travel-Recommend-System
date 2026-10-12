-- Sản phẩm thành phần combo mô phỏng và phần giá combo (docs/prd/data-model.md §3.1, chốt 09/10/2026,
-- đề xuất update-archive/2026-10-09-mo-phong-thanh-phan-combo-va-ve-phu-ngay.md).
-- 1. catalog.product_meta: attributes.comboOnly = true → is_search_unit = false, is_recommendable = false (chỉ đặt qua combo).
-- 2. catalog.combo_items.price_share: phần giá combo của thành phần có sản phẩm; tổng = giá combo (dịch vụ đi kèm: NULL).
-- Idempotent: CREATE OR REPLACE VIEW giữ nguyên cột và quyền; ADD COLUMN IF NOT EXISTS.
CREATE OR REPLACE VIEW catalog.product_meta AS
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
    -- comboOnly: sản phẩm thành phần combo mô phỏng (PRD data-model §3.1, chốt 09/10/2026) — chỉ đặt qua combo, không tìm/gợi ý.
    (COALESCE(p.attributes->>'level', '') NOT IN ('room', 'flight')
     AND NOT COALESCE((p.attributes->>'comboOnly')::boolean, false)) AS is_search_unit,
    -- được gợi ý: search unit và (tự đặt được, hoặc có ít nhất một con đặt được).
    -- 243 property không có hạng phòng → false: vẫn search ra, chỉ hiển thị, không vào /recommendations (availability precision ≥ 95%).
    (COALESCE(p.attributes->>'level', '') NOT IN ('room', 'flight')
     AND NOT COALESCE((p.attributes->>'comboOnly')::boolean, false)
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

ALTER TABLE catalog.combo_items ADD COLUMN IF NOT EXISTS price_share numeric(14,2) CHECK (price_share >= 0);
