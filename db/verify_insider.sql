-- psql "$INSIDER_DATABASE_URL" -f db/verify_insider.sql
\pset format unaligned
\pset tuples_only on
SELECT 'partners has vota: '          || CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END FROM partners WHERE partner_name='vota';
SELECT 'profiles = 2000: '            || CASE WHEN count(*) = 2000 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END FROM insider_profiles;
SELECT 'current identifiers = 6000: ' || CASE WHEN count(*) = 6000 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END FROM identifiers WHERE valid_to IS NULL;
SELECT 'no stale product_view in live_events: ' || CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
  FROM live_events WHERE event_name <> 'purchase' AND event_time < now() - interval '90 days';
SELECT 'channel_events ~10/profile: ' || CASE WHEN count(*) BETWEEN 14000 AND 26000 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END FROM channel_events;
SELECT 'gdpr opt-out has no channel events after opt-out: ' || CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL ('||count(*)||')' END
  FROM channel_events c JOIN insider_profiles p USING (profile_id)
  WHERE NOT p.gdpr_optin AND c.event_time > p.updated_at;
