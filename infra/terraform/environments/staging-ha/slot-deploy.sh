#!/usr/bin/env bash
# Cập nhật image app trên MỘT VM mà không làm gián đoạn: chạy bản mới (slot) song song bản cũ, đợi bản mới
# /health/ready, đổi proxy cục bộ sang bản mới, rồi rút bản cũ sau khi drain. Nếu bản mới không sẵn sàng thì
# bản cũ không bị đụng tới.
#
# Dùng ở hai nơi:
#   - startup.sh.tftpl (mode `boot`): VM mới hoặc khởi động lại dựng infra, proxy và một slot theo image trong template.
#   - scripts/roll-staging-ha-app-slots.sh (mode `deploy`, qua IAP SSH): đổi image trên VM đang chạy.
#
# Bố cục trên VM (network_mode: host cho mọi container):
#   vota-proxy (nginx) :3000  ->  frontend của slot đang hoạt động  ->  backend cùng slot
#   slot blue : frontend :3001, backend :8001      slot green: frontend :3002, backend :8002
#   vota-pgbouncer :6432 dùng chung. VM dựng theo kiểu cũ (một stack ở 3000/8000, không proxy) gọi là `legacy`
#   và được chuyển sang slot ở lần deploy đầu tiên (xem migrate_from_legacy).
#
# Biến môi trường:
#   BACKEND_IMAGE, FRONTEND_IMAGE  image@sha256:... (bắt buộc ở mode boot và deploy)
#   DRAIN_SECONDS (110) READY_TIMEOUT (600) READY_STREAK (3) MIN_AVAILABLE_MB (2200) PROXY_IMAGE
# /etc/vota/slot.env (chỉ có trên VM dựng từ template mới) cung cấp BACKEND_ENV_SECRET và tham số uvicorn.
set -euo pipefail

MODE="${1:-}"
ETC=/etc/vota
PROXY_DIR="$ETC/proxy"
UPSTREAM="$PROXY_DIR/upstream.conf"
PROXY_IMAGE="${PROXY_IMAGE:-nginx:1.27-alpine}"
DRAIN_SECONDS="${DRAIN_SECONDS:-110}"
READY_TIMEOUT="${READY_TIMEOUT:-600}"
READY_STREAK="${READY_STREAK:-3}"
MIN_AVAILABLE_MB="${MIN_AVAILABLE_MB:-2200}"

log() { printf '[slot] %s\n' "$*" >&2; }
die() { log "LỖI: $*"; exit 1; }

if [ -f "$ETC/slot.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ETC/slot.env"
  set +a
fi
export UVICORN_WORKERS="${UVICORN_WORKERS:-2}"
export UVICORN_GRACEFUL_SECONDS="${UVICORN_GRACEFUL_SECONDS:-100}"
export BACKEND_STOP_GRACE="${BACKEND_STOP_GRACE:-110}"

acquire_lock() { # hai lần chạy trên cùng VM (vd. Backend CD và Frontend CD chồng nhau) phải tuần tự
  exec 9> /var/lock/vota-slot-deploy.lock
  flock -w 1800 9 || die "không lấy được khoá slot-deploy sau 30 phút"
}

slot_ports() { # $1 = blue|green -> đặt BACKEND_PORT và FRONTEND_PORT
  case "$1" in
    blue) BACKEND_PORT=8001; FRONTEND_PORT=3001 ;;
    green) BACKEND_PORT=8002; FRONTEND_PORT=3002 ;;
    *) die "slot không hợp lệ: $1" ;;
  esac
  export BACKEND_PORT FRONTEND_PORT
}
other_slot() { if [ "$1" = blue ]; then echo green; else echo blue; fi; }
running() { docker ps --format '{{.Names}}' | grep -qx "$1"; }

