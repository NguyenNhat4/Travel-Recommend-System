#!/usr/bin/env bash
# Job hằng ngày chạy bằng Docker trên VPS (image từ Dockerfile.daily). Một script cho người vận hành:
#   run_daily_docker.sh init <thư mục interim> [<thư mục raw>]  # một lần: chuẩn bị thư mục dữ liệu trên VPS
#   run_daily_docker.sh run                                     # một lượt: cào → chuẩn hoá → gate → promote → nạp DB → embed
#   run_daily_docker.sh daily <lệnh daily.py…>                  # thao tác tay: status | versions | accept <lượt> | switch <version>…
#   run_daily_docker.sh monitor                                 # trang /daily ở 127.0.0.1:8765 của VPS (xem qua ssh -L)
# Cron gợi ý (02:00 giờ máy): 0 2 * * * /đường/dẫn/run_daily_docker.sh run
# Biến (export hoặc đặt trước lệnh): IMAGE, DATA_DIR, ENV_FILE, MAX_HOURS, DOCKER_NETWORK, CONTAINER_NAME, PULL — mặc định bên dưới.
# Kết nối DB/Weaviate/Cohere chỉ nằm trong ENV_FILE (chmod 600), không bao giờ trong image, log hay script này.
set -euo pipefail

IMAGE="${IMAGE:-vota-daily:latest}"
DATA_DIR="${DATA_DIR:-/srv/vota/daily-data}"     # interim, cache, sqlite tiến độ, catalog, version — phải giữ giữa các lượt
ENV_FILE="${ENV_FILE:-/etc/vota/daily.env}"      # KEY=VALUE, không nháy (docker --env-file), mẫu: src/data_collection/.env.example
MAX_HOURS="${MAX_HOURS:-16}"                     # hạn phần cào; quá hạn thì dừng êm rồi vẫn publish phần đã có
DOCKER_NETWORK="${DOCKER_NETWORK:-}"             # vd. app-private nếu Postgres chạy bằng Docker trên cùng VM
NAME="${CONTAINER_NAME:-vota-daily}"
PULL="${PULL:-1}"                                # 1 = kéo IMAGE mới trước mỗi lượt (lỗi kéo thì dùng image đã có)
MANUAL_IN_IMAGE=/app/src/data_collection/snapshots/2026-09-23/combo_items_manual.jsonl

die() { echo "$(date -Is) $*" >&2; exit 1; }

owner() { stat -c %u:%g "$DATA_DIR"; }  # container chạy bằng uid:gid chủ thư mục dữ liệu, file ghi ra vẫn thuộc người vận hành

docker_run() {  # docker_run <tên container> [tuỳ chọn docker…] -- <lệnh trong image…>
  local name="$1"; shift
  local opts=()
  while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do opts+=("$1"); shift; done
  shift
  [ -d "$DATA_DIR/interim" ] || die "chưa có $DATA_DIR/interim — chạy trước: $0 init <thư mục interim>"
  [ -r "$ENV_FILE" ] || die "không đọc được $ENV_FILE (mẫu: src/data_collection/.env.example, khối Job hằng ngày)"
  local args=(--rm --name "$name" --user "$(owner)" -v "$DATA_DIR:/data" --env-file "$ENV_FILE")
  if [ -n "$DOCKER_NETWORK" ]; then args+=(--network "$DOCKER_NETWORK"); fi
  docker run "${args[@]}" "${opts[@]}" "$IMAGE" "$@"
}

cmd_init() {
  local interim="${1:-}" raw="${2:-}"
  [ -n "$interim" ] && [ -d "$interim" ] || die "cách dùng: $0 init <thư mục chứa *.jsonl interim> [<thư mục raw>]"
  mkdir -p "$DATA_DIR/interim" "$DATA_DIR/logs"
  local copied=0 f
  for f in "$interim"/*.jsonl; do  # không đè interim đã có trên VPS (job đã chạy thì bản trên VPS mới hơn)
    [ -e "$f" ] || continue
    if [ ! -e "$DATA_DIR/interim/$(basename "$f")" ]; then cp "$f" "$DATA_DIR/interim/"; copied=$((copied + 1)); fi
  done
  if [ -n "$raw" ]; then  # tuỳ chọn: cache raw (chi tiết tour Vinpearl khi trang bị Cloudflare chặn…)
    [ -d "$raw" ] || die "không thấy thư mục raw $raw"
    mkdir -p "$DATA_DIR/raw"
    cp -r -n "$raw"/. "$DATA_DIR/raw/" || true  # -n: giữ file đã có; vài bản coreutils trả mã khác 0 khi bỏ qua file
  fi
  # seed --catalog-only đọc /data/combo_items_manual.jsonl; thiếu file thì 64 mapping combo duyệt tay bị bỏ qua mà không báo lỗi
  if [ ! -f "$DATA_DIR/combo_items_manual.jsonl" ]; then
    docker run --rm --user "$(owner)" -v "$DATA_DIR:/data" "$IMAGE" cp "$MANUAL_IN_IMAGE" /data/combo_items_manual.jsonl
  fi
  echo "Đã chuẩn bị $DATA_DIR: chép $copied file interim, hiện có $(find "$DATA_DIR/interim" -maxdepth 1 -name '*.jsonl' | wc -l) file."
}

cmd_run() {
  mkdir -p "$DATA_DIR/logs"
  find "$DATA_DIR/logs" -maxdepth 1 -name 'daily-*.log' -mtime +30 -delete 2>/dev/null || true
  if [ -n "$(docker ps -q --filter "name=^${NAME}\$")" ]; then  # lượt trước chưa xong (daily.py cũng có khoá riêng trong /data/state)
    echo "$(date -Is) SKIP: container $NAME vẫn đang chạy lượt trước" >> "$DATA_DIR/logs/daily-errors.log"
    exit 0
  fi
  if [ "$PULL" = 1 ]; then docker pull -q "$IMAGE" >/dev/null 2>&1 || true; fi
  local log status=0
  log="$DATA_DIR/logs/daily-$(date +%Y%m%d-%H%M%S).log"
  docker_run "$NAME" -- python daily.py run --max-hours "$MAX_HOURS" >> "$log" 2>&1 || status=$?
  if [ "$status" -ne 0 ]; then
    echo "$(date -Is) daily.py thoát mã $status — xem $log" >> "$DATA_DIR/logs/daily-errors.log"
  fi
  exit "$status"
}

case "${1:-}" in
  init) shift; cmd_init "$@" ;;
  run) cmd_run ;;
  daily) shift; docker_run "$NAME-manual-$$" -- python daily.py "$@" ;;
  # monitor.py chỉ nghe 127.0.0.1 (chống DNS rebinding) nên dùng mạng của host: trang nằm ở 127.0.0.1:8765 của VPS
  monitor) shift; DOCKER_NETWORK='' docker_run "$NAME-monitor" --network host -- python monitor.py "$@" ;;
  *) sed -n '2,9p' "$0"; exit 2 ;;
esac
