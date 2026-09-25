#!/usr/bin/env bash
# Job VM. `run` (= `legacy-run`), `init`, `daily`, `monitor`: job daily.py (Dockerfile.daily) mà cron của CI/CD đang gọi.
# `fresh-run [auto|full|daily|index|status]`: job cào mới (Dockerfile.fresh-catalog), nạp DB rồi index Weaviate. Chỉ một
#   trong hai job được lên lịch cho cùng DB. Theo dõi job mới: `logs [-f] [-n SỐ_DÒNG] [LƯỢT]` · `report [SỐ_LƯỢT]` ·
#   `fresh-run status`; backend compose cùng VM: `backend [logs [-f] [-n SỐ_DÒNG]]`.
# Only this runner script, Docker, an env file and a data volume are needed on the VM.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${IMAGE:-vota-daily:latest}"
DATA_DIR="${DATA_DIR:-/srv/vota/daily-data}"     # interim, cache, sqlite tiến độ, catalog, version — phải giữ giữa các lượt
ENV_FILE="${ENV_FILE:-/etc/vota/daily.env}"      # KEY=VALUE, không nháy (docker --env-file), mẫu: src/data_collection/.env.example
MAX_HOURS="${MAX_HOURS:-16}"                     # hạn phần cào; quá hạn thì dừng êm rồi vẫn publish phần đã có
DOCKER_NETWORK="${DOCKER_NETWORK:-}"             # vd. app-private nếu Postgres chạy bằng Docker trên cùng VM
NAME="${CONTAINER_NAME:-vota-daily}"
PULL="${PULL:-1}"                                # 1 = kéo IMAGE mới trước mỗi lượt (lỗi kéo thì dùng image đã có)
MANUAL_IN_IMAGE=/app/src/data_collection/snapshots/2026-09-23/combo_items_manual.jsonl
FRESH_IMAGE="${FRESH_IMAGE:-vota-fresh-catalog:latest}"
FRESH_DATA_DIR="${FRESH_DATA_DIR:-/srv/vota/fresh-catalog-data}"
FRESH_ENV_FILE="${CATALOG_ENV_FILE:-/etc/vota/fresh-catalog.env}"
FRESH_NETWORK="${FRESH_NETWORK:-${DOCKER_NETWORK:-host}}"
FRESH_NAME="${FRESH_CONTAINER_NAME:-vota-fresh-catalog}"
FRESH_LOG_DIR="${CATALOG_LOG_DIR:-/srv/vota/fresh-catalog-logs}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"    # backend docker compose trên cùng VM
BACKEND_CONTAINER="${BACKEND_CONTAINER:-}"             # trống: tìm container có nhãn compose service=backend

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

