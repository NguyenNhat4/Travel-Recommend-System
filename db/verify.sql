-- Kiểm tra sau khi seed catalog hiện hành: psql "$SEED_DATABASE_URL" -f db/verify.sql → mọi dòng phải PASS
\pset format unaligned
\pset tuples_only on
SELECT 'products = 10320: '           || CASE WHEN count(*) = 10320 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END FROM cdp.products;
SELECT 'profiles = 2000: '            || CASE WHEN count(*) = 2000 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END FROM cdp.profiles;
SELECT 'events 6000-8000: '           || CASE WHEN count(*) BETWEEN 6000 AND 8000 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END FROM cdp.events;
SELECT 'combo_items >= 93: '          || CASE WHEN count(*) >= 93 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END FROM catalog.combo_items;
SELECT 'every combo has items: '      || CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL ('||count(*)||' combo trống)' END
  FROM cdp.products p WHERE taxonomy='combo' AND NOT EXISTS (SELECT 1 FROM catalog.combo_items c WHERE c.combo_product_id = p.product_id);
SELECT 'purchase without group <= 4%: ' || CASE WHEN 100.0*count(*) FILTER (WHERE event_group_id IS NULL)/NULLIF(count(*),0) <= 4 THEN 'PASS' ELSE 'FAIL' END
  FROM cdp.events WHERE event_name='purchase';
SELECT 'one destination per trip (<=1% bad): ' || CASE WHEN 100.0*count(*) FILTER (WHERE n > 1)/NULLIF(count(*),0) <= 1 THEN 'PASS' ELSE 'FAIL' END
  FROM (SELECT e.event_group_id, count(DISTINCT p.destination) n FROM cdp.events e JOIN cdp.products p USING (product_id)
        WHERE e.event_group_id IS NOT NULL GROUP BY 1) t;
SELECT 'stage distribution: '         || CASE WHEN abs(100.0*count(*) FILTER (WHERE lifecycle_stage='active')/NULLIF(count(*),0) - 45) <= 5
                                             AND abs(100.0*count(*) FILTER (WHERE lifecycle_stage='dormant')/NULLIF(count(*),0) - 20) <= 5 THEN 'PASS' ELSE 'FAIL' END FROM cdp.profiles;
SELECT 'max events per user <= 15: ' || CASE WHEN coalesce(max(n),0) <= 15 THEN 'PASS' ELSE 'FAIL ('||max(n)||')' END FROM (SELECT count(*) n FROM cdp.events GROUP BY cdp_user_id) t;
SELECT 'is_recommendable properties >= 300: ' || CASE WHEN count(*) >= 300 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END
  FROM catalog.product_meta WHERE variant='hotel_property' AND is_recommendable;
SELECT 'window = 30 days: '           || CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END
  FROM cdp.products WHERE available AND (available_to - available_from) > 29;
SELECT 'room calendars 30 chars: '    || CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END
  FROM cdp.products WHERE attributes->>'level'='room' AND length(attributes#>>'{availability,calendar}') IS DISTINCT FROM 30;
SELECT 'future purchases inside window: ' || CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END
  FROM cdp.events e JOIN cdp.products p USING (product_id)
  WHERE e.event_name='purchase' AND e.using_date > current_date AND (e.using_date < p.available_from OR e.using_date > p.available_to);
SELECT 'P1 booking <-> event: '       || CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END
  FROM app.bookings b JOIN cdp.events e ON e.event_group_id = b.event_group_id AND e.event_name='purchase' WHERE b.cdp_user_id='VP0000001';
SELECT 'persona users = 4: '          || CASE WHEN count(*) = 4 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END FROM app.users WHERE persona IS NOT NULL;
SELECT 'P4 has no events: '           || CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM cdp.events WHERE cdp_user_id='VP0000004';
