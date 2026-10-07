#!/usr/bin/env bash
# Chạy thử job cào mới (fresh_catalog.py) trên máy cá nhân và theo dõi bằng monitor.
# Ghi vào Postgres + Weaviate Docker local, vào database và collection RIÊNG (mặc định vota_crawl / ProductCrawl):
# không đụng database `vota` và collection `Product` mà backend local đang dùng, không bao giờ ghi lên staging/cloud
# (fresh_catalog.py chặn khi CATALOG_LOCAL_ONLY=1 mà đích không phải localhost).
#
#   ./local_crawl.sh setup      # bật postgres + weaviate (docker compose), tạo database từ db/vota_schema.sql, kiểm môi trường
#   ./local_crawl.sh small      # (tuỳ chọn) lưu cấu hình lượt thử nhỏ, 4 site song song: Nha Trang + Hà Nội, vài khách sạn/nguồn
#   ./local_crawl.sh monitor    # http://127.0.0.1:8765 — bấm "Cào lớn" cho lượt đầu; Ctrl+C để tắt monitor
#   ./local_crawl.sh run full   # chạy từ terminal thay vì nút trên monitor (full | daily | index | status)
#   ./local_crawl.sh run resume <mã lượt> db   # chạy lại lượt đã kết thúc từ normalise|merge|validate|db|index, không cào lại
#   ./local_crawl.sh run resume <mã lượt> crawl booking   # cào lại riêng một nguồn của lượt rồi chạy tiếp tới index
#   ./local_crawl.sh env        # in nơi ghi dữ liệu (không in mật khẩu)
#   ./local_crawl.sh reset      # xoá database, collection và dữ liệu các lượt local (hỏi xác nhận) rồi chạy lại setup
#
# Bộ dữ liệu tách biệt: `export LOCAL_CRAWL_NAME=demo` → database vota_crawl_demo, collection ProductCrawlDemo, thư mục
# data/local_crawl_demo; mọi lệnh sau trong terminal đó dùng bộ này, không đụng bộ mặc định hay bộ khác.
# Tuỳ chọn: PYTHON (mặc định `python`, nên `conda activate vsf`), LOCAL_CRAWL_DB, LOCAL_CRAWL_COLLECTION, LOCAL_CRAWL_DIR
# (ghi đè từng chỗ riêng lẻ), MONITOR_PORT (8765),
# SHOW_BROWSER=1 để thấy cửa sổ Chromium (mặc định chạy trong Xvfb, không bật cửa sổ).
# Bước index embed bằng e5-small local (không cần khoá; model tải về cache Hugging Face lần đầu).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python}"
NAME="${LOCAL_CRAWL_NAME:-}"
[[ -z "$NAME" || "$NAME" =~ ^[a-z][a-z0-9]{0,20}$ ]] || { echo "local_crawl: LOCAL_CRAWL_NAME chỉ gồm chữ thường và số" >&2; exit 1; }
DB_NAME="${LOCAL_CRAWL_DB:-vota_crawl${NAME:+_$NAME}}"
COLLECTION="${LOCAL_CRAWL_COLLECTION:-ProductCrawl${NAME^}}"
WORK="${LOCAL_CRAWL_DIR:-$HERE/data/local_crawl${NAME:+_$NAME}}"
PORT="${MONITOR_PORT:-8765}"
WEAVIATE="http://localhost:${WEAVIATE_HOST_PORT:-8080}"

die() { echo "local_crawl: $*" >&2; exit 1; }
[[ "$DB_NAME" =~ ^[a-z_][a-z0-9_]*$ && "$DB_NAME" != vota && "$DB_NAME" != insider ]] \
  || die "LOCAL_CRAWL_DB phải là tên database riêng (không phải vota/insider)"
[[ "$COLLECTION" =~ ^[A-Z][A-Za-z0-9_]*$ && "$COLLECTION" != Product ]] \
  || die "LOCAL_CRAWL_COLLECTION phải là collection riêng (không phải Product)"

compose() { (cd "$REPO" && docker compose "$@"); }
psql_admin() { compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres "$@"; }

# URL tới database riêng: lấy tài khoản của SEED_DATABASE_URL trong .env gốc (mặc định tài khoản của docker-compose),
# thay tên database; từ chối host không phải máy này.
crawl_url() {
  "$PY" - "$REPO/.env" "$DB_NAME" "${POSTGRES_HOST_PORT:-5432}" <<'PY'
import sys
from urllib.parse import urlparse, urlunparse
env_file, name, port = sys.argv[1:]
url = f"postgresql://postgres:postgres@localhost:{port}/vota"
try:
    for line in open(env_file, encoding="utf-8"):
        if line.startswith("SEED_DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'") or url
except OSError:
    pass
parsed = urlparse(url)
if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
    sys.exit(f"SEED_DATABASE_URL trong .env trỏ tới {parsed.hostname}; cần Postgres local")
print(urlunparse(parsed._replace(path="/" + name)))
PY
}

