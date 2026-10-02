#!/usr/bin/env bash
# Deploy only the Frontend service on the existing application VM.
set -euo pipefail

frontend_image=''
compose_file=''
frontend_service='frontend'
frontend_health_url='http://127.0.0.1:3000/'
bff_health_url='http://127.0.0.1:3000/api/v1/auth/me'
backend_health_url='http://127.0.0.1:8000/health/ready'
backend_env_file='/etc/vota/backend.env'
health_timeout_seconds='300'
health_interval_seconds='5'
dry_run=0

usage() {
  cat <<'EOF'
Usage:
  deploy-frontend-vm.sh --frontend-image IMAGE@sha256:DIGEST --compose-file /absolute/path/compose.yml
                        [--frontend-service frontend]
                        [--frontend-health-url http://127.0.0.1:3000/]
                        [--bff-health-url http://127.0.0.1:3000/api/v1/auth/me]
                        [--backend-health-url http://127.0.0.1:8000/health/ready]
                        [--backend-env-file /etc/vota/backend.env]
                        [--health-timeout SECONDS] [--health-interval SECONDS]
                        [--dry-run]
EOF
}

die() {
  printf 'deploy-frontend-vm.sh: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --frontend-image) [ "$#" -ge 2 ] || die '--frontend-image requires a value'; frontend_image="$2"; shift 2 ;;
    --compose-file) [ "$#" -ge 2 ] || die '--compose-file requires a value'; compose_file="$2"; shift 2 ;;
    --frontend-service) [ "$#" -ge 2 ] || die '--frontend-service requires a value'; frontend_service="$2"; shift 2 ;;
    --frontend-health-url) [ "$#" -ge 2 ] || die '--frontend-health-url requires a value'; frontend_health_url="$2"; shift 2 ;;
    --bff-health-url) [ "$#" -ge 2 ] || die '--bff-health-url requires a value'; bff_health_url="$2"; shift 2 ;;
    --backend-health-url) [ "$#" -ge 2 ] || die '--backend-health-url requires a value'; backend_health_url="$2"; shift 2 ;;
    --backend-env-file) [ "$#" -ge 2 ] || die '--backend-env-file requires a value'; backend_env_file="$2"; shift 2 ;;
    --health-timeout) [ "$#" -ge 2 ] || die '--health-timeout requires a value'; health_timeout_seconds="$2"; shift 2 ;;
    --health-interval) [ "$#" -ge 2 ] || die '--health-interval requires a value'; health_interval_seconds="$2"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[ -n "$frontend_image" ] || die '--frontend-image is required'