cmd_legacy_run() {
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

cmd_fresh_run() {
  local mode="${1:-auto}" log_dir log status=0 container_name
  [ "$#" -le 1 ] || die 'fresh-run accepts one mode: auto, full, daily, index or status'
  case "$mode" in
    auto|full|daily|index|status|--auto|--full|--daily|--index|--status) mode="${mode#--}" ;;
    *) die 'fresh-run accepts one mode: auto, full, daily, index or status' ;;
  esac
  [ -d "$FRESH_DATA_DIR" ] || die "chưa có $FRESH_DATA_DIR (tạo với UID/GID 10001 cho app trong image)"
  log_dir="$FRESH_LOG_DIR"
  mkdir -p "$log_dir"
  [ "$mode" = status ] || [ -r "$FRESH_ENV_FILE" ] || die "không đọc được $FRESH_ENV_FILE"
  container_name="$FRESH_NAME"
  if [ "$mode" = status ]; then container_name="$FRESH_NAME-status-$$"; fi
  local args=(--rm --init --name "$container_name"
              --network "$FRESH_NETWORK" --shm-size "${FRESH_SHM_SIZE:-512m}"
              -v "$FRESH_DATA_DIR:/data")
  if [ -r "$FRESH_ENV_FILE" ]; then args+=(--env-file "$FRESH_ENV_FILE"); fi
  args+=(-e CATALOG_STATE_DIR=/data/state -e CATALOG_RUN_ROOT=/data/fresh_runs)
  if [ "$mode" = status ]; then
    status_host
    docker run "${args[@]}" "$FRESH_IMAGE" status
    return
  fi
  find "$log_dir" -maxdepth 1 -name 'fresh-catalog-*.log' -mtime +30 -delete 2>/dev/null || true
  if [ -n "$(docker ps -q --filter "name=^${FRESH_NAME}\$")" ]; then
    echo "$(date -Is) SKIP: container $FRESH_NAME vẫn đang chạy" >> "$log_dir/fresh-catalog-errors.log"
    echo "fresh catalog: previous run still active"
    return 0
  fi
  if [ "$PULL" = 1 ]; then docker pull -q "$FRESH_IMAGE" >/dev/null 2>&1 || true; fi
  log="$log_dir/fresh-catalog-$(date +%Y%m%d-%H%M%S).log"
  echo "fresh-catalog.start mode=$mode image=$FRESH_IMAGE at=$(date -Is)" >> "$log"
  docker run "${args[@]}" "$FRESH_IMAGE" "$mode" >> "$log" 2>&1 || status=$?
  echo "fresh-catalog.exit=$status finished=$(date -Is)" >> "$log"  # `report` đọc dòng này
  if [ "$status" -ne 0 ]; then
    echo "$(date -Is) fresh catalog exit=$status — xem $log" >> "$log_dir/fresh-catalog-errors.log"
  fi
  echo "fresh catalog exit=$status; log=$log"
  return "$status"
}

# ---------------------------------------------------------------------- theo dõi trên console
list_logs() { ls -1t "$FRESH_LOG_DIR"/fresh-catalog-2*.log 2>/dev/null || true; }  # mới nhất trước; bỏ errors.log

running_groups() {  # nhóm site đã bắt đầu mà chưa xong trong một log
  awk '/catalog\.group\.start name=/ { sub(/.*name=/, ""); split($0, a, " "); open[a[1]] = 1 }
       /catalog\.group\.done name=/  { sub(/.*name=/, ""); split($0, a, " "); delete open[a[1]] }
       END { s = ""; for (g in open) s = s (s ? ", " : "") g; print s }' "$1"
}

status_host() {
  local log started groups
  log="$(list_logs | head -n 1)"
  if [ -n "$(docker ps -q --filter "name=^${FRESH_NAME}\$")" ]; then
    started="$(docker inspect -f '{{.State.StartedAt}}' "$FRESH_NAME" | cut -c1-19)"
    echo "Đang chạy: $FRESH_NAME từ ${started/T/ } UTC"
    docker stats --no-stream --format 'Tài nguyên: CPU {{.CPUPerc}} · RAM {{.MemUsage}}' "$FRESH_NAME" 2>/dev/null || true
    if [ -n "$log" ]; then
      groups="$(running_groups "$log")"
      echo "Nhóm đang cào: ${groups:-không có (lượt daily, hoặc đang tìm ID/nạp DB/index)}"
      echo "Log: $log"
    fi
  else
    echo "Không có lượt nào đang chạy."
    if [ -n "$log" ]; then
      echo "Lượt gần nhất: $log · $(grep -oE 'fresh-catalog\.exit=[0-9]+ finished=[^ ]+' "$log" | tail -n 1 || true)"
    fi
  fi
}