load_env() {
  local url
  url="$(crawl_url)" || die "không dựng được URL database local"
  export DB_TARGET=local SEED_DATABASE_URL="$url" DATABASE_URL="$url"
  export WEAVIATE_URL="$WEAVIATE" WEAVIATE_API_KEY="" VECTOR_COLLECTION="$COLLECTION" WEAVIATE_VECTOR_INDEX_TYPE=hnsw
  export CATALOG_LOCAL_ONLY=1 CATALOG_STATE_DIR="$WORK/state" CATALOG_RUN_ROOT="$WORK/runs" PYTHONUNBUFFERED=1
  unset CLOUD_SEED_DATABASE_URL CLOUD_DATABASE_URL CLOUD_WEAVIATE_URL CLOUD_WEAVIATE_API_KEY CATALOG_LOG_DIR
  if [[ "${SHOW_BROWSER:-0}" != 1 ]]; then
    command -v xvfb-run >/dev/null || die "thiếu xvfb-run (sudo apt install xvfb) hoặc đặt SHOW_BROWSER=1"
    # Monitor bọc lượt bằng xvfb-run khi không có DISPLAY. Trên phiên Wayland, Chromium của Playwright tự chọn Wayland theo
    # XDG_SESSION_TYPE và nối vào socket mặc định wayland-0 dù DISPLAY trỏ Xvfb → phải bỏ cả biến này thì cửa sổ mới ẩn.
    unset DISPLAY WAYLAND_DISPLAY XDG_SESSION_TYPE
  fi
  mkdir -p "$WORK/state" "$WORK/runs"
}

show_env() {
  "$PY" - <<'PY'
import os
from urllib.parse import urlparse
u = urlparse(os.environ["SEED_DATABASE_URL"])
print(f"Postgres : {u.hostname}:{u.port or 5432}{u.path}")
print(f"Weaviate : {os.environ['WEAVIATE_URL']} · collection {os.environ['VECTOR_COLLECTION']}")
print(f"Dữ liệu  : state {os.environ['CATALOG_STATE_DIR']} · lượt {os.environ['CATALOG_RUN_ROOT']}")
PY
  echo "Bộ      : ${NAME:-mặc định}"
  echo "Trình duyệt: $([[ "${SHOW_BROWSER:-0}" == 1 ]] && echo 'cửa sổ thật' || echo 'Xvfb (ẩn)')"
}

check_python() {
  "$PY" - <<'PY' || die "Python thiếu thư viện — chạy trong env có requirements (vd. conda activate vsf) hoặc đặt PYTHON=..."
import importlib.util, sys
missing = [m for m in ("playwright", "curl_cffi", "httpx", "bs4", "lxml", "psycopg", "pydantic_settings", "numpy", "protego",
                       "rapidfuzz") if importlib.util.find_spec(m) is None]
if sys.version_info < (3, 10) or missing:
    print(f"Python {sys.version.split()[0]} · thiếu: {', '.join(missing) or '-'} (cần ≥ 3.10)", file=sys.stderr)
    sys.exit(1)
PY
}

