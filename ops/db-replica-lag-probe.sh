#!/usr/bin/env bash
# Run on the REPLICA VM every minute (cron/systemd timer). Emits one JSON line to
# /var/log/vota/pg-replica.jsonl; Ops Agent ships it to Cloud Logging, and the
# log-based metrics in infra/monitoring turn status != ok into an alert.
# status: ok | lagging (replay behind by > LAG_THRESHOLD_SECONDS) | broken (not streaming / not in recovery)
set -Eeuo pipefail

CONTAINER_NAME=${CONTAINER_NAME:-vota-postgres}
LAG_THRESHOLD_SECONDS=${LAG_THRESHOLD_SECONDS:-60}
OUT=${OUT:-/var/log/vota/pg-replica.jsonl}

[[ "$LAG_THRESHOLD_SECONDS" =~ ^[0-9]+$ ]] || { echo 'LAG_THRESHOLD_SECONDS must be numeric' >&2; exit 2; }

# lag is 0 when everything received is already replayed, so an idle primary is not reported as lag.
row=$(docker exec "$CONTAINER_NAME" psql -X -U postgres -Atqc "
  SELECT pg_is_in_recovery()::text || '|' ||
         (SELECT count(*) FROM pg_stat_wal_receiver WHERE status = 'streaming')::text || '|' ||
         CASE WHEN pg_last_wal_receive_lsn() IS NOT DISTINCT FROM pg_last_wal_replay_lsn() THEN 0
              ELSE coalesce(extract(epoch FROM now() - pg_last_xact_replay_timestamp()), 0)::int END::text" 2>/dev/null || true)

in_recovery=false; streaming=0; lag=0
if [[ "$row" =~ ^(true|false)\|([0-9]+)\|([0-9]+)$ ]]; then
  in_recovery=${BASH_REMATCH[1]}; streaming=${BASH_REMATCH[2]}; lag=${BASH_REMATCH[3]}
  if [[ "$in_recovery" != true || "$streaming" -lt 1 ]]; then status=broken
  elif (( lag > LAG_THRESHOLD_SECONDS )); then status=lagging
  else status=ok; fi
else
  status=broken
fi

printf '{"event":"pg_replica","probe":"pg-replica","status":"%s","in_recovery":%s,"streaming":%s,"lag_seconds":%s}\n' \
  "$status" "$in_recovery" "$streaming" "$lag" >> "$OUT"