[ -n "$compose_file" ] || die '--compose-file is required'
[[ "$frontend_image" =~ ^asia-southeast1-docker\.pkg\.dev/[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die 'Frontend image must be pinned by Artifact Registry digest'
[[ "$compose_file" == /* ]] || die '--compose-file must be an absolute path'
[[ "$backend_env_file" == /* ]] || die '--backend-env-file must be an absolute path'
[[ "$frontend_service" =~ ^[a-zA-Z0-9_.-]+$ ]] || die 'invalid Frontend service name'
[[ "$frontend_health_url" =~ ^http://127\.0\.0\.1:[0-9]+/[a-zA-Z0-9._/%-]*$ ]] || die 'Frontend health URL must use loopback HTTP'
[[ "$bff_health_url" =~ ^http://127\.0\.0\.1:[0-9]+/[a-zA-Z0-9._/%-]*$ ]] || die 'BFF health URL must use loopback HTTP'
[[ "$backend_health_url" =~ ^http://127\.0\.0\.1:[0-9]+/[a-zA-Z0-9._/%-]*$ ]] || die 'Backend health URL must use loopback HTTP'
[[ "$health_timeout_seconds" =~ ^[1-9][0-9]*$ && "$health_interval_seconds" =~ ^[1-9][0-9]*$ ]] || die 'health timeout and interval must be positive integers'
[ -f "$compose_file" ] || die "Compose file not found: $compose_file"
grep -Eq "^[[:space:]]+$frontend_service([[:space:]]*:|[[:space:]]*$)" "$compose_file" || die 'Compose file does not declare the Frontend service'
grep -Fq 'AUTH_SERVICE_TOKEN:' "$compose_file" || die 'Compose file must pass AUTH_SERVICE_TOKEN to Frontend'
grep -Fq 'SESSION_REDIS_URL:' "$compose_file" || die 'Compose file must pass SESSION_REDIS_URL to Frontend'
command -v docker >/dev/null 2>&1 || die 'docker is required'
command -v curl >/dev/null 2>&1 || die 'curl is required'

if [ "$dry_run" -eq 0 ]; then
  [ "$(id -u)" -ne 0 ] || die 'deploy must run as the SSH user, not root'
  docker info >/dev/null 2>&1 || die 'SSH user cannot access the Docker daemon'

  has_readable_file() {
    [ -r "$1" ] 2>/dev/null || sudo -n test -r "$1" 2>/dev/null
  }
  has_readable_file "$backend_env_file" || die "Backend env file is not readable: $backend_env_file"

  read_backend_value() {
    local key="$1" line
    if [ -r "$backend_env_file" ]; then
      line="$(grep -m 1 -E "^${key}=" "$backend_env_file")" || die "Backend env is missing ${key}"
    else
      line="$(sudo -n grep -m 1 -E "^${key}=" "$backend_env_file")" || die "Backend env is missing ${key}"
    fi
    printf '%s' "${line#*=}"
  }

  AUTH_SERVICE_TOKEN="$(read_backend_value AUTH_SERVICE_TOKEN)"
  AUTH_REDIS_URL="$(read_backend_value AUTH_REDIS_URL)"
  [ -n "$AUTH_SERVICE_TOKEN" ] || die 'Backend AUTH_SERVICE_TOKEN is empty'
  [ -n "$AUTH_REDIS_URL" ] || die 'Backend AUTH_REDIS_URL is empty'
  export AUTH_SERVICE_TOKEN AUTH_REDIS_URL

  docker compose -f "$compose_file" config >/dev/null || die 'Frontend Compose configuration is invalid'
  curl --silent --show-error --fail --max-time 10 "$backend_health_url" >/dev/null || die 'Backend is not healthy on loopback'
fi

override_file=''
rollback_file=''
cleanup() {
  [ -z "$override_file" ] || rm -f "$override_file"
  [ -z "$rollback_file" ] || rm -f "$rollback_file"
}
trap cleanup EXIT

override_file="$(mktemp)"
cat > "$override_file" <<EOF
services:
  $frontend_service:
    image: $frontend_image
EOF

if [ "$dry_run" -eq 1 ]; then
  printf 'DRY-RUN: docker compose -f %s -f <frontend-override> pull %s\n' "$compose_file" "$frontend_service"
  printf 'DRY-RUN: docker compose -f %s -f <frontend-override> up -d --force-recreate --no-deps %s\n' "$compose_file" "$frontend_service"
  printf 'DRY-RUN: curl --fail %s for up to %ss\n' "$frontend_health_url" "$health_timeout_seconds"
  exit 0
fi

container_id="$(docker compose -f "$compose_file" ps -q "$frontend_service" | head -n 1)"
previous_image=''
if [ -n "$container_id" ]; then
  image_id="$(docker inspect --format '{{.Image}}' "$container_id")"
  [ -n "$image_id" ] || die 'could not capture the previous Frontend image ID'
  previous_image="$(docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$image_id" | head -n 1)"
  [ -n "$previous_image" ] || die 'could not capture the previous Frontend image digest'
  [[ "$previous_image" == *@sha256:* ]] || die 'previous Frontend image is not pinned by digest'
  [[ "$previous_image" != *$'\n'* ]] || die 'previous Frontend image contains a newline'
fi

docker compose -f "$compose_file" -f "$override_file" pull "$frontend_service"

wait_for_frontend() {
  local deadline=$((SECONDS + health_timeout_seconds))
  local remaining curl_timeout pause
  while :; do
    remaining=$((deadline - SECONDS))
    [ "$remaining" -gt 0 ] || return 1
    curl_timeout=10
    [ "$remaining" -ge 10 ] || curl_timeout="$remaining"
    if curl --silent --show-error --fail --max-time "$curl_timeout" "$frontend_health_url" >/dev/null 2>&1 && bff_is_reachable; then
      return 0
    fi
    remaining=$((deadline - SECONDS))
    [ "$remaining" -gt 0 ] || return 1
    pause="$health_interval_seconds"
    [ "$pause" -le "$remaining" ] || pause="$remaining"
    sleep "$pause"
  done
}

bff_is_reachable() {
  local status
  status="$(curl --silent --show-error --max-time 10 --output /dev/null --write-out '%{http_code}' "$bff_health_url")" || return 1
  [ "$status" = '200' ] || [ "$status" = '401' ]
}

rollback_frontend() {
  if [ -z "$previous_image" ]; then
    printf 'Removing unhealthy initial Frontend deployment.\n' >&2
    docker compose -f "$compose_file" -f "$override_file" rm -sf "$frontend_service" || die 'could not remove failed Frontend container'
    return 0
  fi
  printf 'Restoring previous Frontend image.\n' >&2
  rollback_file="$(mktemp)"
  cat > "$rollback_file" <<EOF
services:
  $frontend_service:
    image: $previous_image
EOF
  docker compose -f "$compose_file" -f "$rollback_file" up -d --force-recreate --no-deps "$frontend_service" || die 'Frontend rollback command failed'
  wait_for_frontend || die 'Frontend rollback did not become healthy'
}

if ! docker compose -f "$compose_file" -f "$override_file" up -d --force-recreate --no-deps "$frontend_service"; then
  rollback_frontend
  die 'Frontend recreate failed; previous image restored'
fi

if ! wait_for_frontend; then
  printf 'Frontend health failed.\n' >&2
  rollback_frontend
  die 'Frontend deploy failed; previous image restored'
fi

# Dọn image cũ của cùng repository để disk VM không đầy dần. Giữ image vừa deploy và image
# trước đó (để rollback tay); image đang được container dùng thì `docker rmi` tự từ chối.
# Chỉ đụng repository của Frontend, không đụng image của crawler hay service khác. Lỗi dọn không làm hỏng deploy.
prune_old_images() {
  local repo="${frontend_image%@*}" keep id
  keep="$(docker image inspect --format '{{.Id}}' "$frontend_image" ${previous_image:+"$previous_image"} 2>/dev/null || true)"
  docker image ls "$repo" --no-trunc --quiet | sort -u | while read -r id; do
    [ -n "$id" ] || continue
    printf '%s\n' "$keep" | grep -Fxq "$id" && continue
    docker rmi "$id" >/dev/null 2>&1 || true
  done
  docker image prune -f >/dev/null 2>&1 || true
}
prune_old_images || true

printf 'Frontend deploy completed.\n'