cmd_setup() {
  check_python
  compose up -d --wait postgres weaviate
  if [[ -z "$(psql_admin -d vota -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'")" ]]; then
    echo "Tạo database $DB_NAME từ db/vota_schema.sql"
    # template0: không mang phiên bản collation cũ của template1 (volume tạo từ image postgres:16 bản glibc trước báo
    # "collation version mismatch" khi CREATE DATABASE); database mới nhận phiên bản collation hiện tại.
    psql_admin -d vota -c "CREATE DATABASE $DB_NAME TEMPLATE template0"
    psql_admin -q -d "$DB_NAME" < "$REPO/db/vota_schema.sql" >/dev/null
  else
    echo "Database $DB_NAME đã có — giữ nguyên dữ liệu"
  fi
  load_env
  "$PY" "$REPO/db/migrations/run.py" --database-url "$SEED_DATABASE_URL"
  curl -fsS "$WEAVIATE/v1/.well-known/ready" >/dev/null || die "Weaviate $WEAVIATE chưa sẵn sàng"
  ls -d "${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"/chromium-* >/dev/null 2>&1 \
    || echo "Cảnh báo: chưa thấy Chromium của Playwright — chạy: $PY -m playwright install chromium" >&2
  if [[ ! -f "$WORK/state/settings.json" ]]; then
    save_preset base
  else
    echo "Giữ cấu hình đã có: $WORK/state/settings.json"
  fi
  show_env
  echo "Xong. Tiếp theo: ./local_crawl.sh small (tuỳ chọn, phạm vi nhỏ) rồi ./local_crawl.sh monitor"
}

# Cấu hình lưu trong <thư mục>/state/settings.json (monitor đọc/ghi cùng file). `base`: đa luồng + tắt lịch; `small`: base
# + phạm vi nhỏ để thử nhanh. Phạm vi mặc định (không chạy `small`) là cào lớn đầy đủ: @deep, 30/20 khách sạn mỗi điểm đến.
save_preset() {
  cd "$HERE"
  "$PY" - "$1" <<'PY'
import os
import sys
from pathlib import Path
import fresh_settings
BASE = {
    "schedule.enabled": False,                     # local: chỉ chạy khi bấm, không có cron tick
    # Đa luồng: 4 site (trip vé/điểm, vinpearl, booking, agoda) bắt đầu cùng lúc, một site lỗi không làm site khác bị bỏ;
    # booking/agoda 2 tab mỗi site (mức tối đa spec §8).
    "crawl.parallelSites": 4, "booking.tabs": 2, "agoda.tabs": 2,
    # Khách sạn Trip: trang danh sách đang trả "Tìm thấy 0 nơi lưu trú" cho trình duyệt tự động (25/09/2026) → tắt;
    # bật lại ở trang Cấu hình khi Trip trả kết quả.
    "sources.tripHotels": False,
}
SMALL = {
    "scope.destinations": "Nha Trang,Hà Nội",     # hai điểm đến để có tuyến bay (lượt full kiểm đủ nhóm sản phẩm)
    "tripHotels.cities": ["Nha Trang"],
    "booking.hotelsPerDestination": 3, "booking.vinpearlBrand": False,
    "agoda.hotelsPerDestination": 3,
    "tripAttractions.perDestination": 5,
    "tripHotels.initialPerCity": 3, "tripHotels.newPerCity": 2, "tripHotels.scanPerCity": 30,
    "tripHotels.dailyHotels": 5,
    "vinpearl.priceOffsets": [30],
    "runs.keep": 5,
}
state = Path(os.environ["CATALOG_STATE_DIR"])
fresh_settings.save(state, BASE if sys.argv[1] == "base" else {**BASE, **SMALL})
print("Đã lưu cấu hình", sys.argv[1], "vào", fresh_settings.settings_path(state))
print("4 site cào cùng lúc, booking/agoda 2 tab, khách sạn Trip tắt"
      + (". Phạm vi nhỏ: Nha Trang + Hà Nội, 3 khách sạn/nguồn, Vinpearl 1 ngày giá." if sys.argv[1] == "small"
         else ". Phạm vi đầy đủ mặc định (@deep); thu nhỏ: ./local_crawl.sh small"))
PY
}

cmd_small() {
  load_env
  save_preset small
}

cmd_monitor() {
  load_env
  show_env
  echo "Monitor: http://127.0.0.1:$PORT"
  cd "$HERE" && exec "$PY" monitor.py --port "$PORT"
}

cmd_run() {
  local mode="${1:-full}"
  if [[ "$mode" == resume ]]; then  # chạy lại lượt đã kết thúc từ một bước sau cào, hoặc cào lại một nguồn (crawl <nguồn>)
    if [[ $# -eq 4 && "$3" == crawl && "$4" =~ ^[A-Za-z]+$ ]]; then
      load_env
      cd "$HERE"
      if [[ "${SHOW_BROWSER:-0}" == 1 ]]; then
        exec "$PY" fresh_catalog.py resume "$2" --from crawl --source "$4" --trigger manual
      fi
      exec xvfb-run -a -s '-screen 0 1366x768x24' "$PY" fresh_catalog.py resume "$2" --from crawl --source "$4" --trigger manual
    fi
    [[ $# -eq 3 && "$3" =~ ^(normalise|merge|validate|db|index)$ ]] \
      || die "run resume <mã lượt> normalise|merge|validate|db|index  hoặc  run resume <mã lượt> crawl <nguồn>"
    load_env
    cd "$HERE"
    exec "$PY" fresh_catalog.py resume "$2" --from "$3" --trigger manual
  fi
  [[ "$mode" =~ ^(full|daily|index|status)$ ]] || die "run full|daily|index|status|resume"
  load_env
  cd "$HERE"
  if [[ "$mode" == status || "$mode" == index || "${SHOW_BROWSER:-0}" == 1 ]]; then
    exec "$PY" fresh_catalog.py "$mode" --trigger manual
  fi
  exec xvfb-run -a -s '-screen 0 1366x768x24' "$PY" fresh_catalog.py "$mode" --trigger manual
}

cmd_reset() {
  load_env
  show_env
  read -r -p "Xoá database $DB_NAME, collection $COLLECTION và thư mục $WORK? Gõ 'xoa' để xác nhận: " answer
  [[ "$answer" == xoa ]] || die "đã huỷ"
  psql_admin -d vota -c "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE)"
  curl -fsS -X DELETE "$WEAVIATE/v1/schema/$COLLECTION" >/dev/null || true
  rm -rf "$WORK"
  echo "Đã xoá. Chạy lại: ./local_crawl.sh setup"
}

case "${1:-}" in
  setup) cmd_setup ;;
  small) cmd_small ;;
  monitor) cmd_monitor ;;
  run) shift; cmd_run "$@" ;;
  env) load_env; show_env ;;
  reset) cmd_reset ;;
  *) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