# ---------------------------------------------------------------------------------------------------------------
# Cấu hình trên đĩa: compose của slot, compose hạ tầng (pgbouncer), cấu hình nginx. Ghi đè mỗi lần chạy.
# ---------------------------------------------------------------------------------------------------------------
write_files() {
  mkdir -p "$PROXY_DIR"
  cat > "$ETC/compose.infra.yml" <<'INFRACOMPOSE'
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"

services:
  # Gom kết nối Postgres của các worker backend. DATABASE_URL/CDP_DATABASE_URL trỏ 127.0.0.1:6432.
  pgbouncer:
    container_name: vota-pgbouncer
    image: edoburu/pgbouncer@sha256:9c78945868a6a142c7fc40ccd843bbe5a606df163c7ffce4de70e0d628d696a2
    restart: unless-stopped
    logging: *default-logging
    network_mode: host
    volumes:
      - /etc/vota/pgbouncer:/etc/pgbouncer:ro
    mem_limit: 128m
    cpus: 0.25
    healthcheck:
      test: ["CMD-SHELL", "nc -z 127.0.0.1 6432"]
      interval: 10s
      timeout: 3s
      retries: 3
INFRACOMPOSE

  cat > "$ETC/compose.slot.yml" <<'SLOTCOMPOSE'
# Một slot của VM app (backend + frontend). Chạy bằng `docker compose -p vota-<slot>` với SLOT, BACKEND_PORT,
# FRONTEND_PORT, BACKEND_IMAGE, FRONTEND_IMAGE. Host networking: frontend gọi backend ở 127.0.0.1:${BACKEND_PORT}.
# Redis, Postgres và Weaviate KHÔNG nằm ở đây: là dịch vụ dùng chung, truy cập qua env secret.
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"

services:
  backend:
    container_name: vota-backend-${SLOT}
    image: ${BACKEND_IMAGE}
    restart: unless-stopped
    logging: *default-logging
    network_mode: host
    command: ["python", "-m", "uvicorn", "src.backend.app.main:app", "--host", "0.0.0.0", "--port", "${BACKEND_PORT}", "--no-access-log"]
    env_file:
      - /etc/vota/backend.env
    volumes:
      - /etc/vota/secrets:/app/secrets:ro
    environment:
      UVICORN_WORKERS: ${UVICORN_WORKERS:-2}
      # Chờ SSE (90s) xong khi bị rút khỏi LB: bằng LB draining (100s), nhỏ hơn stop_grace_period bên dưới.
      UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN: ${UVICORN_GRACEFUL_SECONDS:-100}
      # URL gọi ngược chính backend phải theo port của slot (blue 8001, green 8002). Secret giữ port 8000 của kiểu cũ,
      # nên ghi đè ở đây: environment thắng env_file. Thêm URL loopback mới của backend thì khai báo ở đây, không sửa secret.
      ITINERARY_SERVICE_BASE_URL: http://127.0.0.1:${BACKEND_PORT}
      ASSISTANT_API_BASE_URL: http://127.0.0.1:${BACKEND_PORT}/api/v1
      # Nhiều bản sao sau LB: chỉ nhận traffic khi RecSys đã nạp, và từ chối Weaviate/Redis loopback.
      READY_REQUIRES_RECSYS: "true"
      REQUIRE_SHARED_BACKENDS: "true"
      # Chỉ readiness (LB) thăm dò DB; liveness cho autohealing cố ý không phụ thuộc DB.
      READY_REQUIRES_DB: "true"
      # Mọi VM cùng mất DB thì giữ lại (catalog/search không cần DB); một VM mất DB một mình vẫn bị loại.
      READY_DB_OUTAGE_KEEPS_READY: "true"
    mem_limit: 3g
    cpus: 1.5
    stop_grace_period: ${BACKEND_STOP_GRACE:-110}s
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:${BACKEND_PORT}/health/ready', timeout=3).status == 200 else 1)"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 60s

  frontend:
    container_name: vota-frontend-${SLOT}
    image: ${FRONTEND_IMAGE}
    restart: unless-stopped
    logging: *default-logging
    network_mode: host
    env_file:
      - /etc/vota/frontend.env   # only AUTH_SERVICE_TOKEN and SESSION_REDIS_URL, never DB credentials
    environment:
      NODE_ENV: production
      APP_ENV: production
      HOSTNAME: 0.0.0.0
      PORT: ${FRONTEND_PORT}
      BACKEND_BASE_URL: http://127.0.0.1:${BACKEND_PORT}
    mem_limit: 768m
    cpus: 0.5
    stop_grace_period: ${BACKEND_STOP_GRACE:-110}s   # frontend proxy SSE, phải sống bằng backend
SLOTCOMPOSE

  # Proxy giữ cổng 3000 (LB và health check không đổi). Đổi upstream bằng `nginx -s reload`: worker cũ giữ kết nối
  # đang chạy (kể cả SSE) tới khi xong hoặc hết worker_shutdown_timeout, worker mới nhận kết nối mới.
  cat > "$PROXY_DIR/nginx.conf" <<'NGINXCONF'
worker_processes 2;
pid /tmp/nginx.pid;
error_log /dev/stderr warn;
# Phải >= LB draining (100s) để SSE đang chạy qua worker cũ không bị cắt khi reload.
worker_shutdown_timeout 120s;

events {
  worker_connections 4096;
}

http {
  access_log off;
  client_max_body_size 50m;

  map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      '';
  }

  upstream vota_frontend {
    include /etc/vota/proxy/upstream.conf;
    keepalive 64;
  }

  server {
    listen 3000 default_server;

    location / {
      proxy_pass http://vota_frontend;
      proxy_http_version 1.1;
      proxy_set_header Connection $connection_upgrade;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Host $http_host;
      # SSE của trợ lý: không đệm, giữ kết nối dài.
      proxy_buffering off;
      proxy_request_buffering off;
      proxy_read_timeout 300s;
      proxy_send_timeout 300s;
    }
  }
}
NGINXCONF
}

