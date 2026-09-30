#!/usr/bin/env bash
# VM-free regression: fake Docker/crontab, real deploy helper + runner + installer.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/data" "$tmp/logs"
export FAKE_LOG="$tmp/docker.log" FAKE_TAB="$tmp/crontab"
cat > "$tmp/bin/docker" <<'DOCKER'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_LOG"
case "$1" in
  pull) exit "${FAKE_PULL_EXIT:-0}" ;;
  ps) if [[ "${FAKE_BUSY:-0}" = 1 ]]; then echo existing-job; fi ;;
  run)
    if [[ "$*" = *release_flights* ]]; then exit "${FAKE_IMPORT_EXIT:-0}"; fi
    if [ -n "${FAKE_NEXT_IMAGE:-}" ]; then printf '%s\n' "$FAKE_NEXT_IMAGE" > "$CATALOG_LOG_DIR/deploy-pending"; fi
    exit "${FAKE_RUN_EXIT:-0}" ;;
  stop|kill|restart|rm) echo 'must never interrupt a container' >&2; exit 99 ;;
esac
DOCKER
cat > "$tmp/bin/crontab" <<'CRON'
#!/usr/bin/env bash
if [[ "$1" = -l ]]; then cat "$FAKE_TAB" 2>/dev/null; else cp "$1" "$FAKE_TAB"; fi
CRON
chmod +x "$tmp/bin/"*
export PATH="$tmp/bin:$PATH"
export FRESH_IMAGE=registry/crawler-fresh:abc FRESH_CRON_IMAGE=registry/crawler-fresh:latest
export RUNNER="$repo/src/data_collection/run_daily_docker.sh" FRESH_DATA_DIR="$tmp/data"
export CATALOG_ENV_FILE="$tmp/fresh.env" CATALOG_LOG_DIR="$tmp/logs"
printf 'DB_TARGET=cloud\n' > "$CATALOG_ENV_FILE"
printf '5 * * * * unrelated-job\n' > "$FAKE_TAB"
fail() { echo "FAIL: $*" >&2; exit 1; }
wait_dispatch() {
  for _ in $(seq 1 100); do
    if grep -q 'fresh catalog' "$CATALOG_LOG_DIR"/deploy-*.log 2>/dev/null; then return; fi
    sleep 0.02
  done
  fail 'background dispatch did not finish'
}
# Busy job: deploy imports, queues, replaces only managed cron; no stop/restart.
export FAKE_BUSY=1
bash "$repo/scripts/deploy-crawler-vm.sh" >/dev/null
wait_dispatch
[[ "$(cat "$CATALOG_LOG_DIR/deploy-pending")" = "$FRESH_IMAGE" ]] || fail 'busy request lost'
grep -q -- '--filter name=\^vota-daily' "$FAKE_LOG" || fail 'legacy job not checked'
grep -q 'unrelated-job' "$FAKE_TAB" || fail 'unrelated cron lost'
grep -q 'fresh-run tick' "$FAKE_TAB" || fail 'fresh cron not installed'
# Next idle tick consumes the request as full, pinned to requested SHA.
export FAKE_BUSY=0 PULL=0
bash "$RUNNER" fresh-run tick >/dev/null
[[ ! -e "$CATALOG_LOG_DIR/deploy-pending" ]] || fail 'completed request not cleared'
grep -q 'registry/crawler-fresh:abc full$' "$FAKE_LOG" || fail 'tick did not request full with pinned image'
# Failure retains work for retry; a later deployment cannot be cleared by old work.
printf '%s\n' "$FRESH_IMAGE" > "$CATALOG_LOG_DIR/deploy-pending"
if FAKE_RUN_EXIT=3 bash "$RUNNER" fresh-run tick >/dev/null; then fail 'real failure hidden'; fi
[[ -f "$CATALOG_LOG_DIR/deploy-pending" ]] || fail 'failed request lost'
FAKE_NEXT_IMAGE=registry/crawler-fresh:def bash "$RUNNER" fresh-run tick >/dev/null
[[ "$(cat "$CATALOG_LOG_DIR/deploy-pending")" = registry/crawler-fresh:def ]] || fail 'newer request was cleared'
# Pull/import errors do not replace the current pending request or cron.
cp "$FAKE_TAB" "$tmp/expected-tab"
if FAKE_PULL_EXIT=1 bash "$repo/scripts/deploy-crawler-vm.sh" >/dev/null; then fail 'pull failure hidden'; fi
if FAKE_IMPORT_EXIT=1 bash "$repo/scripts/deploy-crawler-vm.sh" >/dev/null; then fail 'import failure hidden'; fi
cmp "$FAKE_TAB" "$tmp/expected-tab" || fail 'cron changed on failed deploy'
[[ "$(cat "$CATALOG_LOG_DIR/deploy-pending")" = registry/crawler-fresh:def ]] || fail 'pending changed on failed deploy'
if grep -Eq '^(stop|kill|restart|rm) ' "$FAKE_LOG"; then fail 'destructive Docker command'; fi
# No busy job: deployment starts full immediately, without waiting for cron.
rm -f "$CATALOG_LOG_DIR"/deploy-*.log
bash "$repo/scripts/deploy-crawler-vm.sh" >/dev/null
wait_dispatch
[[ ! -e "$CATALOG_LOG_DIR/deploy-pending" ]] || fail 'idle deployment did not run full'
echo 'crawler deploy checks passed'
