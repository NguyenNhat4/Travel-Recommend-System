#!/usr/bin/env bash
# Patroni gọi script này (bootstrap.method = clone_from_primary) với PGDATA rỗng và chạy bằng user postgres.
# Patroni xoá mọi biến PATRONI_* khỏi môi trường script bootstrap, nên entrypoint.sh chuyển giá trị cần dùng sang
# VOTA_CLONE_*. Mật khẩu replicator không in ra log.
set -Eeuo pipefail
: "${VOTA_CLONE_HOST:?}" "${VOTA_CLONE_PASSWORD:?}" "${VOTA_CLONE_DATA_DIR:?}"
DATA_DIR=$VOTA_CLONE_DATA_DIR
export PGPASSWORD=$VOTA_CLONE_PASSWORD
rm -rf "${DATA_DIR:?}"/* "${DATA_DIR:?}"/.[!.]* 2>/dev/null || true
pg_basebackup -h "$VOTA_CLONE_HOST" -p "${VOTA_CLONE_PORT:-5432}" \
  -U "${VOTA_CLONE_USER:-replicator}" -D "$DATA_DIR" -X stream --checkpoint=fast
chmod 700 "$DATA_DIR"
# Bản sao còn cấu hình streaming trỏ về primary cũ: xoá, để Patroni tự quản recovery của cụm mới.
rm -f "$DATA_DIR/standby.signal" "$DATA_DIR/recovery.signal"
sed -i '/^primary_conninfo/d;/^primary_slot_name/d' "$DATA_DIR/postgresql.auto.conf" 2>/dev/null || true
