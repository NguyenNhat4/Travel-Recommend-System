#!/usr/bin/env bash
# Deploy only the Backend service on an already-running application VM.
# PostgreSQL lives on a separate VM and is reached through a local SSH tunnel.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
backend_image=''
crawler_image=''
compose_file=''
backend_service='backend'
backend_health_url='http://127.0.0.1:8000/health/ready'
db_tunnel_host='127.0.0.1'
db_tunnel_port='15432'
cron_runner='/opt/vota/bin/run_daily_docker.sh'
cron_data_dir='/srv/vota/daily-data'
cron_env_file='/etc/vota/daily.env'
backend_env_file='/etc/vota/backend.env'
jwt_secrets_dir='/etc/vota/backend-secrets'
migrate_dsn_stdin=0
migrate_dsn=''
skip_migrate=0
cron_schedule='0 2 * * *'
cron_crontab_file=''
health_timeout_seconds='900'
health_interval_seconds='5'
dry_run=0

usage() {
  cat <<'EOF'
Usage:
  deploy-backend-vm.sh --backend-image IMAGE@sha256:DIGEST
                       --compose-file /absolute/path/compose.yml
                       [--backend-service backend]
                       [--backend-health-url http://127.0.0.1:8000/health/ready]
                       (--migrate-dsn-stdin | --skip-migrate)
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
    --migrate-dsn-stdin) migrate_dsn_stdin=1; shift ;;
    --skip-migrate) skip_migrate=1; shift ;;
    --dry-run) dry_run=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[ -n "$backend_image" ] || die '--backend-image is required'