# ---------------------------------------------------------------------------------------------------------------
# Docker, image, cấu hình bí mật
# ---------------------------------------------------------------------------------------------------------------
dc() { # docker compose chạy trong image docker:27-cli (Debian docker.io không có plugin compose)
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$ETC:$ETC" -w "$ETC" \
    -e SLOT -e BACKEND_PORT -e FRONTEND_PORT -e BACKEND_IMAGE -e FRONTEND_IMAGE \
    -e UVICORN_WORKERS -e UVICORN_GRACEFUL_SECONDS -e BACKEND_STOP_GRACE \
    docker:27-cli docker compose "$@"
}

registry_login() {
  local host token
  host="${BACKEND_IMAGE%%/*}"
  token=$(curl -fsS -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token | jq -er .access_token)
  printf '%s' "$token" | docker login -u oauth2accesstoken --password-stdin "$host" >/dev/null
}

pull_images() {
  registry_login
  docker pull "$BACKEND_IMAGE" >/dev/null
  docker pull "$FRONTEND_IMAGE" >/dev/null
  docker pull "$PROXY_IMAGE" >/dev/null
}

# Làm mới env từ Secret Manager. Chỉ chạy trên VM dựng từ template mới (có slot.env); VM kiểu cũ giữ nguyên env hiện có.
refresh_config() {
  [ -n "${BACKEND_ENV_SECRET:-}" ] || { log "không có BACKEND_ENV_SECRET: giữ env hiện có"; return 0; }
  local token project
  token=$(curl -fsS -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token | jq -er .access_token)
  project=$(curl -fsS -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/project/project-id)
  curl -fsS -H "Authorization: Bearer $token" "https://secretmanager.googleapis.com/v1/projects/$project/secrets/$BACKEND_ENV_SECRET/versions/latest:access" \
    | jq -er .payload.data | base64 -d > "$ETC/backend.env.new"
  chmod 600 "$ETC/backend.env.new"
  mv -f "$ETC/backend.env.new" "$ETC/backend.env"

  mkdir -p /etc/vota/secrets
  chmod 700 /etc/vota/secrets
  if grep -q '^JWT_PRIVATE_KEY_B64=' /etc/vota/backend.env; then
    grep '^JWT_PRIVATE_KEY_B64=' /etc/vota/backend.env | cut -d'=' -f2- | tr -d '\r' | base64 -d > /etc/vota/secrets/jwt-private.pem
    grep '^JWT_PUBLIC_KEY_B64=' /etc/vota/backend.env | cut -d'=' -f2- | tr -d '\r' | base64 -d > /etc/vota/secrets/jwt-public.pem
    # The backend image runs as UID/GID 10001 (user `app`), so keep the keys root-owned
    # while allowing that process to traverse the directory and read the bind-mounted files.
    chown root:10001 /etc/vota/secrets /etc/vota/secrets/*.pem
    chmod 750 /etc/vota/secrets
    chmod 640 /etc/vota/secrets/*.pem
  fi
  # The frontend gets only what it needs, not the DB credentials in backend.env.
  {
    grep -E '^AUTH_SERVICE_TOKEN=' /etc/vota/backend.env || true
    sed -n 's/^AUTH_REDIS_URL=/SESSION_REDIS_URL=/p' /etc/vota/backend.env
  } > /etc/vota/frontend.env
  chmod 600 /etc/vota/frontend.env
  if [ -x "$ETC/pgbouncer-setup.sh" ]; then
    "$ETC/pgbouncer-setup.sh" "$ETC/backend.env" "$ETC/pgbouncer" "$ETC/pgbouncer.ini.tmpl"
  fi
}

ensure_infra() { # pgbouncer: không tạo lại nếu đang chạy, để không cắt kết nối DB của bản đang phục vụ
  if running vota-pgbouncer; then return 0; fi
  log "khởi động pgbouncer"
  dc -p vota -f "$ETC/compose.infra.yml" up -d pgbouncer >/dev/null
}

# ---------------------------------------------------------------------------------------------------------------
# Slot và proxy
# ---------------------------------------------------------------------------------------------------------------
start_slot() { # $1 = slot
  slot_ports "$1"
  export SLOT="$1"
  log "dựng slot $1 (backend :$BACKEND_PORT, frontend :$FRONTEND_PORT)"
  dc -p "vota-$1" -f "$ETC/compose.slot.yml" up -d --force-recreate --remove-orphans >/dev/null
}

stop_slot() { # $1 = slot; dừng êm rồi xoá container
  docker stop -t "$BACKEND_STOP_GRACE" "vota-frontend-$1" "vota-backend-$1" >/dev/null 2>&1 || true
  docker rm -f "vota-frontend-$1" "vota-backend-$1" >/dev/null 2>&1 || true
}

wait_ready() { # $1 = url, $2 = timeout giây, $3 = số lần 200 liên tiếp
  local url="$1" timeout="$2" need="$3" streak=0 waited=0
  while [ "$waited" -lt "$timeout" ]; do
    if curl -fsS -m 5 -o /dev/null "$url" 2>/dev/null; then
      streak=$((streak + 1))
      [ "$streak" -ge "$need" ] && return 0
    else
      streak=0
    fi
    sleep 5
    waited=$((waited + 5))
  done
  return 1
}

write_upstream() { # $1 = cổng frontend
  mkdir -p "$PROXY_DIR"
  printf 'server 127.0.0.1:%s;\n' "$1" > "$UPSTREAM.new"
  mv -f "$UPSTREAM.new" "$UPSTREAM"
}

ensure_proxy() {
  if running vota-proxy; then return 0; fi
  docker rm -f vota-proxy >/dev/null 2>&1 || true
  log "khởi động proxy :3000"
  docker run -d --name vota-proxy --restart unless-stopped --network host --memory 256m \
    --log-driver json-file --log-opt max-size=50m --log-opt max-file=5 \
    -v "$PROXY_DIR:$PROXY_DIR:ro" "$PROXY_IMAGE" nginx -c "$PROXY_DIR/nginx.conf" -g 'daemon off;' >/dev/null
}

reload_proxy() { # trả khác 0 nếu lỗi để caller đưa upstream về slot cũ
  docker exec vota-proxy nginx -t -c "$PROXY_DIR/nginx.conf" >/dev/null 2>&1 || { log "cấu hình nginx không hợp lệ"; return 1; }
  # Phải kèm -c: file pid do nginx.conf đặt (/tmp/nginx.pid); thiếu -c thì nginx tìm /run/nginx.pid và báo lỗi.
  docker exec vota-proxy nginx -c "$PROXY_DIR/nginx.conf" -s reload >/dev/null 2>&1 || { log "nginx reload lỗi"; return 1; }
}

detect_active() { # blue|green nếu proxy đang trỏ slot đó; legacy nếu còn stack cũ; none nếu chưa có gì
  if running vota-proxy && [ -f "$UPSTREAM" ]; then
    case "$(cat "$UPSTREAM")" in
      *:3001\;*) running vota-frontend-blue && { echo blue; return; } ;;
      *:3002\;*) running vota-frontend-green && { echo green; return; } ;;
    esac
  fi
  if running vota-frontend && ! running vota-proxy; then echo legacy; return; fi
  echo none
}

slot_images() { # $1 = slot -> "backend frontend"
  printf '%s %s' "$(docker inspect -f '{{.Config.Image}}' "vota-backend-$1" 2>/dev/null || true)" \
    "$(docker inspect -f '{{.Config.Image}}' "vota-frontend-$1" 2>/dev/null || true)"
}

report() { # dòng kết quả cho CD đối chiếu
  local slot="$1" imgs
  imgs="$(slot_images "$slot")"
  echo "SLOT_RESULT host=$(hostname) active=$slot backend=${imgs% *} frontend=${imgs#* }"
}

# Chuyển VM kiểu cũ (stack ở 3000/8000, chưa có proxy) sang slot. Bản mới ($1) đã ready ở cổng slot.
# Chỉ một khoảng ngắn giữa lúc frontend cũ nhả cổng 3000 và proxy bind cổng đó (dưới vài giây, một lần duy nhất).
migrate_from_legacy() {
  local new="$1" waited=0
  slot_ports "$new"
  write_upstream "$FRONTEND_PORT"
  # Không để Docker tự khởi động lại container cũ khi nó thoát.
  docker update --restart=no vota-frontend vota-backend >/dev/null
  log "legacy: tắt êm frontend cũ để giải phóng cổng 3000"
  docker kill --signal TERM vota-frontend >/dev/null
  while ss -ltn 'sport = :3000' | grep -q LISTEN; do
    sleep 0.5
    waited=$((waited + 1))
    if [ "$waited" -ge 300 ]; then
      log "cổng 3000 chưa được nhả sau 150 giây: khôi phục stack cũ"
      docker update --restart=unless-stopped vota-frontend vota-backend >/dev/null
      docker start vota-frontend >/dev/null 2>&1 || true
      stop_slot "$new"
      die "không chuyển được khỏi stack legacy"
    fi
  done
  ensure_proxy
}

drain_and_remove_old() { # $1 = tên slot cũ hoặc legacy; chạy nền để CD không phải đợi
  local old="$1"
  setsid nohup bash -c "
    sleep $DRAIN_SECONDS
    if [ '$old' = legacy ]; then
      docker stop -t $BACKEND_STOP_GRACE vota-frontend vota-backend >/dev/null 2>&1 || true
      docker rm -f vota-frontend vota-backend >/dev/null 2>&1 || true
    else
      docker stop -t $BACKEND_STOP_GRACE vota-frontend-$old vota-backend-$old >/dev/null 2>&1 || true
      docker rm -f vota-frontend-$old vota-backend-$old >/dev/null 2>&1 || true
    fi
  " 9>&- > /var/log/vota-slot-drain.log 2>&1 < /dev/null &
  log "bản cũ ($old) sẽ được rút sau $DRAIN_SECONDS giây"
}

require_images() {
  [ -n "${BACKEND_IMAGE:-}" ] && [ -n "${FRONTEND_IMAGE:-}" ] || die "BACKEND_IMAGE và FRONTEND_IMAGE là bắt buộc"
  [[ "$BACKEND_IMAGE" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die "BACKEND_IMAGE phải là image@sha256:<64 hex>"
  [[ "$FRONTEND_IMAGE" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die "FRONTEND_IMAGE phải là image@sha256:<64 hex>"
}

# ---------------------------------------------------------------------------------------------------------------
# Các mode
# ---------------------------------------------------------------------------------------------------------------
mode_boot() {
  acquire_lock
  require_images
  refresh_config
  write_files
  pull_images
  ensure_infra
  local active
  active="$(detect_active)"
  case "$active" in
    blue|green)
      # Khởi động lại VM: Docker tự bật container (restart: unless-stopped); đảm bảo đủ và để nguyên image đang chạy.
      log "boot: giữ slot $active"
      docker start "vota-backend-$active" "vota-frontend-$active" >/dev/null 2>&1 || true
      ensure_proxy
      ;;
    *)
      log "boot: dựng slot blue theo image của template"
      docker rm -f vota-frontend vota-backend >/dev/null 2>&1 || true
      stop_slot green
      start_slot blue
      slot_ports blue
      write_upstream "$FRONTEND_PORT"
      ensure_proxy
      wait_ready "http://127.0.0.1:$FRONTEND_PORT/health/ready" "$READY_TIMEOUT" 1 || log "cảnh báo: blue chưa ready sau $READY_TIMEOUT giây"
      ;;
  esac
}

mode_deploy() {
  acquire_lock
  require_images
  local avail active new
  avail="$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"
  [ "$avail" -ge "$MIN_AVAILABLE_MB" ] || die "chỉ còn ${avail} MB RAM trống (< $MIN_AVAILABLE_MB): không chạy hai bản song song để tránh OOM"

  refresh_config
  write_files
  active="$(detect_active)"
  log "slot đang hoạt động: $active"

  if [ "$active" = blue ] || [ "$active" = green ]; then
    if [ "$(slot_images "$active")" = "$BACKEND_IMAGE $FRONTEND_IMAGE" ]; then
      log "image đã đúng, không đổi"
      report "$active"
      return 0
    fi
    new="$(other_slot "$active")"
  else
    new=blue
  fi

  pull_images
  ensure_infra
  stop_slot "$new"   # dọn dấu vết của lần thử trước (nếu có)
  start_slot "$new"
  slot_ports "$new"

  log "đợi slot $new sẵn sàng (/health/ready qua frontend :$FRONTEND_PORT)"
  if ! wait_ready "http://127.0.0.1:$FRONTEND_PORT/health/ready" "$READY_TIMEOUT" "$READY_STREAK"; then
    log "slot $new không sẵn sàng trong $READY_TIMEOUT giây: bỏ bản mới, giữ bản cũ ($active)"
    docker logs --tail 40 "vota-backend-$new" >&2 2>&1 || true
    stop_slot "$new"
    die "slot $new không ready; $active vẫn phục vụ"
  fi

  if [ "$active" = legacy ]; then
    migrate_from_legacy "$new"
  elif running vota-proxy; then
    write_upstream "$FRONTEND_PORT"
    if ! reload_proxy; then
      log "reload proxy lỗi: đưa upstream về $active, bỏ slot $new"
      slot_ports "$active"
      write_upstream "$FRONTEND_PORT"
      stop_slot "$new"
      die "không đổi được proxy sang $new; $active vẫn phục vụ"
    fi
  else
    write_upstream "$FRONTEND_PORT"
    ensure_proxy
  fi

  log "kiểm tra qua proxy :3000"
  if ! wait_ready "http://127.0.0.1:3000/health/ready" 90 "$READY_STREAK"; then
    if [ "$active" = blue ] || [ "$active" = green ]; then
      log "proxy không ready với slot mới: đổi lại $active"
      slot_ports "$active"
      write_upstream "$FRONTEND_PORT"
      reload_proxy || log "cảnh báo: reload proxy về $active cũng lỗi"
      stop_slot "$new"
      die "proxy không ready sau khi đổi sang $new; đã đổi lại $active"
    fi
    die "proxy không ready sau khi chuyển từ legacy sang $new"
  fi

  echo "$new" > "$ETC/active-slot"
  if [ "$active" != none ]; then
    drain_and_remove_old "$active"
  fi
  report "$new"
}

case "$MODE" in
  boot) mode_boot ;;
  deploy) mode_deploy ;;
  status) detect_active ;;
  *) die "dùng: $0 boot|deploy|status" ;;
esac
