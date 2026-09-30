#!/usr/bin/env bash
# Deploy the fresh crawler and queue a full crawl without stopping active jobs.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${FRESH_IMAGE:?set the immutable fresh crawler image}"
: "${FRESH_CRON_IMAGE:?set the fresh crawler :latest image}"
RUNNER="${RUNNER:-/opt/vota/bin/run_daily_docker.sh}"
FRESH_DATA_DIR="${FRESH_DATA_DIR:-/srv/vota/fresh-catalog-data}"
CATALOG_ENV_FILE="${CATALOG_ENV_FILE:-/etc/vota/fresh-catalog.env}"
CATALOG_LOG_DIR="${CATALOG_LOG_DIR:-/srv/vota/fresh-catalog-logs}"
FRESH_NETWORK="${FRESH_NETWORK:-host}"
[[ "$FRESH_IMAGE" =~ ^[a-zA-Z0-9._/:@-]+$ && "$FRESH_CRON_IMAGE" =~ ^[a-zA-Z0-9._/-]+:latest$ ]] || exit 2
for path in "$RUNNER" "$FRESH_DATA_DIR" "$CATALOG_ENV_FILE" "$CATALOG_LOG_DIR"; do
  [[ "$path" =~ ^/[a-zA-Z0-9._/-]+$ ]] || { echo 'Paths must be absolute without shell metacharacters' >&2; exit 2; }
done
[[ -x "$RUNNER" && -d "$FRESH_DATA_DIR" && -r "$CATALOG_ENV_FILE" ]] || {
  echo 'Fresh runner, data directory and env file must already exist on the VM' >&2; exit 2;
}
mkdir -p "$CATALOG_LOG_DIR"
docker pull "$FRESH_IMAGE"
# Insert-only release fares: keep any newer existing quote. No secret in argv/output.
docker run --rm --network "$FRESH_NETWORK" --env-file "$CATALOG_ENV_FILE" \
  --entrypoint python "$FRESH_IMAGE" -m src.data_collection.seed.release_flights
bash "$here/install-vota-cron.sh" --job fresh --image "$FRESH_CRON_IMAGE" --runner "$RUNNER" \
  --data-dir "$FRESH_DATA_DIR" --env-file "$CATALOG_ENV_FILE" --log-dir "$CATALOG_LOG_DIR"
# The host runner consumes this token only after a successful full run. If a
# previous job is busy, the cron tick retains and processes the request later.
exec 9>"$CATALOG_LOG_DIR/deploy-request.lock"
flock -x 9
pending="$(mktemp "$CATALOG_LOG_DIR/.deploy-pending.XXXXXX")"
trap 'rm -f "$pending"' EXIT
printf '%s\n' "$FRESH_IMAGE" > "$pending"
chmod 0644 "$pending"
mv "$pending" "$CATALOG_LOG_DIR/deploy-pending"
flock -u 9
exec 9>&-
log="$CATALOG_LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S)-$$.log"
nohup env FRESH_IMAGE="$FRESH_IMAGE" FRESH_DATA_DIR="$FRESH_DATA_DIR" CATALOG_ENV_FILE="$CATALOG_ENV_FILE" \
  CATALOG_LOG_DIR="$CATALOG_LOG_DIR" FRESH_NETWORK="$FRESH_NETWORK" PULL=0 \
  "$RUNNER" fresh-run full > "$log" 2>&1 < /dev/null &
# Queueing is asynchronous: this does not claim the multi-hour crawl completed.
echo "Fresh full crawl requested; progress: $log; active jobs/monitor retained."
