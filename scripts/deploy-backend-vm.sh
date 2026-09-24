#!/usr/bin/env bash
# Deploy only the Backend service on an already-running application VM.
# PostgreSQL lives on a separate VM and is reached through a local SSH tunnel.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
backend_image=''
crawler_image=''
compose_file=''
backend_service='backend'
backend_health_url='http://127.0.0.1:8000/health'
db_tunnel_host='127.0.0.1'
db_tunnel_port='15432'
cron_runner='/opt/vota/bin/run_daily_docker.sh'
cron_data_dir='/srv/vota/daily-data'
cron_env_file='/etc/vota/daily.env'
cron_schedule='0 2 * * *'
cron_crontab_file=''
health_timeout_seconds='900'
health_interval_seconds='5'
dry_run=0

usage() {
  cat <<'EOF'
Usage:
  deploy-backend-vm.sh --backend-image IMAGE:latest
                       --crawler-image IMAGE:latest
                       --compose-file /absolute/path/compose.yml
                       [--backend-service backend]
                       [--backend-health-url http://127.0.0.1:8000/health]
                       [--db-tunnel-host 127.0.0.1] [--db-tunnel-port 15432]
                       [--cron-runner /opt/vota/bin/run_daily_docker.sh]
                       [--cron-data-dir /srv/vota/daily-data]
                       [--cron-env-file /etc/vota/daily.env]
                       [--cron-schedule '0 2 * * *']
                       [--cron-crontab-file PATH]
                       [--health-timeout SECONDS] [--health-interval SECONDS]
                       [--dry-run]
EOF
}

die() {
  printf 'deploy-backend-vm.sh: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --backend-image) [ "$#" -ge 2 ] || die '--backend-image requires a value'; backend_image="$2"; shift 2 ;;
    --crawler-image) [ "$#" -ge 2 ] || die '--crawler-image requires a value'; crawler_image="$2"; shift 2 ;;
    --compose-file) [ "$#" -ge 2 ] || die '--compose-file requires a value'; compose_file="$2"; shift 2 ;;
    --backend-service) [ "$#" -ge 2 ] || die '--backend-service requires a value'; backend_service="$2"; shift 2 ;;
    --backend-health-url) [ "$#" -ge 2 ] || die '--backend-health-url requires a value'; backend_health_url="$2"; shift 2 ;;
    --db-tunnel-host) [ "$#" -ge 2 ] || die '--db-tunnel-host requires a value'; db_tunnel_host="$2"; shift 2 ;;
    --db-tunnel-port) [ "$#" -ge 2 ] || die '--db-tunnel-port requires a value'; db_tunnel_port="$2"; shift 2 ;;
    --cron-runner) [ "$#" -ge 2 ] || die '--cron-runner requires a value'; cron_runner="$2"; shift 2 ;;
    --cron-data-dir) [ "$#" -ge 2 ] || die '--cron-data-dir requires a value'; cron_data_dir="$2"; shift 2 ;;
    --cron-env-file) [ "$#" -ge 2 ] || die '--cron-env-file requires a value'; cron_env_file="$2"; shift 2 ;;
    --cron-schedule) [ "$#" -ge 2 ] || die '--cron-schedule requires a value'; cron_schedule="$2"; shift 2 ;;
    --cron-crontab-file) [ "$#" -ge 2 ] || die '--cron-crontab-file requires a value'; cron_crontab_file="$2"; shift 2 ;;
    --health-timeout) [ "$#" -ge 2 ] || die '--health-timeout requires a value'; health_timeout_seconds="$2"; shift 2 ;;
    --health-interval) [ "$#" -ge 2 ] || die '--health-interval requires a value'; health_interval_seconds="$2"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[ -n "$backend_image" ] || die '--backend-image is required'
