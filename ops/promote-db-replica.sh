#!/usr/bin/env bash
# Failover tay có người quyết định, MỘT lệnh: tắt primary, nâng replica, đổi bản ghi DNS db.vota.internal.
# Nhóm HA nối DB qua tên này (TTL 30 giây) và pgbouncer phân giải lại khi mở kết nối mới, nên không phải sửa env
# hay deploy lại VM nào. Không có failover tự động: chạy script là một quyết định của người vận hành.
#
#   PRIMARY_VM=vota-staging-db REPLICA_VM=vota-staging-db-replica REPLICA_IP=10.148.0.4 ZONE=asia-southeast1-a \
#   DNS_ZONE=vota-ha-internal ops/promote-db-replica.sh --yes
#
# Chạy không có --yes chỉ kiểm điều kiện và in kế hoạch (dry run).
set -Eeuo pipefail

PRIMARY_VM=${PRIMARY_VM:?set PRIMARY_VM}
REPLICA_VM=${REPLICA_VM:?set REPLICA_VM}
REPLICA_IP=${REPLICA_IP:?set REPLICA_IP (IP private của replica)}
ZONE=${ZONE:?set ZONE}
DNS_ZONE=${DNS_ZONE:?set DNS_ZONE (tên managed zone, ví dụ vota-ha-internal)}
DNS_NAME=${DNS_NAME:-db.vota.internal.}
DNS_TTL=${DNS_TTL:-30}
CATCHUP_SECONDS=${CATCHUP_SECONDS:-30}
GCLOUD=${GCLOUD:-gcloud}
# Lệnh chạy psql -Atqc trên replica (tham số cuối là câu SQL). Mặc định qua SSH vào container; test ghi đè.
REPLICA_PSQL=${REPLICA_PSQL:-"$GCLOUD compute ssh $REPLICA_VM --zone $ZONE --command"}
REPLICA_CONTAINER=${REPLICA_CONTAINER:-vota-postgres}
CONFIRM=0; [[ "${1:-}" == "--yes" ]] && CONFIRM=1

[[ "$REPLICA_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'REPLICA_IP phải là IPv4' >&2; exit 2; }
[[ "$DNS_NAME" == *. ]] || { echo 'DNS_NAME phải kết thúc bằng dấu chấm' >&2; exit 2; }

log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }
started=$(date +%s)

sql() {   # chạy một câu SQL trên replica
  if [[ -n "${REPLICA_PSQL_TEST:-}" ]]; then $REPLICA_PSQL_TEST "$1"; else
    $REPLICA_PSQL "sudo docker exec -u postgres $REPLICA_CONTAINER psql -X -U postgres -Atqc \"$1\""
  fi
}

in_recovery=$(sql 'SELECT pg_is_in_recovery()')
if [[ "$in_recovery" != t ]]; then
  echo "DỪNG: $REPLICA_VM không ở chế độ standby (pg_is_in_recovery=$in_recovery). Có thể đã được nâng; không làm gì thêm." >&2
  exit 1
fi
backlog=$(sql "SELECT coalesce(pg_wal_lsn_diff(pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn()), 0)::bigint")
log "replica là standby; WAL đã nhận nhưng chưa replay: ${backlog} byte"

cat <<PLAN
Kế hoạch:
  1. tắt hẳn primary $PRIMARY_VM (tránh hai primary cùng ghi)
  2. chờ replica replay hết WAL đã nhận (tối đa ${CATCHUP_SECONDS}s)
  3. nâng $REPLICA_VM thành primary (pg_promote)
  4. đổi $DNS_NAME -> $REPLICA_IP (TTL ${DNS_TTL}s) trong zone $DNS_ZONE
PLAN
if [[ $CONFIRM -ne 1 ]]; then echo 'Dry run: thêm --yes để thực hiện.'; exit 0; fi

log "1/4 tắt primary $PRIMARY_VM"
"$GCLOUD" compute instances stop "$PRIMARY_VM" --zone "$ZONE" >/dev/null

log "2/4 chờ replay"
for _ in $(seq "$CATCHUP_SECONDS"); do
  backlog=$(sql "SELECT coalesce(pg_wal_lsn_diff(pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn()), 0)::bigint")
  [[ "$backlog" == 0 ]] && break
  sleep 1
done
[[ "$backlog" == 0 ]] || log "CẢNH BÁO: còn ${backlog} byte WAL chưa replay khi hết thời gian chờ"

log "3/4 nâng replica"
promoted=$(sql 'SELECT pg_promote(true, 60)')
[[ "$promoted" == t ]] || { echo "pg_promote không thành công: $promoted" >&2; exit 1; }
[[ "$(sql 'SELECT pg_is_in_recovery()')" == f ]] || { echo 'replica vẫn ở chế độ recovery sau promote' >&2; exit 1; }

log "4/4 đổi DNS $DNS_NAME -> $REPLICA_IP"
"$GCLOUD" dns record-sets update "$DNS_NAME" --zone "$DNS_ZONE" --type A --ttl "$DNS_TTL" --rrdatas "$REPLICA_IP" >/dev/null

log "XONG sau $(( $(date +%s) - started )) giây. Backend nhận IP mới trong tối đa ${DNS_TTL}s (+ thời gian pgbouncer mở lại kết nối)."
cat <<NEXT
Việc còn lại (làm tay):
  - KHÔNG bật lại $PRIMARY_VM vào cụm: dữ liệu của nó có thể lệch. Giữ disk để điều tra.
  - Dựng replica mới từ primary mới (docs/guide/van-hanh-db-replica.md mục 5) và chạy ops/bootstrap-db-primary-replication.sh trên primary mới.
  - Cập nhật PRIMARY_VM/REPLICA_VM/REPLICA_IP cho lần failover kế tiếp.
NEXT
