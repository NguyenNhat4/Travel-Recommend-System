#!/usr/bin/env bash
# Đường di trú: dựng nút Patroni đầu tiên bằng pg_basebackup từ một Postgres thường đang chạy (primary hiện tại), rồi
# thêm nút thứ hai làm replica. Kiểm: dữ liệu cũ còn nguyên, nút Patroni là leader ghi được, nút hai là replica,
# primary cũ không bị đổi gì (vẫn ghi được, là phương án quay lại). SKIP nếu không có Docker.
set -euo pipefail
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
command -v docker >/dev/null && docker info >/dev/null 2>&1 || { echo 'SKIP: cần Docker'; exit 0; }

id=$$; net=vota-pclone-net-$id; img=${PATRONI_TEST_IMAGE:-vota-patroni:test-$id}
etcd=vota-etcd-$id; old=vota-old-$id; n1=vota-pgc1-$id; n2=vota-pgc2-$id
cleanup() { docker rm -f "$etcd" "$old" "$n1" "$n2" >/dev/null 2>&1 || true
            docker volume rm "vol1-$id" "vol2-$id" >/dev/null 2>&1 || true
            docker network rm "$net" >/dev/null 2>&1 || true
            [[ -n "${PATRONI_TEST_IMAGE:-}" ]] || docker rmi "$img" >/dev/null 2>&1 || true; }
trap cleanup EXIT
[[ -n "${PATRONI_TEST_IMAGE:-}" ]] || docker build -q -t "$img" "$repo_root/ops/patroni" >/dev/null
docker network create "$net" >/dev/null

docker run -d --name "$old" --network "$net" -e POSTGRES_PASSWORD=su-pw pgvector/pgvector:0.8.6-pg18-bookworm >/dev/null
for _ in $(seq 60); do docker exec "$old" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
sleep 3
docker exec -u postgres "$old" psql -U postgres -qc "CREATE ROLE replicator REPLICATION LOGIN PASSWORD 'repl-pw'"
docker exec "$old" sh -c 'echo "host replication replicator all scram-sha-256" >> "$PGDATA/pg_hba.conf"'
docker exec -u postgres "$old" psql -U postgres -qc "SELECT pg_reload_conf()" >/dev/null
docker exec -u postgres "$old" psql -U postgres -qc "CREATE TABLE booking_demo(id int primary key, ref text); INSERT INTO booking_demo VALUES (1,'VP-12M-PHUQUOC')"

docker run -d --name "$etcd" --network "$net" quay.io/coreos/etcd:v3.5.17 etcd \
  --listen-client-urls http://0.0.0.0:2379 --advertise-client-urls "http://$etcd:2379" >/dev/null
docker volume create "vol1-$id" >/dev/null; docker volume create "vol2-$id" >/dev/null
start_node() { # start_node <name> <vol> [extra docker args…]
  local name=$1 vol=$2; shift 2
  docker run -d --name "$name" --network "$net" --hostname "$name" -v "$vol:/var/lib/postgresql" "$@" \
    -e PATRONI_NAME="$name" -e PATRONI_NODE_IP="$name" -e PATRONI_ETCD3_HOSTS="$etcd:2379" \
    -e PATRONI_SUPERUSER_PASSWORD=su-pw -e PATRONI_REPLICATION_PASSWORD=repl-pw "$img" >/dev/null
}
rest() { docker exec "$1" curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8008/$2" 2>/dev/null || echo 000; }
wait_for() { local limit=$1 what=$2; shift 2
  for _ in $(seq "$limit"); do if "$@" >/dev/null 2>&1; then return 0; fi; sleep 1; done
  echo "QUÁ HẠN: $what" >&2; docker logs --tail 30 "$n1" >&2 || true; docker logs --tail 30 "$n2" >&2 || true; exit 1; }
is_leader() { [[ "$(rest "$1" primary)" == 200 ]]; }
is_replica() { [[ "$(rest "$1" replica)" == 200 ]]; }
q() { docker exec -u postgres "$1" psql -X -h /var/run/postgresql -U postgres -d postgres -Atqc "$2"; }

echo '1. nút Patroni đầu tiên clone từ primary cũ'
start_node "$n1" "vol1-$id" -e PATRONI_CLONE_FROM_HOST="$old"
wait_for 120 'nút 1 thành leader' is_leader "$n1"
[[ "$(q "$n1" 'SELECT ref FROM booking_demo WHERE id=1')" == VP-12M-PHUQUOC ]] || { echo 'mất dữ liệu khi clone'; exit 1; }
q "$n1" "INSERT INTO booking_demo VALUES (2,'TREN-PATRONI')"

echo '2. nút thứ hai vào làm replica (không cần cờ clone)'
start_node "$n2" "vol2-$id"
wait_for 120 'nút 2 thành replica' is_replica "$n2"
wait_for 30 'nút 2 có dữ liệu' bash -c "[[ \$(docker exec -u postgres $n2 psql -X -h /var/run/postgresql -U postgres -d postgres -Atqc 'SELECT count(*) FROM booking_demo') == 2 ]]"

echo '3. primary cũ không bị động tới'
docker exec -u postgres "$old" psql -U postgres -Atqc "INSERT INTO booking_demo VALUES (3,'CU-VAN-GHI-DUOC')" >/dev/null
echo 'PASS: clone từ primary cũ, replica vào cụm, primary cũ còn nguyên làm đường quay lại'