cmd_logs() {
  local follow=0 lines=100 nth=1 log
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -f) follow=1 ;;
      -n) shift; lines="${1:-}" ;;
      *) nth="$1" ;;
    esac
    shift
  done
  [[ "$lines" =~ ^[0-9]+$ && "$nth" =~ ^[1-9][0-9]*$ ]] || die 'cách dùng: logs [-f] [-n SỐ_DÒNG] [LƯỢT]'
  log="$(list_logs | sed -n "${nth}p")"
  [ -n "$log" ] || die "không có log lượt $nth trong $FRESH_LOG_DIR"
  echo "== $log"
  if [ "$follow" = 1 ]; then tail -n "$lines" -f "$log"; else tail -n "$lines" "$log"; fi
}

json_number() {  # json_number <log> <mẫu dòng> <khoá>: số của khoá trong dòng cuối cùng khớp mẫu
  grep -E "$2" "$1" | tail -n 1 | grep -oE "\"$3\": [0-9]+" | head -n 1 | grep -oE '[0-9]+$' || true
}

cmd_report() {
  local count="${1:-7}" log ts start mode code result finished seconds rows index note new refreshed
  [[ "$count" =~ ^[1-9][0-9]*$ ]] || die 'cách dùng: report [SỐ_LƯỢT]'
  # Cột cố định để ASCII cho thẳng hàng (printf đếm byte); ghi chú ở cột cuối.
  printf '%-16s  %-6s  %5s  %-10s  %-13s  %-11s  %s\n' START MODE MIN RESULT NEW/REFRESH EMBED/DEL NOTE
  list_logs | head -n "$count" | while IFS= read -r log; do
    ts="$(basename "$log" .log)"; ts="${ts#fresh-catalog-}"
    start="${ts:0:4}-${ts:4:2}-${ts:6:2} ${ts:9:2}:${ts:11:2}"
    mode="$(grep -m 1 -oE '^Run (full|daily)' "$log" | cut -d' ' -f2 || true)"
    [ -n "$mode" ] || mode="$(grep -m 1 -oE 'fresh-catalog\.start mode=[a-z]+' "$log" | cut -d= -f2 || true)"
    code="$(grep -oE 'fresh-catalog\.exit=[0-9]+' "$log" | tail -n 1 | cut -d= -f2 || true)"
    finished="$(grep -oE 'finished=[^ ]+' "$log" | tail -n 1 | cut -d= -f2 || true)"
    if [ -z "$code" ] && [ "$log" = "$(list_logs | head -n 1)" ] && [ -n "$(docker ps -q --filter "name=^${FRESH_NAME}\$" 2>/dev/null)" ]; then
      result='running'; finished="$(date -Is)"
    elif [ -z "$code" ]; then result='?'
    elif [ "$code" = 0 ]; then result='ok'
    elif grep -q 'Fresh catalog failed' "$log"; then result="fail:$code"
    else result="partial:$code"  # mã 3 khi còn ngày chưa có giá hoặc có nguồn bị chặn
    fi
    seconds=''
    if [ -n "$finished" ]; then seconds=$(( $(date -d "$finished" +%s) - $(date -d "$start" +%s) )); fi
    new="$(json_number "$log" '^\{"mode"' new)"; refreshed="$(json_number "$log" '^\{"mode"' refreshed)"
    rows="${new:--}/${refreshed:--}"
    index="$(json_number "$log" 'catalog\.index\.complete' embedded)/$(json_number "$log" 'catalog\.index\.complete' deletedOrphans)"
    if grep -q 'catalog\.index\.failed' "$log"; then index='index-fail'; elif [ "$index" = / ]; then index='-'; fi
    note="$(grep -m 1 -oE 'Fresh catalog failed: .*' "$log" || true)"; note="${note#Fresh catalog failed: }"; note="${note:0:80}"
    [ -n "$note" ] || note="$(grep -oE 'catalog\.group\.done name=[a-z]+ status=(error|stopped)' "$log" \
                              | sed -E 's/.*name=([a-z]+) status=/\1 /' | paste -sd, - || true)"
    printf '%-16s  %-6s  %5s  %-10s  %-13s  %-11s  %s\n' "$start" "${mode:-?}" "${seconds:+$(( seconds / 60 ))}" \
      "$result" "$rows" "$index" "$note"
  done
}

