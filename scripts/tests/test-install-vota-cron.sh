#!/usr/bin/env bash
# install-vota-cron.sh: only one crawler job (legacy daily.py or fresh_catalog.py) is ever scheduled, the default
# keeps the current CD behaviour, and unrelated crontab lines survive. Uses a temporary crontab file only.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
installer="$here/../install-vota-cron.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tab="$tmp/crontab"
runner=/opt/vota/bin/run_daily_docker.sh

fail() { echo "FAIL: $*" >&2; echo "--- crontab:" >&2; cat "$tab" >&2 || true; exit 1; }
blocks() { grep -c '^# BEGIN VOTA CRAWLER$' "$tab" || true; }

printf '%s\n' 'MAILTO=ops@example.test' '5 * * * * /usr/local/bin/other-job' > "$tab"

# 1. Default = legacy, exactly the line the current CD installs.
bash "$installer" --image registry/daily:latest --runner "$runner" --crontab-file "$tab" >/dev/null
expected="0 2 * * * IMAGE='registry/daily:latest' DATA_DIR='/srv/vota/daily-data' ENV_FILE='/etc/vota/daily.env' PULL=1 $runner run"
grep -qxF "$expected" "$tab" || fail "default line changed"
[ "$(blocks)" = 1 ] || fail "expected one managed block"

# 2. Switching to the fresh job replaces the legacy entry; unrelated lines are kept.
bash "$installer" --job fresh --image registry/fresh:latest --runner "$runner" --crontab-file "$tab" >/dev/null
expected="*/15 * * * * FRESH_IMAGE='registry/fresh:latest' FRESH_DATA_DIR='/srv/vota/fresh-catalog-data' CATALOG_ENV_FILE='/etc/vota/fresh-catalog.env' CATALOG_LOG_DIR='/srv/vota/fresh-catalog-logs' PULL=1 $runner fresh-run tick"
grep -qxF "$expected" "$tab" || fail "fresh line missing"
grep -q " run$" "$tab" && fail "legacy entry still scheduled"
[ "$(blocks)" = 1 ] || fail "expected one managed block after switch"
grep -qxF 'MAILTO=ops@example.test' "$tab" || fail "unrelated MAILTO lost"
grep -qxF '5 * * * * /usr/local/bin/other-job' "$tab" || fail "unrelated job lost"

# 3. Re-running is idempotent, and rolling back restores the legacy entry only.
bash "$installer" --job fresh --image registry/fresh:latest --runner "$runner" --crontab-file "$tab" >/dev/null
[ "$(grep -c 'fresh-run tick' "$tab")" = 1 ] || fail "fresh entry duplicated"
bash "$installer" --job legacy --image registry/daily:latest --runner "$runner" --crontab-file "$tab" >/dev/null
grep -q 'fresh-run tick' "$tab" && fail "fresh entry left after rollback"
grep -q " $runner run$" "$tab" || fail "legacy entry not restored"
[ "$(blocks)" = 1 ] || fail "expected one managed block after rollback"

# 4. Overrides and bad input.
out="$(bash "$installer" --job fresh --image r/f:latest --runner "$runner" --data-dir /data/f --env-file /etc/f.env \
  --log-dir /logs/f --schedule '*/5 * * * *' --crontab-file "$tab" --dry-run)"
grep -qF "*/5 * * * * FRESH_IMAGE='r/f:latest' FRESH_DATA_DIR='/data/f' CATALOG_ENV_FILE='/etc/f.env' CATALOG_LOG_DIR='/logs/f'" <<< "$out" \
  || fail "overrides not applied"
if bash "$installer" --job nightly --image r/x:latest --runner "$runner" --crontab-file "$tab" >/dev/null 2>&1; then
  fail "unknown --job accepted"
fi
if bash "$installer" --job fresh --image r/x:latest --runner "$runner" --log-dir relative --crontab-file "$tab" >/dev/null 2>&1; then
  fail "relative --log-dir accepted"
fi

echo "install-vota-cron checks passed"