[ -n "$crawler_image" ] || die '--crawler-image is required'
[ -n "$compose_file" ] || die '--compose-file is required'
[[ "$backend_image" =~ :latest$ ]] || die 'Backend image must use the :latest tag'
[[ "$crawler_image" =~ :latest$ ]] || die 'Crawler image must use the :latest tag'
[[ "$compose_file" == /* ]] || die '--compose-file must be an absolute path'
[[ "$cron_runner" == /* ]] || die '--cron-runner must be an absolute path'
[[ "$cron_data_dir" == /* ]] || die '--cron-data-dir must be an absolute path'
[[ "$cron_env_file" == /* ]] || die '--cron-env-file must be an absolute path'
[[ "$backend_service" =~ ^[a-zA-Z0-9_.-]+$ ]] || die 'invalid Backend service name'
[[ "$db_tunnel_host" == 127.0.0.1 || "$db_tunnel_host" == localhost ]] || die 'DB tunnel host must be loopback'
[[ "$db_tunnel_port" =~ ^[0-9]+$ ]] || die 'DB tunnel port must be numeric'
[[ "$health_timeout_seconds" =~ ^[0-9]+$ && "$health_interval_seconds" =~ ^[0-9]+$ ]] || die 'health timeouts must be numeric'
[ -f "$compose_file" ] || die "Compose file not found: $compose_file"
grep -Eq '^[[:space:]]+postgres([[:space:]]*:|[[:space:]]*$)' "$compose_file" && die 'application Compose file must not declare a postgres service'
command -v docker >/dev/null 2>&1 || die 'docker is required'
command -v curl >/dev/null 2>&1 || die 'curl is required'
[ -x "$script_dir/check-db-tunnel.sh" ] || die 'check-db-tunnel.sh is missing or not executable'
[ -x "$script_dir/install-vota-cron.sh" ] || die 'install-vota-cron.sh is missing or not executable'

"$script_dir/check-db-tunnel.sh" --host "$db_tunnel_host" --port "$db_tunnel_port"

override_file=''
rollback_file=''
cleanup() {
  [ -z "$override_file" ] || rm -f "$override_file"
  [ -z "$rollback_file" ] || rm -f "$rollback_file"
}
trap cleanup EXIT

if [ "$dry_run" -eq 1 ]; then
  printf 'DRY-RUN: docker pull %s\n' "$crawler_image"
  printf 'DRY-RUN: docker compose -f %s -f backend-override.yml pull %s\n' "$compose_file" "$backend_service"
  printf 'DRY-RUN: docker compose -f %s -f backend-override.yml up -d --no-deps %s\n' "$compose_file" "$backend_service"
  printf 'DRY-RUN: curl --fail %s for up to %ss\n' "$backend_health_url" "$health_timeout_seconds"
  printf 'DRY-RUN: install cron for %s with %s\n' "$crawler_image" "$cron_runner"
  exit 0
fi

override_file="$(mktemp)"
cat > "$override_file" <<EOF
services:
  $backend_service:
    image: $backend_image
EOF

container_id="$(docker compose -f "$compose_file" -f "$override_file" ps -q "$backend_service" | head -n 1)"
[ -n "$container_id" ] || die "Backend service is not running: $backend_service"
previous_image="$(docker inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$container_id" | head -n 1)"
[ -n "$previous_image" ] || die 'could not capture the previous Backend image digest'
[[ "$previous_image" != *$'\n'* ]] || die 'previous Backend image contains a newline'

docker pull "$crawler_image"
docker compose -f "$compose_file" -f "$override_file" pull "$backend_service"
docker compose -f "$compose_file" -f "$override_file" up -d --force-recreate --no-deps "$backend_service"

wait_for_health() {
  local attempts=$((health_timeout_seconds / health_interval_seconds))
  [ "$attempts" -ge 1 ] || attempts=1
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl --silent --show-error --fail --max-time 10 "$backend_health_url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$health_interval_seconds"
  done
  return 1
}

if ! wait_for_health; then
  printf 'Backend health failed; restoring previous image.\n' >&2
  rollback_file="$(mktemp)"
  cat > "$rollback_file" <<EOF
services:
  $backend_service:
    image: $previous_image
EOF
  docker compose -f "$compose_file" -f "$rollback_file" up -d --force-recreate --no-deps "$backend_service" || die 'Backend rollback command failed'
  wait_for_health || die 'Backend rollback did not become healthy'
  die 'Backend deploy failed; previous image restored'
fi

install_cron() {
  "$script_dir/install-vota-cron.sh" \
    --image "$crawler_image" \
    --runner "$cron_runner" \
    --data-dir "$cron_data_dir" \
    --env-file "$cron_env_file" \
    --schedule "$cron_schedule" "$@"
}
if [ -n "$cron_crontab_file" ]; then
  install_cron --crontab-file "$cron_crontab_file"
else
  install_cron
fi
printf 'Backend deploy and crawler cron update completed.\n'
