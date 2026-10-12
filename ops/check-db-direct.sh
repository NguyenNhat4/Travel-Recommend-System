#!/usr/bin/env bash
# Kiểm một VM của nhóm HA nối được DB trực tiếp (không SSH tunnel) và đủ chỗ cho số kết nối dự kiến.
# Chạy trên VM app hoặc máy có route tới DB:
#   DB_HOST=db.vota.internal DB_PASSWORD_FILE=/etc/vota/db_pw ops/check-db-direct.sh
# POOLED=1 tính theo pgbouncer sidecar (trần cố định) thay vì theo số worker.
# Thoát 0 nếu đạt, khác 0 kèm lý do. Không in mật khẩu.
set -Eeuo pipefail

DB_HOST=${DB_HOST:?set DB_HOST (ví dụ db.vota.internal)}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-vota}
DB_USER=${DB_USER:-vota_app_login}
DB_PASSWORD_FILE=${DB_PASSWORD_FILE:?set DB_PASSWORD_FILE (file mode 600 chứa mật khẩu role)}
VMS=${VMS:-2}                     # số VM tối đa của MIG (max_replicas)
WORKERS=${WORKERS:-2}             # UVICORN_WORKERS mỗi VM
CONNS_PER_WORKER=${CONNS_PER_WORKER:-10}   # đỉnh kết nối đồng thời ước lượng mỗi worker (đo bằng k6 và pg_stat_activity)
RESERVED=${RESERVED:-10}          # chừa cho superuser, replication, job cào, người vận hành

fail() { echo "FAIL: $*" >&2; exit 1; }
[[ "$DB_PORT" =~ ^[0-9]+$ ]] || fail 'DB_PORT phải là số'
[[ -r "$DB_PASSWORD_FILE" ]] || fail "không đọc được $DB_PASSWORD_FILE"
[[ "$DB_HOST" != "127.0.0.1" && "$DB_HOST" != "localhost" ]] || fail "DB_HOST=$DB_HOST là loopback: đó là tunnel SSH, VM của MIG không có"

PSQL=(psql -X -Atq -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1)
export PGCONNECT_TIMEOUT=5
PGPASSWORD=$(cat "$DB_PASSWORD_FILE"); export PGPASSWORD

if ! out=$("${PSQL[@]}" -c 'SELECT 1' 2>&1); then
  fail "không kết nối được $DB_HOST:$DB_PORT: ${out%%$'\n'*} (kiểm firewall, pg_hba, DNS db.vota.internal)"
fi
echo "OK: kết nối $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"

max=$("${PSQL[@]}" -c 'SHOW max_connections')
used=$("${PSQL[@]}" -c 'SELECT count(*) FROM pg_stat_activity')
if [[ "${POOLED:-0}" == 1 ]]; then
  # Có pgbouncer sidecar: trần kết nối thật là VM × role × (default_pool_size + reserve_pool_size), không theo số worker.
  ROLES=${ROLES:-2}; POOL_SIZE=${POOL_SIZE:-10}; RESERVE_POOL=${RESERVE_POOL:-2}
  need=$(( VMS * ROLES * (POOL_SIZE + RESERVE_POOL) + RESERVED ))
  echo "max_connections=$max đang dùng=$used trần có pooler=$need (VM=$VMS × role=$ROLES × (pool=$POOL_SIZE + dự phòng=$RESERVE_POOL) + dự trữ=$RESERVED)"
else
  need=$(( VMS * WORKERS * CONNS_PER_WORKER + RESERVED ))
  echo "max_connections=$max đang dùng=$used dự kiến đỉnh=$need (VM=$VMS × worker=$WORKERS × kết nối/worker=$CONNS_PER_WORKER + dự trữ=$RESERVED)"
fi
(( need <= max )) || fail "dự kiến $need kết nối vượt max_connections=$max: giảm worker, tăng max_connections hoặc bật pgbouncer (docs/plan/2026-10-05-ha-load-balancing.md)"
echo 'OK: đủ chỗ kết nối'