backend_container() {
  if [ -n "$BACKEND_CONTAINER" ]; then echo "$BACKEND_CONTAINER"; return; fi
  docker ps --filter 'label=com.docker.compose.service=backend' --format '{{.Names}}' | head -n 1
}

cmd_backend() {
  local name body errors args=()
  name="$(backend_container)"
  if [ "${1:-}" = logs ]; then
    shift
    [ -n "$name" ] || die 'không thấy container backend đang chạy (đặt BACKEND_CONTAINER=<tên>)'
    args=(--tail 200)
    while [ "$#" -gt 0 ]; do
      case "$1" in
        -f) args+=(--follow) ;;
        -n) shift; [[ "${1:-}" =~ ^[0-9]+$ ]] || die 'cách dùng: backend logs [-f] [-n SỐ_DÒNG]'; args+=(--tail "$1") ;;
        *) die 'cách dùng: backend logs [-f] [-n SỐ_DÒNG]' ;;
      esac
      shift
    done
    docker logs --timestamps "${args[@]}" "$name" 2>&1
    return
  fi
  [ "$#" -eq 0 ] || die 'cách dùng: backend [logs [-f] [-n SỐ_DÒNG]]'
  echo "== Backend $BACKEND_URL"
  if ! command -v curl >/dev/null 2>&1; then echo 'health: không có curl trên máy này'
  elif body="$(curl -fsS -m 5 "$BACKEND_URL/health" 2>&1)"; then echo "health: $body"
  else echo "health: KHÔNG PHẢN HỒI — $body"
  fi
  if [ -z "$name" ]; then
    echo 'container: không thấy container compose service=backend đang chạy (đặt BACKEND_CONTAINER nếu khác tên)'
    return 0
  fi
  docker ps -a --filter "name=^${name}\$" --format 'container: {{.Names}} · {{.Status}}'
  docker stats --no-stream --format 'tài nguyên: CPU {{.CPUPerc}} · RAM {{.MemUsage}}' "$name" 2>/dev/null || true
  echo '-- RecSys trong 24 giờ (nạp catalog, lệch vector)'
  docker logs --timestamps --since 24h "$name" 2>&1 \
    | grep -E 'RecSys (ready|disabled)|startup\.recsys\.(ready|disabled)|catalog\.refresh\.(ready|failed)|recsys\.vectors\.out_of_sync' \
    | tail -n 8 || echo '(không có dòng nào)'
  echo '-- Lỗi trong 1 giờ'
  errors="$(docker logs --timestamps --since 1h "$name" 2>&1 | grep -E 'ERROR|Traceback|Exception' || true)"
  if [ -z "$errors" ]; then echo 'không có'; else echo "$errors" | tail -n 5; echo "(tổng $(echo "$errors" | wc -l) dòng)"; fi
}

case "${1:-}" in
  init) shift; cmd_init "$@" ;;
  run) cmd_legacy_run ;;  # cron của CI/CD (scripts/install-vota-cron.sh) gọi `run`: giữ đúng job daily.py
  fresh-run) shift; cmd_fresh_run "$@" ;;
  logs) shift; cmd_logs "$@" ;;
  report) shift; cmd_report "$@" ;;
  backend) shift; cmd_backend "$@" ;;
  legacy-run) shift; cmd_legacy_run "$@" ;;
  daily) shift; docker_run "$NAME-manual-$$" -- python daily.py "$@" ;;
  # monitor.py chỉ nghe 127.0.0.1 (chống DNS rebinding) nên dùng mạng của host: trang nằm ở 127.0.0.1:8765 của VPS
  monitor) shift; DOCKER_NETWORK='' docker_run "$NAME-monitor" --network host -- python monitor.py "$@" ;;
  *) sed -n '2,6p' "$0"; exit 2 ;;
esac
