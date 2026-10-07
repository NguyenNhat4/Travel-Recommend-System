#!/usr/bin/env bash
# Điểm vào của container Patroni. Biến bắt buộc:
#   PATRONI_NAME, PATRONI_NODE_IP, PATRONI_ETCD3_HOSTS (ip:2379,ip:2379,ip:2379),
#   PATRONI_SUPERUSER_PASSWORD, PATRONI_REPLICATION_PASSWORD
# Tuỳ chọn: PATRONI_SCOPE (mặc định vota-pg), PATRONI_CLONE_FROM_HOST (di trú lần đầu từ primary cũ).
set -Eeuo pipefail
: "${PATRONI_NAME:?}" "${PATRONI_NODE_IP:?}" "${PATRONI_ETCD3_HOSTS:?}" \
  "${PATRONI_SUPERUSER_PASSWORD:?}" "${PATRONI_REPLICATION_PASSWORD:?}"
export PATRONI_SCOPE=${PATRONI_SCOPE:-vota-pg}
export PATRONI_SUPERUSER_USERNAME=${PATRONI_SUPERUSER_USERNAME:-postgres}
export PATRONI_REPLICATION_USERNAME=${PATRONI_REPLICATION_USERNAME:-replicator}
export PATRONI_RESTAPI_CONNECT_ADDRESS="$PATRONI_NODE_IP:8008"
export PATRONI_POSTGRESQL_CONNECT_ADDRESS="$PATRONI_NODE_IP:5432"
export PATRONI_POSTGRESQL_DATA_DIR=${PATRONI_DATA_DIR:?}
export PATRONI_POSTGRESQL_BIN_DIR=${PATRONI_POSTGRESQL_BIN_DIR:-$(dirname "$(ls /usr/lib/postgresql/*/bin/postgres | sort -V | tail -1)")}

cfg=/etc/patroni
mkdir -p "$cfg" "$PATRONI_DATA_DIR"
cp /opt/vota/patroni/patroni.yml "$cfg/00-patroni.yml"
rm -f "$cfg/10-clone.yml"
if [[ -n "${PATRONI_CLONE_FROM_HOST:-}" ]]; then
  cp /opt/vota/patroni/bootstrap-clone.yml "$cfg/10-clone.yml"
  # Patroni xoá biến PATRONI_* khỏi môi trường script bootstrap; chuyển sang VOTA_CLONE_*.
  export VOTA_CLONE_HOST=$PATRONI_CLONE_FROM_HOST VOTA_CLONE_PORT=${PATRONI_CLONE_FROM_PORT:-5432} \
    VOTA_CLONE_USER=$PATRONI_REPLICATION_USERNAME VOTA_CLONE_PASSWORD=$PATRONI_REPLICATION_PASSWORD \
    VOTA_CLONE_DATA_DIR=$PATRONI_DATA_DIR
fi
chown -R postgres:postgres "$PATRONI_DATA_DIR"
chmod 700 "$PATRONI_DATA_DIR"

# Patroni chạy bằng user postgres; secret chỉ có trong môi trường tiến trình.
exec gosu postgres /opt/patroni/bin/patroni "$cfg"