[ -n "$compose_file" ] || die '--compose-file is required'
[[ "$backend_image" =~ ^asia-southeast1-docker\.pkg\.dev/[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die 'Backend image must be pinned by Artifact Registry digest'
if [ -n "$crawler_image" ]; then
  [[ "$crawler_image" =~ @sha256:[a-f0-9]{64}$ ]] || die 'Crawler image must be pinned by digest (IMAGE@sha256:DIGEST)'
fi
[[ "$backend_health_url" =~ ^https?://[a-zA-Z0-9.:-]+/health/ready$ ]] || die 'Backend health URL must target /health/ready'
[[ "$compose_file" == /* ]] || die '--compose-file must be an absolute path'
[[ "$cron_runner" == /* ]] || die '--cron-runner must be an absolute path'
[[ "$cron_data_dir" == /* ]] || die '--cron-data-dir must be an absolute path'
[[ "$cron_env_file" == /* ]] || die '--cron-env-file must be an absolute path'
if [ "$skip_migrate" -eq 0 ] && [ "$migrate_dsn_stdin" -eq 0 ] && [ "$dry_run" -eq 0 ]; then
  die 'pass --migrate-dsn-stdin (DSN on stdin) or --skip-migrate'
fi
[ "$skip_migrate" -eq 0 ] || [ "$migrate_dsn_stdin" -eq 0 ] || die '--skip-migrate and --migrate-dsn-stdin are mutually exclusive'
[[ "$backend_service" =~ ^[a-zA-Z0-9_.-]+$ ]] || die 'invalid Backend service name'
[[ "$db_tunnel_host" == 127.0.0.1 || "$db_tunnel_host" == localhost ]] || die 'DB tunnel host must be loopback'
[[ "$db_tunnel_port" =~ ^[0-9]+$ ]] || die 'DB tunnel port must be numeric'
[[ "$health_timeout_seconds" =~ ^[1-9][0-9]*$ && "$health_interval_seconds" =~ ^[1-9][0-9]*$ ]] || die 'health timeout and interval must be positive integers'
[ -f "$compose_file" ] || die "Compose file not found: $compose_file"
grep -Eq '^[[:space:]]+postgres([[:space:]]*:|[[:space:]]*$)' "$compose_file" && die 'application Compose file must not declare a postgres service'
command -v docker >/dev/null 2>&1 || die 'docker is required'
command -v curl >/dev/null 2>&1 || die 'curl is required'
[ -x "$script_dir/check-db-tunnel.sh" ] || die 'check-db-tunnel.sh is missing or not executable'
[ -x "$script_dir/install-vota-cron.sh" ] || die 'install-vota-cron.sh is missing or not executable'

# DSN của role có quyền tạo bảng đến từ Secret Manager qua stdin: không nằm trong argv, env file hay log. Đọc sớm, một lần,
# trước mọi lệnh docker để chúng không nuốt stdin.
if [ "$migrate_dsn_stdin" -eq 1 ] && [ "$dry_run" -eq 0 ]; then
  IFS= read -r migrate_dsn || true
  [[ "$migrate_dsn" =~ ^postgres(ql)?://[^[:space:]]+$ ]] || die 'stdin did not provide a postgresql:// DSN for migrations'
fi

if [ "$dry_run" -eq 0 ]; then
  [ "$(id -u)" -ne 0 ] || die 'deploy must run as the SSH user, not root (cron is per-user)'
  [ -r "$compose_file" ] || die "Compose file is not readable: $compose_file"
  docker info >/dev/null 2>&1 || die 'SSH user cannot access the Docker daemon'
  grep -Fq '/etc/vota/backend.env' "$compose_file" || die 'Compose file must load /etc/vota/backend.env'
  grep -Fq '/etc/vota/backend-secrets:/app/secrets:ro' "$compose_file" || die 'Compose file must mount the RS256 key directory read-only'

  has_readable_file() {
    [ -r "$1" ] 2>/dev/null || sudo -n test -r "$1" 2>/dev/null
  }

  has_nonempty_file() {
    [ -s "$1" ] 2>/dev/null || sudo -n test -s "$1" 2>/dev/null
  }

  env_has_key() {
    grep -Eq "^$1=" "$backend_env_file" 2>/dev/null || \
      sudo -n grep -Eq "^$1=" "$backend_env_file" 2>/dev/null
  }

  has_readable_file "$backend_env_file" || die "Backend env file is not readable: $backend_env_file"
  for required_key in DATABASE_URL CDP_DATABASE_URL JWT_PRIVATE_KEY_PATH JWT_PUBLIC_KEY_PATH AUTH_REDIS_URL; do
    env_has_key "$required_key" || die "Backend env is missing ${required_key}"
  done
  for key_file in jwt-private.pem jwt-public.pem; do
    has_nonempty_file "$jwt_secrets_dir/$key_file" || die "Missing backend key file: $jwt_secrets_dir/$key_file"
  done
  docker compose -f "$compose_file" config >/dev/null || die 'Backend Compose configuration is invalid'
fi

"$script_dir/check-db-tunnel.sh" --host "$db_tunnel_host" --port "$db_tunnel_port"

override_file=''
rollback_file=''
cleanup() {
  [ -z "$override_file" ] || rm -f "$override_file"
  [ -z "$rollback_file" ] || rm -f "$rollback_file"
}
trap cleanup EXIT

if [ "$dry_run" -eq 1 ]; then
  printf 'DRY-RUN: docker compose -f %s -f backend-override.yml pull %s\n' "$compose_file" "$backend_service"
  [ "$skip_migrate" -eq 1 ] || printf 'DRY-RUN: docker run --rm --network host -e SEED_DATABASE_URL %s python db/migrations/run.py\n' "$backend_image"
  printf 'DRY-RUN: docker compose -f %s -f backend-override.yml up -d --no-deps %s\n' "$compose_file" "$backend_service"
  printf 'DRY-RUN: curl --fail %s for up to %ss\n' "$backend_health_url" "$health_timeout_seconds"
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
image_id="$(docker inspect --format '{{.Image}}' "$container_id")"
[ -n "$image_id" ] || die 'could not capture the previous Backend image ID'
previous_image="$(docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$image_id" | head -n 1)"
[ -n "$previous_image" ] || die 'could not capture the previous Backend image digest'
[[ "$previous_image" == *@sha256:* ]] || die 'previous Backend image is not pinned by digest'
[[ "$previous_image" != *$'\n'* ]] || die 'previous Backend image contains a newline'

docker compose -f "$compose_file" -f "$override_file" pull "$backend_service"

# Migration chạy bằng chính image sắp deploy, TRƯỚC khi đụng tới container đang chạy. Lỗi ở đây dừng deploy; backend cũ vẫn
# chạy nguyên vẹn nên không cần rollback. Migration idempotent và chỉ thêm (backward-compatible) nên rollback image sau đó
# vẫn chạy được với schema mới.
if [ "$skip_migrate" -eq 0 ]; then
  printf 'Applying database migrations.\n'
  # `-e NAME` không kèm giá trị: Docker lấy từ môi trường của tiến trình này, DSN không xuất hiện trong `ps`.
  SEED_DATABASE_URL="$migrate_dsn" docker run --rm --network host -e SEED_DATABASE_URL "$backend_image" python db/migrations/run.py \
    || die 'Database migration failed; Backend was not changed'
fi

wait_for_health() {
  local deadline=$((SECONDS + health_timeout_seconds))
  local remaining curl_timeout pause
  while :; do
    remaining=$((deadline - SECONDS))
    [ "$remaining" -gt 0 ] || return 1
    curl_timeout=10
    [ "$remaining" -ge 10 ] || curl_timeout="$remaining"
    if curl --silent --show-error --fail --max-time "$curl_timeout" "$backend_health_url" >/dev/null 2>&1; then
      return 0
    fi
    remaining=$((deadline - SECONDS))
    [ "$remaining" -gt 0 ] || return 1
    pause="$health_interval_seconds"
    [ "$pause" -le "$remaining" ] || pause="$remaining"
    sleep "$pause"
  done
}

rollback_backend() {
  printf 'Restoring previous Backend image.\n' >&2
  rollback_file="$(mktemp)"
  cat > "$rollback_file" <<EOF
services:
  $backend_service:
    image: $previous_image
EOF
  docker compose -f "$compose_file" -f "$rollback_file" up -d --force-recreate --no-deps "$backend_service" || die 'Backend rollback command failed'
  wait_for_health || die 'Backend rollback did not become healthy'
}

if ! docker compose -f "$compose_file" -f "$override_file" up -d --force-recreate --no-deps "$backend_service"; then
  rollback_backend
  die 'Backend recreate failed; previous image restored'
fi

if ! wait_for_health; then
  printf 'Backend health failed.\n' >&2
  rollback_backend
  die 'Backend deploy failed; previous image restored'
fi

# Dọn image cũ của cùng repository để disk VM không đầy dần. Giữ image vừa deploy và image
# trước đó (để rollback tay); image đang được container dùng thì `docker rmi` tự từ chối.
# Chỉ đụng repository của Backend, không đụng image của crawler hay service khác. Lỗi dọn không làm hỏng deploy.
prune_old_images() {
  local repo="${backend_image%@*}" keep id
  keep="$(docker image inspect --format '{{.Id}}' "$backend_image" ${previous_image:+"$previous_image"} 2>/dev/null || true)"
  docker image ls "$repo" --no-trunc --quiet | sort -u | while read -r id; do
    [ -n "$id" ] || continue
    printf '%s\n' "$keep" | grep -Fxq "$id" && continue
    docker rmi "$id" >/dev/null 2>&1 || true
  done
}
prune_old_images || true

printf 'Backend deploy completed.\n'
